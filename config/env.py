import os

from config.paths import PROJECT_ROOT


def _load_dotenv():
    env_path = os.path.join(PROJECT_ROOT, ".env")
    if not os.path.exists(env_path):
        return
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())


_load_dotenv()

# AWS IoT MQTT
MQTT_ENDPOINT = os.environ["MQTT_ENDPOINT"]
MQTT_PORT = int(os.environ.get("MQTT_PORT", "8883"))
MQTT_CLIENT_ID = os.environ["MQTT_CLIENT_ID"]
MQTT_TOPIC = os.environ["MQTT_TOPIC"]
MQTT_CERT_PATH = os.environ["MQTT_CERT_PATH"]
MQTT_KEY_PATH = os.environ["MQTT_KEY_PATH"]
MQTT_CA_PATH = os.environ["MQTT_CA_PATH"]

# SwitchBot API
SB_TOKEN = os.environ["SB_TOKEN"]
SB_SECRET_KEY = os.environ["SB_SECRET_KEY"]

# System
NEPENTHES_SCRIPT_PATH = os.environ["NEPENTHES_SCRIPT_PATH"]
BT_INTERFACE = os.environ.get("BT_INTERFACE", "hci0")
