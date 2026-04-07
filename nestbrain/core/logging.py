from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from .paths import get_logs_dir


def setup_logging(app_name: str = "Nestbrain", level: int = logging.INFO) -> Path:
    """Configure a shared file and console logger for the application."""
    logs_dir = get_logs_dir(app_name)
    log_file = logs_dir / "nestbrain.log"

    root_logger = logging.getLogger()
    if getattr(root_logger, "_nestbrain_logging_configured", False):
        return log_file

    root_logger.setLevel(level)

    formatter = logging.Formatter(
        fmt="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = RotatingFileHandler(log_file, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)
    setattr(root_logger, "_nestbrain_logging_configured", True)
    return log_file
