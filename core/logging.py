import logging
import sys

from core.config import LOG_LEVEL, FORCE_JSON_LOGGER, DEPLOYMENT
from asgi_correlation_id.context import correlation_id
import structlog

logging.basicConfig(
    format="%(message)s",
    stream=sys.stdout,
    level=LOG_LEVEL,
)

def add_correlation(logger, method_name, event_dict):
    cid = correlation_id.get()
    if cid:
        event_dict["correlation_id"] = cid
    return event_dict


if FORCE_JSON_LOGGER or DEPLOYMENT == "production":
    renderer = structlog.processors.JSONRenderer()
else:
    renderer = structlog.dev.ConsoleRenderer()


structlog.configure(
    processors=[
        add_correlation,
        structlog.processors.TimeStamper(fmt="iso", key="timestamp"),
        structlog.stdlib.add_log_level,
        structlog.processors.format_exc_info,
        renderer,
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)


log = structlog.get_logger()
