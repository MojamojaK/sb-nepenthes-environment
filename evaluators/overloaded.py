import datetime
import logging
from helpers.deep_update import deep_update

logger = logging.getLogger(__name__)


def _is_overloaded(current_datetime, device_data):
    if "Code"  not in device_data:
        return False
    return device_data["Code"] == "0b"

def task(data):
    current_datetime = datetime.datetime.now()
    result = {}
    for device_type, mapper in data.items():
        for v, entry in mapper.items():
            for alias, device_data in entry.items():
                overloaded = _is_overloaded(current_datetime, device_data)
                if overloaded:
                    logger.warning("Device %s/%s/%s is OVERLOADED (code=0b)", device_type, v, alias)
                    result = deep_update(result, {device_type: {v: {alias: {"IsOverloaded": overloaded}}}})
    return result

