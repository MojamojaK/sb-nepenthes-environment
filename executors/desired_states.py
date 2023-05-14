import time
import logging
from helpers.deep_update import deep_update

from drivers.plugmini import switchbotplugmini
from config.desired_states import PLUG_TASK_PRIORITY, PLUG_DEFAULT_DESIRED_STATES

logger = logging.getLogger(__name__)

def task(data):
    result = {}
    plugs = data.get("plugs", {}).get("v0", {})
    for alias in PLUG_TASK_PRIORITY:
        plug = plugs.get(alias, {})
        mac_addr = plug.get("MacAddress")
        if not mac_addr:
            continue
        default_desired_state = PLUG_DEFAULT_DESIRED_STATES.get(alias, False)
        current_switch_state = plug.get("Switch", not default_desired_state)
        desired_switch_state = plug.get("Desired", {}).get("Switch", default_desired_state)
        force_on = False
        desired_switch_state = desired_switch_state if not force_on else not current_switch_state
        do_toggle = current_switch_state != desired_switch_state
        if do_toggle:
            operation = "turnon" if desired_switch_state else "turnoff"
            logger.info("Toggling %s (%s) -> %s", alias, mac_addr, operation)
            exec_result, result_code = switchbotplugmini(mac_addr, operation)
            logger.info("Toggle result for %s: success=%s code=%s", alias, exec_result, result_code)
            result = deep_update(result, {"plugs": {"v0": { alias: { "ToggleResult": exec_result, "Code": result_code } } } })
            time.sleep(1)
    return result
