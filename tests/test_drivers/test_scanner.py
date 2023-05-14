import pytest
import datetime
from unittest.mock import MagicMock

# Mock bluepy before importing scanner
import sys


class _FakeDefaultDelegate:
    def __init__(self):
        pass


# Set up bluepy mocks - need to ensure scanner module uses our mock
_mock_btle_module = MagicMock()
_mock_btle_module.DefaultDelegate = _FakeDefaultDelegate

_mock_bluepy = MagicMock()
_mock_bluepy.btle = _mock_btle_module

sys.modules["bluepy"] = _mock_bluepy
sys.modules["bluepy.btle"] = _mock_btle_module

# Force reimport to pick up our mock
if "drivers.scanner" in sys.modules:
    del sys.modules["drivers.scanner"]

from drivers.scanner import SwitchbotScanDelegate


@pytest.fixture
def sample_config():
    return {
        "meters": {"v0": {
            "N. Meter 1": {"MacAddress": "AA:BB:CC:DD:EE:FF"},
        }},
        "plugs": {"v0": {
            "N. Pump": {"MacAddress": "11:22:33:44:55:66"},
        }},
    }


class TestSwitchbotScanDelegate:
    def test_init_creates_reader_mapper(self, sample_config):
        callback = MagicMock()
        delegate = SwitchbotScanDelegate(sample_config, callback)
        assert hasattr(delegate, "reader_mapper")
        assert isinstance(delegate.reader_mapper, dict)

    def test_reader_mapper_has_meters_and_plugs(self, sample_config):
        callback = MagicMock()
        delegate = SwitchbotScanDelegate(sample_config, callback)
        assert "meters" in delegate.reader_mapper
        assert "plugs" in delegate.reader_mapper

    def test_reader_mapper_has_decode_functions(self, sample_config):
        callback = MagicMock()
        delegate = SwitchbotScanDelegate(sample_config, callback)
        assert "v0" in delegate.reader_mapper["meters"]
        assert "v0" in delegate.reader_mapper["plugs"]
        assert callable(delegate.reader_mapper["meters"]["v0"])
        assert callable(delegate.reader_mapper["plugs"]["v0"])

    def test_config_stored(self, sample_config):
        callback = MagicMock()
        delegate = SwitchbotScanDelegate(sample_config, callback)
        assert delegate.config is sample_config

    def test_callback_stored(self, sample_config):
        callback = MagicMock()
        delegate = SwitchbotScanDelegate(sample_config, callback)
        assert delegate.on_new_data is callback

    def test_decode_sensor_data_returns_none_for_missing_service_data(self, sample_config):
        callback = MagicMock()
        delegate = SwitchbotScanDelegate(sample_config, callback)
        result = delegate._decodeSensorData({})
        assert result is None

    def test_decode_sensor_data_returns_none_for_unknown_length(self, sample_config):
        callback = MagicMock()
        delegate = SwitchbotScanDelegate(sample_config, callback)
        result = delegate._decodeSensorData({"16b Service Data": "aabb"})
        assert result is None

    def test_decode_sensor_data_indoor_meter(self, sample_config):
        callback = MagicMock()
        delegate = SwitchbotScanDelegate(sample_config, callback)
        # Indoor MeterPlus: 16 hex chars in "16b Service Data"
        # First 4 chars = prefix, then valueBinary = bytes.fromhex(data[4:])
        # valueBinary[2] = battery & 0x7F
        # valueBinary[3] = temp fraction (& 0x0F) / 10
        # valueBinary[4] = temp whole (& 0x7F), bit7 = above freezing
        # valueBinary[5] = humidity & 0x7F
        # 4 chars prefix + 6 bytes (12 chars) = 16 chars total
        service_data = "0000" + "00" + "00" + "5a" + "03" + "99" + "41"
        assert len(service_data) == 16
        result = delegate._decodeSensorData({"16b Service Data": service_data})
        assert result is not None
        assert result["Temperature"] == 25.3
        assert result["Humidity"] == 65
        assert result["BatteryVoltage"] == 90

    def test_decode_plug_data_returns_none_for_wrong_length(self, sample_config):
        callback = MagicMock()
        delegate = SwitchbotScanDelegate(sample_config, callback)
        result = delegate._decodePlugData({"Manufacturer": "aabb"})
        assert result is None

    def test_decode_plug_data_with_valid_data(self, sample_config):
        callback = MagicMock()
        delegate = SwitchbotScanDelegate(sample_config, callback)
        value = "000000000000000000" + "8" + "00000" + "0064"
        assert len(value) == 28
        result = delegate._decodePlugData({"Manufacturer": value})
        assert result is not None
        assert result["Switch"] is True
        assert result["Power"] == 10.0

    def test_decode_plug_data_switch_off(self, sample_config):
        callback = MagicMock()
        delegate = SwitchbotScanDelegate(sample_config, callback)
        value = "000000000000000000" + "0" + "00000" + "0000"
        assert len(value) == 28
        result = delegate._decodePlugData({"Manufacturer": value})
        assert result is not None
        assert result["Switch"] is False
        assert result["Power"] == 0.0

    def test_decode_sensor_data_outdoor_meter(self, sample_config):
        """Outdoor meter: has Manufacturer key AND 16b Service Data length == 10."""
        callback = MagicMock()
        delegate = SwitchbotScanDelegate(sample_config, callback)
        # Service Data: 10 hex chars -> 5 bytes
        # data2[4] & 0x7F = battery
        # data1[11] bit7 = above freezing, data1[11] & 0x7F = temp whole
        # data1[10] & 0x0F = temp fraction / 10
        # data1[12] & 0x7F = humidity
        # Manufacturer: 13+ bytes (indices 10,11,12 used)
        # Let's set data1[10]=0x03 (fraction=3), data1[11]=0x99 (bit7=1 above freezing, 0x19=25),
        # data1[12]=0x41 (humidity=65)
        manufacturer = "00" * 10 + "03" + "99" + "41"  # 13 bytes = 26 chars
        service_data = "00" * 4 + "5a"  # 5 bytes = 10 chars, data2[4]=0x5a -> batt=90
        assert len(service_data) == 10
        result = delegate._decodeSensorData({
            "16b Service Data": service_data,
            "Manufacturer": manufacturer,
        })
        assert result is not None
        assert result["Temperature"] == 25.3
        assert result["Humidity"] == 65
        assert result["BatteryVoltage"] == 90

    def test_decode_sensor_data_outdoor_meter_below_freezing(self, sample_config):
        """Outdoor meter with below-freezing temperature."""
        callback = MagicMock()
        delegate = SwitchbotScanDelegate(sample_config, callback)
        # data1[11] = 0x05 (bit7=0 -> below freezing, temp whole = 5)
        # data1[10] = 0x03 (fraction = 3 -> 0.3)
        # temp = -(0.3 + 5) = -5.3
        manufacturer = "00" * 10 + "03" + "05" + "32"  # humidity = 50
        service_data = "00" * 4 + "64"  # batt = 100
        result = delegate._decodeSensorData({
            "16b Service Data": service_data,
            "Manufacturer": manufacturer,
        })
        assert result is not None
        assert result["Temperature"] == -5.3
        assert result["Humidity"] == 50
        assert result["BatteryVoltage"] == 100

    def test_decode_sensor_data_indoor_meter_below_freezing(self, sample_config):
        """Indoor meter with below-freezing temperature (line 77)."""
        callback = MagicMock()
        delegate = SwitchbotScanDelegate(sample_config, callback)
        # Indoor meter: 16 hex chars, no Manufacturer key
        # valueBinary[4] bit7=0 -> below freezing, valueBinary[4] & 0x7F = temp whole
        # valueBinary[3] & 0x0F = fraction /10
        # Set valueBinary[4]=0x0A (bit7=0, temp=10), valueBinary[3]=0x05 (frac=5 -> 0.5)
        # -> temp = -(0.5 + 10) = -10.5
        service_data = "0000" + "00" + "00" + "5a" + "05" + "0a" + "3c"
        assert len(service_data) == 16
        result = delegate._decodeSensorData({"16b Service Data": service_data})
        assert result is not None
        assert result["Temperature"] == -10.5
        assert result["Humidity"] == 60
        assert result["BatteryVoltage"] == 90


class TestHandleDiscovery:
    def test_skips_when_not_new(self, sample_config):
        """handleDiscovery returns early if neither isNewDev nor isNewData."""
        callback = MagicMock()
        delegate = SwitchbotScanDelegate(sample_config, callback)
        dev = MagicMock()
        delegate.handleDiscovery(dev, isNewDev=False, isNewData=False)
        callback.assert_not_called()

    def test_calls_callback_on_meter_match(self, sample_config):
        """handleDiscovery decodes and calls back when a meter MAC matches."""
        callback = MagicMock()
        delegate = SwitchbotScanDelegate(sample_config, callback)
        dev = MagicMock()
        dev.addr = "aa:bb:cc:dd:ee:ff"  # matches AA:BB:CC:DD:EE:FF lowered
        # Indoor meter: 16 hex chars
        service_data = "0000" + "00" + "00" + "5a" + "03" + "99" + "41"
        dev.getScanData.return_value = [
            (0, "16b Service Data", service_data),
        ]
        delegate.handleDiscovery(dev, isNewDev=True, isNewData=False)
        callback.assert_called_once()
        call_data = callback.call_args[0][0]
        assert "meters" in call_data
        assert "N. Meter 1" in call_data["meters"]["v0"]
        device_data = call_data["meters"]["v0"]["N. Meter 1"]
        assert device_data["Temperature"] == 25.3
        assert "Datetime" in device_data

    def test_calls_callback_on_plug_match(self, sample_config):
        """handleDiscovery decodes and calls back when a plug MAC matches."""
        callback = MagicMock()
        delegate = SwitchbotScanDelegate(sample_config, callback)
        dev = MagicMock()
        dev.addr = "11:22:33:44:55:66"  # matches plug MAC
        value = "000000000000000000" + "8" + "00000" + "0064"
        dev.getScanData.return_value = [
            (0, "Manufacturer", value),
        ]
        delegate.handleDiscovery(dev, isNewDev=False, isNewData=True)
        callback.assert_called_once()
        call_data = callback.call_args[0][0]
        assert "plugs" in call_data
        assert "N. Pump" in call_data["plugs"]["v0"]
        assert call_data["plugs"]["v0"]["N. Pump"]["Switch"] is True

    def test_no_callback_when_mac_does_not_match(self, sample_config):
        """handleDiscovery does not call back when MAC doesn't match any device."""
        callback = MagicMock()
        delegate = SwitchbotScanDelegate(sample_config, callback)
        dev = MagicMock()
        dev.addr = "ff:ff:ff:ff:ff:ff"  # no match
        dev.getScanData.return_value = []
        delegate.handleDiscovery(dev, isNewDev=True, isNewData=False)
        callback.assert_not_called()

    def test_no_callback_when_decode_fails(self, sample_config):
        """handleDiscovery skips callback when decode returns None."""
        callback = MagicMock()
        delegate = SwitchbotScanDelegate(sample_config, callback)
        dev = MagicMock()
        dev.addr = "aa:bb:cc:dd:ee:ff"
        # Provide data that _decodeSensorData can't decode (short service data)
        dev.getScanData.return_value = [
            (0, "16b Service Data", "aabb"),
        ]
        delegate.handleDiscovery(dev, isNewDev=True, isNewData=False)
        callback.assert_not_called()
