import pytest
import datetime
from evaluators.fogger import (
    base_calculate_desired_fogger_state,
    calculate_desired_fogger_state,
    evaluate_desired_fogger_state,
)
from config.device_aliases import fogger_alias


def _make_data(humidity=None, fogger_switch=None, fogger_power=None):
    """Build test data with meter humidities and fogger plug state."""
    data = {"meters": {"v0": {}}, "plugs": {"v0": {}}}
    if humidity is not None:
        data["meters"]["v0"]["N. Meter 1"] = {"Valid": True, "Humidity": humidity}
        data["meters"]["v0"]["N. Meter 2"] = {"Valid": True, "Humidity": humidity + 5}
    if fogger_switch is not None:
        data["plugs"]["v0"][fogger_alias] = {
            "Valid": True,
            "Switch": fogger_switch,
            "Power": fogger_power if fogger_power is not None else 25.0,
        }
    return data


class TestBaseCalculateDesiredFoggerState:
    def test_fog_when_dry(self):
        # At midnight, desired humidity ~94. If current is 70, should fog.
        dt = datetime.datetime(2024, 1, 1, 0, 30, 0)
        data = _make_data(humidity=70)
        assert base_calculate_desired_fogger_state(dt, data) is True

    def test_no_fog_when_humid(self):
        dt = datetime.datetime(2024, 1, 1, 0, 30, 0)
        data = _make_data(humidity=99)
        assert base_calculate_desired_fogger_state(dt, data) is False

    def test_fallback_on_when_no_humidity(self):
        dt = datetime.datetime(2024, 1, 1, 12, 0, 0)
        data = {"meters": {"v0": {}}, "plugs": {"v0": {}}}
        assert base_calculate_desired_fogger_state(dt, data) is True


class TestCalculateDesiredFoggerState:
    def test_power_anomaly_turns_off(self):
        dt = datetime.datetime(2024, 1, 1, 0, 30, 0)
        # Humidity low (should fog), but fogger switch ON with near-zero power
        data = _make_data(humidity=70, fogger_switch=True, fogger_power=0.001)
        assert calculate_desired_fogger_state(dt, data) is False

    def test_normal_operation_stays_on(self):
        dt = datetime.datetime(2024, 1, 1, 0, 30, 0)
        data = _make_data(humidity=70, fogger_switch=True, fogger_power=25.0)
        assert calculate_desired_fogger_state(dt, data) is True

    def test_no_anomaly_when_fogger_off(self):
        dt = datetime.datetime(2024, 1, 1, 0, 30, 0)
        data = _make_data(humidity=70, fogger_switch=False, fogger_power=0.0)
        # Should still want to fog (humidity low)
        assert calculate_desired_fogger_state(dt, data) is True


class TestEvaluateDesiredFoggerState:
    def test_returns_plug_structure(self):
        dt = datetime.datetime(2024, 1, 1, 12, 0, 0)
        data = _make_data(humidity=99, fogger_switch=False, fogger_power=0.0)
        result = evaluate_desired_fogger_state(dt, data)
        assert "plugs" in result
        assert "v0" in result["plugs"]
        assert fogger_alias in result["plugs"]["v0"]
        assert "Desired" in result["plugs"]["v0"][fogger_alias]
        assert "Switch" in result["plugs"]["v0"][fogger_alias]["Desired"]

    def test_desired_switch_is_bool(self):
        dt = datetime.datetime(2024, 1, 1, 12, 0, 0)
        data = _make_data(humidity=70, fogger_switch=False, fogger_power=0.0)
        result = evaluate_desired_fogger_state(dt, data)
        assert isinstance(result["plugs"]["v0"][fogger_alias]["Desired"]["Switch"], bool)
