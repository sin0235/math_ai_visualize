from __future__ import annotations

import logging

from app.core.logging import ReadinessAccessFilter, configure_logging


def access_record(method: str, path: str, status_code: int) -> logging.LogRecord:
    return logging.LogRecord(
        name="uvicorn.access",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg='%s - "%s %s HTTP/%s" %d',
        args=("100.127.21.197:0", method, path, "1.1", status_code),
        exc_info=None,
    )


def test_readiness_access_filter_suppresses_successful_probe() -> None:
    log_filter = ReadinessAccessFilter()

    assert not log_filter.filter(access_record("GET", "/api/health/ready", 200))
    assert not log_filter.filter(access_record("GET", "/api/health/ready?source=platform", 200))


def test_readiness_access_filter_preserves_failures_and_other_requests() -> None:
    log_filter = ReadinessAccessFilter()

    assert log_filter.filter(access_record("GET", "/api/health/ready", 503))
    assert log_filter.filter(access_record("GET", "/api/health", 200))
    assert log_filter.filter(access_record("POST", "/api/health/ready", 200))


def test_readiness_access_filter_preserves_non_access_logs() -> None:
    record = logging.LogRecord(
        name="app.services.health",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="Readiness dependency failed",
        args=(),
        exc_info=None,
    )

    assert ReadinessAccessFilter().filter(record)


def test_configure_logging_attaches_filter_to_uvicorn_access_handler() -> None:
    configure_logging()

    access_logger = logging.getLogger("uvicorn.access")

    assert not access_logger.propagate
    assert len(access_logger.handlers) == 1
    assert any(
        isinstance(log_filter, ReadinessAccessFilter)
        for log_filter in access_logger.handlers[0].filters
    )
