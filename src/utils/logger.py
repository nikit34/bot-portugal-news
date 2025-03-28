import logging
import os
import sys
from datetime import datetime

def get_log_level():
    level_str = os.getenv('LOG_LEVEL', 'DEBUG').upper()
    levels = {
        'DEBUG': logging.DEBUG,
        'INFO': logging.INFO,
        'WARNING': logging.WARNING,
        'ERROR': logging.ERROR,
        'CRITICAL': logging.CRITICAL
    }
    return levels.get(level_str, logging.DEBUG)

def setup_logging():
    log_format = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(name)s | %(filename)s:%(lineno)d | %(funcName)s | %(message)s'
    )

    log_level = get_log_level()
    logger = logging.getLogger()
    logger.info(f"Setting up logging with level: {logging.getLevelName(log_level)}")

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(log_format)
    console_handler.setLevel(log_level)

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    root_logger.handlers = []
    
    root_logger.addHandler(console_handler)

    loggers_config = {
        'src.parsers': log_level,
        'src.producers': log_level,
        'src.processor': log_level,
        
        'httpx': logging.WARNING,
        'urllib3': logging.WARNING,
        'asyncio': logging.WARNING,
        'telethon': logging.WARNING,
        'facebook': logging.WARNING,
        'spacy': logging.WARNING,
        'googletrans': logging.WARNING,
        
        'PIL': logging.WARNING,
        'feedparser': logging.WARNING
    }

    for logger_name, level in loggers_config.items():
        logging.getLogger(logger_name).setLevel(level)

    root_logger.info("Logging system initialized")
    root_logger.debug(f"Log level: {logging.getLevelName(log_level)}")
    root_logger.debug(f"Log format: {log_format._fmt}")
