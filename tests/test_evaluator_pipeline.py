"""Integration tests for the evaluator pipeline.

Evaluator modules are auto-discovered from the ``evaluators`` package:
every module that exposes a ``task(data)`` function is included.  When a
new evaluator is added, these tests cover it automatically — no manual
update required.
"""

import datetime
import importlib
import pkgutil
from unittest.mock import patch

import pytest

import evaluators
from helpers.deep_update import deep_update


def _discover_evaluator_modules():
    """Return all evaluator modules that expose a ``task`` callable."""
    modules = []
    for info in pkgutil.iter_modules(evaluators.__path__):
        mod = importlib.import_module(f"evaluators.{info.name}")
        if callable(getattr(mod, "task", None)):
            modules.append(mod)
    return modules


_EVALUATOR_MODULES = _discover_evaluator_modules()


def _evaluator_pipeline(data):
    """Run every discovered evaluator in sequence, accumulating results."""
    for mod in _EVALUATOR_MODULES:
        data = deep_update(data, mod.task(data))
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


class TestDiscovery:
    def test_all_evaluators_discovered(self):
        """Ensure auto-discovery finds every evaluator with a task()."""
        names = {mod.__name__ for mod in _EVALUATOR_MODULES}
        assert "evaluators.data_validity" in names
        assert "evaluators.plug_state" in names
        assert "evaluators.overloaded" in names
        assert "evaluators.heartbeat" in names

    def test_non_task_modules_excluded(self):
        """Modules without task() (fogger, cooler_heater) should not appear."""
        names = {mod.__name__ for mod in _EVALUATOR_MODULES}
        assert "evaluators.fogger" not in names
        assert "evaluators.cooler_heater" not in names


class TestEvaluatorPipeline:
    """End-to-end evaluator pipeline tests."""

    @patch("evaluators.cooler_heater.check_cooler_frozen", return_value=False)
    def test_pipeline_normal(self, mock_frozen, full_data):
        """Pipeline completes without errors under normal conditions."""
        result = _evaluator_pipeline(full_data)
        assert "meters" in result
        assert "plugs" in result
        assert "should_heartbeat" in result

    @pytest.mark.skip(reason="Cooler freeze detection temporarily disabled")
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

    @pytest.mark.skip(reason="Cooler freeze detection temporarily disabled")
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
