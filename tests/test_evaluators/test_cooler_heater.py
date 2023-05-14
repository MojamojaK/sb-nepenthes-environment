import pytest
import datetime
from evaluators.cooler_heater import (
    uv_time_based_on, ext_fan_state, evaluate_desired_cooler_states,
)
from config.device_aliases import uv_aliases


class TestUvTimeBasedOn:
    def test_uv_on_during_day(self):
        dt = datetime.datetime(2024, 1, 1, 10, 0, 0)
        for alias in uv_aliases:
            assert uv_time_based_on(alias, dt) is True

    def test_uv_off_at_night(self):
        dt = datetime.datetime(2024, 1, 1, 22, 0, 0)
        for alias in uv_aliases:
            assert uv_time_based_on(alias, dt) is False

    def test_uv_on_at_6am(self):
        dt = datetime.datetime(2024, 1, 1, 6, 0, 0)
        for alias in uv_aliases:
            assert uv_time_based_on(alias, dt) is True

    def test_uv_off_at_1315(self):
        dt = datetime.datetime(2024, 1, 1, 13, 15, 0)
        for alias in uv_aliases:
            assert uv_time_based_on(alias, dt) is False

    def test_uv_on_at_1314(self):
        dt = datetime.datetime(2024, 1, 1, 13, 14, 0)
        for alias in uv_aliases:
            assert uv_time_based_on(alias, dt) is True

    def test_non_uv_alias_always_false(self):
        dt = datetime.datetime(2024, 1, 1, 10, 0, 0)
        assert uv_time_based_on("N. Heater", dt) is False

    def test_uv_off_before_6(self):
        dt = datetime.datetime(2024, 1, 1, 5, 59, 0)
        for alias in uv_aliases:
            assert uv_time_based_on(alias, dt) is False


class TestExtFanState:
    def test_on_at_4_50(self):
        dt = datetime.datetime(2024, 1, 1, 4, 50, 0)
        values = {"Temperature": 0, "Humidity": 0}
        thresholds = {"Temperature": -1.0, "Humidity": -10}
        assert ext_fan_state(dt, values, thresholds) is True

    def test_off_at_4_00(self):
        dt = datetime.datetime(2024, 1, 1, 4, 0, 0)
        values = {"Temperature": 0, "Humidity": 0}
        thresholds = {"Temperature": -1.0, "Humidity": -10}
        # Temperature and Humidity both 0 vs thresholds -1 and -10
        # 0 <= -1 is False, so should return False
        assert ext_fan_state(dt, values, thresholds) is False

    def test_on_at_13_30(self):
        dt = datetime.datetime(2024, 1, 1, 13, 30, 0)
        values = {"Temperature": 0, "Humidity": 0}
        thresholds = {"Temperature": -1.0, "Humidity": -10}
        assert ext_fan_state(dt, values, thresholds) is True

    def test_on_at_15(self):
        dt = datetime.datetime(2024, 1, 1, 15, 0, 0)
        values = {"Temperature": 0, "Humidity": 0}
        thresholds = {"Temperature": -1.0, "Humidity": -10}
        assert ext_fan_state(dt, values, thresholds) is True

    def test_on_when_cool_and_dry(self):
        dt = datetime.datetime(2024, 1, 1, 10, 0, 0)
        values = {"Temperature": -2.0, "Humidity": -15}
        thresholds = {"Temperature": -1.0, "Humidity": -10}
        assert ext_fan_state(dt, values, thresholds) is True

    def test_off_when_warm(self):
        dt = datetime.datetime(2024, 1, 1, 10, 0, 0)
        values = {"Temperature": 0, "Humidity": -15}
        thresholds = {"Temperature": -1.0, "Humidity": -10}
        assert ext_fan_state(dt, values, thresholds) is False


class TestEvaluateDesiredCoolerStates:
    @pytest.fixture
    def full_data(self):
        now = datetime.datetime.now()
        return {
            "meters": {"v0": {
                "N. Meter 1": {"Valid": True, "Temperature": 22.0, "Humidity": 80, "Datetime": now},
                "N. Meter 2": {"Valid": True, "Temperature": 20.0, "Humidity": 75, "Datetime": now},
            }},
            "plugs": {"v0": {
                "N. Pump": {"Valid": True, "Switch": True},
                "N. Peltier Upper": {"Valid": True, "Switch": False},
                "N. Peltier Lower": {"Valid": True, "Switch": False},
                "N. UV": {"Valid": True, "Switch": False},
                "N. Heater": {"Valid": True, "Switch": False},
                "N. ExtFan": {"Valid": True, "Switch": False},
            }},
        }

    def test_returns_meters_and_plugs(self, full_data):
        dt = datetime.datetime(2024, 1, 1, 12, 0, 0)
        result = evaluate_desired_cooler_states(dt, full_data)
        assert "meters" in result
        assert "plugs" in result

    def test_meter_desired_has_temperature(self, full_data):
        dt = datetime.datetime(2024, 1, 1, 12, 0, 0)
        result = evaluate_desired_cooler_states(dt, full_data)
        for alias in result["meters"]["v0"]:
            desired = result["meters"]["v0"][alias]["Desired"]
            assert "Temperature" in desired
            assert "Humidity" in desired
            assert "TemperatureDiff" in desired

    def test_plug_desired_has_switch(self, full_data):
        dt = datetime.datetime(2024, 1, 1, 12, 0, 0)
        result = evaluate_desired_cooler_states(dt, full_data)
        for alias in result["plugs"]["v0"]:
            desired = result["plugs"]["v0"][alias]["Desired"]
            assert "Switch" in desired
            assert isinstance(desired["Switch"], bool)

    def test_heater_disabled_when_extfan_on(self, full_data):
        # Force very warm temperatures so ExtFan turns on via evaporative cooling
        dt = datetime.datetime(2024, 1, 1, 15, 0, 0)  # 15:00 -> ExtFan always on
        result = evaluate_desired_cooler_states(dt, full_data)
        heater_switch = result["plugs"]["v0"].get("N. Heater", {}).get("Desired", {}).get("Switch")
        # When ExtFan is on, heater should be disabled
        assert heater_switch is False
