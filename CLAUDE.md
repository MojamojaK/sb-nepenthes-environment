# CLAUDE.md

## Project overview

BLE-based environment controller for Nepenthes (tropical pitcher plants) running on a Raspberry Pi Zero W. Reads SwitchBot Meter/Plug Mini devices via Bluetooth, evaluates conditions, and toggles plugs.

## Commands

### Install dependencies
```
uv sync
```

### Run tests
```
uv run pytest
```

### Run tests with HTML coverage report
```
uv run pytest --cov-report=html
```

## Architecture

- `evaluators/` — Pure-logic modules that inspect device data and annotate it (e.g. validity checks, overload detection, heartbeat decisions). Each evaluator exposes a `task(data)` function.
- `executors/` — Side-effect modules that act on evaluated data (BLE toggle, MQTT publish, heartbeat file write). Each exposes a `task(data)` function.
- `config/` — Static configuration (device aliases, desired states, thresholds).
- `drivers/` — Low-level BLE and SwitchBot API drivers.
- `helpers/` — Small utilities (deep_update, etc.).
- `nepenthes.py` — Main entry point; runs the evaluate → execute pipeline.
- `tests/` — pytest test suite. Uses `uv run pytest` (not bare `pytest` or `python -m pytest`).
