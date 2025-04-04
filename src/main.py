import argparse
import asyncio
import json

from core.logging import log
from monitoring.metrics import publish_metrics_loop
from src.asr.model_pool import compute_model_pool_size, ASRModelPool
from src.vad.vad_factory import VADFactory

from .server import Server


def parse_args():
    parser = argparse.ArgumentParser(
        description="VoiceStreamAI Server: Real-time audio transcription "
        "using self-hosted Whisper and WebSocket."
    )
    parser.add_argument(
        "--vad-type",
        type=str,
        default="pyannote",
        help="Type of VAD pipeline to use (e.g., 'pyannote')",
    )
    parser.add_argument(
        "--vad-args",
        type=str,
        default='{"auth_token": "huggingface_token"}',
        help="JSON string of additional arguments for VAD pipeline",
    )
    parser.add_argument(
        "--asr-type",
        type=str,
        default="faster_whisper",
        help="Type of ASR pipeline to use (e.g., 'whisper')",
    )
    parser.add_argument(
        "--asr-args",
        type=str,
        default='{"model_size": "large-v3"}',
        help="JSON string of additional arguments for ASR pipeline",
    )
    parser.add_argument(
        "--host",
        type=str,
        default="127.0.0.1",
        help="Host for the WebSocket server",
    )
    parser.add_argument(
        "--port", type=int, default=8765, help="Port for the WebSocket server"
    )
    parser.add_argument(
        "--certfile",
        type=str,
        default=None,
        help="The path to the SSL certificate (cert file) if using secure "
        "websockets",
    )
    parser.add_argument(
        "--keyfile",
        type=str,
        default=None,
        help="The path to the SSL key file if using secure websockets",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="error",
        choices=["debug", "info", "warning", "error"],
        help="Logging level: debug, info, warning, error. default: error",
    )
    parser.add_argument(
        "--cw-interval",
        type=int,
        default=5,
        help="Interval (in seconds) to publish metrics to CloudWatch",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    try:
        vad_args = json.loads(args.vad_args)
        asr_args = json.loads(args.asr_args)
    except json.JSONDecodeError as e:
        log.info(f"Error parsing JSON arguments: {e}")
        return

    # VAD
    vad_pipeline = VADFactory.create_vad_pipeline(args.vad_type, **vad_args)

    # ASR
    pool_size = compute_model_pool_size()
    log.info("Initializing ASR model pool", pool_size=pool_size)
    asr_model_pool = ASRModelPool(pool_size=pool_size, asr_type=args.asr_type, model_kwargs=asr_args)
    # asr_pipeline = ASRFactory.create_asr_pipeline(args.asr_type, **asr_args)

    server = Server(
        vad_pipeline,
        asr_model_pool,
        host=args.host,
        port=args.port,
        sampling_rate=8000,
        samples_width=2,
        certfile=args.certfile,
        keyfile=args.keyfile,
    )

    loop = asyncio.get_event_loop()

    loop.run_until_complete(server.start())
    loop.create_task(publish_metrics_loop(server, interval=args.cw_interval))

    log.info("Awaaz service is running")
    asyncio.get_event_loop().run_forever()


if __name__ == "__main__":
    main()
