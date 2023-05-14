import pytest
import datetime
from evaluators.overloaded import task


class TestOverloaded:
    def test_marks_overloaded_plug(self):
        data = {"plugs": {"v0": {
            "P1": {"Code": "0b", "Datetime": datetime.datetime.now()},
        }}, "meters": {"v0": {}}}
        result = task(data)
        assert result["plugs"]["v0"]["P1"]["IsOverloaded"] is True

    def test_normal_plug_not_overloaded(self):
        data = {"plugs": {"v0": {
            "P1": {"Code": "00", "Datetime": datetime.datetime.now()},
        }}, "meters": {"v0": {}}}
        result = task(data)
        p1 = result.get("plugs", {}).get("v0", {}).get("P1", {})
        assert p1.get("IsOverloaded", False) is False

    def test_device_without_code_not_overloaded(self):
        """Device data without 'Code' key should not be marked overloaded."""
        data = {"plugs": {"v0": {
            "P1": {"Datetime": datetime.datetime.now()},
        }}, "meters": {"v0": {}}}
        result = task(data)
        p1 = result.get("plugs", {}).get("v0", {}).get("P1", {})
        assert p1.get("IsOverloaded", False) is False

    def test_empty_data(self):
        data = {"plugs": {"v0": {}}, "meters": {"v0": {}}}
        result = task(data)
        # No devices to evaluate, so result is empty
        assert result == {}
