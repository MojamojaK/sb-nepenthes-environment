import logging
import logging.handlers
import os
import threading

from config.paths import DATA_DIR


def setup_logger(name, debug_minutes=0):
    logger = logging.getLogger(name)
    if debug_minutes > 0:
        logger.setLevel(logging.DEBUG)
        timer = threading.Timer(debug_minutes * 60, _raise_log_level, args=[logger])
        timer.daemon = True
        timer.start()
    else:
        logger.setLevel(logging.INFO)

    log_path = os.path.join(DATA_DIR, f"{name}.log")
    os.makedirs(DATA_DIR, exist_ok=True)

    file_handler = logging.handlers.TimedRotatingFileHandler(
        log_path, when="H", backupCount=2
    )
    file_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))

    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)
    return logger


def setup_data_logger(name):
    """Set up a separate logger for state dumps that only writes to its own file (no stdout)."""
    logger = logging.getLogger(f"{name}.state")
    logger.setLevel(logging.INFO)
    logger.propagate = False

    log_path = os.path.join(DATA_DIR, f"{name}_state.log")
    os.makedirs(DATA_DIR, exist_ok=True)

    file_handler = logging.handlers.TimedRotatingFileHandler(
        log_path, when="H", backupCount=2
    )
    file_handler.setFormatter(logging.Formatter("%(asctime)s %(message)s"))

    logger.addHandler(file_handler)
    return logger


def _raise_log_level(logger):
    logger.setLevel(logging.INFO)
    logger.info("Debug period ended, log level raised to INFO")
