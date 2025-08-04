"""
Set up the logger with custom settings.
Logs are written to a file with automatic rotation.
"""

from loguru import logger

LOGS_PATH = "logs"

logger.add(
    f"{LOGS_PATH}/server.log",
    rotation="1 MB",
    # level="DEBUG",
    retention="7 days",
    compression="zip",
)
