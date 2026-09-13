"""Config logger"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from loguru import logger


class InterceptHandler(logging.Handler):
    """
    Redirect standard-library logging to Loguru.

    This allows logs from libraries using `logging` (uvicorn, FastAPI,
    SQLAlchemy, etc.) to go through the same Loguru configuration.
    """

    def emit(self, record: logging.LogRecord) -> None:
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        frame = logging.currentframe()
        depth = 2

        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(
            depth=depth,
            exception=record.exc_info,
        ).log(level, record.getMessage())


def configure_logging(
    *,
    log_level: str = "INFO",
    log_dir: str | Path = "logs",
    app_name: str = "app",
    json_logs: bool = False,
) -> None:
    """
    Configure production logging.

    Features:
    - Colored human-readable terminal logs
    - Rotating application log
    - Separate error log
    - Log retention
    - Compression
    - Multiprocess-safe enqueue mode
    - Standard logging -> Loguru interception

    Args:
        log_level:
            Minimum logging level.
        log_dir:
            Directory containing log files.
        app_name:
            Prefix used for log filenames.
        json_logs:
            Serialize logs as JSON. Useful for ELK/Loki/Datadog ingestion.
    """

    log_dir = Path(log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)

    # Remove Loguru's default stderr handler.
    logger.remove()

    terminal_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{process.name}</cyan>:<cyan>{process.id}</cyan> | "
        "<cyan>{thread.name}</cyan> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
        "<level>{message}</level>"
    )

    file_format = (
        "{time:YYYY-MM-DD HH:mm:ss.SSS} | "
        "{level: <8} | "
        "{process.name}:{process.id} | "
        "{thread.name} | "
        "{name}:{function}:{line} - "
        "{message}"
    )

    # ------------------------------------------------------------------
    # Terminal
    # ------------------------------------------------------------------
    logger.add(
        sys.stderr,
        level=log_level.upper(),
        format=terminal_format,
        colorize=True,
        backtrace=False,
        diagnose=False,
        enqueue=True,
    )

    # ------------------------------------------------------------------
    # Main application log
    # ------------------------------------------------------------------
    logger.add(
        log_dir / f"{app_name}.log",
        level=log_level.upper(),
        format=file_format,
        rotation="100 MB",
        retention="30 days",
        compression="gz",
        encoding="utf-8",
        enqueue=True,
        backtrace=False,
        diagnose=False,
        serialize=json_logs,
    )

    # ------------------------------------------------------------------
    # Dedicated error log
    # ------------------------------------------------------------------
    logger.add(
        log_dir / f"{app_name}.error.log",
        level="ERROR",
        format=file_format,
        rotation="100 MB",
        retention="60 days",
        compression="gz",
        encoding="utf-8",
        enqueue=True,
        backtrace=False,
        diagnose=False,
        serialize=json_logs,
    )

    # ------------------------------------------------------------------
    # Redirect stdlib logging to Loguru
    # ------------------------------------------------------------------
    intercept_handler = InterceptHandler()

    logging.basicConfig(
        handlers=[intercept_handler],
        level=0,
        force=True,
    )

    # Libraries that commonly install their own handlers.
    for logger_name in (
        "uvicorn",
        "uvicorn.access",
        "uvicorn.error",
        "fastapi",
        "sqlalchemy",
    ):
        std_logger = logging.getLogger(logger_name)
        std_logger.handlers = [intercept_handler]
        std_logger.propagate = False

    logger.info(
        "Logging initialized: level={}, directory={}, json={}",
        log_level.upper(),
        log_dir.resolve(),
        json_logs,
    )
