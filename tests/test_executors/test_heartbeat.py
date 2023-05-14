import pytest
import json
import os
from unittest.mock import patch
from executors.heartbeat import task, _do_heartbeat


class TestHeartbeatExecutor:
    def test_writes_heartbeat_when_should_heartbeat(self, tmp_path):
        with patch("executors.heartbeat.DATA_DIR", str(tmp_path)):
            result = task({"should_heartbeat": True})
            hb_path = tmp_path / "heartbeat.json"
            assert hb_path.exists()
            data = json.loads(hb_path.read_text())
            assert "timestamp" in data

    def test_no_heartbeat_when_should_not(self, tmp_path):
        with patch("executors.heartbeat.DATA_DIR", str(tmp_path)):
            result = task({"should_heartbeat": False})
            hb_path = tmp_path / "heartbeat.json"
            assert not hb_path.exists()

    def test_no_heartbeat_when_missing_key(self, tmp_path):
        with patch("executors.heartbeat.DATA_DIR", str(tmp_path)):
            result = task({})
            hb_path = tmp_path / "heartbeat.json"
            assert not hb_path.exists()

    def test_returns_empty_dict(self, tmp_path):
        with patch("executors.heartbeat.DATA_DIR", str(tmp_path)):
            result = task({"should_heartbeat": True})
            assert result == {}

    def test_returns_empty_dict_when_skipped(self):
        result = task({"should_heartbeat": False})
        assert result == {}

    def test_heartbeat_json_has_iso_timestamp(self, tmp_path):
        with patch("executors.heartbeat.DATA_DIR", str(tmp_path)):
            task({"should_heartbeat": True})
            hb_path = tmp_path / "heartbeat.json"
            data = json.loads(hb_path.read_text())
            # Verify it's a valid ISO format timestamp
            from datetime import datetime
            parsed = datetime.fromisoformat(data["timestamp"])
            assert isinstance(parsed, datetime)

    def test_heartbeat_overwrites_previous(self, tmp_path):
        with patch("executors.heartbeat.DATA_DIR", str(tmp_path)):
            task({"should_heartbeat": True})
            first_data = json.loads((tmp_path / "heartbeat.json").read_text())
            task({"should_heartbeat": True})
            second_data = json.loads((tmp_path / "heartbeat.json").read_text())
            # Both should be valid, second should be >= first
            assert second_data["timestamp"] >= first_data["timestamp"]
