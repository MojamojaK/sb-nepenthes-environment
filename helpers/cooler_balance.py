import json
import logging
import os

from config.device_aliases import cooler_aliases

logger = logging.getLogger(__name__)

DEFAULT_STATE_PATH = os.path.join("data", "cooler_balance_state.json")


def get_primary_cooler(state_path: str = DEFAULT_STATE_PATH) -> str:
    """Return which cooler is currently the primary (activates first).

    Falls back to the first alias in cooler_aliases when the state file is
    missing, unreadable, or contains an unknown alias.
    """
    try:
        with open(state_path, "r") as f:
            state = json.load(f)
        primary = state.get("primary")
        if primary in cooler_aliases:
            return primary
    except (OSError, json.JSONDecodeError, KeyError):
        pass
    return cooler_aliases[0]


def rotate_primary_cooler(state_path: str = DEFAULT_STATE_PATH) -> None:
    """Rotate the primary cooler to the next one in the list and persist."""
    current = get_primary_cooler(state_path)
    idx = cooler_aliases.index(current) if current in cooler_aliases else 0
    next_primary = cooler_aliases[(idx + 1) % len(cooler_aliases)]
    try:
        directory = os.path.dirname(state_path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        with open(state_path, "w") as f:
            json.dump({"primary": next_primary}, f)
        logger.info(
            "Cooler balance: rotated primary from %s to %s", current, next_primary
        )
    except OSError:
        logger.warning(
            "Cooler balance: failed to save state to %s", state_path
        )
