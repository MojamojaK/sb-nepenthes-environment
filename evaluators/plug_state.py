import datetime
import logging
from helpers.deep_update import deep_update

from evaluators.fogger import evaluate_desired_fogger_state
from evaluators.cooler_heater import evaluate_desired_cooler_states

logger = logging.getLogger(__name__)

def task(data):
    current_datetime = datetime.datetime.now()
    logger.debug("Evaluating plug states at %s", current_datetime)
    result = evaluate_desired_fogger_state(current_datetime, data)
    result = deep_update(result, evaluate_desired_cooler_states(current_datetime, data))
    return result
