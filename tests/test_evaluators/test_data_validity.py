import pytest
import datetime
from evaluators.data_validity import task


def _make_data(meter_datetimes=None, plug_datetimes=None):
    """Helper to build test data with optional datetimes."""
    data = {"meters": {"v0": {}}, "plugs": {"v0": {}}}
    if meter_datetimes:
        for alias, dt in meter_datetimes.items():
            data["meters"]["v0"][alias] = {"Datetime": dt}
    if plug_datetimes:
        for alias, dt in plug_datetimes.items():
            data["plugs"]["v0"][alias] = {"Datetime": dt}
    return data


class TestDataValidity:
    def test_recent_device_is_valid(self):
        now = datetime.datetime.now()
        data = _make_data(meter_datetimes={"M1": now})
        result = task(data)
        assert result["meters"]["v0"]["M1"]["Valid"] is True

    def test_stale_device_is_invalid(self):
        old = datetime.datetime.now() - datetime.timedelta(minutes=20)
        data = _make_data(meter_datetimes={"M1": old})
        result = task(data)
        assert result["meters"]["v0"]["M1"]["Valid"] is False

    def test_15_minute_boundary(self):
        # Just under 15 minutes should be valid
        just_under = datetime.datetime.now() - datetime.timedelta(minutes=14, seconds=50)
        data = _make_data(meter_datetimes={"M1": just_under})
        result = task(data)
        assert result["meters"]["v0"]["M1"]["Valid"] is True

    def test_plug_validity(self):
        now = datetime.datetime.now()
        data = _make_data(plug_datetimes={"P1": now})
        result = task(data)
        assert result["plugs"]["v0"]["P1"]["Valid"] is True

    def test_stale_plug_is_invalid(self):
        old = datetime.datetime.now() - datetime.timedelta(minutes=20)
        data = _make_data(plug_datetimes={"P1": old})
        result = task(data)
        assert result["plugs"]["v0"]["P1"]["Valid"] is False

    def test_missing_datetime_keeps_no_valid_field(self):
        data = {"meters": {"v0": {"M1": {"MacAddress": "AA:BB"}}}, "plugs": {"v0": {}}}
        result = task(data)
        # Device without Datetime should not have Valid set to True
        m1 = result.get("meters", {}).get("v0", {}).get("M1", {})
        assert m1.get("Valid", False) is False

    def test_empty_data(self):
        data = {"meters": {"v0": {}}, "plugs": {"v0": {}}}
        result = task(data)
        # No devices to evaluate, so result is empty
        assert result == {}
