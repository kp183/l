import logging
import logging.config
import time
import uuid
import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

def setup_logging():
    from app.config import get_settings
    settings = get_settings()

    def inject_metadata(logger, method_name, event_dict):
        event_dict["service"] = "api"
        event_dict["environment"] = settings.environment
        
        # Attach request_id from structlog context variables
        request_id = structlog.contextvars.get_contextvars().get("request_id")
        if request_id:
            event_dict["request_id"] = request_id
            
        # Standardize logging levels
        if "level" in event_dict:
            level = event_dict["level"].lower()
            if level == "warning":
                event_dict["level"] = "warn"
            else:
                event_dict["level"] = level.upper()
        return event_dict

    logging.config.dictConfig({
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "json": {
                "()": structlog.stdlib.ProcessorFormatter,
                "processor": structlog.processors.JSONRenderer(),
            },
        },
        "handlers": {
            "default": {
                "class": "logging.StreamHandler",
                "formatter": "json",
            },
        },
        "loggers": {
            "": {
                "handlers": ["default"],
                "level": "INFO",
            },
            "uvicorn.error": {
                "handlers": ["default"],
                "level": "INFO",
                "propagate": False,
            },
            "uvicorn.access": {
                "handlers": ["default"],
                "level": "INFO",
                "propagate": False,
            },
        },
    })

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", key="timestamp"),
            inject_metadata,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

logger = structlog.get_logger(__name__)

class RequestIDMiddleware(BaseHTTPMiddleware):
    """Middleware that injects a unique X-Request-ID header and binds it to structured logs."""

    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id
        
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)
        
        start_time = time.time()
        
        logger.info(
            "Request started",
            method=request.method,
            path=request.url.path,
        )
        
        try:
            response: Response = await call_next(request)
            duration_ms = int((time.time() - start_time) * 1000)
            logger.info(
                "Request finished",
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                duration_ms=duration_ms,
            )
            response.headers["X-Request-ID"] = request_id
            return response
        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            logger.error(
                "Request failed",
                method=request.method,
                path=request.url.path,
                error=str(e),
                duration_ms=duration_ms,
            )
            raise e
