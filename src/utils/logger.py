import logging
import os
import sys
from datetime import datetime
from logging.handlers import RotatingFileHandler

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
    log_dir = "logs"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    log_file = os.path.join(log_dir, f"bot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")

    log_format = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(name)s | %(filename)s:%(lineno)d | %(funcName)s | %(message)s'
    )

    log_level = get_log_level()
    logger = logging.getLogger()
    logger.info(f"Setting up logging with level: {logging.getLevelName(log_level)}")

    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setFormatter(log_format)
    file_handler.setLevel(log_level)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(log_format)
    console_handler.setLevel(log_level)

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    root_logger.handlers = []
    
    root_logger.addHandler(file_handler)
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
    root_logger.debug(f"Log file: {log_file}")
    root_logger.debug(f"Log directory: {os.path.abspath(log_dir)}")
    root_logger.debug(f"Log format: {log_format._fmt}")

    return log_file
