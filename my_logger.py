# logger.py
import logging
from logging.handlers import TimedRotatingFileHandler
import sys


def setup_logger(log_file="Logs/bot.log", log_level=logging.INFO):
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    formatter = logging.Formatter(log_format)

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    file_handler = TimedRotatingFileHandler(
        log_file, when="D", interval=1, backupCount=7)
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
