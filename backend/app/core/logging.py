from __future__ import annotations

import json
import logging
import os
from contextvars import ContextVar
from datetime import UTC, datetime
from logging.config import dictConfig

request_id_ctx: ContextVar[str | None] = ContextVar("request_id", default=None)


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_ctx.get() or "-"
        return True


class ReadinessAccessFilter(logging.Filter):
    """Bỏ access log readiness thành công nhưng vẫn giữ lỗi và request khác."""

    readiness_path = "/api/health/ready"

    def filter(self, record: logging.LogRecord) -> bool:
        if record.name != "uvicorn.access":
            return True

        method, path, status_code = self._access_fields(record)
        return not (
            method == "GET"
            and path.partition("?")[0] == self.readiness_path
            and status_code == 200
        )

    @staticmethod
    def _access_fields(record: logging.LogRecord) -> tuple[str, str, int | None]:
        args = record.args
        if isinstance(args, tuple) and len(args) >= 5:
            try:
                status_code = int(args[4])
            except (TypeError, ValueError):
                status_code = None
            return str(args[1]).upper(), str(args[2]), status_code
        return "", "", None


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", "-"),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


class StandardFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        if not hasattr(record, "request_id"):
            record.request_id = request_id_ctx.get() or "-"
        return super().format(record)


def configure_logging() -> None:
    log_format = (os.getenv("LOG_FORMAT") or "standard").strip().lower()
    use_json = log_format == "json"
    formatter_name = "json" if use_json else "standard"
    dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "filters": {
                "request_id": {"()": "app.core.logging.RequestIdFilter"},
                "readiness_access": {"()": "app.core.logging.ReadinessAccessFilter"},
            },
            "formatters": {
                "standard": {
                    "()": "app.core.logging.StandardFormatter",
                    "format": "%(asctime)s %(levelname)s [%(name)s] rid=%(request_id)s %(message)s",
                },
                "json": {
                    "()": "app.core.logging.JsonFormatter",
                },
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": formatter_name,
                    "filters": ["request_id", "readiness_access"],
                },
            },
            "root": {
                "handlers": ["console"],
                "level": "INFO",
            },
            "loggers": {
                "app": {"level": "INFO", "propagate": True},
                "app.services.ai_providers": {"level": "INFO", "propagate": True},
                "httpx": {"level": "WARNING", "propagate": True},
                "uvicorn.access": {
                    "handlers": ["console"],
                    "level": "INFO",
                    "propagate": False,
                },
            },
        }
    )
    logging.getLogger("app").debug("Logging configured format=%s", formatter_name)


def get_request_id() -> str | None:
    return request_id_ctx.get()


def set_request_id(value: str | None) -> None:
    request_id_ctx.set(value)
