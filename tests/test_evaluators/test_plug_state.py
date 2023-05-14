import pytest
import datetime
from unittest.mock import patch, MagicMock
from evaluators.plug_state import task


class TestPlugStateEvaluator:
    @patch("evaluators.plug_state.evaluate_desired_cooler_states")
    @patch("evaluators.plug_state.evaluate_desired_fogger_state")
    def test_returns_dict(self, mock_fogger, mock_cooler):
        mock_fogger.return_value = {}
        mock_cooler.return_value = {}
        data = {
            "meters": {"v0": {"N. Meter 1": {"Temperature": 25, "Humidity": 70}}},
            "plugs": {"v0": {}},
        }
        result = task(data)
        assert isinstance(result, dict)

    @patch("evaluators.plug_state.evaluate_desired_cooler_states")
    @patch("evaluators.plug_state.evaluate_desired_fogger_state")
    def test_calls_fogger_evaluator(self, mock_fogger, mock_cooler):
        mock_fogger.return_value = {"plugs": {"v0": {"N. Fogger": {"Desired": {"Switch": True}}}}}
        mock_cooler.return_value = {}
        data = {"meters": {"v0": {}}, "plugs": {"v0": {}}}
        task(data)
        mock_fogger.assert_called_once()

    @patch("evaluators.plug_state.evaluate_desired_cooler_states")
    @patch("evaluators.plug_state.evaluate_desired_fogger_state")
    def test_calls_cooler_evaluator(self, mock_fogger, mock_cooler):
        mock_fogger.return_value = {}
        mock_cooler.return_value = {"plugs": {"v0": {"N. Peltier Upper": {"Desired": {"Switch": True}}}}}
        data = {"meters": {"v0": {}}, "plugs": {"v0": {}}}
        task(data)
        mock_cooler.assert_called_once()

    @patch("evaluators.plug_state.evaluate_desired_cooler_states")
    @patch("evaluators.plug_state.evaluate_desired_fogger_state")
    def test_merges_fogger_and_cooler_results(self, mock_fogger, mock_cooler):
        mock_fogger.return_value = {"plugs": {"v0": {"N. Fogger": {"Desired": {"Switch": True}}}}}
        mock_cooler.return_value = {"plugs": {"v0": {"N. Peltier Upper": {"Desired": {"Switch": False}}}}}
        data = {"meters": {"v0": {}}, "plugs": {"v0": {}}}
        result = task(data)
        assert "N. Fogger" in result.get("plugs", {}).get("v0", {})
        assert "N. Peltier Upper" in result.get("plugs", {}).get("v0", {})

    @patch("evaluators.plug_state.evaluate_desired_cooler_states")
    @patch("evaluators.plug_state.evaluate_desired_fogger_state")
    def test_passes_datetime_to_evaluators(self, mock_fogger, mock_cooler):
        mock_fogger.return_value = {}
        mock_cooler.return_value = {}
        data = {"meters": {"v0": {}}, "plugs": {"v0": {}}}
        task(data)
        fogger_dt = mock_fogger.call_args[0][0]
        cooler_dt = mock_cooler.call_args[0][0]
        assert isinstance(fogger_dt, datetime.datetime)
        assert isinstance(cooler_dt, datetime.datetime)
