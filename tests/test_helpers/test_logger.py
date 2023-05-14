import pytest
import os
import logging
from unittest.mock import patch, MagicMock
from helpers.logger import setup_logger, setup_data_logger, _raise_log_level


class TestSetupLogger:
    def test_returns_logger(self, tmp_path):
        with patch("helpers.logger.DATA_DIR", str(tmp_path)):
            logger = setup_logger("test_app")
            assert isinstance(logger, logging.Logger)
            assert logger.name == "test_app"

    def test_creates_log_file(self, tmp_path):
        with patch("helpers.logger.DATA_DIR", str(tmp_path)):
            logger = setup_logger("test_app")
            logger.info("test message")
            log_path = tmp_path / "test_app.log"
            assert log_path.exists()

    def test_has_file_and_stream_handlers(self, tmp_path):
        with patch("helpers.logger.DATA_DIR", str(tmp_path)):
            logger = setup_logger("test_app2")
            handler_types = [type(h).__name__ for h in logger.handlers]
            assert "TimedRotatingFileHandler" in handler_types
            assert "StreamHandler" in handler_types


    def test_debug_minutes_sets_debug_level(self, tmp_path):
        with patch("helpers.logger.DATA_DIR", str(tmp_path)), \
             patch("helpers.logger.threading") as mock_threading:
            logger = setup_logger("test_debug", debug_minutes=30)
            assert logger.level == logging.DEBUG
            mock_threading.Timer.assert_called_once()
            mock_threading.Timer.return_value.start.assert_called_once()

    def test_debug_minutes_zero_sets_info_level(self, tmp_path):
        with patch("helpers.logger.DATA_DIR", str(tmp_path)):
            logger = setup_logger("test_no_debug", debug_minutes=0)
            assert logger.level == logging.INFO


class TestRaiseLogLevel:
    def test_raises_to_info(self):
        logger = logging.getLogger("test_raise_level")
        logger.setLevel(logging.DEBUG)
        _raise_log_level(logger)
        assert logger.level == logging.INFO


class TestSetupDataLogger:
    def test_returns_logger(self, tmp_path):
        with patch("helpers.logger.DATA_DIR", str(tmp_path)):
            logger = setup_data_logger("test_app")
            assert isinstance(logger, logging.Logger)
            assert logger.name == "test_app.state"

    def test_does_not_propagate(self, tmp_path):
        with patch("helpers.logger.DATA_DIR", str(tmp_path)):
            logger = setup_data_logger("test_app")
            assert logger.propagate is False

    def test_creates_state_log_file(self, tmp_path):
        with patch("helpers.logger.DATA_DIR", str(tmp_path)):
            logger = setup_data_logger("test_app")
            logger.info("state dump")
            log_path = tmp_path / "test_app_state.log"
            assert log_path.exists()

    def test_only_file_handler(self, tmp_path):
        with patch("helpers.logger.DATA_DIR", str(tmp_path)):
            logger = setup_data_logger("test_app3")
            handler_types = [type(h).__name__ for h in logger.handlers]
            assert "TimedRotatingFileHandler" in handler_types
            assert "StreamHandler" not in handler_types
