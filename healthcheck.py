#!/usr/bin/env python3

import os
import subprocess
import datetime
import json
import time

from config.paths import DATA_DIR
from config.env import NEPENTHES_SCRIPT_PATH, BT_INTERFACE
from helpers.logger import setup_logger

logger = setup_logger("healthcheck")

MAINTANECE_MODE = False
# MAINTANECE_MODE = True

# Backoff intervals in minutes: 3, 5, 10, 30, 60
REBOOT_BACKOFF_MINUTES = [3, 5, 10, 30, 60]


def _get_reboot_history_path():
    return os.path.join(DATA_DIR, "reboot_history.json")


def _get_reboot_history():
    try:
        with open(_get_reboot_history_path(), "r") as f:
            history = json.load(f)
        return history.get("reboot_timestamps", [])
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def _save_reboot_history(timestamps):
    with open(_get_reboot_history_path(), "w") as f:
        json.dump({"reboot_timestamps": timestamps}, f)


def _get_reboot_backoff_minutes():
    """Return the required wait time in minutes based on total reboot count.
    Only resets when a successful heartbeat clears the history."""
    timestamps = _get_reboot_history()
    idx = min(len(timestamps), len(REBOOT_BACKOFF_MINUTES) - 1)
    return REBOOT_BACKOFF_MINUTES[idx]


def _should_reboot():
    """Check if enough time has passed since the last reboot given the backoff."""
    timestamps = _get_reboot_history()
    if not timestamps:
        return True
    last_reboot = datetime.datetime.fromisoformat(timestamps[-1])
    backoff = _get_reboot_backoff_minutes()
    logger.info(f"Reboot backoff: {backoff} minutes (total reboots: {len(timestamps)})")
    return datetime.datetime.now() - datetime.timedelta(minutes=backoff) > last_reboot


def _clear_reboot_history():
    """Clear reboot history after a successful heartbeat."""
    try:
        os.remove(_get_reboot_history_path())
    except FileNotFoundError:
        pass


def _record_reboot():
    """Record this reboot timestamp and prune old entries."""
    now = datetime.datetime.now()
    timestamps = _get_reboot_history()
    timestamps.append(now.isoformat())
    # Keep only reboots from the last 24 hours
    cutoff = now - datetime.timedelta(hours=24)
    timestamps = [ts for ts in timestamps if datetime.datetime.fromisoformat(ts) > cutoff]
    _save_reboot_history(timestamps)


def _get_nepenthes_pid():
    # Try tmux session first
    try:
        result = subprocess.run(
            ["tmux", "list-panes", "-t", "nep-session", "-F", "#{pane_pid}"],
            capture_output=True,
            text=True,
        )
        pid_str = result.stdout.strip()
        if result.returncode == 0 and pid_str:
            return int(pid_str.splitlines()[0])
    except Exception as e:
        logger.debug("tmux lookup failed: %s", e)

    # Fall back to pgrep for manually started processes
    try:
        result = subprocess.run(
            ["pgrep", "-o", "-f", "nepenthes.py"],
            capture_output=True,
            text=True,
        )
        pid_str = result.stdout.strip()
        if result.returncode == 0 and pid_str:
            return int(pid_str.splitlines()[0])
    except Exception as e:
        logger.debug("pgrep lookup failed: %s", e)

    return -1


def _get_heartbeat_timestamp():
    try:
        hb_path = os.path.join(DATA_DIR, "heartbeat.json")
        with open(hb_path, "r") as f:
            hb = json.load(f)
        return datetime.datetime.fromisoformat(hb["timestamp"]) if "timestamp" in hb else datetime.datetime.utcfromtimestamp(0)
    except (FileNotFoundError, json.JSONDecodeError, KeyError, ValueError):
        return datetime.datetime.utcfromtimestamp(0)


def _wait_for_next_heartbeat():
    logger.info("Waiting for next heartbeat")
    start_ts = _get_heartbeat_timestamp()
    # Timesout in 30s
    for _ in range(30):
        ts = _get_heartbeat_timestamp()
        if start_ts != ts:
            return
        time.sleep(1)

def _trigger_reboot():
    logger.info("Rebooting...")
    subprocess.run(["sudo", "reboot"])


def _uv_sync():
    logger.info("Running uv sync...")
    result = subprocess.run(
        ["uv", "sync"],
        cwd=os.path.dirname(os.path.abspath(__file__)),
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        logger.error("uv sync failed: %s", result.stderr.strip())
    return result.returncode == 0


def _setcap_bluepy():
    """Grant BLE capabilities to bluepy-helper after uv sync."""
    project_dir = os.path.dirname(os.path.abspath(__file__))
    venv_dir = os.path.join(project_dir, ".venv")
    result = subprocess.run(
        ["find", venv_dir, "-name", "bluepy-helper"],
        capture_output=True,
        text=True,
    )
    helper_path = result.stdout.strip()
    if not helper_path:
        logger.warning("bluepy-helper not found, skipping setcap")
        return
    result = subprocess.run(
        ["sudo", "setcap", "cap_net_raw,cap_net_admin+eip", helper_path],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        logger.error("setcap failed: %s", result.stderr.strip())
    else:
        logger.info("setcap applied to %s", helper_path)


def _start_nep_process():
    _uv_sync()
    _setcap_bluepy()
    cmd = ["tmux", "new-session", "-d", "-s", "nep-session", "uv", "run", NEPENTHES_SCRIPT_PATH]
    process = subprocess.Popen(cmd, shell=False, stdout=subprocess.PIPE,
    stderr=subprocess.PIPE)
    nep_pid, err = process.communicate()
    logger.info("Started New Nepenthes Process: " + str(_get_nepenthes_pid()))

def _disable_bluetooth():
    subprocess.run(["sudo", "hciconfig", BT_INTERFACE, "down"])

def _enable_bluetooth():
    subprocess.run(["sudo", "hciconfig", BT_INTERFACE, "up"])

def _reenable_bluetooth():
    _disable_bluetooth()
    _enable_bluetooth()

def main():
    if MAINTANECE_MODE:
        return
    # Script intended to be run every minute using crontab

    # Check for process
    nep_pid = _get_nepenthes_pid()
    logger.info("Nepenthes PID: " + str(nep_pid))
    if nep_pid < 0:
        _start_nep_process()
        return

    # Check for heartbeat
    _wait_for_next_heartbeat()
    hb_timestamp = _get_heartbeat_timestamp()
    logger.info("Heartbeat Timestamp: " + hb_timestamp.isoformat())
    if datetime.datetime.now() - datetime.timedelta(minutes=3) > hb_timestamp:
        _reenable_bluetooth()
        if _should_reboot():
            _record_reboot()
            _trigger_reboot()
        else:
            logger.info("Heartbeat stale but skipping reboot due to backoff")
    else:
        _clear_reboot_history()


if __name__ == "__main__":
    main()

