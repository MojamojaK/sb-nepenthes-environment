import json
import logging
import os
import datetime

from config.device_aliases import cooler_aliases

logger = logging.getLogger(__name__)

DEFAULT_STATE_PATH = os.path.join("data", "cooler_frozen_state.json")

# Detection window per number of active coolers (minutes).
# More coolers → faster expected cooling → shorter detection window.
FROZEN_DETECTION_MINUTES = {
    1: 60,
    2: 30,
}

# Ignore small fluctuations when deciding whether the coolant is frozen.
# The SwitchBot sensor has 0.1 °C granularity.  A tolerance of 0.3 °C
# filters out minor noise while catching a genuine temperature rise.
FROZEN_TEMP_TOLERANCE = 0.3

# How long to pause all thermal systems to allow coolant to thaw (minutes).
FROZEN_THAW_MINUTES = 90


def _detection_minutes(active_cooler_count: int) -> int:
    """Return the freeze-detection window for the given number of active coolers."""
    return FROZEN_DETECTION_MINUTES.get(
        active_cooler_count,
        FROZEN_DETECTION_MINUTES[max(FROZEN_DETECTION_MINUTES)],
    )


def _load_state(state_path: str) -> dict:
    try:
        with open(state_path, "r") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def _save_state(state_path: str, state: dict) -> None:
    try:
        directory = os.path.dirname(state_path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        with open(state_path, "w") as f:
            json.dump(state, f)
    except OSError:
        logger.warning("Failed to save cooler frozen state to %s", state_path)


def check_cooler_frozen(
    current_datetime: datetime.datetime,
    active_cooler_count: int,
    current_temperature: float,
    state_path: str = DEFAULT_STATE_PATH,
) -> bool:
    """Detect cooler freeze and manage the thaw pause cycle.

    Tracks temperature while coolers are running.  If temperature has not
    dropped after a detection window (which varies with the number of active
    coolers) the coolant is assumed frozen and a thaw pause of
    ``FROZEN_THAW_MINUTES`` begins during which all thermal systems should
    be disabled.

    Returns ``True`` when the system should be in a freeze-thaw pause
    (all thermal outputs off), ``False`` for normal operation.
    """
    state = _load_state(state_path)

    # --- Active freeze-thaw pause ---
    frozen_at = state.get("frozen_at")
    if frozen_at:
        frozen_at_dt = datetime.datetime.fromisoformat(frozen_at)
        elapsed = (current_datetime - frozen_at_dt).total_seconds() / 60.0
        if elapsed < FROZEN_THAW_MINUTES:
            logger.info(
                "Cooler frozen: thaw pause active (%.1f / %d min)",
                elapsed, FROZEN_THAW_MINUTES,
            )
            return True
        # Thaw period complete – clear state and fall through to tracking
        logger.info("Cooler frozen: thaw period complete after %.1f min, resuming", elapsed)
        state = {}
        _save_state(state_path, state)

    # --- Not in pause – track cooling effectiveness ---
    if active_cooler_count == 0:
        # Cooling stopped, reset any tracking
        if state.get("cooling_started_at") is not None:
            _save_state(state_path, {})
        return False

    # Coolers are active – record or evaluate
    cooling_started_at = state.get("cooling_started_at")
    stored_count = state.get("active_cooler_count")

    if cooling_started_at is None or stored_count != active_cooler_count:
        # Cooling just started, or the number of active coolers changed –
        # (re-)start the detection window with the current baseline.
        state["cooling_started_at"] = current_datetime.isoformat()
        state["cooling_start_temp"] = current_temperature
        state["active_cooler_count"] = active_cooler_count
        _save_state(state_path, state)
        return False

    started_dt = datetime.datetime.fromisoformat(cooling_started_at)
    elapsed = (current_datetime - started_dt).total_seconds() / 60.0
    detection_window = _detection_minutes(active_cooler_count)

    if elapsed < detection_window:
        return False

    start_temp = state.get("cooling_start_temp", current_temperature)

    if current_temperature >= start_temp + FROZEN_TEMP_TOLERANCE:
        # Temperature flat or rising despite active cooling – FROZEN
        logger.warning(
            "Cooler frozen detected! %d cooler(s) active for %.1f min (window %d min), "
            "start_temp=%.1f, current_temp=%.1f. Entering %d-min thaw pause.",
            active_cooler_count, elapsed, detection_window,
            start_temp, current_temperature, FROZEN_THAW_MINUTES,
        )
        _save_state(state_path, {"frozen_at": current_datetime.isoformat()})
        return True

    # Temperature has dropped – cooling is working.  Reset the detection
    # window so we keep monitoring from the new baseline.
    state["cooling_started_at"] = current_datetime.isoformat()
    state["cooling_start_temp"] = current_temperature
    _save_state(state_path, state)
    return False
