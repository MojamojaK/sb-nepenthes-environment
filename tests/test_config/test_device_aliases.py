import pytest
from config.device_aliases import (
    cooler_aliases, heater_aliases, uv_aliases, extfan_aliases,
    pump_alias, air_meter_aliases, fogger_alias, allowed_names,
)


class TestDeviceAliases:
    def test_cooler_aliases_are_list(self):
        assert isinstance(cooler_aliases, list)
        assert len(cooler_aliases) > 0

    def test_heater_aliases_are_list(self):
        assert isinstance(heater_aliases, list)
        assert len(heater_aliases) > 0

    def test_uv_is_subset_of_heater(self):
        for alias in uv_aliases:
            assert alias in heater_aliases

    def test_pump_alias_is_string(self):
        assert isinstance(pump_alias, str)

    def test_fogger_alias_is_string(self):
        assert isinstance(fogger_alias, str)


class TestAllowedNames:
    def test_is_a_set(self):
        assert isinstance(allowed_names, set)

    def test_contains_all_aliases(self):
        all_aliases = (
            air_meter_aliases + cooler_aliases + heater_aliases
            + extfan_aliases + [fogger_alias, pump_alias]
        )
        for alias in all_aliases:
            assert alias in allowed_names

    def test_no_extra_entries(self):
        all_aliases = set(
            air_meter_aliases + cooler_aliases + heater_aliases
            + extfan_aliases + [fogger_alias, pump_alias]
        )
        assert allowed_names == all_aliases
