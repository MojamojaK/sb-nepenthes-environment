#!/usr/bin/env python3

import os
import subprocess

from healthcheck import _should_reboot, _record_reboot
from helpers.logger import setup_logger

logger = setup_logger("auto_update")

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


def _git(args):
    result = subprocess.run(
        ["git"] + args,
        cwd=SCRIPT_DIR,
        capture_output=True,
        text=True,
    )
    return result


def _get_local_head():
    result = _git(["rev-parse", "HEAD"])
    return result.stdout.strip() if result.returncode == 0 else None


def _fetch():
    result = _git(["fetch", "origin", "main"])
    if result.returncode != 0:
        logger.error("Failed to fetch: " + result.stderr.strip())
    return result.returncode == 0


def _get_remote_head():
    result = _git(["rev-parse", "origin/main"])
    return result.stdout.strip() if result.returncode == 0 else None


def _pull():
    result = _git(["pull", "origin", "main"])
    if result.returncode != 0:
        logger.error("Failed to pull: " + result.stderr.strip())
    return result.returncode == 0


def _trigger_reboot():
    logger.info("Rebooting after update...")
    subprocess.run(["sudo", "reboot"])


def main():
    logger.info("Checking for updates...")

    if not _fetch():
        return

    local_head = _get_local_head()
    remote_head = _get_remote_head()

    if local_head is None or remote_head is None:
        logger.error("Failed to get commit hashes")
        return

    if local_head == remote_head:
        logger.info("Already up to date")
        return

    logger.info(f"Update available: {local_head[:7]} -> {remote_head[:7]}")

    if not _pull():
        return

    logger.info("Update applied successfully")

    if _should_reboot():
        _record_reboot()
        _trigger_reboot()
    else:
        logger.info("Skipping reboot due to backoff")


if __name__ == "__main__":
    main()
