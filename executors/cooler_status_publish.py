import datetime
import logging

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from config.env import CLOUDWATCH_NAMESPACE

logger = logging.getLogger(__name__)

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = boto3.client("cloudwatch")
    return _client


def publish_cooler_frozen_metric(is_frozen: bool) -> bool:
    """Publish the CoolerFrozen metric to CloudWatch.

    Publishes 1.0 when frozen, 0.0 when not frozen.
    Returns True on success, False on failure.
    """
    try:
        client = _get_client()
        client.put_metric_data(
            Namespace=CLOUDWATCH_NAMESPACE,
            MetricData=[
                {
                    "MetricName": "CoolerFrozen",
                    "Timestamp": datetime.datetime.now(datetime.timezone.utc),
                    "Value": 1.0 if is_frozen else 0.0,
                    "Unit": "None",
                },
            ],
        )
        logger.info("Published CoolerFrozen=%d to CloudWatch namespace %s",
                     int(is_frozen), CLOUDWATCH_NAMESPACE)
        return True
    except (BotoCoreError, ClientError) as e:
        logger.error("Failed to publish CoolerFrozen metric: %s", e)
        return False


def task(data):
    is_frozen = data.get("cooler_frozen", False)
    success = publish_cooler_frozen_metric(is_frozen)
    return {"cooler_status_publish_successful": success}
