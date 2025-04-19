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
        '%(asctime)s | %(levelname)-8s | %(filename)s:%(lineno)d | %(funcName)s | %(message)s'
    )

    log_level = get_log_level()
    
    log_dir = "logs"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    stats_log_file = os.path.join(log_dir, f"stats_{datetime.now().strftime('%Y-%m-%d')}.log")
    stats_handler = logging.FileHandler(stats_log_file)
    stats_handler.setFormatter(log_format)
    stats_handler.setLevel(logging.INFO)
    
    stats_logger = logging.getLogger('stats')
    stats_logger.setLevel(logging.INFO)
    stats_logger.handlers = []
    stats_logger.addHandler(stats_handler)
    stats_logger.propagate = False

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(log_format)
    console_handler.setLevel(log_level)
    
    app_logger = logging.getLogger('app')
    app_logger.setLevel(log_level)
    app_logger.handlers = []
    app_logger.addHandler(console_handler)
    app_logger.propagate = False

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
        'hpack': logging.WARNING,
        
        'PIL': logging.WARNING,
        'feedparser': logging.WARNING
    }

    for logger_name, level in loggers_config.items():
        logging.getLogger(logger_name).setLevel(level)

    app_logger.info("Logging system initialized")
    app_logger.debug(f"Log level: {logging.getLevelName(log_level)}")
    app_logger.debug(f"Log format: {log_format._fmt}")
