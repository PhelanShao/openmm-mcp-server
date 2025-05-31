# src/utils/logging_config.py
# Logging configuration for the OpenMM MCP Server

import logging
import sys
from logging.handlers import RotatingFileHandler

# Attempt to import AppConfig, handle potential circular import if this module is imported too early
# or if config itself tries to log during its initialization.
# A common pattern is to have config loaded first, then logging.
try:
    from src.config import config
except ImportError:
    # Fallback or simplified config if AppConfig is not yet available
    # This might happen if logging is set up before config is fully parsed,
    # or in unit tests where config might be mocked.
    class FallbackConfig:
        LOG_LEVEL = "INFO"
        LOG_FILE = None
    config = FallbackConfig() # type: ignore


def setup_logging():
    """
    Configures logging for the application.
    """
    log_level_str = getattr(config, "LOG_LEVEL", "INFO").upper()
    log_level = getattr(logging, log_level_str, logging.INFO)

    log_formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(module)s:%(lineno)d - %(message)s"
    )

    # Get the root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Clear existing handlers, if any, to avoid duplicate logs
    if root_logger.hasHandlers():
        root_logger.handlers.clear()

    # Console Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(log_formatter)
    root_logger.addHandler(console_handler)

    # File Handler (optional)
    log_file_path = getattr(config, "LOG_FILE", None)
    if log_file_path:
        try:
            # Use RotatingFileHandler for better log management
            # Max 5MB per file, keep 5 backup files
            file_handler = RotatingFileHandler(
                log_file_path, maxBytes=5*1024*1024, backupCount=5, encoding='utf-8'
            )
            file_handler.setFormatter(log_formatter)
            root_logger.addHandler(file_handler)
            root_logger.info(f"Logging to file: {log_file_path}")
        except Exception as e:
            root_logger.error(f"Failed to configure file logger at {log_file_path}: {e}")
            # Continue with console logging

    root_logger.info(f"Logging configured with level {log_level_str}.")

# Call setup_logging() when this module is imported,
# or provide a function to be called explicitly from the main application entry point.
# For simplicity in smaller apps, direct call is okay.
# For larger apps, explicit call from main is often preferred.
# setup_logging() # Let's make this explicit call from server startup.

def get_logger(name: str) -> logging.Logger:
    """
    Convenience function to get a logger instance.
    """
    return logging.getLogger(name)

if __name__ == "__main__":
    # Example of using the logger
    setup_logging() # Call setup for testing this module
    logger = get_logger(__name__)
    logger.debug("This is a debug message.")
    logger.info("This is an info message.")
    logger.warning("This is a warning message.")
    logger.error("This is an error message.")
    logger.critical("This is a critical message.")

    # Test with a logger from another module's perspective
    # other_module_logger = get_logger("src.some_other_module")
    # other_module_logger.info("Message from another module.")