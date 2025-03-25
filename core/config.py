import os
from dotenv import load_dotenv

from core.consts import TRUTH_VALUES


load_dotenv()


def get_int_from_env(env_var: str, default: int = 0) -> int:
    env_var_val = os.environ.get(env_var)
    if env_var_val is None:
        return default
    try:
        return int(env_var_val)
    except (ValueError, TypeError):
        return default


def get_bool_from_env(env_var: str, default: bool = False) -> bool:
    try:
        return os.environ.get(env_var, "").lower() in TRUTH_VALUES
    except (ValueError, TypeError, AttributeError):
        return default


TARA_API_KEY = os.getenv("TARA_API_KEY")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
DEPLOYMENT = os.getenv("DEPLOYMENT", "local")
FORCE_JSON_LOGGER = get_bool_from_env(os.getenv("FORCE_JSON_LOGGER"))

API_KEYS = [TARA_API_KEY]



