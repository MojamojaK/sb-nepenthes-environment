import pytest
import json
from unittest.mock import patch, MagicMock
from drivers.switchbot_api import (
    _build_headers, _device_id_to_mac, fetch_devices, build_device_config,
    METER_DEVICE_TYPES, PLUG_DEVICE_TYPES,
)


class TestDeviceIdToMac:
    def test_basic_conversion(self):
        assert _device_id_to_mac("6055F93B18EE") == "60:55:F9:3B:18:EE"

    def test_lowercase_input(self):
        assert _device_id_to_mac("aabbccddeeff") == "AA:BB:CC:DD:EE:FF"

    def test_mixed_case(self):
        assert _device_id_to_mac("48Ca43c3E5AE") == "48:CA:43:C3:E5:AE"


class TestBuildHeaders:
    def test_returns_required_keys(self):
        headers = _build_headers("test_token", "test_secret")
        assert "Authorization" in headers
        assert "sign" in headers
        assert "t" in headers
        assert "nonce" in headers
        assert "Content-Type" in headers

    def test_authorization_is_token(self):
        headers = _build_headers("my_token", "my_secret")
        assert headers["Authorization"] == "my_token"

    def test_timestamp_is_numeric(self):
        headers = _build_headers("token", "secret")
        assert headers["t"].isdigit()

    def test_sign_is_base64(self):
        import base64
        headers = _build_headers("token", "secret")
        # Should not raise
        base64.b64decode(headers["sign"])


class TestFetchDevices:
    def test_successful_fetch(self):
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "statusCode": 100,
            "body": {"deviceList": [{"deviceName": "Test"}]}
        }).encode("utf-8")
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_response):
            result = fetch_devices("token", "secret")
        assert result == [{"deviceName": "Test"}]

    def test_api_error_raises(self):
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "statusCode": 200,
            "message": "error"
        }).encode("utf-8")
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_response):
            with pytest.raises(RuntimeError, match="SwitchBot API error"):
                fetch_devices("token", "secret")

    def test_empty_device_list(self):
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "statusCode": 100,
            "body": {"deviceList": []}
        }).encode("utf-8")
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_response):
            result = fetch_devices("token", "secret")
        assert result == []


class TestBuildDeviceConfig:
    def test_registers_meter(self):
        devices = [{
            "deviceName": "N. Meter 1",
            "deviceId": "AABBCCDDEEFF",
            "deviceType": "MeterPlus",
            "enableCloudService": True,
        }]
        config = build_device_config(devices)
        assert "N. Meter 1" in config["meters"]["v0"]
        assert config["meters"]["v0"]["N. Meter 1"]["MacAddress"] == "AA:BB:CC:DD:EE:FF"

    def test_registers_plug(self):
        devices = [{
            "deviceName": "N. Pump",
            "deviceId": "112233445566",
            "deviceType": "Plug Mini (JP)",
            "enableCloudService": True,
        }]
        config = build_device_config(devices)
        assert "N. Pump" in config["plugs"]["v0"]

    def test_skips_cloud_disabled(self):
        devices = [{
            "deviceName": "N. Meter 1",
            "deviceId": "AABBCCDDEEFF",
            "deviceType": "MeterPlus",
            "enableCloudService": False,
        }]
        config = build_device_config(devices)
        assert config["meters"]["v0"] == {}

    def test_skips_unknown_type(self):
        devices = [{
            "deviceName": "Robot",
            "deviceId": "AABBCCDDEEFF",
            "deviceType": "Robot Vacuum",
            "enableCloudService": True,
        }]
        config = build_device_config(devices)
        assert config["meters"]["v0"] == {}
        assert config["plugs"]["v0"] == {}

    def test_allowed_names_filter(self):
        devices = [
            {"deviceName": "N. Meter 1", "deviceId": "AABB", "deviceType": "MeterPlus", "enableCloudService": True},
            {"deviceName": "Other Meter", "deviceId": "CCDD", "deviceType": "MeterPlus", "enableCloudService": True},
        ]
        config = build_device_config(devices, allowed_names={"N. Meter 1"})
        assert "N. Meter 1" in config["meters"]["v0"]
        assert "Other Meter" not in config["meters"]["v0"]

    def test_allowed_names_none_allows_all(self):
        devices = [
            {"deviceName": "A", "deviceId": "AABB", "deviceType": "MeterPlus", "enableCloudService": True},
            {"deviceName": "B", "deviceId": "CCDD", "deviceType": "Meter", "enableCloudService": True},
        ]
        config = build_device_config(devices, allowed_names=None)
        assert len(config["meters"]["v0"]) == 2

    def test_all_meter_types_recognized(self):
        for device_type in METER_DEVICE_TYPES:
            devices = [{"deviceName": "M", "deviceId": "AABB", "deviceType": device_type, "enableCloudService": True}]
            config = build_device_config(devices)
            assert "M" in config["meters"]["v0"], f"{device_type} not recognized as meter"

    def test_all_plug_types_recognized(self):
        for device_type in PLUG_DEVICE_TYPES:
            devices = [{"deviceName": "P", "deviceId": "AABB", "deviceType": device_type, "enableCloudService": True}]
            config = build_device_config(devices)
            assert "P" in config["plugs"]["v0"], f"{device_type} not recognized as plug"

    def test_empty_device_list(self):
        config = build_device_config([])
        assert config == {"meters": {"v0": {}}, "plugs": {"v0": {}}}
