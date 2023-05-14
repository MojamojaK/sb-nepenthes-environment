import json
import logging
import threading
import pathlib
import datetime
import os

from config.paths import DATA_DIR
from config.env import MQTT_ENDPOINT, MQTT_PORT, MQTT_CLIENT_ID, MQTT_TOPIC, \
    MQTT_CERT_PATH, MQTT_KEY_PATH, MQTT_CA_PATH

logger = logging.getLogger(__name__)

from awscrt import mqtt
from awsiot import mqtt_connection_builder
received_all_event = threading.Event()

# Callback when the connection successfully connects
def on_connection_success(connection, callback_data):
    assert isinstance(callback_data, mqtt.OnConnectionSuccessData)
    logger.info("Connection Successful with return code: {} session present: {}".format(callback_data.return_code, callback_data.session_present))

# Callback when a connection attempt fails
def on_connection_failure(connection, callback_data):
    assert isinstance(callback_data, mqtt.OnConnectionFailureData)
    logger.error("Connection failed with error code: {}".format(callback_data.error))

# Callback when a connection has been disconnected or shutdown successfully
def on_connection_closed(connection, callback_data):
    logger.info("Connection closed")

def on_connection_interrupted_do_nothing(connection, error, **kwargs):
    pass

def on_connection_resumed(connection, return_code, session_present, **kwargs):
    pass

def on_message_received(topic, payload, dup, qos, retain, **kwargs):
    received_all_event.set()

def get_connection_and_connect():
    mqtt_connection = mqtt_connection_builder.mtls_from_path(
        endpoint=MQTT_ENDPOINT,
        port=MQTT_PORT,
        cert_filepath=MQTT_CERT_PATH,
        pri_key_filepath=MQTT_KEY_PATH,
        ca_filepath=MQTT_CA_PATH,
        client_id=MQTT_CLIENT_ID,
        clean_session=False,
        keep_alive_secs=30,
        on_connection_resumed=on_connection_resumed,
        on_connection_interrupted=on_connection_interrupted_do_nothing,
        on_connection_success=on_connection_success,
        on_connection_failure=on_connection_failure,
        on_connection_closed=on_connection_closed)
    logger.debug("Connecting to %s with client ID '%s'...", MQTT_ENDPOINT, MQTT_CLIENT_ID)
    connect_future = mqtt_connection.connect()
    connect_future.result()
    logger.debug("Connected!")
    return mqtt_connection

def subscribe(mqtt_connection: mqtt.Connection):
    subscribe_future, _ = mqtt_connection.subscribe(
        topic=MQTT_TOPIC,
        qos=mqtt.QoS.AT_MOST_ONCE,
        callback=on_message_received)
    subscribe_future.result()
    logger.debug("Subscribed!")

def default(o):
    if hasattr(o, "isoformat"):
        return o.astimezone().isoformat()
    else:
        return str(o)

def publish(mqtt_connection: mqtt.Connection, data):
    message = json.dumps(data, sort_keys=True, default=default)
    publish_future, _ = mqtt_connection.publish(
        topic=MQTT_TOPIC,
        payload=message,
        qos=mqtt.QoS.AT_MOST_ONCE)
    publish_future.result()
    logger.debug("Published!")
    received_all_event.wait(timeout=30)
    logger.debug("Callbacked!")

def disconnect(mqtt_connection: mqtt.Connection):
    disconnect_future = mqtt_connection.disconnect()
    disconnect_future.result()
    logger.debug("Disconnected")

def _get_last_log_push():
    try:
        lp_path = os.path.join(DATA_DIR, "log_push.json")
        with open(lp_path, "r") as f:
            lp = json.load(f)
        return datetime.datetime.fromisoformat(lp["timestamp"]) if "timestamp" in lp else datetime.datetime.min
    except (FileNotFoundError, json.JSONDecodeError, KeyError, ValueError):
        return datetime.datetime.min

def _set_last_log_push():
    lp_path = os.path.join(DATA_DIR, "log_push.json")
    with open(lp_path, "w") as f:
        json.dump({"timestamp": datetime.datetime.now().isoformat()}, f)

def extract_diff(data, last_data):
    return {
        **{key: { version: {alias:  device for alias, device in dd.items() if last_data.get(key, {}).get(version, {}).get("Datetime", datetime.datetime.min) != device.get("Datetime", datetime.datetime.min)} for version, dd in data[key].items()} for key in ["meters", "plugs"]},
        **{key: v for key, v in data.items() if key not in ["meters", "plugs"]}
    }

_last_data = {}

def task(data):
    global _last_data
    if _get_last_log_push() + datetime.timedelta(minutes=2) > datetime.datetime.now():
        logger.debug("Log push skipped (cooldown)")
        return { }
    filtered_data = extract_diff(data, _last_data)
    logger.debug("Log push filtered data: %s", filtered_data)
    try:
        mqtt_connection = get_connection_and_connect()
        subscribe(mqtt_connection)
        publish(mqtt_connection, filtered_data)
        disconnect(mqtt_connection)
    except Exception as e:
        logger.error(e)
        return { "log_push_successful": False }
    _set_last_log_push()
    _last_data = data
    logger.info("Log push successful")
    return { "log_push_successful": True }

