import os

# Provide dummy values for required environment variables so that
# ``config.env`` can be imported during test collection even when no
# ``.env`` file is present (e.g. in CI).
_REQUIRED_ENV = {
    "MQTT_ENDPOINT": "test-endpoint",
    "MQTT_CLIENT_ID": "test-client-id",
    "MQTT_TOPIC": "test/topic",
    "MQTT_CERT_PATH": "/tmp/cert.pem",
    "MQTT_KEY_PATH": "/tmp/key.pem",
    "MQTT_CA_PATH": "/tmp/ca.pem",
    "SB_TOKEN": "test-token",
    "SB_SECRET_KEY": "test-secret",
    "NEPENTHES_SCRIPT_PATH": "/tmp/nepenthes.py",
}

for key, value in _REQUIRED_ENV.items():
    os.environ.setdefault(key, value)
