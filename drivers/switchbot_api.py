import time
import hashlib
import hmac
import base64
import uuid
import json
import logging
import urllib.request

logger = logging.getLogger(__name__)

GET_DEVICES_ENDPOINT = "https://api.switch-bot.com/v1.1/devices"

METER_DEVICE_TYPES = {"Meter", "MeterPlus", "Meter Pro", "Meter Pro(CO2)", "WoIOSensor"}
PLUG_DEVICE_TYPES = {"Plug Mini (JP)", "Plug Mini (US)", "Plug Mini (EU)", "Plug"}


def _build_headers(token, secret_key):
    t = str(int(round(time.time() * 1000)))
    nonce = str(uuid.uuid4())
    string_to_sign = bytes("{}{}{}".format(token, t, nonce), "utf-8")
    secret = bytes(secret_key, "utf-8")
    sign = base64.b64encode(
        hmac.new(secret, msg=string_to_sign, digestmod=hashlib.sha256).digest()
    )
    return {
        "Authorization": token,
        "sign": sign.decode("utf-8"),
        "t": t,
        "nonce": nonce,
        "Content-Type": "application/json; charset=utf-8",
    }


def _device_id_to_mac(device_id):
    """Convert SwitchBot deviceId to BLE MAC address.
    e.g. '6055F93B18EE' -> '60:55:F9:3B:18:EE'
    """
    raw = device_id.upper()
    return ":".join(raw[i : i + 2] for i in range(0, len(raw), 2))


def fetch_devices(token, secret_key):
    """Fetch device list from SwitchBot cloud API."""
    headers = _build_headers(token, secret_key)
    req = urllib.request.Request(GET_DEVICES_ENDPOINT, headers=headers)
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    if data.get("statusCode") != 100:
        raise RuntimeError("SwitchBot API error: {}".format(data))
    return data.get("body", {}).get("deviceList", [])


def build_device_config(device_list, allowed_names=None):
    """Convert SwitchBot API device list into DEVICE_CONFIG format.

    If allowed_names is provided, only devices whose deviceName is in
    the set will be registered.
    """
    config = {"meters": {"v0": {}}, "plugs": {"v0": {}}}
    for device in device_list:
        if not device.get("enableCloudService"):
            continue
        device_type = device.get("deviceType", "")
        device_name = device.get("deviceName", "")
        device_id = device.get("deviceId", "")
        if allowed_names is not None and device_name not in allowed_names:
            logger.debug("Skipping device not in aliases: %s", device_name)
            continue
        mac = _device_id_to_mac(device_id)
        if device_type in METER_DEVICE_TYPES:
            config["meters"]["v0"][device_name] = {"MacAddress": mac}
            logger.info("Registered meter: %s -> %s", device_name, mac)
        elif device_type in PLUG_DEVICE_TYPES:
            config["plugs"]["v0"][device_name] = {"MacAddress": mac}
            logger.info("Registered plug: %s -> %s", device_name, mac)
        else:
            logger.debug("Skipping device: %s (type=%s)", device_name, device_type)
    return config
