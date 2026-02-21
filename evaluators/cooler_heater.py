import datetime
import math
import logging

from config.device_aliases import air_meter_aliases, cooler_aliases, pump_alias, heater_aliases,\
    extfan_aliases, uv_aliases
from helpers.extract_data import extract_humidities, extract_temperatures, extract_pump_switch_state,\
    extract_pump_element_switch_states, extract_current_humidity
from config.desired_states import desired_temperature, desired_min_humidity,\
    desired_temperature_map, COOLER_PRIMARY_THRESHOLD, COOLER_SECONDARY_THRESHOLD,\
    heater_active_diff_thresholds, ext_fan_diff_thresholds
from helpers.cooler_balance import get_primary_cooler, rotate_primary_cooler, DEFAULT_STATE_PATH
from helpers.cooler_frozen import check_cooler_frozen

logger = logging.getLogger(__name__)


def get_balanced_cooler_desired_state(
    max_diff_temp: float,
    current_switch_states: dict,
    state_path: str = DEFAULT_STATE_PATH,
) -> dict:
    """Return desired on/off state for each cooler, alternating the primary cooler.

    When light cooling is needed (diff within the primary threshold) only the
    current primary cooler activates.  When heavy cooling is needed (diff at or
    below the secondary threshold) both activate.  Each time a cooling session
    ends the primary role passes to the other cooler, balancing wear.
    """
    was_cooling = any(current_switch_states.get(alias, False) for alias in cooler_aliases)

    if max_diff_temp > COOLER_PRIMARY_THRESHOLD:
        desired = {alias: False for alias in cooler_aliases}
    elif max_diff_temp <= COOLER_SECONDARY_THRESHOLD:
        desired = {alias: True for alias in cooler_aliases}
    else:
        primary = get_primary_cooler(state_path)
        desired = {alias: alias == primary for alias in cooler_aliases}

    is_cooling = any(desired.values())
    if was_cooling and not is_cooling:
        rotate_primary_cooler(state_path)

    return desired


def uv_time_based_on(alias: str, current_datetime: datetime.datetime):
    if alias not in uv_aliases:
        return False
    hour = current_datetime.hour
    minute = current_datetime.minute
    return hour >= 6 and (hour < 13 or (hour == 13 and minute < 15))

def ext_fan_state(current_datetime: datetime.datetime, values: dict, thresholds: dict):  
    # Decide based on time
    hour = current_datetime.hour
    minute = current_datetime.minute
    if hour == 4:
        return minute >= 50
    if hour == 13:
        return minute >= 30
    if hour in [15]:
        return True

    # Decide whether to execute evaporative cooling
    # When should cool and should de-fog
    if values["Temperature"] <= thresholds["Temperature"]\
        and values["Humidity"] <= thresholds["Humidity"]:
        return True
    return False

def evaluate_desired_cooler_states(current_datetime: datetime.datetime, data):
    # Get Meter Temperature Max Diff
    temperatures = extract_temperatures(data)
    max_temperature = max(list(t for t in temperatures.values() if t is not None), default=15) # TODO: set default, probably time dependant
    temperatures = { alias: temperatures.get(alias, max_temperature) for alias in air_meter_aliases }
    pump_switch_state = extract_pump_switch_state(data)
    pump_element_switch_states = extract_pump_element_switch_states(data)
    air_meter_desired = { alias: math.floor((desired_temperature(alias, current_datetime)) * 10.0) / 10.0 for alias in desired_temperature_map.keys()}
    air_meter_desired_diffs = { alias: math.floor((air_meter_desired[alias] - temperatures[alias]) * 10.0) / 10.0 for alias in air_meter_desired.keys() }
    pre_max_diff_temp = min(list(air_meter_desired_diffs.values())) # Positive = should warm, Negative = should cool
    logger.debug("Temperatures: %s, desired_diffs: %s, pre_max_diff_temp: %.1f", temperatures, air_meter_desired_diffs, pre_max_diff_temp)

    # Detect cooler frozen condition
    active_cooler_count = sum(1 for alias in cooler_aliases if pump_element_switch_states.get(alias, False))
    frozen_paused = check_cooler_frozen(current_datetime, active_cooler_count, max_temperature)

    if frozen_paused:
        desired_humidity = desired_min_humidity(current_datetime)
        plug_desired_state = {alias: False for alias in cooler_aliases + heater_aliases + extfan_aliases}
        plug_desired_state[pump_alias] = False
        logger.warning("Cooler frozen: all thermal systems paused for thawing")
        return {
            "cooler_frozen": True,
            "meters": {
                "v0": { alias: {"Desired": {
                    "Temperature": air_meter_desired[alias],
                    "Humidity": desired_humidity,
                    "TemperatureDiff": air_meter_desired_diffs[alias],
                } } for alias in air_meter_desired_diffs.keys() }
            },
            "plugs": {
                "v0": { alias: {"Desired": { "Switch": desired_state } } for alias, desired_state in plug_desired_state.items() }
            }
        }

    # Get Meter Humidity Max Diff
    humidities = extract_humidities(data)
    current_humidity = extract_current_humidity(humidities)
    desired_humidity = desired_min_humidity(current_datetime)
    max_diff_hum = desired_humidity - current_humidity # Positive = should fog, Negative should de-fog
    logger.debug("Humidity: current=%.1f desired=%.1f diff=%.1f", current_humidity, desired_humidity, max_diff_hum)

    # Decide ExtFan state
    input_value = {"Temperature": pre_max_diff_temp, "Humidity": max_diff_hum}
    extfan_desired_state = { alias: ext_fan_state(current_datetime, input_value, ext_fan_diff_thresholds[alias]) for alias in extfan_aliases}
    logger.debug("ExtFan desired: %s", extfan_desired_state)

    # When External fan is on, actual temperature is perceived lower than actual
    # Should try to turn cooler on by lowering max_diff_temp
    ext_fan_is_on =  any(extfan_desired_state.values())
    max_diff_temp = pre_max_diff_temp - (1.0 if ext_fan_is_on else 0.0)

    # Decide pump-safe Cooler and Heater state
    cooler_prime_desired_state = get_balanced_cooler_desired_state(max_diff_temp, pump_element_switch_states)
    heater_prime_desired_state = { alias: max_diff_temp >= heater_active_diff_thresholds[alias] or uv_time_based_on(alias, current_datetime) for alias in heater_aliases}

    # Override Disable Heater when Ext Fan is on
    if ext_fan_is_on and "N. Heater" in heater_prime_desired_state.keys():
       heater_prime_desired_state["N. Heater"] = False
       logger.debug("Heater override: N. Heater disabled (ExtFan is ON)")
    prime_desired_state = {**cooler_prime_desired_state, **heater_prime_desired_state}
    logger.debug("Cooler desired: %s, Heater desired: %s", cooler_prime_desired_state, heater_prime_desired_state)

    # Decide Pump
    desired_pump_switch_state = any(s for s in prime_desired_state.values())
    elements_plug_desired_state = { alias: prime_desired_state[alias] and pump_switch_state for alias in cooler_aliases + heater_aliases}
    pump_plug_desired_state = { pump_alias: desired_pump_switch_state or any(s for s in pump_element_switch_states.values()) }
    plug_desired_state = {**elements_plug_desired_state, **pump_plug_desired_state, **extfan_desired_state}
    logger.debug("Pump desired: %s, all plug desired: %s", desired_pump_switch_state, plug_desired_state)
    return {
        "cooler_frozen": False,
        "meters": {
            "v0": { alias: {"Desired": {
                "Temperature": air_meter_desired[alias],
                "Humidity": desired_humidity,
                "TemperatureDiff": air_meter_desired_diffs[alias],
            } } for alias in air_meter_desired_diffs.keys() }
        },
        "plugs": {
            "v0": { alias: {"Desired": { "Switch": desired_state } } for alias, desired_state in plug_desired_state.items() }
        }
    }
