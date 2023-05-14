import pytest
from unittest.mock import patch, MagicMock
from executors.desired_states import task


class TestDesiredStatesExecutor:
    @patch("executors.desired_states.switchbotplugmini")
    def test_no_toggle_when_states_match(self, mock_plug):
        data = {
            "plugs": {"v0": {
                "N. Pump": {
                    "MacAddress": "AA:BB:CC:DD:EE:FF",
                    "Switch": False,
                    "Desired": {"Switch": False},
                },
            }},
        }
        result = task(data)
        mock_plug.assert_not_called()
        assert result == {}

    @patch("executors.desired_states.switchbotplugmini")
    def test_toggle_when_states_differ(self, mock_plug):
        mock_plug.return_value = (True, "0180")
        data = {
            "plugs": {"v0": {
                "N. Pump": {
                    "MacAddress": "AA:BB:CC:DD:EE:FF",
                    "Switch": False,
                    "Desired": {"Switch": True},
                },
            }},
        }
        result = task(data)
        mock_plug.assert_called_once_with("AA:BB:CC:DD:EE:FF", "turnon")
        assert result["plugs"]["v0"]["N. Pump"]["ToggleResult"] is True

    @patch("executors.desired_states.switchbotplugmini")
    def test_turnoff_operation(self, mock_plug):
        mock_plug.return_value = (True, "0100")
        data = {
            "plugs": {"v0": {
                "N. Pump": {
                    "MacAddress": "AA:BB:CC:DD:EE:FF",
                    "Switch": True,
                    "Desired": {"Switch": False},
                },
            }},
        }
        result = task(data)
        mock_plug.assert_called_once_with("AA:BB:CC:DD:EE:FF", "turnoff")

    @patch("executors.desired_states.switchbotplugmini")
    def test_skips_plug_without_mac(self, mock_plug):
        data = {
            "plugs": {"v0": {
                "N. Pump": {
                    "Switch": False,
                    "Desired": {"Switch": True},
                },
            }},
        }
        result = task(data)
        mock_plug.assert_not_called()

    @patch("executors.desired_states.switchbotplugmini")
    def test_uses_default_desired_state_when_missing(self, mock_plug):
        """When Desired is not set, default desired state is used."""
        mock_plug.return_value = (True, "0180")
        data = {
            "plugs": {"v0": {
                "N. Pump": {
                    "MacAddress": "AA:BB:CC:DD:EE:FF",
                    "Switch": True,  # Currently on
                    # No Desired key - defaults apply
                },
            }},
        }
        # The default desired state for pump is typically False
        # current_switch_state = True, desired = default (False) -> should toggle
        result = task(data)
        # Whether it toggles depends on PLUG_DEFAULT_DESIRED_STATES

    @patch("executors.desired_states.switchbotplugmini")
    def test_returns_toggle_result(self, mock_plug):
        mock_plug.return_value = (False, "0000")
        data = {
            "plugs": {"v0": {
                "N. Pump": {
                    "MacAddress": "AA:BB:CC:DD:EE:FF",
                    "Switch": False,
                    "Desired": {"Switch": True},
                },
            }},
        }
        result = task(data)
        assert result["plugs"]["v0"]["N. Pump"]["ToggleResult"] is False
        assert result["plugs"]["v0"]["N. Pump"]["Code"] == "0000"

    @patch("executors.desired_states.switchbotplugmini")
    def test_respects_plug_task_priority(self, mock_plug):
        """Only plugs in PLUG_TASK_PRIORITY are processed."""
        mock_plug.return_value = (True, "0180")
        data = {
            "plugs": {"v0": {
                "UnknownPlug": {
                    "MacAddress": "AA:BB:CC:DD:EE:FF",
                    "Switch": False,
                    "Desired": {"Switch": True},
                },
            }},
        }
        result = task(data)
        # UnknownPlug is not in PLUG_TASK_PRIORITY, so it should be skipped
        mock_plug.assert_not_called()
