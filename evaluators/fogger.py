import logging

from config.device_aliases import fogger_alias
from helpers.extract_data import extract_humidities, extract_current_humidity, extract_fogger_switch_state_and_power
from config.desired_states import desired_min_humidity

logger = logging.getLogger(__name__)

def base_calculate_desired_fogger_state(current_datetime, data):
    humidities = extract_humidities(data)
    current_humidity = extract_current_humidity(humidities)
    if not current_humidity:
        logger.warning("Humidity unavailable, falling back to fogger ON")
        return True # Fallback: turns on fogger when humidity is unavailable
    desired = desired_min_humidity(current_datetime)
    logger.debug("Fogger base: current_humidity=%.1f desired_min=%.1f", current_humidity, desired)
    return current_humidity < desired

def calculate_desired_fogger_state(current_datetime, data):
    base_desired_state = base_calculate_desired_fogger_state(current_datetime, data)
    fogger_switch_state = extract_fogger_switch_state_and_power(data)
    if base_desired_state:
        if fogger_switch_state[0] and fogger_switch_state[1] < 0.01:
            logger.warning("Fogger power anomaly detected (switch=ON, power<0.01W), turning OFF")
            return False
    return base_desired_state

def evaluate_desired_fogger_state(current_datetime, data):
    desired = calculate_desired_fogger_state(current_datetime, data)
    logger.debug("Fogger desired state: %s", desired)
    return {
        "plugs": {
            "v0": {
                fogger_alias: {
                    "Desired": {"Switch": desired}
                }
            }
        }
    }