from __future__ import annotations

import os
import sys
from loguru import logger


def setup_logger(log_file: str, level: str = "INFO", console: bool = True):
    """初始化日志。

    Args:
        log_file: 日志文件路径。
        level: 日志等级。
        console: 是否输出到控制台。
    """
    os.makedirs(os.path.dirname(log_file), exist_ok=True)
    logger.remove()
    logger.add(
        log_file,
        level=level,
        rotation="00:00",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}",
    )
    if console:
        logger.add(
            sys.stdout,
            level=level,
            format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level}</level> | <level>{message}</level>",
        )
    return logger
