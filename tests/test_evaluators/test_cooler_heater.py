import json
import pytest
import datetime
from unittest.mock import patch
from evaluators.cooler_heater import (
    uv_time_based_on, ext_fan_state, evaluate_desired_cooler_states,
    get_balanced_cooler_desired_state,
)
from config.device_aliases import cooler_aliases, heater_aliases, extfan_aliases, uv_aliases
from config.desired_states import COOLER_PRIMARY_THRESHOLD, COOLER_SECONDARY_THRESHOLD


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


class TestGetBalancedCoolerDesiredState:
    """Tests for the session-based cooler alternation logic."""

    @pytest.fixture
    def state_path(self, tmp_path):
        return str(tmp_path / "cooler_balance_state.json")

    def _set_primary(self, state_path, alias):
        with open(state_path, "w") as f:
            json.dump({"primary": alias}, f)

    def test_no_cooling_both_off(self, state_path):
        diff = COOLER_PRIMARY_THRESHOLD + 0.1  # above primary threshold → no cooling
        current = {alias: False for alias in cooler_aliases}
        result = get_balanced_cooler_desired_state(diff, current, state_path)
        assert all(v is False for v in result.values())

    def test_heavy_cooling_both_on(self, state_path):
        diff = COOLER_SECONDARY_THRESHOLD - 0.1  # at or below secondary threshold
        current = {alias: True for alias in cooler_aliases}
        result = get_balanced_cooler_desired_state(diff, current, state_path)
        assert all(v is True for v in result.values())

    def test_light_cooling_only_primary_on(self, state_path):
        # Diff between secondary and primary thresholds → only primary runs
        diff = (COOLER_PRIMARY_THRESHOLD + COOLER_SECONDARY_THRESHOLD) / 2
        primary = cooler_aliases[0]
        self._set_primary(state_path, primary)
        current = {alias: False for alias in cooler_aliases}
        result = get_balanced_cooler_desired_state(diff, current, state_path)
        assert result[primary] is True
        for alias in cooler_aliases:
            if alias != primary:
                assert result[alias] is False

    def test_light_cooling_uses_second_alias_as_primary(self, state_path):
        diff = (COOLER_PRIMARY_THRESHOLD + COOLER_SECONDARY_THRESHOLD) / 2
        primary = cooler_aliases[1]
        self._set_primary(state_path, primary)
        current = {alias: False for alias in cooler_aliases}
        result = get_balanced_cooler_desired_state(diff, current, state_path)
        assert result[primary] is True
        for alias in cooler_aliases:
            if alias != primary:
                assert result[alias] is False

    def test_session_end_rotates_primary(self, state_path):
        """When cooling stops (was on, now off) the primary should rotate."""
        first_primary = cooler_aliases[0]
        self._set_primary(state_path, first_primary)
        # Session was active (one cooler was on)
        current = {cooler_aliases[0]: True, **{a: False for a in cooler_aliases[1:]}}
        diff = COOLER_PRIMARY_THRESHOLD + 0.1  # no longer cooling
        get_balanced_cooler_desired_state(diff, current, state_path)
        # Primary should have rotated
        with open(state_path) as f:
            saved = json.load(f)
        assert saved["primary"] == cooler_aliases[1]

    def test_no_rotation_when_cooling_continues(self, state_path):
        """Primary should not rotate while a cooling session is still active."""
        first_primary = cooler_aliases[0]
        self._set_primary(state_path, first_primary)
        current = {cooler_aliases[0]: True, **{a: False for a in cooler_aliases[1:]}}
        # Still light cooling
        diff = (COOLER_PRIMARY_THRESHOLD + COOLER_SECONDARY_THRESHOLD) / 2
        get_balanced_cooler_desired_state(diff, current, state_path)
        with open(state_path) as f:
            saved = json.load(f)
        assert saved["primary"] == first_primary

    def test_no_rotation_when_was_not_cooling(self, state_path):
        """Primary should not rotate when there was no prior cooling session."""
        first_primary = cooler_aliases[0]
        self._set_primary(state_path, first_primary)
        current = {alias: False for alias in cooler_aliases}
        diff = COOLER_PRIMARY_THRESHOLD + 0.1  # no cooling needed
        get_balanced_cooler_desired_state(diff, current, state_path)
        with open(state_path) as f:
            saved = json.load(f)
        assert saved["primary"] == first_primary

    def test_at_primary_threshold_boundary(self, state_path):
        """Exactly at the primary threshold → only primary cooler activates."""
        diff = COOLER_PRIMARY_THRESHOLD  # <= threshold → light cooling
        primary = cooler_aliases[0]
        self._set_primary(state_path, primary)
        current = {alias: False for alias in cooler_aliases}
        result = get_balanced_cooler_desired_state(diff, current, state_path)
        assert result[primary] is True

    def test_at_secondary_threshold_boundary(self, state_path):
        """Exactly at the secondary threshold → both coolers activate."""
        diff = COOLER_SECONDARY_THRESHOLD
        current = {alias: True for alias in cooler_aliases}
        result = get_balanced_cooler_desired_state(diff, current, state_path)
        assert all(v is True for v in result.values())

    def test_returns_all_cooler_aliases(self, state_path):
        """Result dict must contain an entry for every cooler alias."""
        diff = COOLER_PRIMARY_THRESHOLD + 0.1
        current = {alias: False for alias in cooler_aliases}
        result = get_balanced_cooler_desired_state(diff, current, state_path)
        assert set(result.keys()) == set(cooler_aliases)


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

    @patch("evaluators.cooler_heater.check_cooler_frozen", return_value=False)
    def test_cooler_frozen_flag_false_normal(self, mock_frozen, full_data):
        dt = datetime.datetime(2024, 1, 1, 12, 0, 0)
        result = evaluate_desired_cooler_states(dt, full_data)
        assert result["cooler_frozen"] is False


class TestEvaluateDesiredCoolerStatesFrozen:
    """Tests for the cooler-frozen override path."""

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
                "N. Peltier Upper": {"Valid": True, "Switch": True},
                "N. Peltier Lower": {"Valid": True, "Switch": False},
                "N. UV": {"Valid": True, "Switch": False},
                "N. Heater": {"Valid": True, "Switch": False},
                "N. ExtFan": {"Valid": True, "Switch": False},
            }},
        }

    @patch("evaluators.cooler_heater.check_cooler_frozen", return_value=True)
    def test_all_thermal_plugs_off_when_frozen(self, mock_frozen, full_data):
        dt = datetime.datetime(2024, 1, 1, 12, 0, 0)
        result = evaluate_desired_cooler_states(dt, full_data)
        plugs = result["plugs"]["v0"]
        for alias in cooler_aliases + heater_aliases + extfan_aliases + ["N. Pump"]:
            assert plugs[alias]["Desired"]["Switch"] is False, f"{alias} should be OFF"

    @patch("evaluators.cooler_heater.check_cooler_frozen", return_value=True)
    def test_cooler_frozen_flag_true(self, mock_frozen, full_data):
        dt = datetime.datetime(2024, 1, 1, 12, 0, 0)
        result = evaluate_desired_cooler_states(dt, full_data)
        assert result["cooler_frozen"] is True

    @patch("evaluators.cooler_heater.check_cooler_frozen", return_value=True)
    def test_meter_desired_still_computed_when_frozen(self, mock_frozen, full_data):
        dt = datetime.datetime(2024, 1, 1, 12, 0, 0)
        result = evaluate_desired_cooler_states(dt, full_data)
        for alias in result["meters"]["v0"]:
            desired = result["meters"]["v0"][alias]["Desired"]
            assert "Temperature" in desired
            assert "Humidity" in desired
            assert "TemperatureDiff" in desired

    @patch("evaluators.cooler_heater.check_cooler_frozen", return_value=True)
    def test_frozen_passes_correct_args(self, mock_frozen, full_data):
        dt = datetime.datetime(2024, 1, 1, 12, 0, 0)
        evaluate_desired_cooler_states(dt, full_data)
        mock_frozen.assert_called_once()
        args = mock_frozen.call_args
        # First positional arg: current_datetime
        assert args[0][0] == dt
        # Second positional arg: active_cooler_count (Peltier Upper is ON in fixture)
        assert args[0][1] == 1
        # Third positional arg: max_temperature (max of 22.0, 20.0)
        assert args[0][2] == 22.0

    @patch("evaluators.cooler_heater.check_cooler_frozen", return_value=True)
    def test_frozen_passes_dual_count(self, mock_frozen, full_data):
        full_data["plugs"]["v0"]["N. Peltier Lower"]["Switch"] = True
        dt = datetime.datetime(2024, 1, 1, 12, 0, 0)
        evaluate_desired_cooler_states(dt, full_data)
        assert mock_frozen.call_args[0][1] == 2
