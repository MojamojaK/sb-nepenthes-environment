import json
import os
import time
import logging

from config.paths import DATA_DIR
from config.env import SB_TOKEN, SB_SECRET_KEY
from config.device_aliases import allowed_names
from drivers.switchbot_api import fetch_devices, build_device_config

logger = logging.getLogger(__name__)

_CACHE_PATH = os.path.join(DATA_DIR, "device_config.json")
_config = None
_last_refresh_time = 0
_REFRESH_INTERVAL = 3600  # 1 hour


def _load_cache():
    try:
        with open(_CACHE_PATH, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def _save_cache(config):
    with open(_CACHE_PATH, "w") as f:
        json.dump(config, f, indent=2)


def get_config():
    """Return cached device config. Fetches from API if no cache exists."""
    global _config
    if _config is not None:
        return _config
    _config = _load_cache()
    if _config is None:
        logger.info("No cached device config found, fetching from SwitchBot API")
        _config = refresh_config()
    return _config


def refresh_config():
    """Fetch device config from SwitchBot API and update cache.

    On failure, keeps the existing config (if any) so that a network
    outage does not wipe the known device list.
    """
    global _config, _last_refresh_time
    _last_refresh_time = time.monotonic()
    try:
        device_list = fetch_devices(SB_TOKEN, SB_SECRET_KEY)
        _config = build_device_config(device_list, allowed_names=allowed_names)
        _save_cache(_config)
        logger.info("Device config refreshed from SwitchBot API (%d meters, %d plugs)",
                     len(_config.get("meters", {}).get("v0", {})),
                     len(_config.get("plugs", {}).get("v0", {})))
    except Exception as e:
        logger.error("Failed to fetch device config from API: %s", e)
        if _config is None:
            _config = {"meters": {"v0": {}}, "plugs": {"v0": {}}}
    return _config


def is_refresh_due():
    """Return True if enough time has elapsed since the last refresh."""
    return time.monotonic() - _last_refresh_time >= _REFRESH_INTERVAL


def should_refresh(data):
    """Return True if any configured device has never been seen by the BLE scanner.

    A device that has been seen will have a 'Datetime' field in its data.
    A device that is around but not responding will still have a 'Datetime'
    (just stale) - we do NOT refresh for those.
    """
    for device_type in ["meters", "plugs"]:
        devices = data.get(device_type, {}).get("v0", {})
        for alias, device_data in devices.items():
            if "MacAddress" in device_data and "Datetime" not in device_data:
                logger.debug("Device %s has never been seen by scanner", alias)
                return True
    return False
