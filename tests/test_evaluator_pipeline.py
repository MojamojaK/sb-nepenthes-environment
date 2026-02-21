"""Integration tests for the evaluator pipeline.

These tests verify that evaluators can run in sequence without crashing,
even when earlier evaluators inject non-device top-level keys (like
``cooler_frozen``) into the shared data dict.
"""

import datetime
from unittest.mock import patch

import pytest

from helpers.deep_update import deep_update
from evaluators import data_validity as evaluate_data_validity
from evaluators import plug_state as evaluate_plug_state
from evaluators import overloaded as evaluate_overloaded
from evaluators import heartbeat as evaluate_heartbeat


def _evaluator_pipeline(data):
    """Run the evaluator portion of the processing pipeline.

    Mirrors the evaluator steps in nepenthes._process() but excludes the
    executor steps (desired_states, heartbeat write, log_push) which
    require hardware or network access.
    """
    data = deep_update(data, evaluate_data_validity.task(data))
    data = deep_update(data, evaluate_plug_state.task(data))
    data = deep_update(data, evaluate_overloaded.task(data))
    data = deep_update(data, evaluate_heartbeat.task(data))
    return data


@pytest.fixture
def full_data():
    now = datetime.datetime.now()
    return {
        "meters": {"v0": {
            "N. Meter 1": {"Temperature": 22.0, "Humidity": 80, "Datetime": now, "MacAddress": "AA:BB:CC:DD:EE:01"},
            "N. Meter 2": {"Temperature": 20.0, "Humidity": 75, "Datetime": now, "MacAddress": "AA:BB:CC:DD:EE:02"},
        }},
        "plugs": {"v0": {
            "N. Pump": {"Switch": True, "Datetime": now, "MacAddress": "AA:BB:CC:DD:EE:10"},
            "N. Peltier Upper": {"Switch": True, "Datetime": now, "MacAddress": "AA:BB:CC:DD:EE:11"},
            "N. Peltier Lower": {"Switch": False, "Datetime": now, "MacAddress": "AA:BB:CC:DD:EE:12"},
            "N. UV": {"Switch": False, "Datetime": now, "MacAddress": "AA:BB:CC:DD:EE:13"},
            "N. Heater": {"Switch": False, "Datetime": now, "MacAddress": "AA:BB:CC:DD:EE:14"},
            "N. ExtFan": {"Switch": False, "Datetime": now, "MacAddress": "AA:BB:CC:DD:EE:15"},
            "N. Fogger": {"Switch": False, "Power": 0.0, "Datetime": now, "MacAddress": "AA:BB:CC:DD:EE:16"},
        }},
    }


class TestEvaluatorPipeline:
    """End-to-end evaluator pipeline tests."""

    @patch("evaluators.cooler_heater.check_cooler_frozen", return_value=False)
    def test_pipeline_normal(self, mock_frozen, full_data):
        """Pipeline completes without errors under normal conditions."""
        result = _evaluator_pipeline(full_data)
        assert "meters" in result
        assert "plugs" in result
        assert result["cooler_frozen"] is False
        assert "should_heartbeat" in result

    @patch("evaluators.cooler_heater.check_cooler_frozen", return_value=True)
    def test_pipeline_with_cooler_frozen(self, mock_frozen, full_data):
        """Pipeline completes when cooler_frozen injects a top-level bool.

        This is the scenario that caused the original AttributeError in
        evaluate_overloaded: the cooler freeze detection adds
        ``"cooler_frozen": True`` to data, and downstream evaluators that
        iterate data.items() must handle non-dict values gracefully.
        """
        result = _evaluator_pipeline(full_data)
        assert result["cooler_frozen"] is True
        assert "should_heartbeat" in result

    @patch("evaluators.cooler_heater.check_cooler_frozen", return_value=True)
    def test_overloaded_detected_despite_frozen(self, mock_frozen, full_data):
        """Overload detection still works when cooler_frozen is present."""
        full_data["plugs"]["v0"]["N. Pump"]["Code"] = "0b"
        result = _evaluator_pipeline(full_data)
        assert result["plugs"]["v0"]["N. Pump"].get("IsOverloaded") is True

    @patch("evaluators.cooler_heater.check_cooler_frozen", return_value=False)
    def test_validity_propagates_to_heartbeat(self, mock_frozen, full_data):
        """Valid devices should result in heartbeat being allowed."""
        result = _evaluator_pipeline(full_data)
        assert result["should_heartbeat"] is True

    @patch("evaluators.cooler_heater.check_cooler_frozen", return_value=False)
    def test_stale_device_blocks_heartbeat(self, mock_frozen, full_data):
        """A stale device should block the heartbeat."""
        old = datetime.datetime.now() - datetime.timedelta(minutes=20)
        full_data["meters"]["v0"]["N. Meter 1"]["Datetime"] = old
        result = _evaluator_pipeline(full_data)
        assert result["meters"]["v0"]["N. Meter 1"]["Valid"] is False
        assert result["should_heartbeat"] is False
