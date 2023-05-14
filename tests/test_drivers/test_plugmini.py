import pytest
from unittest.mock import patch, MagicMock, PropertyMock


class _MockTimeoutException(Exception):
    pass


class _MockPexpectExceptions:
    TIMEOUT = _MockTimeoutException


@pytest.fixture
def mock_pexpect():
    mock = MagicMock()
    mock.exceptions = _MockPexpectExceptions()
    with patch.dict("sys.modules", {"pexpect": mock}):
        # Force reimport so plugmini picks up our mock
        import importlib
        import drivers.plugmini
        importlib.reload(drivers.plugmini)
        yield mock, drivers.plugmini


# Simulates gatttool char-desc output:
# "handle: 0x000e, char properties: 0x08, char value handle: 0x000f, uuid: ..."
# split('\n')[-1].split()[2] extracts "0x000f," -> strip(',') -> "0x000f"
CHAR_DESC_BEFORE = b"some header\nhandle: 0x000e, char properties: 0x08, char value handle: 0x000f, uuid:"
VALUE_RESPONSE = b"value:01 80"
VALUE_OFF_RESPONSE = b"value:01 00"


class TestSwitchbotPlugMini:
    def test_invalid_mac_raises_valueerror(self, mock_pexpect):
        _, plugmini = mock_pexpect
        with pytest.raises(ValueError, match="Invalid MAC address"):
            plugmini.switchbotplugmini("not-a-mac", "turnon")

    def test_connection_error_returns_false(self, mock_pexpect):
        mock_mod, plugmini = mock_pexpect
        child = MagicMock()
        mock_mod.spawn.return_value = child

        child.expect.side_effect = [
            None,           # first expect: \[LE\]>
            0, 0, 0,        # three retries, all return 0 (Error)
        ]

        result, data = plugmini.switchbotplugmini("AA:BB:CC:DD:EE:FF", "turnon")
        assert result is False
        assert data == "0000"

    def test_connection_timeout_returns_false(self, mock_pexpect):
        mock_mod, plugmini = mock_pexpect
        child = MagicMock()
        mock_mod.spawn.return_value = child

        child.expect.side_effect = [
            None,  # first expect: \[LE\]>
            3,     # timeout index on first try
        ]

        result, data = plugmini.switchbotplugmini("AA:BB:CC:DD:EE:FF", "turnon")
        assert result is False
        assert data == "0001"

    def test_turnon_success(self, mock_pexpect):
        mock_mod, plugmini = mock_pexpect
        child = MagicMock()
        mock_mod.spawn.return_value = child

        child.expect.side_effect = [
            None,  # \[LE\]>
            1,     # connection successful (\[CON\])
            None,  # char-desc expect
            None,  # \[LE\]> after write
            0,     # char-read-uuid success (value:...)
            None,  # final \[LE\]>
        ]
        child.before = CHAR_DESC_BEFORE
        child.after = VALUE_RESPONSE

        result, data = plugmini.switchbotplugmini("AA:BB:CC:DD:EE:FF", "turnon")
        assert result is True
        assert data == "0180"
        # Verify correct write command was sent
        write_calls = [c for c in child.sendline.call_args_list
                       if "570f50010180" in str(c)]
        assert len(write_calls) == 1

    def test_turnoff_success(self, mock_pexpect):
        mock_mod, plugmini = mock_pexpect
        child = MagicMock()
        mock_mod.spawn.return_value = child

        child.expect.side_effect = [
            None,  # \[LE\]>
            1,     # \[CON\]
            None,  # char-desc
            None,  # \[LE\]>
            0,     # value match
            None,  # final \[LE\]>
        ]
        child.before = CHAR_DESC_BEFORE
        child.after = VALUE_OFF_RESPONSE

        result, data = plugmini.switchbotplugmini("AA:BB:CC:DD:EE:FF", "turnoff")
        assert result is True
        assert data == "0100"
        write_calls = [c for c in child.sendline.call_args_list
                       if "570f50010100" in str(c)]
        assert len(write_calls) == 1

    def test_toggle_success(self, mock_pexpect):
        mock_mod, plugmini = mock_pexpect
        child = MagicMock()
        mock_mod.spawn.return_value = child

        child.expect.side_effect = [
            None,  # \[LE\]>
            1,     # \[CON\]
            None,  # char-desc
            None,  # \[LE\]>
            0,     # value match
            None,  # final \[LE\]>
        ]
        child.before = CHAR_DESC_BEFORE
        child.after = VALUE_RESPONSE

        result, data = plugmini.switchbotplugmini("AA:BB:CC:DD:EE:FF", "toggle")
        assert result is True
        assert data == "0180"
        write_calls = [c for c in child.sendline.call_args_list
                       if "570f50010280" in str(c)]
        assert len(write_calls) == 1

    def test_readstate_success(self, mock_pexpect):
        mock_mod, plugmini = mock_pexpect
        child = MagicMock()
        mock_mod.spawn.return_value = child

        child.expect.side_effect = [
            None,  # \[LE\]>
            1,     # \[CON\]
            None,  # char-desc
            None,  # \[LE\]>
            0,     # value match
            None,  # final \[LE\]>
        ]
        child.before = CHAR_DESC_BEFORE
        child.after = VALUE_RESPONSE

        result, data = plugmini.switchbotplugmini("AA:BB:CC:DD:EE:FF", "readstate")
        assert result is True
        assert data == "0180"
        write_calls = [c for c in child.sendline.call_args_list
                       if "570f5101" in str(c)]
        assert len(write_calls) == 1

    def test_unsupported_operation(self, mock_pexpect):
        mock_mod, plugmini = mock_pexpect
        child = MagicMock()
        mock_mod.spawn.return_value = child

        child.expect.side_effect = [
            None,  # \[LE\]>
            1,     # \[CON\]
            None,  # char-desc
        ]
        child.before = CHAR_DESC_BEFORE

        result, data = plugmini.switchbotplugmini("AA:BB:CC:DD:EE:FF", "invalid_op")
        assert result is False
        assert data == "0000"

    def test_read_error_returns_0000(self, mock_pexpect):
        mock_mod, plugmini = mock_pexpect
        child = MagicMock()
        mock_mod.spawn.return_value = child

        child.expect.side_effect = [
            None,  # \[LE\]>
            1,     # \[CON\]
            None,  # char-desc
            None,  # \[LE\]> after write
            1,     # read error (Error index)
            None,  # final \[LE\]>
        ]
        child.before = CHAR_DESC_BEFORE

        result, data = plugmini.switchbotplugmini("AA:BB:CC:DD:EE:FF", "turnon")
        assert result is True
        assert data == "0000"

    def test_connection_retries_then_succeeds(self, mock_pexpect):
        mock_mod, plugmini = mock_pexpect
        child = MagicMock()
        mock_mod.spawn.return_value = child

        child.expect.side_effect = [
            None,  # \[LE\]>
            0,     # first connect attempt: Error
            1,     # second connect attempt: \[CON\] success
            None,  # char-desc
            None,  # \[LE\]> after write
            0,     # value match
            None,  # final \[LE\]>
        ]
        child.before = CHAR_DESC_BEFORE
        child.after = VALUE_RESPONSE

        result, data = plugmini.switchbotplugmini("AA:BB:CC:DD:EE:FF", "turnon")
        assert result is True

    def test_connection_successful_via_third_pattern(self, mock_pexpect):
        """Test connection via 'Connection successful.*[LE]>' pattern (index 2)."""
        mock_mod, plugmini = mock_pexpect
        child = MagicMock()
        mock_mod.spawn.return_value = child

        child.expect.side_effect = [
            None,  # \[LE\]>
            2,     # Connection successful pattern
            None,  # char-desc
            None,  # \[LE\]> after write
            0,     # value match
            None,  # final \[LE\]>
        ]
        child.before = CHAR_DESC_BEFORE
        child.after = VALUE_RESPONSE

        result, data = plugmini.switchbotplugmini("AA:BB:CC:DD:EE:FF", "turnon")
        assert result is True


class TestPlugMiniMain:
    def test_no_args_exits(self, mock_pexpect):
        _, plugmini = mock_pexpect
        with patch("sys.argv", ["switchbotplugmini.py"]):
            with pytest.raises(SystemExit) as exc_info:
                plugmini.main()
            assert exc_info.value.code == 1

    def test_main_success_on(self, mock_pexpect, capsys):
        _, plugmini = mock_pexpect
        with patch("sys.argv", ["switchbotplugmini.py", "AA:BB:CC:DD:EE:FF", "readstate"]):
            with patch.object(plugmini, "switchbotplugmini", return_value=(True, "0180")):
                with pytest.raises(SystemExit) as exc_info:
                    plugmini.main()
                assert exc_info.value.code == 0
                output = capsys.readouterr().out
                assert "on" in output

    def test_main_success_off(self, mock_pexpect, capsys):
        _, plugmini = mock_pexpect
        with patch("sys.argv", ["switchbotplugmini.py", "AA:BB:CC:DD:EE:FF", "readstate"]):
            with patch.object(plugmini, "switchbotplugmini", return_value=(True, "1000")):
                with pytest.raises(SystemExit) as exc_info:
                    plugmini.main()
                assert exc_info.value.code == 0
                output = capsys.readouterr().out
                assert "off" in output

    def test_main_success_other_code(self, mock_pexpect, capsys):
        _, plugmini = mock_pexpect
        with patch("sys.argv", ["switchbotplugmini.py", "AA:BB:CC:DD:EE:FF", "readstate"]):
            with patch.object(plugmini, "switchbotplugmini", return_value=(True, "abcd")):
                with pytest.raises(SystemExit) as exc_info:
                    plugmini.main()
                assert exc_info.value.code == 0
                output = capsys.readouterr().out
                assert "abcd" in output

    def test_main_failure(self, mock_pexpect, capsys):
        _, plugmini = mock_pexpect
        with patch("sys.argv", ["switchbotplugmini.py", "AA:BB:CC:DD:EE:FF", "turnon"]):
            with patch.object(plugmini, "switchbotplugmini", return_value=(False, "0000")):
                with pytest.raises(SystemExit) as exc_info:
                    plugmini.main()
                assert exc_info.value.code == 1
