#!/usr/bin/env python3
# coding: UTF-8

import bluepy
import json
import copy

from helpers.deep_update import deep_update
from helpers.logger import setup_logger, setup_data_logger
from drivers.scanner import SwitchbotScanDelegate
from config.device_config_store import get_config, should_refresh, refresh_config, is_refresh_due
from evaluators import data_validity as evaluate_data_validity
from evaluators import plug_state as evaluate_plug_state
from evaluators import overloaded as evaluate_overloaded
from evaluators import heartbeat as evaluate_heartbeat
from executors import desired_states as execute_desired_states
from executors import heartbeat as execute_heartbeat
from executors import log_push as execute_log_push

logger = setup_logger("nepenthes", debug_minutes=5)
data_logger = setup_data_logger("nepenthes")

_data = {}


def on_update(new_data):
    global _data
    _data = deep_update(_data, new_data)


def _build_scanner(config):
    return bluepy.btle.Scanner().withDelegate(SwitchbotScanDelegate(config, on_update))


def _process(data):
    data = deep_update(data, evaluate_data_validity.task(data))
    data = deep_update(data, evaluate_plug_state.task(data))
    data = deep_update(data, execute_desired_states.task(data))
    data = deep_update(data, evaluate_overloaded.task(data))
    data = deep_update(data, evaluate_heartbeat.task(data))
    data = deep_update(data, execute_heartbeat.task(data))
    data = deep_update(data, execute_log_push.task(data))
    return data


def main():
    global _data
    device_config = get_config()
    scanner = _build_scanner(device_config)
    i = 0
    warmup_refreshed = False

    while True:
        try:
            scanner.scan(timeout=5, passive=False)
        except bluepy.btle.BTLEDisconnectError as e:
            logger.warning("BLE disconnect error during scan: %s", e)
        except Exception as e:
            logger.error("Unexpected error during BLE scan: %s", e)

        data = deep_update(device_config, copy.deepcopy(_data))

        if i < 3:
            logger.info("Skipping head data (scan %d/3).", i + 1)
            i += 1
            continue

        # After warmup, check if any device was never seen by the scanner
        if not warmup_refreshed and should_refresh(data):
            logger.info("Devices missing from BLE scan, refreshing config from SwitchBot API")
            device_config = refresh_config()
            _data = {}
            scanner = _build_scanner(device_config)
            warmup_refreshed = True
            i = 0
            continue

        # Periodic refresh (hourly)
        if is_refresh_due():
            logger.info("Hourly config refresh from SwitchBot API")
            device_config = refresh_config()
            scanner = _build_scanner(device_config)

        logger.debug("--- Processing cycle %d ---", i)
        data = _process(data)
        logger.debug("should_heartbeat=%s", data.get("should_heartbeat", False))
        data_logger.info(json.dumps(data, indent=4, sort_keys=True, default=str))
        i += 1


def run():
    try:
        main()
    except Exception:
        logger.exception("Fatal crash")
        raise


if __name__ == "__main__":
    run()
