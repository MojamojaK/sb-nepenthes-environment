import pytest
from evaluators.heartbeat import task


class TestHeartbeatEvaluator:
    def test_all_valid_returns_true(self):
        data = {
            "meters": {"v0": {
                "M1": {"Valid": True},
                "M2": {"Valid": True},
            }},
            "plugs": {"v0": {
                "P1": {"Valid": True, "ToggleResult": True},
            }},
        }
        result = task(data)
        assert result["should_heartbeat"] is True

    def test_invalid_meter_blocks_heartbeat(self):
        data = {
            "meters": {"v0": {
                "M1": {"Valid": True},
                "M2": {"Valid": False},
            }},
            "plugs": {"v0": {
                "P1": {"Valid": True, "ToggleResult": True},
            }},
        }
        result = task(data)
        assert result["should_heartbeat"] is False

    def test_invalid_plug_blocks_heartbeat(self):
        data = {
            "meters": {"v0": {
                "M1": {"Valid": True},
            }},
            "plugs": {"v0": {
                "P1": {"Valid": False, "ToggleResult": True},
            }},
        }
        result = task(data)
        assert result["should_heartbeat"] is False

    def test_toggle_failure_blocks_heartbeat(self):
        data = {
            "meters": {"v0": {
                "M1": {"Valid": True},
            }},
            "plugs": {"v0": {
                "P1": {"Valid": True, "ToggleResult": False},
            }},
        }
        result = task(data)
        assert result["should_heartbeat"] is False

    def test_empty_plugs_blocks_heartbeat(self):
        data = {
            "meters": {"v0": {"M1": {"Valid": True}}},
            "plugs": {"v0": {}},
        }
        result = task(data)
        assert result["should_heartbeat"] is False

    def test_empty_meters_blocks_heartbeat(self):
        data = {
            "meters": {"v0": {}},
            "plugs": {"v0": {"P1": {"Valid": True, "ToggleResult": True}}},
        }
        result = task(data)
        assert result["should_heartbeat"] is False

    def test_missing_valid_defaults_false(self):
        data = {
            "meters": {"v0": {"M1": {}}},
            "plugs": {"v0": {"P1": {}}},
        }
        result = task(data)
        assert result["should_heartbeat"] is False

    def test_missing_toggle_result_defaults_true(self):
        """ToggleResult defaults to True when not present."""
        data = {
            "meters": {"v0": {"M1": {"Valid": True}}},
            "plugs": {"v0": {"P1": {"Valid": True}}},
        }
        result = task(data)
        assert result["should_heartbeat"] is True

    def test_both_empty_blocks_heartbeat(self):
        data = {"meters": {"v0": {}}, "plugs": {"v0": {}}}
        result = task(data)
        assert result["should_heartbeat"] is False

    def test_multiple_plugs_one_invalid(self):
        data = {
            "meters": {"v0": {"M1": {"Valid": True}}},
            "plugs": {"v0": {
                "P1": {"Valid": True, "ToggleResult": True},
                "P2": {"Valid": True, "ToggleResult": False},
            }},
        }
        result = task(data)
        assert result["should_heartbeat"] is False
