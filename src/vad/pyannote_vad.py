import os
from os import remove

from pyannote.audio import Model
from pyannote.audio.pipelines import VoiceActivityDetection

from core.logging import log
from src.audio_utils import save_audio_to_file

from .vad_interface import VADInterface


class PyannoteVAD(VADInterface):
    """
    Pyannote-based implementation of the VADInterface.
    """

    def __init__(self, **kwargs):
        """
        Initializes Pyannote's VAD pipeline.

        Args:
            model_name (str): The model name for Pyannote.
            auth_token (str, optional): Authentication token for Hugging Face.
        """

        model_name = kwargs.get("model_name", "pyannote/segmentation")

        auth_token = os.environ.get("PYANNOTE_AUTH_TOKEN")
        if not auth_token:
            auth_token = kwargs.get("auth_token")

        if auth_token is None:
            raise ValueError(
                "Missing required env var in PYANNOTE_AUTH_TOKEN or argument "
                "in --vad-args: 'auth_token'"
            )

        pyannote_args = kwargs.get(
            "pyannote_args",
            {
                "onset": 0.7, # the threshold at which the model detects the start of speech, default: 0.5
                "offset": 0.3, # threshold for when speech is considered to have ended. default: 0.5
                "min_duration_on": 0.5, # minimum duration of speech required for it to be considered valid, default: 0.3
                "min_duration_off": 0.3, # how long silence must last for the model to consider that speech has ended and that a new speech segment may start. default: 0.3
            },
        )
        self.model = Model.from_pretrained(
            model_name, use_auth_token=auth_token
        )
        self.vad_pipeline = VoiceActivityDetection(segmentation=self.model)
        self.vad_pipeline.instantiate(pyannote_args)

    async def detect_activity(self, client):
        audio_file_path = await save_audio_to_file(
            client.scratch_buffer, client.get_file_name()
        )
        vad_results = self.vad_pipeline(audio_file_path)
        remove(audio_file_path)
        vad_segments = []
        if len(vad_results) > 0:
            log.debug("VAD segments", vad_results=vad_results)
            for s in vad_results.itersegments():
                log.debug("Vad segment", s=s)
            vad_segments = [
                {"start": segment.start, "end": segment.end, "confidence": 1.0}
                for segment in vad_results.itersegments()
            ]
        return vad_segments
