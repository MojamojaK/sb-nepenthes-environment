import pytest
import os
from unittest.mock import patch

from config.env import _load_dotenv


class TestLoadDotenv:
    def test_loads_env_file(self, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text("TEST_LOAD_KEY=test_value\nOTHER_LOAD_KEY=other_value\n")
        with patch("config.env.PROJECT_ROOT", str(tmp_path)):
            with patch.dict(os.environ, {}, clear=False):
                _load_dotenv()
                assert os.environ.get("TEST_LOAD_KEY") == "test_value"
                assert os.environ.get("OTHER_LOAD_KEY") == "other_value"
        # Cleanup
        os.environ.pop("TEST_LOAD_KEY", None)
        os.environ.pop("OTHER_LOAD_KEY", None)

    def test_skips_comments(self, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text("# This is a comment\nCOMMENT_TEST_KEY=value\n")
        with patch("config.env.PROJECT_ROOT", str(tmp_path)):
            with patch.dict(os.environ, {}, clear=False):
                _load_dotenv()
                assert os.environ.get("COMMENT_TEST_KEY") == "value"
        os.environ.pop("COMMENT_TEST_KEY", None)

    def test_does_not_overwrite_existing(self, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text("EXISTING_ENV_KEY=from_file\n")
        with patch("config.env.PROJECT_ROOT", str(tmp_path)):
            with patch.dict(os.environ, {"EXISTING_ENV_KEY": "from_env"}, clear=False):
                _load_dotenv()
                assert os.environ["EXISTING_ENV_KEY"] == "from_env"

    def test_returns_early_when_no_env_file(self, tmp_path):
        """Covers line 9: early return when .env file does not exist."""
        with patch("config.env.PROJECT_ROOT", str(tmp_path)):
            # No .env file in tmp_path, so _load_dotenv should return early
            _load_dotenv()  # Should not raise

    def test_skips_empty_lines(self, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text("\n\nEMPTY_LINE_KEY=value\n\n")
        with patch("config.env.PROJECT_ROOT", str(tmp_path)):
            with patch.dict(os.environ, {}, clear=False):
                _load_dotenv()
                assert os.environ.get("EMPTY_LINE_KEY") == "value"
        os.environ.pop("EMPTY_LINE_KEY", None)
