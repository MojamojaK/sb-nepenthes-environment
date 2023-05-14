cooler_aliases = ["N. Peltier Upper", "N. Peltier Lower"]
heater_aliases = ["N. UV", "N. Heater"]
uv_aliases = ["N. UV"]
extfan_aliases = ["N. ExtFan"]
pump_alias = "N. Pump"
air_meter_aliases = ["N. Meter 1", "N. Meter 2"]
fogger_alias = "N. Fogger"

allowed_names = set(
    air_meter_aliases + cooler_aliases + heater_aliases + extfan_aliases
    + [fogger_alias, pump_alias]
)
