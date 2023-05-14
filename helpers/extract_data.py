
from config.device_aliases import air_meter_aliases, fogger_alias, pump_alias, cooler_aliases, heater_aliases

def extract_current_humidity(humidities):
    if not humidities:
        return None
    return min(humidities.values(), default=None)

def extract_humidities(data):
    result = {}
    meters = data.get("meters", {}).get("v0", {})
    for alias in air_meter_aliases:
        meter = meters.get(alias, {})
        if meter.get("Valid", False) and "Humidity" in meter:
            result.update({alias: meter["Humidity"]})
    return result

def extract_fogger_switch_state_and_power(data):
    plugs = data.get("plugs", {}).get("v0", {})
    fogger = plugs.get(fogger_alias, {})
    if fogger.get("Valid", False) and "Switch" in fogger and "Power" in fogger:
        return [fogger["Switch"], fogger["Power"]]
    else:
        return [False, 0.0] # Assume on when missing, will try to turn it on
    
def extract_temperatures(data):
    result = {}
    meters = data.get("meters", {}).get("v0", {})
    for alias in air_meter_aliases:
        meter = meters.get(alias, {})
        if meter.get("Valid", False) and "Temperature" in meter:
            result.update({alias: meter["Temperature"]})
    return result

def extract_pump_switch_state(data):
    plugs = data.get("plugs", {}).get("v0", {})
    pump = plugs.get(pump_alias, {})
    return pump.get("Switch", False) and pump.get("Valid", False)

def extract_pump_element_switch_states(data):
    result = {}
    plugs = data.get("plugs", {}).get("v0", {})
    for alias in cooler_aliases + heater_aliases:
        element = plugs.get(alias, {})
        if element.get("Valid", False) and "Switch" in element:
            result.update({alias: element["Switch"]})
        else:
            result.update({alias: True}) # Assume on when missing, will try to turn it off
    return result
