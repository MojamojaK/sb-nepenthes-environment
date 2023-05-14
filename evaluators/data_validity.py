import datetime
import logging
from helpers.deep_update import deep_update

logger = logging.getLogger(__name__)


def _is_valid(current_datetime, device_data):
    if "Datetime"  not in device_data:
        return False
    threshold = current_datetime - datetime.timedelta(minutes=15)
    return threshold <= device_data["Datetime"]

def task(data):
    current_datetime = datetime.datetime.now()
    result = {}
    for device_type, mapper in data.items():
        for v, entry in mapper.items():
            for alias, device_data in entry.items():
                validity = _is_valid(current_datetime, device_data)
                if not validity:
                    logger.warning("Device %s/%s/%s is INVALID (last seen: %s)", device_type, v, alias, device_data.get("Datetime", "never"))
                result = deep_update(result, {device_type: {v: {alias: {"Valid": validity}}}})
    return result

