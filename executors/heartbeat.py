import datetime
import os
import json
import logging

from config.paths import DATA_DIR

logger = logging.getLogger(__name__)


def _do_heartbeat():
    hb_path = os.path.join(DATA_DIR, "heartbeat.json")
    with open(hb_path, "w") as f:
        json.dump({"timestamp": datetime.datetime.now().isoformat()}, f)
    logger.debug("Heartbeat written")


def task(data):
    if data.get("should_heartbeat", False):
        _do_heartbeat()
    else:
        logger.debug("Heartbeat skipped (should_heartbeat=False)")
    return {}

