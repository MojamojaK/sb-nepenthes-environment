import datetime
import pytest
from unittest.mock import patch, MagicMock

from botocore.exceptions import BotoCoreError, ClientError


class TestPublishCoolerFrozenMetric:
    @patch("executors.cooler_status_publish._get_client")
    def test_publishes_frozen_true(self, mock_get_client):
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        from executors.cooler_status_publish import publish_cooler_frozen_metric
        result = publish_cooler_frozen_metric(True)
        assert result is True
        mock_client.put_metric_data.assert_called_once()
        call_kwargs = mock_client.put_metric_data.call_args[1]
        metric = call_kwargs["MetricData"][0]
        assert metric["MetricName"] == "CoolerFrozen"
        assert metric["Value"] == 1.0
        assert metric["Unit"] == "None"

    @patch("executors.cooler_status_publish._get_client")
    def test_publishes_frozen_false(self, mock_get_client):
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        from executors.cooler_status_publish import publish_cooler_frozen_metric
        result = publish_cooler_frozen_metric(False)
        assert result is True
        call_kwargs = mock_client.put_metric_data.call_args[1]
        metric = call_kwargs["MetricData"][0]
        assert metric["Value"] == 0.0

    @patch("executors.cooler_status_publish._get_client")
    def test_uses_configured_namespace(self, mock_get_client):
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        from executors.cooler_status_publish import publish_cooler_frozen_metric
        publish_cooler_frozen_metric(False)
        call_kwargs = mock_client.put_metric_data.call_args[1]
        assert "Namespace" in call_kwargs

    @patch("executors.cooler_status_publish._get_client")
    def test_timestamp_is_utc(self, mock_get_client):
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        from executors.cooler_status_publish import publish_cooler_frozen_metric
        publish_cooler_frozen_metric(True)
        call_kwargs = mock_client.put_metric_data.call_args[1]
        ts = call_kwargs["MetricData"][0]["Timestamp"]
        assert ts.tzinfo is not None

    @patch("executors.cooler_status_publish._get_client")
    def test_returns_false_on_boto_error(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.put_metric_data.side_effect = BotoCoreError()
        mock_get_client.return_value = mock_client
        from executors.cooler_status_publish import publish_cooler_frozen_metric
        result = publish_cooler_frozen_metric(True)
        assert result is False

    @patch("executors.cooler_status_publish._get_client")
    def test_returns_false_on_client_error(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.put_metric_data.side_effect = ClientError(
            {"Error": {"Code": "AccessDenied", "Message": "denied"}},
            "PutMetricData",
        )
        mock_get_client.return_value = mock_client
        from executors.cooler_status_publish import publish_cooler_frozen_metric
        result = publish_cooler_frozen_metric(False)
        assert result is False


class TestTask:
    @patch("executors.cooler_status_publish.publish_cooler_frozen_metric")
    def test_task_passes_cooler_frozen_true(self, mock_publish):
        mock_publish.return_value = True
        from executors.cooler_status_publish import task
        result = task({"cooler_frozen": True})
        mock_publish.assert_called_once_with(True)
        assert result == {"cooler_status_publish_successful": True}

    @patch("executors.cooler_status_publish.publish_cooler_frozen_metric")
    def test_task_passes_cooler_frozen_false(self, mock_publish):
        mock_publish.return_value = True
        from executors.cooler_status_publish import task
        result = task({"cooler_frozen": False})
        mock_publish.assert_called_once_with(False)
        assert result == {"cooler_status_publish_successful": True}

    @patch("executors.cooler_status_publish.publish_cooler_frozen_metric")
    def test_task_defaults_to_false_when_key_missing(self, mock_publish):
        mock_publish.return_value = True
        from executors.cooler_status_publish import task
        result = task({})
        mock_publish.assert_called_once_with(False)
        assert result == {"cooler_status_publish_successful": True}

    @patch("executors.cooler_status_publish.publish_cooler_frozen_metric")
    def test_task_reports_failure(self, mock_publish):
        mock_publish.return_value = False
        from executors.cooler_status_publish import task
        result = task({"cooler_frozen": True})
        assert result == {"cooler_status_publish_successful": False}


class TestGetClient:
    @patch("executors.cooler_status_publish.boto3")
    def test_creates_cloudwatch_client(self, mock_boto3):
        import executors.cooler_status_publish as mod
        mod._client = None  # Reset singleton
        mock_boto3.client.return_value = MagicMock()
        client = mod._get_client()
        mock_boto3.client.assert_called_once_with("cloudwatch")
        assert client is mock_boto3.client.return_value

    @patch("executors.cooler_status_publish.boto3")
    def test_reuses_client(self, mock_boto3):
        import executors.cooler_status_publish as mod
        mod._client = None  # Reset singleton
        mock_boto3.client.return_value = MagicMock()
        client1 = mod._get_client()
        client2 = mod._get_client()
        mock_boto3.client.assert_called_once()
        assert client1 is client2
        mod._client = None  # Clean up
