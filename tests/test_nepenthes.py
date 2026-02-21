from unittest.mock import patch

import pytest

import nepenthes


class TestRun:
    @patch("nepenthes.main")
    def test_normal_exit_does_not_log_exception(self, mock_main):
        with patch.object(nepenthes.logger, "exception") as mock_log:
            nepenthes.run()
            mock_log.assert_not_called()

    @patch("nepenthes.main", side_effect=RuntimeError("something broke"))
    def test_fatal_crash_is_logged(self, mock_main):
        with patch.object(nepenthes.logger, "exception") as mock_log:
            with pytest.raises(RuntimeError, match="something broke"):
                nepenthes.run()
            mock_log.assert_called_once_with("Fatal crash")

    @patch("nepenthes.main", side_effect=RuntimeError("something broke"))
    def test_fatal_crash_is_reraised(self, mock_main):
        with patch.object(nepenthes.logger, "exception"):
            with pytest.raises(RuntimeError, match="something broke"):
                nepenthes.run()
