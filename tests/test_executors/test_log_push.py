import pytest
import json
import datetime
from unittest.mock import patch, MagicMock
from executors.log_push import (
    extract_diff, default, _get_last_log_push, _set_last_log_push,
    on_connection_success, on_connection_failure, on_connection_closed,
    on_connection_interrupted_do_nothing, on_connection_resumed,
    on_message_received, received_all_event,
)


class TestDefault:
    def test_datetime_serialization(self):
        dt = datetime.datetime(2024, 1, 15, 12, 30, 0,
                               tzinfo=datetime.timezone.utc)
        result = default(dt)
        assert "2024-01-15" in result
        # astimezone() converts to local tz, so just check date is present
        assert isinstance(result, str)

    def test_non_datetime_serialization(self):
        result = default(42)
        assert result == "42"

    def test_naive_datetime(self):
        dt = datetime.datetime(2024, 6, 15, 10, 0, 0)
        result = default(dt)
        assert "2024-06-15" in result
        assert isinstance(result, str)


class TestExtractDiff:
    def test_new_data_included(self):
        data = {
            "meters": {"v0": {
                "M1": {"Temperature": 25, "Datetime": datetime.datetime(2024, 1, 1, 12, 0)},
            }},
            "plugs": {"v0": {}},
        }
        last_data = {
            "meters": {"v0": {}},
            "plugs": {"v0": {}},
        }
        result = extract_diff(data, last_data)
        assert "M1" in result["meters"]["v0"]

    def test_device_without_datetime_excluded(self):
        """Devices without Datetime match the epoch default, so they're excluded
        when last_data also has no version-level Datetime (both default to epoch)."""
        data = {
            "meters": {"v0": {
                "M1": {"Temperature": 25},
            }},
            "plugs": {"v0": {}},
        }
        last_data = {
            "meters": {"v0": {}},
            "plugs": {"v0": {}},
        }
        result = extract_diff(data, last_data)
        # M1 has no Datetime, defaults to epoch. last_data version level also
        # defaults to epoch. epoch == epoch -> excluded.
        assert "M1" not in result["meters"]["v0"]

    def test_changed_datetime_included(self):
        data = {
            "meters": {"v0": {
                "M1": {"Temperature": 25, "Datetime": datetime.datetime(2024, 1, 1, 12, 1)},
            }},
            "plugs": {"v0": {}},
        }
        last_data = {
            "meters": {"v0": {
                "M1": {"Datetime": datetime.datetime(2024, 1, 1, 12, 0)},
            }},
            "plugs": {"v0": {}},
        }
        result = extract_diff(data, last_data)
        assert "M1" in result["meters"]["v0"]

    def test_non_device_keys_preserved(self):
        data = {
            "meters": {"v0": {}},
            "plugs": {"v0": {}},
            "should_heartbeat": True,
        }
        last_data = {}
        result = extract_diff(data, last_data)
        assert result["should_heartbeat"] is True

    def test_empty_data(self):
        data = {"meters": {"v0": {}}, "plugs": {"v0": {}}}
        last_data = {}
        result = extract_diff(data, last_data)
        assert result["meters"]["v0"] == {}
        assert result["plugs"]["v0"] == {}


class TestGetLastLogPush:
    def test_returns_epoch_when_no_file(self, tmp_path):
        with patch("executors.log_push.DATA_DIR", str(tmp_path)):
            result = _get_last_log_push()
            assert result == datetime.datetime.min

    def test_reads_existing_file(self, tmp_path):
        ts = "2024-06-15T12:30:00"
        lp_path = tmp_path / "log_push.json"
        lp_path.write_text(json.dumps({"timestamp": ts}))
        with patch("executors.log_push.DATA_DIR", str(tmp_path)):
            result = _get_last_log_push()
            assert result.year == 2024
            assert result.month == 6

    def test_returns_epoch_on_invalid_json(self, tmp_path):
        lp_path = tmp_path / "log_push.json"
        lp_path.write_text("not json")
        with patch("executors.log_push.DATA_DIR", str(tmp_path)):
            result = _get_last_log_push()
            assert result == datetime.datetime.min


class TestSetLastLogPush:
    def test_creates_file(self, tmp_path):
        with patch("executors.log_push.DATA_DIR", str(tmp_path)):
            _set_last_log_push()
            lp_path = tmp_path / "log_push.json"
            assert lp_path.exists()
            data = json.loads(lp_path.read_text())
            assert "timestamp" in data


class TestLogPushTask:
    @patch("executors.log_push.get_connection_and_connect")
    @patch("executors.log_push.subscribe")
    @patch("executors.log_push.publish")
    @patch("executors.log_push.disconnect")
    @patch("executors.log_push._get_last_log_push")
    @patch("executors.log_push._set_last_log_push")
    def test_skips_within_cooldown(self, mock_set, mock_get, mock_disc, mock_pub, mock_sub, mock_conn):
        mock_get.return_value = datetime.datetime.now()  # just now
        from executors.log_push import task
        result = task({"meters": {"v0": {}}, "plugs": {"v0": {}}})
        mock_conn.assert_not_called()
        assert result == {}

    @patch("executors.log_push.get_connection_and_connect")
    @patch("executors.log_push.subscribe")
    @patch("executors.log_push.publish")
    @patch("executors.log_push.disconnect")
    @patch("executors.log_push._get_last_log_push")
    @patch("executors.log_push._set_last_log_push")
    def test_pushes_when_cooldown_expired(self, mock_set, mock_get, mock_disc, mock_pub, mock_sub, mock_conn):
        mock_get.return_value = datetime.datetime.min  # epoch = long ago
        mock_conn.return_value = MagicMock()
        from executors.log_push import task
        result = task({"meters": {"v0": {}}, "plugs": {"v0": {}}})
        mock_conn.assert_called_once()
        assert result.get("log_push_successful") is True

    @patch("executors.log_push.get_connection_and_connect")
    @patch("executors.log_push._get_last_log_push")
    def test_returns_false_on_exception(self, mock_get, mock_conn):
        mock_get.return_value = datetime.datetime.min
        mock_conn.side_effect = Exception("connection failed")
        from executors.log_push import task
        result = task({"meters": {"v0": {}}, "plugs": {"v0": {}}})
        assert result.get("log_push_successful") is False


class TestGetLastLogPushMissingTimestamp:
    def test_returns_epoch_when_timestamp_key_missing(self, tmp_path):
        """File exists with valid JSON but no 'timestamp' key."""
        lp_path = tmp_path / "log_push.json"
        lp_path.write_text(json.dumps({"other_key": "value"}))
        with patch("executors.log_push.DATA_DIR", str(tmp_path)):
            result = _get_last_log_push()
            assert result == datetime.datetime.min


class TestMqttCallbacks:
    def test_on_connection_success(self):
        connection = MagicMock()
        callback_data = MagicMock()
        callback_data.return_code = 0
        callback_data.session_present = False
        with patch("executors.log_push.mqtt.OnConnectionSuccessData", type(callback_data)):
            on_connection_success(connection, callback_data)

    def test_on_connection_failure(self):
        connection = MagicMock()
        callback_data = MagicMock()
        callback_data.error = "some error"
        with patch("executors.log_push.mqtt.OnConnectionFailureData", type(callback_data)):
            on_connection_failure(connection, callback_data)

    def test_on_connection_closed(self):
        connection = MagicMock()
        callback_data = MagicMock()
        on_connection_closed(connection, callback_data)

    def test_on_connection_interrupted_do_nothing(self):
        on_connection_interrupted_do_nothing(MagicMock(), "error")

    def test_on_connection_resumed(self):
        on_connection_resumed(MagicMock(), 0, True)

    def test_on_message_received(self):
        received_all_event.clear()
        on_message_received("topic", b"payload", False, 0, False)
        assert received_all_event.is_set()


class TestGetConnectionAndConnect:
    @patch("executors.log_push.mqtt_connection_builder")
    def test_connects_and_returns_connection(self, mock_builder):
        mock_conn = MagicMock()
        mock_future = MagicMock()
        mock_conn.connect.return_value = mock_future
        mock_builder.mtls_from_path.return_value = mock_conn
        from executors.log_push import get_connection_and_connect
        result = get_connection_and_connect()
        mock_builder.mtls_from_path.assert_called_once()
        mock_conn.connect.assert_called_once()
        mock_future.result.assert_called_once()
        assert result is mock_conn


class TestSubscribe:
    def test_subscribes_to_topic(self):
        mock_conn = MagicMock()
        mock_future = MagicMock()
        mock_conn.subscribe.return_value = (mock_future, None)
        from executors.log_push import subscribe
        subscribe(mock_conn)
        mock_conn.subscribe.assert_called_once()
        mock_future.result.assert_called_once()


class TestPublish:
    def test_publishes_data(self):
        mock_conn = MagicMock()
        mock_future = MagicMock()
        mock_conn.publish.return_value = (mock_future, None)
        from executors.log_push import publish
        received_all_event.set()  # Pre-set so wait doesn't block
        publish(mock_conn, {"key": "value"})
        mock_conn.publish.assert_called_once()
        mock_future.result.assert_called_once()

    def test_publishes_with_datetime_serialization(self):
        mock_conn = MagicMock()
        mock_future = MagicMock()
        mock_conn.publish.return_value = (mock_future, None)
        from executors.log_push import publish
        received_all_event.set()
        data = {"timestamp": datetime.datetime(2024, 1, 1, tzinfo=datetime.timezone.utc)}
        publish(mock_conn, data)
        # Verify the payload was serialized with our default function
        call_kwargs = mock_conn.publish.call_args
        payload = call_kwargs[1]["payload"] if "payload" in call_kwargs[1] else call_kwargs[0][0]
        assert "2024" in str(payload)


class TestDisconnect:
    def test_disconnects(self):
        mock_conn = MagicMock()
        mock_future = MagicMock()
        mock_conn.disconnect.return_value = mock_future
        from executors.log_push import disconnect
        disconnect(mock_conn)
        mock_conn.disconnect.assert_called_once()
        mock_future.result.assert_called_once()
