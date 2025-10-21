from __future__ import annotations
from loguru import logger
from .config import config
import sys

# Remove default and set structured sink
logger.remove()
logger.add(
    sys.stdout,
    level=config.log_level,
    enqueue=True,
    backtrace=False,
    diagnose=False,
    colorize=True,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level}</level> | {extra[component]} | {message}",
)
logger.add(
    config.log_file,
    rotation="20 MB",
    retention="14 days",
    compression="zip",
    level=config.log_level,
    enqueue=True,
    serialize=True,  # JSON logs for better analysis
)

def get_logger(name: str = "app"):
    return logger.bind(component=name)
