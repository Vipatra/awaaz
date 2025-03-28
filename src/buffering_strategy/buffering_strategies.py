import asyncio
import json
import os
import time

from core.logging import log
from monitoring.metrics import get_metric_publisher
from .buffering_strategy_interface import BufferingStrategyInterface


class SilenceAtEndOfChunk(BufferingStrategyInterface):
    """
    A buffering strategy that processes audio at the end of each chunk with
    silence detection.

    This class is responsible for handling audio chunks, detecting silence at
    the end of each chunk, and initiating the transcription process for the
    chunk.

    Attributes:
        client (Client): The client instance associated with this buffering
                         strategy.
        chunk_length_seconds (float): Length of each audio chunk in seconds.
        chunk_offset_seconds (float): Offset time in seconds to be considered
                                      for processing audio chunks.
    """

    def __init__(self, client, **kwargs):
        """
        Initialize the SilenceAtEndOfChunk buffering strategy.

        Args:
            client (Client): The client instance associated with this buffering
                             strategy.
            **kwargs: Additional keyword arguments, including
                      'chunk_length_seconds' and 'chunk_offset_seconds'.
        """
        self.client = client

        self.chunk_length_seconds = os.environ.get(
            "BUFFERING_CHUNK_LENGTH_SECONDS"
        )
        if not self.chunk_length_seconds:
            self.chunk_length_seconds = kwargs.get("chunk_length_seconds")
        self.chunk_length_seconds = float(self.chunk_length_seconds)

        self.chunk_offset_seconds = os.environ.get(
            "BUFFERING_CHUNK_OFFSET_SECONDS"
        )
        if not self.chunk_offset_seconds:
            self.chunk_offset_seconds = kwargs.get("chunk_offset_seconds")
        self.chunk_offset_seconds = float(self.chunk_offset_seconds)

        self.error_if_not_realtime = os.environ.get("ERROR_IF_NOT_REALTIME")
        if not self.error_if_not_realtime:
            self.error_if_not_realtime = kwargs.get(
                "error_if_not_realtime", False
            )

        self.processing_flag = False

    def process_audio(self, websocket, vad_pipeline, asr_pipeline):
        """
        Process audio chunks by checking their length and scheduling
        asynchronous processing.

        This method checks if the length of the audio buffer exceeds the chunk
        length and, if so, it schedules asynchronous processing of the audio.

        Args:
            websocket: The WebSocket connection for sending transcriptions.
            vad_pipeline: The voice activity detection pipeline.
            asr_pipeline: The automatic speech recognition pipeline.
        """
        chunk_length_in_bytes = (
            self.chunk_length_seconds
            * self.client.sampling_rate
            * self.client.samples_width
        )
        if len(self.client.buffer) > chunk_length_in_bytes:
            if self.processing_flag:
                if self.error_if_not_realtime:
                    exit(
                        "Error in realtime processing: tried processing a new "
                        "chunk while the previous one was still being processed"
                    )

                log.info(
                    "Dropping incoming audio data: previous chunk is still being processed",
                    client_id=self.client.client_id
                )
                self.client.buffer.clear()
                return

            self.client.scratch_buffer += self.client.buffer
            self.client.buffer.clear()
            self.processing_flag = True
            # Schedule the processing in a separate task
            asyncio.create_task(
                self.process_audio_async(websocket, vad_pipeline, asr_pipeline)
            )

    async def process_audio_async(self, websocket, vad_pipeline, asr_pipeline):
        """
        Asynchronously process audio for activity detection and transcription.

        This method performs heavy processing, including voice activity
        detection and transcription of the audio data. It sends the
        transcription results through the WebSocket connection.

        Args:
            websocket (Websocket): The WebSocket connection for sending
                                   transcriptions.
            vad_pipeline: The voice activity detection pipeline.
            asr_pipeline: The automatic speech recognition pipeline.
        """
        start = time.perf_counter()
        vad_results = await vad_pipeline.detect_activity(self.client)
        end = time.perf_counter()
        time_diff = end - start
        log.info("Time taken for vad", time_diff=time_diff)

        if len(vad_results) == 0:
            log.info("VAD did not detect any speech")
            self.client.scratch_buffer.clear()
            self.client.buffer.clear()
            self.processing_flag = False
            return

        last_segment_should_end_before = (
            len(self.client.scratch_buffer)
            / (self.client.sampling_rate * self.client.samples_width)
        ) - self.chunk_offset_seconds
        if vad_results[-1]["end"] < last_segment_should_end_before:

            # transcription = await asr_pipeline.transcribe(self.client)

            model_instance = await asr_pipeline.acquire()
            try:
                transcription = await model_instance.transcribe(self.client)
            finally:
                asr_pipeline.release(model_instance)

            if transcription["text"] != "":
                end = time.perf_counter()
                time_diff = end - start
                formatted_processing_time = f"{time_diff:.4f}"
                audio_duration = len(self.client.scratch_buffer) / (
                    self.client.sampling_rate * self.client.samples_width
                )

                transcription["processing_time"] = formatted_processing_time
                transcription["audio_duration"] = audio_duration
                json_transcription = json.dumps(transcription)
                await websocket.send(json_transcription)

                log.info(
                    "Time taken processing",
                    processing_time=formatted_processing_time,
                    audio_duration=audio_duration
                )

                cw = get_metric_publisher()
                cw.publish_metric(
                    "ChunkProcessingTime",
                    float(formatted_processing_time),
                    unit="Seconds",
                )
                cw.publish_metric(
                    "TranscriptionLength",
                    len(transcription["text"]),
                    unit="None",
                )
                if audio_duration > 0:
                    cw.publish_metric(
                        "TranscriptionSpeed",
                        len(transcription["text"]) / audio_duration,
                        unit="None",
                    )
                    processing_eff = float(formatted_processing_time) / audio_duration
                    cw.publish_metric(
                        "ProcessingEfficiency",
                        processing_eff,
                        unit="None",
                    )

            self.client.scratch_buffer.clear()
            self.client.increment_file_counter()

        self.processing_flag = False
