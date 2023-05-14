import pytest
import json
import os
import time
from unittest.mock import patch, MagicMock
import config.device_config_store as store


@pytest.fixture(autouse=True)
def reset_store_globals():
    """Reset module-level globals before each test."""
    store._config = None
    store._last_refresh_time = 0
    yield
    store._config = None
    store._last_refresh_time = 0


class TestLoadCache:
    def test_loads_valid_json(self, tmp_path):
        cache_file = tmp_path / "device_config.json"
        config = {"meters": {"v0": {"M1": {"MacAddress": "AA:BB:CC:DD:EE:FF"}}}, "plugs": {"v0": {}}}
        cache_file.write_text(json.dumps(config))
        with patch.object(store, "_CACHE_PATH", str(cache_file)):
            result = store._load_cache()
        assert result == config

    def test_returns_none_if_missing(self, tmp_path):
        with patch.object(store, "_CACHE_PATH", str(tmp_path / "nonexistent.json")):
            assert store._load_cache() is None

    def test_returns_none_on_invalid_json(self, tmp_path):
        cache_file = tmp_path / "bad.json"
        cache_file.write_text("not json{{{")
        with patch.object(store, "_CACHE_PATH", str(cache_file)):
            assert store._load_cache() is None


class TestSaveCache:
    def test_writes_json_file(self, tmp_path):
        cache_file = tmp_path / "device_config.json"
        config = {"meters": {"v0": {}}, "plugs": {"v0": {}}}
        with patch.object(store, "_CACHE_PATH", str(cache_file)):
            store._save_cache(config)
        assert json.loads(cache_file.read_text()) == config


class TestGetConfig:
    def test_returns_cached_config(self):
        store._config = {"meters": {"v0": {}}, "plugs": {"v0": {}}}
        result = store.get_config()
        assert result == store._config

    def test_loads_from_file_if_no_memory_cache(self, tmp_path):
        config = {"meters": {"v0": {"M1": {}}}, "plugs": {"v0": {}}}
        cache_file = tmp_path / "device_config.json"
        cache_file.write_text(json.dumps(config))
        with patch.object(store, "_CACHE_PATH", str(cache_file)):
            result = store.get_config()
        assert result == config

    def test_fetches_from_api_if_no_cache(self, tmp_path):
        api_config = {"meters": {"v0": {"M1": {"MacAddress": "AA:BB"}}}, "plugs": {"v0": {}}}
        cache_file = tmp_path / "device_config.json"
        with patch.object(store, "_CACHE_PATH", str(cache_file)):
            with patch.object(store, "refresh_config", return_value=api_config) as mock_refresh:
                result = store.get_config()
        mock_refresh.assert_called_once()
        assert result == api_config


class TestRefreshConfig:
    def test_successful_refresh(self, tmp_path):
        device_list = [
            {"deviceName": "N. Meter 1", "deviceId": "AABBCCDDEEFF",
             "deviceType": "MeterPlus", "enableCloudService": True}
        ]
        cache_file = tmp_path / "device_config.json"
        with patch.object(store, "_CACHE_PATH", str(cache_file)):
            with patch.object(store, "fetch_devices", return_value=device_list):
                with patch.object(store, "build_device_config", return_value={
                    "meters": {"v0": {"N. Meter 1": {"MacAddress": "AA:BB:CC:DD:EE:FF"}}},
                    "plugs": {"v0": {}},
                }) as mock_build:
                    result = store.refresh_config()

        assert "N. Meter 1" in result["meters"]["v0"]
        assert cache_file.exists()

    def test_keeps_old_config_on_failure(self):
        store._config = {"meters": {"v0": {"old": {}}}, "plugs": {"v0": {}}}
        with patch.object(store, "fetch_devices", side_effect=Exception("network error")):
            result = store.refresh_config()
        assert result == {"meters": {"v0": {"old": {}}}, "plugs": {"v0": {}}}

    def test_creates_empty_config_if_none_on_failure(self):
        store._config = None
        with patch.object(store, "fetch_devices", side_effect=Exception("network error")):
            result = store.refresh_config()
        assert result == {"meters": {"v0": {}}, "plugs": {"v0": {}}}

    def test_updates_last_refresh_time(self):
        with patch.object(store, "fetch_devices", side_effect=Exception("fail")):
            store.refresh_config()
        assert store._last_refresh_time > 0


class TestIsRefreshDue:
    def test_due_when_never_refreshed(self):
        store._last_refresh_time = 0
        with patch("time.monotonic", return_value=3601):
            assert store.is_refresh_due() is True

    def test_not_due_when_recently_refreshed(self):
        store._last_refresh_time = 1000
        with patch("time.monotonic", return_value=1500):
            assert store.is_refresh_due() is False

    def test_due_after_interval(self):
        store._last_refresh_time = 1000
        with patch("time.monotonic", return_value=4601):
            assert store.is_refresh_due() is True


class TestShouldRefresh:
    def test_true_when_device_never_seen(self):
        data = {"meters": {"v0": {
            "M1": {"MacAddress": "AA:BB:CC:DD:EE:FF"},
        }}, "plugs": {"v0": {}}}
        assert store.should_refresh(data) is True

    def test_false_when_all_devices_seen(self):
        data = {"meters": {"v0": {
            "M1": {"MacAddress": "AA:BB:CC:DD:EE:FF", "Datetime": "2024-01-01"},
        }}, "plugs": {"v0": {
            "P1": {"MacAddress": "11:22:33:44:55:66", "Datetime": "2024-01-01"},
        }}}
        assert store.should_refresh(data) is False

    def test_false_when_no_devices(self):
        data = {"meters": {"v0": {}}, "plugs": {"v0": {}}}
        assert store.should_refresh(data) is False

    def test_true_when_plug_never_seen(self):
        data = {"meters": {"v0": {}}, "plugs": {"v0": {
            "P1": {"MacAddress": "11:22:33:44:55:66"},
        }}}
        assert store.should_refresh(data) is True
