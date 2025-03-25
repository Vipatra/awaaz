from core.config import API_KEYS
from core.logging import log


async def validate_api_key(api_key: str) -> bool:

    log.info(f"API keys are {API_KEYS}")
    if api_key not in API_KEYS:
        return False

    return True
