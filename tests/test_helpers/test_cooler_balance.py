import json
import os
import pytest

from config.device_aliases import cooler_aliases
from helpers.cooler_balance import get_primary_cooler, rotate_primary_cooler


class TestGetPrimaryCooler:
    def test_returns_first_alias_when_no_file(self, tmp_path):
        state_path = str(tmp_path / "state.json")
        result = get_primary_cooler(state_path)
        assert result == cooler_aliases[0]

    def test_reads_known_primary_from_file(self, tmp_path):
        state_path = str(tmp_path / "state.json")
        for alias in cooler_aliases:
            with open(state_path, "w") as f:
                json.dump({"primary": alias}, f)
            assert get_primary_cooler(state_path) == alias

    def test_falls_back_on_invalid_json(self, tmp_path):
        state_path = str(tmp_path / "state.json")
        with open(state_path, "w") as f:
            f.write("not-json")
        assert get_primary_cooler(state_path) == cooler_aliases[0]

    def test_falls_back_on_unknown_alias(self, tmp_path):
        state_path = str(tmp_path / "state.json")
        with open(state_path, "w") as f:
            json.dump({"primary": "N. Unknown Device"}, f)
        assert get_primary_cooler(state_path) == cooler_aliases[0]

    def test_falls_back_when_primary_key_missing(self, tmp_path):
        state_path = str(tmp_path / "state.json")
        with open(state_path, "w") as f:
            json.dump({"other": "value"}, f)
        assert get_primary_cooler(state_path) == cooler_aliases[0]


class TestRotatePrimaryCooler:
    def test_rotates_to_next_alias(self, tmp_path):
        state_path = str(tmp_path / "state.json")
        with open(state_path, "w") as f:
            json.dump({"primary": cooler_aliases[0]}, f)
        rotate_primary_cooler(state_path)
        assert get_primary_cooler(state_path) == cooler_aliases[1]

    def test_wraps_around_to_first(self, tmp_path):
        state_path = str(tmp_path / "state.json")
        with open(state_path, "w") as f:
            json.dump({"primary": cooler_aliases[-1]}, f)
        rotate_primary_cooler(state_path)
        assert get_primary_cooler(state_path) == cooler_aliases[0]

    def test_creates_directory_if_missing(self, tmp_path):
        state_path = str(tmp_path / "subdir" / "state.json")
        rotate_primary_cooler(state_path)
        assert os.path.exists(state_path)

    def test_handles_write_error_gracefully(self, tmp_path):
        # Point at a path whose parent is actually a file so os.makedirs fails
        blocker = tmp_path / "blocker"
        blocker.write_text("file")
        state_path = str(blocker / "state.json")
        # Should not raise
        rotate_primary_cooler(state_path)

    def test_full_rotation_cycle(self, tmp_path):
        state_path = str(tmp_path / "state.json")
        seen = []
        for _ in range(len(cooler_aliases)):
            seen.append(get_primary_cooler(state_path))
            rotate_primary_cooler(state_path)
        # After a full cycle the primary returns to the first alias
        assert get_primary_cooler(state_path) == cooler_aliases[0]
        # Every alias appeared exactly once
        assert sorted(seen) == sorted(cooler_aliases)
