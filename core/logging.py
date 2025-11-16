import logging
import sys
import os
from core.config import settings

def setup_logging():
    """
    Configures the root logger to output to both a file and the console.
    The log file path and log level are determined by settings and environment variables.
    """
    # Determine the log level from environment variable, defaulting to INFO
    log_level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    log_level = getattr(logging, log_level_name, logging.INFO)

    # Use the log file path from the settings
    log_file_path = settings.LOG_FILE

    # Define a rich format for the logs
    log_format = "%(asctime)s - %(levelname)s - P%(process)d - %(name)s:%(funcName)s:%(lineno)d - %(message)s"
    encoding='utf-8'
    # Get the root logger
    logger = logging.getLogger()
    logger.setLevel(log_level)

    # Avoid adding duplicate handlers if this function is called again (e.g., in a subprocess)
    if not logger.handlers:
        # File Handler - writes logs to a file
        file_handler = logging.FileHandler(log_file_path, mode='a')
        file_handler.setFormatter(logging.Formatter(log_format))
        logger.addHandler(file_handler)

        # Console/Stream Handler - writes logs to the console
        stream_handler = logging.StreamHandler(sys.stdout)
        stream_handler.setFormatter(logging.Formatter(log_format))
        logger.addHandler(stream_handler)

    if log_level == logging.DEBUG:
        logging.info("DEBUG mode enabled. Logging will be verbose.")