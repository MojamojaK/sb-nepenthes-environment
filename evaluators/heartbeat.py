import logging

logger = logging.getLogger(__name__)

def task(data):
    should_heartbeat = True
    meters = data.get("meters", {}).get("v0", {})
    plugs = data.get("plugs", {}).get("v0", {})
    for alias, meter in meters.items():
        if not meter.get("Valid", False):
            logger.debug("Heartbeat blocked: meter %s is invalid", alias)
        should_heartbeat = should_heartbeat and meter.get("Valid", False)
    for alias, plug in plugs.items():
        if not plug.get("Valid", False):
            logger.debug("Heartbeat blocked: plug %s is invalid", alias)
        if not plug.get("ToggleResult", True):
            logger.debug("Heartbeat blocked: plug %s toggle failed", alias)
        should_heartbeat = should_heartbeat and plug.get("Valid", False)
        should_heartbeat = should_heartbeat and plug.get("ToggleResult", True)
    if len(plugs) == 0 or len(meters) == 0:
        logger.warning("Heartbeat blocked: no plugs (%d) or no meters (%d) found", len(plugs), len(meters))
        should_heartbeat = False
    logger.debug("Heartbeat evaluation: should_heartbeat=%s", should_heartbeat)
    return { "should_heartbeat": should_heartbeat }
