import json
import logging
import pytest
import datetime
from helpers.cooler_frozen import (
    check_cooler_frozen,
    FROZEN_DETECTION_MINUTES,
    FROZEN_THAW_MINUTES,
    _detection_minutes,
)


class TestDetectionMinutes:
    def test_single_cooler(self):
        assert _detection_minutes(1) == FROZEN_DETECTION_MINUTES[1]

    def test_dual_cooler(self):
        assert _detection_minutes(2) == FROZEN_DETECTION_MINUTES[2]

    def test_single_longer_than_dual(self):
        assert FROZEN_DETECTION_MINUTES[1] > FROZEN_DETECTION_MINUTES[2]

    def test_unknown_count_uses_max_key(self):
        assert _detection_minutes(5) == FROZEN_DETECTION_MINUTES[max(FROZEN_DETECTION_MINUTES)]


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
        assert check_cooler_frozen(dt, 0, 25.0, state_path) is False

    def test_no_state_single_cooler_starts_tracking(self, state_path):
        dt = datetime.datetime(2024, 1, 1, 12, 0, 0)
        assert check_cooler_frozen(dt, 1, 25.0, state_path) is False
        state = self._get_state(state_path)
        assert state["cooling_started_at"] == dt.isoformat()
        assert state["cooling_start_temp"] == 25.0
        assert state["active_cooler_count"] == 1

    def test_no_state_dual_cooler_starts_tracking(self, state_path):
        dt = datetime.datetime(2024, 1, 1, 12, 0, 0)
        assert check_cooler_frozen(dt, 2, 25.0, state_path) is False
        state = self._get_state(state_path)
        assert state["active_cooler_count"] == 2

    # --- Tracking phase (before detection window) ---

    def test_single_cooler_before_window_returns_false(self, state_path):
        start = datetime.datetime(2024, 1, 1, 12, 0, 0)
        self._set_state(state_path, {
            "cooling_started_at": start.isoformat(),
            "cooling_start_temp": 25.0,
            "active_cooler_count": 1,
        })
        check_time = start + datetime.timedelta(minutes=FROZEN_DETECTION_MINUTES[1] - 1)
        assert check_cooler_frozen(check_time, 1, 25.0, state_path) is False

    def test_dual_cooler_before_window_returns_false(self, state_path):
        start = datetime.datetime(2024, 1, 1, 12, 0, 0)
        self._set_state(state_path, {
            "cooling_started_at": start.isoformat(),
            "cooling_start_temp": 25.0,
            "active_cooler_count": 2,
        })
        check_time = start + datetime.timedelta(minutes=FROZEN_DETECTION_MINUTES[2] - 1)
        assert check_cooler_frozen(check_time, 2, 25.0, state_path) is False

    # --- Freeze detection (dual cooler = 20 min) ---

    def test_dual_frozen_detected_when_temp_flat(self, state_path):
        start = datetime.datetime(2024, 1, 1, 12, 0, 0)
        self._set_state(state_path, {
            "cooling_started_at": start.isoformat(),
            "cooling_start_temp": 25.0,
            "active_cooler_count": 2,
        })
        check_time = start + datetime.timedelta(minutes=FROZEN_DETECTION_MINUTES[2])
        assert check_cooler_frozen(check_time, 2, 25.0, state_path) is True

    def test_dual_frozen_detected_when_temp_rising(self, state_path):
        start = datetime.datetime(2024, 1, 1, 12, 0, 0)
        self._set_state(state_path, {
            "cooling_started_at": start.isoformat(),
            "cooling_start_temp": 25.0,
            "active_cooler_count": 2,
        })
        check_time = start + datetime.timedelta(minutes=FROZEN_DETECTION_MINUTES[2])
        assert check_cooler_frozen(check_time, 2, 26.0, state_path) is True

    def test_dual_not_frozen_when_temp_dropping(self, state_path):
        start = datetime.datetime(2024, 1, 1, 12, 0, 0)
        self._set_state(state_path, {
            "cooling_started_at": start.isoformat(),
            "cooling_start_temp": 25.0,
            "active_cooler_count": 2,
        })
        check_time = start + datetime.timedelta(minutes=FROZEN_DETECTION_MINUTES[2])
        assert check_cooler_frozen(check_time, 2, 24.0, state_path) is False

    # --- Freeze detection (single cooler = 40 min) ---

    def test_single_not_frozen_at_dual_window(self, state_path):
        """Single cooler should NOT trigger at the dual-cooler window time."""
        start = datetime.datetime(2024, 1, 1, 12, 0, 0)
        self._set_state(state_path, {
            "cooling_started_at": start.isoformat(),
            "cooling_start_temp": 25.0,
            "active_cooler_count": 1,
        })
        check_time = start + datetime.timedelta(minutes=FROZEN_DETECTION_MINUTES[2])
        assert check_cooler_frozen(check_time, 1, 25.0, state_path) is False

    def test_single_frozen_detected_at_single_window(self, state_path):
        start = datetime.datetime(2024, 1, 1, 12, 0, 0)
        self._set_state(state_path, {
            "cooling_started_at": start.isoformat(),
            "cooling_start_temp": 25.0,
            "active_cooler_count": 1,
        })
        check_time = start + datetime.timedelta(minutes=FROZEN_DETECTION_MINUTES[1])
        assert check_cooler_frozen(check_time, 1, 25.0, state_path) is True

    def test_single_not_frozen_when_temp_dropping(self, state_path):
        start = datetime.datetime(2024, 1, 1, 12, 0, 0)
        self._set_state(state_path, {
            "cooling_started_at": start.isoformat(),
            "cooling_start_temp": 25.0,
            "active_cooler_count": 1,
        })
        check_time = start + datetime.timedelta(minutes=FROZEN_DETECTION_MINUTES[1])
        assert check_cooler_frozen(check_time, 1, 24.0, state_path) is False

    # --- Cooler count change resets tracking ---

    def test_count_increase_resets_window(self, state_path):
        """Switching from 1 to 2 coolers should reset the detection window."""
        start = datetime.datetime(2024, 1, 1, 12, 0, 0)
        self._set_state(state_path, {
            "cooling_started_at": start.isoformat(),
            "cooling_start_temp": 25.0,
            "active_cooler_count": 1,
        })
        reset_time = start + datetime.timedelta(minutes=10)
        assert check_cooler_frozen(reset_time, 2, 24.5, state_path) is False
        state = self._get_state(state_path)
        assert state["cooling_started_at"] == reset_time.isoformat()
        assert state["cooling_start_temp"] == 24.5
        assert state["active_cooler_count"] == 2

    def test_count_decrease_resets_window(self, state_path):
        """Switching from 2 to 1 coolers should reset the detection window."""
        start = datetime.datetime(2024, 1, 1, 12, 0, 0)
        self._set_state(state_path, {
            "cooling_started_at": start.isoformat(),
            "cooling_start_temp": 25.0,
            "active_cooler_count": 2,
        })
        reset_time = start + datetime.timedelta(minutes=15)
        assert check_cooler_frozen(reset_time, 1, 24.0, state_path) is False
        state = self._get_state(state_path)
        assert state["active_cooler_count"] == 1
        assert state["cooling_started_at"] == reset_time.isoformat()

    # --- Window reset on temp drop ---

    def test_detection_window_resets_when_temp_drops(self, state_path):
        start = datetime.datetime(2024, 1, 1, 12, 0, 0)
        self._set_state(state_path, {
            "cooling_started_at": start.isoformat(),
            "cooling_start_temp": 25.0,
            "active_cooler_count": 2,
        })
        check_time = start + datetime.timedelta(minutes=FROZEN_DETECTION_MINUTES[2])
        check_cooler_frozen(check_time, 2, 24.0, state_path)
        state = self._get_state(state_path)
        assert state["cooling_start_temp"] == 24.0
        assert state["cooling_started_at"] == check_time.isoformat()
        assert state["active_cooler_count"] == 2

    def test_frozen_sets_frozen_at_and_clears_tracking(self, state_path):
        start = datetime.datetime(2024, 1, 1, 12, 0, 0)
        self._set_state(state_path, {
            "cooling_started_at": start.isoformat(),
            "cooling_start_temp": 25.0,
            "active_cooler_count": 2,
        })
        check_time = start + datetime.timedelta(minutes=FROZEN_DETECTION_MINUTES[2])
        check_cooler_frozen(check_time, 2, 25.0, state_path)
        state = self._get_state(state_path)
        assert state["frozen_at"] == check_time.isoformat()
        assert "cooling_started_at" not in state

    # --- Thaw pause ---

    def test_thaw_pause_active_within_window(self, state_path):
        frozen_at = datetime.datetime(2024, 1, 1, 12, 0, 0)
        self._set_state(state_path, {"frozen_at": frozen_at.isoformat()})
        check_time = frozen_at + datetime.timedelta(minutes=FROZEN_THAW_MINUTES - 1)
        assert check_cooler_frozen(check_time, 2, 25.0, state_path) is True

    def test_thaw_pause_active_ignores_cooler_state(self, state_path):
        frozen_at = datetime.datetime(2024, 1, 1, 12, 0, 0)
        self._set_state(state_path, {"frozen_at": frozen_at.isoformat()})
        check_time = frozen_at + datetime.timedelta(minutes=10)
        assert check_cooler_frozen(check_time, 0, 20.0, state_path) is True

    def test_thaw_pause_ends_after_window(self, state_path):
        frozen_at = datetime.datetime(2024, 1, 1, 12, 0, 0)
        self._set_state(state_path, {"frozen_at": frozen_at.isoformat()})
        check_time = frozen_at + datetime.timedelta(minutes=FROZEN_THAW_MINUTES)
        assert check_cooler_frozen(check_time, 2, 25.0, state_path) is False

    def test_thaw_pause_clears_frozen_state(self, state_path):
        frozen_at = datetime.datetime(2024, 1, 1, 12, 0, 0)
        self._set_state(state_path, {"frozen_at": frozen_at.isoformat()})
        check_time = frozen_at + datetime.timedelta(minutes=FROZEN_THAW_MINUTES)
        check_cooler_frozen(check_time, 0, 25.0, state_path)
        state = self._get_state(state_path)
        assert "frozen_at" not in state

    def test_thaw_pause_starts_tracking_if_coolers_active(self, state_path):
        frozen_at = datetime.datetime(2024, 1, 1, 12, 0, 0)
        self._set_state(state_path, {"frozen_at": frozen_at.isoformat()})
        check_time = frozen_at + datetime.timedelta(minutes=FROZEN_THAW_MINUTES)
        check_cooler_frozen(check_time, 1, 25.0, state_path)
        state = self._get_state(state_path)
        assert "frozen_at" not in state
        assert state["cooling_started_at"] == check_time.isoformat()
        assert state["active_cooler_count"] == 1

    # --- Cooling stopped ---

    def test_cooling_stopped_resets_tracking(self, state_path):
        start = datetime.datetime(2024, 1, 1, 12, 0, 0)
        self._set_state(state_path, {
            "cooling_started_at": start.isoformat(),
            "cooling_start_temp": 25.0,
            "active_cooler_count": 2,
        })
        check_time = start + datetime.timedelta(minutes=5)
        assert check_cooler_frozen(check_time, 0, 25.0, state_path) is False
        state = self._get_state(state_path)
        assert state.get("cooling_started_at") is None

    def test_cooling_stopped_no_tracking_no_write(self, state_path):
        dt = datetime.datetime(2024, 1, 1, 12, 0, 0)
        check_cooler_frozen(dt, 0, 25.0, state_path)
        import os
        assert not os.path.exists(state_path)

    # --- Save state failure ---

    def test_save_state_failure_logs_warning(self, state_path, caplog):
        """When _save_state cannot write, it logs a warning and continues."""
        bad_path = "/proc/nonexistent/cooler_frozen_state.json"
        dt = datetime.datetime(2024, 1, 1, 12, 0, 0)
        with caplog.at_level(logging.WARNING):
            result = check_cooler_frozen(dt, 1, 25.0, bad_path)
        assert result is False
        assert "Failed to save cooler frozen state" in caplog.text

    # --- State file robustness ---

    def test_missing_state_file_treated_as_empty(self, state_path):
        dt = datetime.datetime(2024, 1, 1, 12, 0, 0)
        result = check_cooler_frozen(dt, 1, 25.0, state_path)
        assert result is False

    def test_corrupt_state_file_treated_as_empty(self, state_path):
        with open(state_path, "w") as f:
            f.write("not json")
        dt = datetime.datetime(2024, 1, 1, 12, 0, 0)
        result = check_cooler_frozen(dt, 1, 25.0, state_path)
        assert result is False

    # --- Full cycle: detect → pause → resume → re-detect ---

    def test_full_freeze_thaw_cycle_dual(self, state_path):
        """Full cycle with two coolers active."""
        t0 = datetime.datetime(2024, 1, 1, 0, 0, 0)

        # Cooling starts (2 coolers)
        assert check_cooler_frozen(t0, 2, 25.0, state_path) is False

        # After dual detection window, temp hasn't dropped → frozen
        t1 = t0 + datetime.timedelta(minutes=FROZEN_DETECTION_MINUTES[2])
        assert check_cooler_frozen(t1, 2, 25.0, state_path) is True

        # During thaw pause → still paused
        t2 = t1 + datetime.timedelta(minutes=45)
        assert check_cooler_frozen(t2, 0, 25.0, state_path) is True

        # After thaw period → resume
        t3 = t1 + datetime.timedelta(minutes=FROZEN_THAW_MINUTES)
        assert check_cooler_frozen(t3, 2, 25.0, state_path) is False

        state = self._get_state(state_path)
        assert state.get("cooling_started_at") == t3.isoformat()
        assert state.get("active_cooler_count") == 2

    def test_full_freeze_thaw_cycle_single(self, state_path):
        """Full cycle with one cooler – uses the longer detection window."""
        t0 = datetime.datetime(2024, 1, 1, 0, 0, 0)

        assert check_cooler_frozen(t0, 1, 25.0, state_path) is False

        # At dual-cooler window time → should NOT detect (single cooler window is longer)
        t_mid = t0 + datetime.timedelta(minutes=FROZEN_DETECTION_MINUTES[2])
        assert check_cooler_frozen(t_mid, 1, 25.0, state_path) is False

        # At single-cooler window → frozen
        t1 = t0 + datetime.timedelta(minutes=FROZEN_DETECTION_MINUTES[1])
        assert check_cooler_frozen(t1, 1, 25.0, state_path) is True

        # After thaw period → resume
        t2 = t1 + datetime.timedelta(minutes=FROZEN_THAW_MINUTES)
        assert check_cooler_frozen(t2, 1, 25.0, state_path) is False
