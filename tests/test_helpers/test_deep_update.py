import pytest
from helpers.deep_update import deep_update


class TestDeepUpdate:
    def test_flat_merge(self):
        assert deep_update({"a": 1}, {"b": 2}) == {"a": 1, "b": 2}

    def test_overwrite_value(self):
        assert deep_update({"a": 1}, {"a": 2}) == {"a": 2}

    def test_nested_merge(self):
        base = {"a": {"x": 1, "y": 2}}
        update = {"a": {"y": 3, "z": 4}}
        result = deep_update(base, update)
        assert result == {"a": {"x": 1, "y": 3, "z": 4}}

    def test_deeply_nested(self):
        base = {"a": {"b": {"c": 1}}}
        update = {"a": {"b": {"d": 2}}}
        result = deep_update(base, update)
        assert result == {"a": {"b": {"c": 1, "d": 2}}}

    def test_empty_update(self):
        assert deep_update({"a": 1}, {}) == {"a": 1}

    def test_empty_base(self):
        assert deep_update({}, {"a": 1}) == {"a": 1}

    def test_both_empty(self):
        assert deep_update({}, {}) == {}

    def test_overwrite_dict_with_scalar(self):
        result = deep_update({"a": {"nested": 1}}, {"a": "scalar"})
        assert result == {"a": "scalar"}

    def test_overwrite_scalar_with_dict(self):
        result = deep_update({"a": "scalar"}, {"a": {"nested": 1}})
        assert result == {"a": {"nested": 1}}

    def test_returns_new_dict(self):
        base = {"a": {"x": 1}}
        update = {"a": {"y": 2}}
        result = deep_update(base, update)
        # deep_update returns a shallow copy at the top level
        assert result is not base
        assert result == {"a": {"x": 1, "y": 2}}
