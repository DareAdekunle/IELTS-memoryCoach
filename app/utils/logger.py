"""
Structured logging for IELTS MemoryCoach.

Every HTTP request gets a unique 8-character request ID that
flows through all service calls and background tasks. This means
you can grep logs for a single request ID and see the complete
pipeline: API entry → Qwen call → memory extraction → DB write.

Usage in any service or route:
    from app.utils.logger import get_logger
    logger = get_logger(__name__)
    logger.info("Memory extraction complete")
    logger.warning("Skill classification fallback triggered")
    logger.error(f"TTS generation failed: {e}")
"""

import logging
import sys
from contextvars import ContextVar

# ─── Request ID Context ────────────────────────────────────────────────────────
# A ContextVar propagates automatically through async call chains
# and background tasks within the same request context.
# Set by the FastAPI middleware in api/main.py for every request.

request_id_var: ContextVar[str] = ContextVar(
    'request_id',
    default='--------'
)


def set_request_id(req_id: str) -> None:
    """Called by FastAPI middleware at the start of each request."""
    request_id_var.set(req_id)


def get_request_id() -> str:
    """Returns the current request ID or a placeholder if not set."""
    return request_id_var.get()


# ─── Log formatter ─────────────────────────────────────────────────────────────

class RequestIDFilter(logging.Filter):
    """Injects the current request ID into every log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        return True


_LOG_FORMAT = (
    "%(asctime)s | %(levelname)-8s | "
    "req:%(request_id)s | %(name)s | %(message)s"
)
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

_handler = logging.StreamHandler(sys.stdout)
_handler.addFilter(RequestIDFilter())
_handler.setFormatter(logging.Formatter(_LOG_FORMAT, _DATE_FORMAT))

# ─── Root logger ───────────────────────────────────────────────────────────────

_root = logging.getLogger("ielts")
_root.setLevel(logging.INFO)
_root.addHandler(_handler)
_root.propagate = False


def get_logger(name: str) -> logging.Logger:
    """
    Returns a named child logger under the 'ielts' root.

    All child loggers inherit the request ID filter and formatter.
    Use __name__ as the name so log output identifies the source module.

    Example:
        logger = get_logger(__name__)
        # Produces: 2026-07-05 04:45:01 | INFO | req:a3f2b1c4 | app.services.memory_service | ...
    """
    return logging.getLogger(f"ielts.{name}")
