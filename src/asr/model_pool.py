import math
import asyncio
import pynvml

from core.logging import log
from .asr_factory import ASRFactory
from .faster_whisper_asr import FasterWhisperASR


def get_available_gpu_memory_bytes():
    try:
        pynvml.nvmlInit()
        handle = pynvml.nvmlDeviceGetHandleByIndex(0)
        mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
        available_memory = mem_info.free
        pynvml.nvmlShutdown()
        return available_memory
    except Exception as e:
        log.error(f"Error getting available GPU memory: {e}")
        return 0


def compute_model_pool_size():
    available_memory = get_available_gpu_memory_bytes()
    model_memory_bytes = FasterWhisperASR.get_model_memory_bytes()

    log.info("Available GPU memory", available_memory=available_memory)

    available_memory *= 0.8

    pool_size = math.floor(available_memory / model_memory_bytes)
    log.info("Computed model pool size", pool_size=pool_size, final_pool_size=max(1, pool_size))

    return max(1, pool_size)


class ASRModelPool:
    def __init__(self, pool_size: int, asr_type: str, model_kwargs: dict):
        self.pool = asyncio.Queue(maxsize=pool_size)
        for _ in range(pool_size):
            model_instance = ASRFactory.create_asr_pipeline(asr_type, **model_kwargs)
            self.pool.put_nowait(model_instance)

    async def acquire(self):
        return await self.pool.get()

    def release(self, model_instance):
        self.pool.put_nowait(model_instance)

    async def __aenter__(self):
        self._instance = await self.acquire()
        return self._instance

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.release(self._instance)
