import pytest
import datetime
from config.desired_states import (
    desired_temperature, desired_min_humidity,
    time_in_range, get_between_time, to_second_stamp, stamp_diff,
    desired_temperature_map, PLUG_TASK_PRIORITY, PLUG_DEFAULT_DESIRED_STATES,
    COOLER_PRIMARY_THRESHOLD, COOLER_SECONDARY_THRESHOLD,
    heater_active_diff_thresholds, ext_fan_diff_thresholds,
)
from config.device_aliases import (
    cooler_aliases, heater_aliases, extfan_aliases,
    pump_alias, fogger_alias, air_meter_aliases,
)


class TestToSecondStamp:
    def test_midnight(self):
        assert to_second_stamp(datetime.time(0, 0, 0)) == 0

    def test_noon(self):
        assert to_second_stamp(datetime.time(12, 0, 0)) == 43200

    def test_with_minutes_and_seconds(self):
        assert to_second_stamp(datetime.time(1, 30, 45)) == 5445


class TestStampDiff:
    def test_forward_diff(self):
        a = datetime.time(10, 0, 0)
        b = datetime.time(12, 0, 0)
        assert stamp_diff(a, b) == 7200

    def test_wraparound_diff(self):
        a = datetime.time(23, 0, 0)
        b = datetime.time(1, 0, 0)
        assert stamp_diff(a, b) == 7200

    def test_same_time(self):
        t = datetime.time(5, 0, 0)
        # Same time wraps around to full day
        assert stamp_diff(t, t) == 0 or stamp_diff(t, t) == 86400


class TestTimeInRange:
    def test_normal_range(self):
        assert time_in_range(datetime.time(8, 0), datetime.time(17, 0), datetime.time(12, 0)) is True

    def test_outside_normal_range(self):
        assert time_in_range(datetime.time(8, 0), datetime.time(17, 0), datetime.time(20, 0)) is False

    def test_wraparound_range_inside(self):
        assert time_in_range(datetime.time(22, 0), datetime.time(6, 0), datetime.time(2, 0)) is True

    def test_wraparound_range_outside(self):
        assert time_in_range(datetime.time(22, 0), datetime.time(6, 0), datetime.time(12, 0)) is False

    def test_boundary_start(self):
        assert time_in_range(datetime.time(8, 0), datetime.time(17, 0), datetime.time(8, 0)) is True

    def test_boundary_end(self):
        assert time_in_range(datetime.time(8, 0), datetime.time(17, 0), datetime.time(17, 0)) is True


class TestGetBetweenTime:
    def test_finds_bounding_entries(self):
        schedule = [
            (datetime.time(0, 0), 10.0),
            (datetime.time(6, 0), 20.0),
            (datetime.time(12, 0), 25.0),
            (datetime.time(18, 0), 15.0),
        ]
        start, end = get_between_time(schedule, datetime.time(9, 0))
        assert start == (datetime.time(6, 0), 20.0)
        assert end == (datetime.time(12, 0), 25.0)

    def test_raises_on_empty_list(self):
        with pytest.raises(ValueError, match="Invalid Time Input"):
            get_between_time([], datetime.time(12, 0))


class TestDesiredTemperature:
    def test_returns_float(self):
        for alias in desired_temperature_map.keys():
            dt = datetime.datetime(2024, 1, 1, 12, 0, 0)
            temp = desired_temperature(alias, dt)
            assert isinstance(temp, float)

    def test_midday_temperature_reasonable(self):
        for alias in desired_temperature_map.keys():
            dt = datetime.datetime(2024, 1, 1, 12, 0, 0)
            temp = desired_temperature(alias, dt)
            assert 10.0 <= temp <= 30.0

    def test_night_temperature_lower(self):
        for alias in desired_temperature_map.keys():
            night = datetime.datetime(2024, 1, 1, 2, 0, 0)
            day = datetime.datetime(2024, 1, 1, 12, 0, 0)
            night_temp = desired_temperature(alias, night)
            day_temp = desired_temperature(alias, day)
            assert night_temp <= day_temp


class TestDesiredMinHumidity:
    def test_returns_float(self):
        dt = datetime.datetime(2024, 1, 1, 12, 0, 0)
        result = desired_min_humidity(dt)
        assert isinstance(result, float)

    def test_humidity_in_range(self):
        for hour in range(24):
            dt = datetime.datetime(2024, 1, 1, hour, 0, 0)
            h = desired_min_humidity(dt)
            assert 60.0 <= h <= 100.0


class TestPlugConstants:
    def test_task_priority_contains_all_plugs(self):
        expected = (
            cooler_aliases + heater_aliases + extfan_aliases
            + [pump_alias, fogger_alias]
        )
        for alias in expected:
            assert alias in PLUG_TASK_PRIORITY

    def test_default_states_has_all_plugs(self):
        for alias in PLUG_TASK_PRIORITY:
            assert alias in PLUG_DEFAULT_DESIRED_STATES

    def test_cooler_thresholds_ordered(self):
        # Secondary threshold must be strictly lower than primary threshold so
        # staged cooling makes sense.
        assert COOLER_SECONDARY_THRESHOLD < COOLER_PRIMARY_THRESHOLD

    def test_threshold_dicts_match_aliases(self):
        for alias in heater_aliases:
            assert alias in heater_active_diff_thresholds
        for alias in extfan_aliases:
            assert alias in ext_fan_diff_thresholds
