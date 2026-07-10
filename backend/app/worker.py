"""Background worker entrypoint: python -m app.worker"""

from __future__ import annotations

import asyncio
import logging

from app.core.logging import configure_logging
from app.services.render_jobs import run_worker_loop

configure_logging()
logger = logging.getLogger("app.worker")


def main() -> None:
    try:
        asyncio.run(run_worker_loop())
    except KeyboardInterrupt:
        logger.info("Worker interrupted")


if __name__ == "__main__":
    main()
