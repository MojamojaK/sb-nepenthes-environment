import pytest
from unittest.mock import patch, MagicMock


class _MockTimeoutException(Exception):
    pass


class _MockPexpectExceptions:
    TIMEOUT = _MockTimeoutException


@pytest.fixture
def mock_pexpect():
    mock = MagicMock()
    mock.exceptions = _MockPexpectExceptions()
    with patch.dict("sys.modules", {"pexpect": mock}):
        import importlib
        import drivers.switchbotbot
        importlib.reload(drivers.switchbotbot)
        yield mock, drivers.switchbotbot


# Simulates gatttool char-desc output
CHAR_DESC_BEFORE = b"some header\nhandle: 0x000e, char properties: 0x08, char value handle: 0x000f, uuid:"


class TestSwitchbotBot:
    def test_connection_error_returns_false(self, mock_pexpect):
        mock_mod, botmod = mock_pexpect
        child = MagicMock()
        mock_mod.spawn.return_value = child

        child.expect.side_effect = [
            None,           # \[LE\]>
            0, 0, 0,        # three retries, all return 0 (Error)
        ]

        result, data = botmod.switchbotbot("AA:BB:CC:DD:EE:FF", "turnon")
        assert result is False
        assert data == "0000"

    def test_connection_timeout_returns_false(self, mock_pexpect):
        mock_mod, botmod = mock_pexpect
        child = MagicMock()
        mock_mod.spawn.return_value = child

        child.expect.side_effect = [
            None,  # \[LE\]>
            3,     # timeout index
        ]

        result, data = botmod.switchbotbot("AA:BB:CC:DD:EE:FF", "turnon")
        assert result is False
        assert data == "0001"

    def test_turnon_success(self, mock_pexpect):
        mock_mod, botmod = mock_pexpect
        child = MagicMock()
        mock_mod.spawn.return_value = child

        child.expect.side_effect = [
            None,  # \[LE\]>
            1,     # \[CON\]
            None,  # char-desc
            None,  # \[LE\]> after write
        ]
        child.before = CHAR_DESC_BEFORE

        result, data = botmod.switchbotbot("AA:BB:CC:DD:EE:FF", "turnon")
        assert result is True
        assert data == ""
        write_calls = [c for c in child.sendline.call_args_list
                       if "570101" in str(c)]
        assert len(write_calls) == 1

    def test_turnoff_success(self, mock_pexpect):
        mock_mod, botmod = mock_pexpect
        child = MagicMock()
        mock_mod.spawn.return_value = child

        child.expect.side_effect = [
            None, 1, None, None,
        ]
        child.before = CHAR_DESC_BEFORE

        result, data = botmod.switchbotbot("AA:BB:CC:DD:EE:FF", "turnoff")
        assert result is True
        write_calls = [c for c in child.sendline.call_args_list
                       if "570102" in str(c)]
        assert len(write_calls) == 1

    def test_press_success(self, mock_pexpect):
        mock_mod, botmod = mock_pexpect
        child = MagicMock()
        mock_mod.spawn.return_value = child

        child.expect.side_effect = [
            None, 1, None, None,
        ]
        child.before = CHAR_DESC_BEFORE

        result, data = botmod.switchbotbot("AA:BB:CC:DD:EE:FF", "press")
        assert result is True
        write_calls = [c for c in child.sendline.call_args_list
                       if "570100" in str(c)]
        assert len(write_calls) == 1

    def test_down_success(self, mock_pexpect):
        mock_mod, botmod = mock_pexpect
        child = MagicMock()
        mock_mod.spawn.return_value = child

        child.expect.side_effect = [
            None, 1, None, None,
        ]
        child.before = CHAR_DESC_BEFORE

        result, data = botmod.switchbotbot("AA:BB:CC:DD:EE:FF", "down")
        assert result is True
        write_calls = [c for c in child.sendline.call_args_list
                       if "570103" in str(c)]
        assert len(write_calls) == 1

    def test_up_success(self, mock_pexpect):
        mock_mod, botmod = mock_pexpect
        child = MagicMock()
        mock_mod.spawn.return_value = child

        child.expect.side_effect = [
            None, 1, None, None,
        ]
        child.before = CHAR_DESC_BEFORE

        result, data = botmod.switchbotbot("AA:BB:CC:DD:EE:FF", "up")
        assert result is True
        write_calls = [c for c in child.sendline.call_args_list
                       if "570104" in str(c)]
        assert len(write_calls) == 1

    def test_unsupported_operation(self, mock_pexpect):
        mock_mod, botmod = mock_pexpect
        child = MagicMock()
        mock_mod.spawn.return_value = child

        child.expect.side_effect = [
            None,  # \[LE\]>
            1,     # \[CON\]
            None,  # char-desc
        ]
        child.before = CHAR_DESC_BEFORE

        result, data = botmod.switchbotbot("AA:BB:CC:DD:EE:FF", "invalid_op")
        assert result is False
        assert data == "0000"

    def test_connection_retries_then_succeeds(self, mock_pexpect):
        mock_mod, botmod = mock_pexpect
        child = MagicMock()
        mock_mod.spawn.return_value = child

        child.expect.side_effect = [
            None,  # \[LE\]>
            0,     # first attempt: Error
            1,     # second attempt: \[CON\]
            None,  # char-desc
            None,  # \[LE\]> after write
        ]
        child.before = CHAR_DESC_BEFORE

        result, data = botmod.switchbotbot("AA:BB:CC:DD:EE:FF", "press")
        assert result is True

    def test_connection_via_third_pattern(self, mock_pexpect):
        mock_mod, botmod = mock_pexpect
        child = MagicMock()
        mock_mod.spawn.return_value = child

        child.expect.side_effect = [
            None,  # \[LE\]>
            2,     # Connection successful pattern
            None,  # char-desc
            None,  # \[LE\]> after write
        ]
        child.before = CHAR_DESC_BEFORE

        result, data = botmod.switchbotbot("AA:BB:CC:DD:EE:FF", "turnon")
        assert result is True

    def test_spawns_with_random_flag(self, mock_pexpect):
        """switchbotbot uses '-t random' unlike plugmini."""
        mock_mod, botmod = mock_pexpect
        child = MagicMock()
        mock_mod.spawn.return_value = child

        child.expect.side_effect = [None, 3]  # timeout quickly

        botmod.switchbotbot("AA:BB:CC:DD:EE:FF", "turnon")
        spawn_cmd = mock_mod.spawn.call_args[0][0]
        assert "-t random" in spawn_cmd


class TestSwitchbotBotMain:
    def test_no_args_exits(self, mock_pexpect):
        _, botmod = mock_pexpect
        with patch("sys.argv", ["switchbotbot.py"]):
            with pytest.raises(SystemExit) as exc_info:
                botmod.main()
            assert exc_info.value.code == 1

    def test_main_success(self, mock_pexpect, capsys):
        _, botmod = mock_pexpect
        with patch("sys.argv", ["switchbotbot.py", "AA:BB:CC:DD:EE:FF", "press"]):
            with patch.object(botmod, "switchbotbot", return_value=(True, "")):
                with pytest.raises(SystemExit) as exc_info:
                    botmod.main()
                assert exc_info.value.code == 0

    def test_main_failure(self, mock_pexpect, capsys):
        _, botmod = mock_pexpect
        with patch("sys.argv", ["switchbotbot.py", "AA:BB:CC:DD:EE:FF", "turnon"]):
            with patch.object(botmod, "switchbotbot", return_value=(False, "0000")):
                with pytest.raises(SystemExit) as exc_info:
                    botmod.main()
                assert exc_info.value.code == 1
