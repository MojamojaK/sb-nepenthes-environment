import pytest
from helpers.extract_data import (
    extract_current_humidity,
    extract_humidities,
    extract_fogger_switch_state_and_power,
    extract_temperatures,
    extract_pump_switch_state,
    extract_pump_element_switch_states,
)


class TestExtractCurrentHumidity:
    def test_returns_min(self):
        assert extract_current_humidity({"A": 80, "B": 70, "C": 90}) == 70

    def test_single_value(self):
        assert extract_current_humidity({"A": 55}) == 55

    def test_empty_dict(self):
        assert extract_current_humidity({}) is None

    def test_none_input(self):
        assert extract_current_humidity(None) is None


class TestExtractHumidities:
    def test_extracts_valid_meters(self):
        data = {
            "meters": {"v0": {
                "N. Meter 1": {"Valid": True, "Humidity": 80},
                "N. Meter 2": {"Valid": True, "Humidity": 70},
            }}
        }
        result = extract_humidities(data)
        assert result == {"N. Meter 1": 80, "N. Meter 2": 70}

    def test_skips_invalid_meters(self):
        data = {
            "meters": {"v0": {
                "N. Meter 1": {"Valid": True, "Humidity": 80},
                "N. Meter 2": {"Valid": False, "Humidity": 70},
            }}
        }
        result = extract_humidities(data)
        assert result == {"N. Meter 1": 80}

    def test_skips_missing_humidity(self):
        data = {"meters": {"v0": {"N. Meter 1": {"Valid": True}}}}
        assert extract_humidities(data) == {}

    def test_skips_unknown_aliases(self):
        data = {"meters": {"v0": {"Unknown": {"Valid": True, "Humidity": 99}}}}
        assert extract_humidities(data) == {}

    def test_empty_data(self):
        assert extract_humidities({}) == {}


class TestExtractFoggerSwitchStateAndPower:
    def test_valid_fogger(self):
        data = {"plugs": {"v0": {
            "N. Fogger": {"Valid": True, "Switch": True, "Power": 25.5}
        }}}
        assert extract_fogger_switch_state_and_power(data) == [True, 25.5]

    def test_fogger_off(self):
        data = {"plugs": {"v0": {
            "N. Fogger": {"Valid": True, "Switch": False, "Power": 0.0}
        }}}
        assert extract_fogger_switch_state_and_power(data) == [False, 0.0]

    def test_invalid_fogger_returns_fallback(self):
        data = {"plugs": {"v0": {
            "N. Fogger": {"Valid": False, "Switch": True, "Power": 25.5}
        }}}
        assert extract_fogger_switch_state_and_power(data) == [False, 0.0]

    def test_missing_fogger_returns_fallback(self):
        data = {"plugs": {"v0": {}}}
        assert extract_fogger_switch_state_and_power(data) == [False, 0.0]

    def test_missing_power_returns_fallback(self):
        data = {"plugs": {"v0": {
            "N. Fogger": {"Valid": True, "Switch": True}
        }}}
        assert extract_fogger_switch_state_and_power(data) == [False, 0.0]


class TestExtractTemperatures:
    def test_extracts_valid_meters(self):
        data = {
            "meters": {"v0": {
                "N. Meter 1": {"Valid": True, "Temperature": 22.5},
                "N. Meter 2": {"Valid": True, "Temperature": 18.0},
            }}
        }
        result = extract_temperatures(data)
        assert result == {"N. Meter 1": 22.5, "N. Meter 2": 18.0}

    def test_skips_invalid(self):
        data = {"meters": {"v0": {
            "N. Meter 1": {"Valid": False, "Temperature": 22.5},
        }}}
        assert extract_temperatures(data) == {}

    def test_empty_data(self):
        assert extract_temperatures({}) == {}


class TestExtractPumpSwitchState:
    def test_pump_on(self):
        data = {"plugs": {"v0": {
            "N. Pump": {"Valid": True, "Switch": True}
        }}}
        assert extract_pump_switch_state(data) is True

    def test_pump_off(self):
        data = {"plugs": {"v0": {
            "N. Pump": {"Valid": True, "Switch": False}
        }}}
        assert extract_pump_switch_state(data) is False

    def test_pump_invalid(self):
        data = {"plugs": {"v0": {
            "N. Pump": {"Valid": False, "Switch": True}
        }}}
        assert extract_pump_switch_state(data) is False

    def test_pump_missing(self):
        data = {"plugs": {"v0": {}}}
        assert extract_pump_switch_state(data) is False


class TestExtractPumpElementSwitchStates:
    def test_all_valid(self):
        data = {"plugs": {"v0": {
            "N. Peltier Upper": {"Valid": True, "Switch": True},
            "N. Peltier Lower": {"Valid": True, "Switch": False},
            "N. UV": {"Valid": True, "Switch": True},
            "N. Heater": {"Valid": True, "Switch": False},
        }}}
        result = extract_pump_element_switch_states(data)
        assert result["N. Peltier Upper"] is True
        assert result["N. Peltier Lower"] is False
        assert result["N. UV"] is True
        assert result["N. Heater"] is False

    def test_missing_device_defaults_to_true(self):
        data = {"plugs": {"v0": {}}}
        result = extract_pump_element_switch_states(data)
        # All missing devices assumed on (fail-safe)
        for alias in result:
            assert result[alias] is True

    def test_invalid_device_defaults_to_true(self):
        data = {"plugs": {"v0": {
            "N. Peltier Upper": {"Valid": False, "Switch": False},
        }}}
        result = extract_pump_element_switch_states(data)
        assert result["N. Peltier Upper"] is True
