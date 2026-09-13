"""Console-only Loguru configuration for application-owned logs."""

import sys

from loguru import logger


def _write_to_stderr(message: str) -> None:
    """Resolve stderr at write time so test and server streams stay valid."""
    sys.stderr.write(message)


def configure_logging(*, log_level: str = "INFO", json_logs: bool = False) -> None:
    """Configure Loguru without intercepting third-party debug loggers."""
    logger.remove()
    logger.add(
        _write_to_stderr,
        level=log_level.upper(),
        serialize=json_logs,
        colorize=not json_logs,
        backtrace=False,
        diagnose=False,
        enqueue=False,
    )
