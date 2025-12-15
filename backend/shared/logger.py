# encoding: utf-8
"""
项目内统一的日志记录器。

尽量保持零依赖，方便在不同宿主应用中复用。
"""
from __future__ import annotations

import logging
import os
from typing import Final

LOGGER_NAME: Final[str] = "ai_demo"
DEFAULT_LEVEL: Final[str] = os.getenv("AI_DEMO_LOG_LEVEL", "INFO").upper()


def _configure_logger() -> logging.Logger:
    logger = logging.getLogger(LOGGER_NAME)
    if logger.handlers:
        return logger

    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] %(name)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(formatter)

    logger.addHandler(handler)
    logger.propagate = False

    try:
        logger.setLevel(DEFAULT_LEVEL)
    except ValueError:
        logger.setLevel(logging.INFO)

    return logger


log = _configure_logger()

__all__ = ["log"]

