import json
import pytest
import datetime
from helpers.cooler_frozen import (
    check_cooler_frozen,
    FROZEN_DETECTION_MINUTES,
    FROZEN_THAW_MINUTES,
)


class TestCheckCoolerFrozen:
    @pytest.fixture
    def state_path(self, tmp_path):
        return str(tmp_path / "cooler_frozen_state.json")

    def _set_state(self, state_path, state):
        with open(state_path, "w") as f:
            json.dump(state, f)

    def _get_state(self, state_path):
        with open(state_path, "r") as f:
            return json.load(f)

    # --- No prior state ---

    def test_no_state_coolers_off_returns_false(self, state_path):
        dt = datetime.datetime(2024, 1, 1, 12, 0, 0)
        assert check_cooler_frozen(dt, False, 25.0, state_path) is False

    def test_no_state_coolers_on_starts_tracking(self, state_path):
        dt = datetime.datetime(2024, 1, 1, 12, 0, 0)
        assert check_cooler_frozen(dt, True, 25.0, state_path) is False
        state = self._get_state(state_path)
        assert state["cooling_started_at"] == dt.isoformat()
        assert state["cooling_start_temp"] == 25.0

    # --- Tracking phase (before detection window) ---

    def test_before_detection_window_returns_false(self, state_path):
        start = datetime.datetime(2024, 1, 1, 12, 0, 0)
        self._set_state(state_path, {
            "cooling_started_at": start.isoformat(),
            "cooling_start_temp": 25.0,
        })
        check_time = start + datetime.timedelta(minutes=FROZEN_DETECTION_MINUTES - 1)
        assert check_cooler_frozen(check_time, True, 25.0, state_path) is False

    # --- Freeze detection ---

    def test_frozen_detected_when_temp_flat(self, state_path):
        start = datetime.datetime(2024, 1, 1, 12, 0, 0)
        self._set_state(state_path, {
            "cooling_started_at": start.isoformat(),
            "cooling_start_temp": 25.0,
        })
        check_time = start + datetime.timedelta(minutes=FROZEN_DETECTION_MINUTES)
        assert check_cooler_frozen(check_time, True, 25.0, state_path) is True

    def test_frozen_detected_when_temp_rising(self, state_path):
        start = datetime.datetime(2024, 1, 1, 12, 0, 0)
        self._set_state(state_path, {
            "cooling_started_at": start.isoformat(),
            "cooling_start_temp": 25.0,
        })
        check_time = start + datetime.timedelta(minutes=FROZEN_DETECTION_MINUTES)
        assert check_cooler_frozen(check_time, True, 26.0, state_path) is True

    def test_not_frozen_when_temp_dropping(self, state_path):
        start = datetime.datetime(2024, 1, 1, 12, 0, 0)
        self._set_state(state_path, {
            "cooling_started_at": start.isoformat(),
            "cooling_start_temp": 25.0,
        })
        check_time = start + datetime.timedelta(minutes=FROZEN_DETECTION_MINUTES)
        assert check_cooler_frozen(check_time, True, 24.0, state_path) is False

    def test_detection_window_resets_when_temp_drops(self, state_path):
        """After successful cooling is confirmed the window resets to the new baseline."""
        start = datetime.datetime(2024, 1, 1, 12, 0, 0)
        self._set_state(state_path, {
            "cooling_started_at": start.isoformat(),
            "cooling_start_temp": 25.0,
        })
        check_time = start + datetime.timedelta(minutes=FROZEN_DETECTION_MINUTES)
        check_cooler_frozen(check_time, True, 24.0, state_path)
        state = self._get_state(state_path)
        assert state["cooling_start_temp"] == 24.0
        assert state["cooling_started_at"] == check_time.isoformat()

    def test_frozen_sets_frozen_at_and_clears_tracking(self, state_path):
        start = datetime.datetime(2024, 1, 1, 12, 0, 0)
        self._set_state(state_path, {
            "cooling_started_at": start.isoformat(),
            "cooling_start_temp": 25.0,
        })
        check_time = start + datetime.timedelta(minutes=FROZEN_DETECTION_MINUTES)
        check_cooler_frozen(check_time, True, 25.0, state_path)
        state = self._get_state(state_path)
        assert state["frozen_at"] == check_time.isoformat()
        assert "cooling_started_at" not in state

    # --- Thaw pause ---

    def test_thaw_pause_active_within_window(self, state_path):
        frozen_at = datetime.datetime(2024, 1, 1, 12, 0, 0)
        self._set_state(state_path, {"frozen_at": frozen_at.isoformat()})
        check_time = frozen_at + datetime.timedelta(minutes=FROZEN_THAW_MINUTES - 1)
        assert check_cooler_frozen(check_time, True, 25.0, state_path) is True

    def test_thaw_pause_active_ignores_cooler_state(self, state_path):
        """Even if coolers are off the pause stays active until the window elapses."""
        frozen_at = datetime.datetime(2024, 1, 1, 12, 0, 0)
        self._set_state(state_path, {"frozen_at": frozen_at.isoformat()})
        check_time = frozen_at + datetime.timedelta(minutes=10)
        assert check_cooler_frozen(check_time, False, 20.0, state_path) is True

    def test_thaw_pause_ends_after_window(self, state_path):
        frozen_at = datetime.datetime(2024, 1, 1, 12, 0, 0)
        self._set_state(state_path, {"frozen_at": frozen_at.isoformat()})
        check_time = frozen_at + datetime.timedelta(minutes=FROZEN_THAW_MINUTES)
        assert check_cooler_frozen(check_time, True, 25.0, state_path) is False

    def test_thaw_pause_clears_frozen_state(self, state_path):
        """After thaw period with coolers off, state file is cleared."""
        frozen_at = datetime.datetime(2024, 1, 1, 12, 0, 0)
        self._set_state(state_path, {"frozen_at": frozen_at.isoformat()})
        check_time = frozen_at + datetime.timedelta(minutes=FROZEN_THAW_MINUTES)
        check_cooler_frozen(check_time, False, 25.0, state_path)
        state = self._get_state(state_path)
        assert "frozen_at" not in state

    def test_thaw_pause_starts_tracking_if_coolers_active(self, state_path):
        """After thaw period with coolers active, tracking starts immediately."""
        frozen_at = datetime.datetime(2024, 1, 1, 12, 0, 0)
        self._set_state(state_path, {"frozen_at": frozen_at.isoformat()})
        check_time = frozen_at + datetime.timedelta(minutes=FROZEN_THAW_MINUTES)
        check_cooler_frozen(check_time, True, 25.0, state_path)
        state = self._get_state(state_path)
        assert "frozen_at" not in state
        assert state["cooling_started_at"] == check_time.isoformat()
        assert state["cooling_start_temp"] == 25.0

    # --- Cooling stopped ---

    def test_cooling_stopped_resets_tracking(self, state_path):
        start = datetime.datetime(2024, 1, 1, 12, 0, 0)
        self._set_state(state_path, {
            "cooling_started_at": start.isoformat(),
            "cooling_start_temp": 25.0,
        })
        check_time = start + datetime.timedelta(minutes=5)
        assert check_cooler_frozen(check_time, False, 25.0, state_path) is False
        state = self._get_state(state_path)
        assert state.get("cooling_started_at") is None

    def test_cooling_stopped_no_tracking_no_write(self, state_path):
        """When there's no tracking state and coolers are off, no file is written."""
        dt = datetime.datetime(2024, 1, 1, 12, 0, 0)
        check_cooler_frozen(dt, False, 25.0, state_path)
        import os
        assert not os.path.exists(state_path)

    # --- State file robustness ---

    def test_missing_state_file_treated_as_empty(self, state_path):
        dt = datetime.datetime(2024, 1, 1, 12, 0, 0)
        result = check_cooler_frozen(dt, True, 25.0, state_path)
        assert result is False  # starts tracking

    def test_corrupt_state_file_treated_as_empty(self, state_path):
        with open(state_path, "w") as f:
            f.write("not json")
        dt = datetime.datetime(2024, 1, 1, 12, 0, 0)
        result = check_cooler_frozen(dt, True, 25.0, state_path)
        assert result is False  # starts tracking fresh

    # --- Full cycle: detect → pause → resume → re-detect ---

    def test_full_freeze_thaw_cycle(self, state_path):
        """Simulate a complete freeze-detect-thaw-resume cycle."""
        t0 = datetime.datetime(2024, 1, 1, 0, 0, 0)

        # Cooling starts
        assert check_cooler_frozen(t0, True, 25.0, state_path) is False

        # After detection window, temp hasn't dropped → frozen
        t1 = t0 + datetime.timedelta(minutes=FROZEN_DETECTION_MINUTES)
        assert check_cooler_frozen(t1, True, 25.0, state_path) is True

        # During thaw pause → still paused
        t2 = t1 + datetime.timedelta(minutes=45)
        assert check_cooler_frozen(t2, False, 25.0, state_path) is True

        # After thaw period → resume
        t3 = t1 + datetime.timedelta(minutes=FROZEN_THAW_MINUTES)
        assert check_cooler_frozen(t3, True, 25.0, state_path) is False

        # Cooling resumes, starts tracking again
        state = self._get_state(state_path)
        assert state.get("cooling_started_at") == t3.isoformat()
