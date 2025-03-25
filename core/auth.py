from core.config import API_KEYS


async def validate_api_key(api_key: str) -> bool:

    if api_key not in API_KEYS:
        return False

    return True
