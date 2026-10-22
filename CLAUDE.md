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

## Raspberry Pi maintenance

See README.md for initial setup.

Before changing anything, `git fetch` and compare with what the Pi runs (`ssh pi0 'cd ~/bin/nepenthes && git log --oneline -1'`). The Pi tracks `origin/main`, and a local clone can be far behind it.

### The Pi

- SSH alias: `pi0` (192.168.176.15), user `kazuki_fujita`, key auth (`~/.ssh/id_ed25519`). Use `ssh -o BatchMode=yes pi0 ...` so a broken key fails fast instead of hanging on a password prompt.
- Raspberry Pi Zero W: armv6l, 429 MB RAM, Raspbian 11 (bullseye), system Python 3.9. Everything is slow.
- Passwordless sudo is available.
- The project lives at `~/bin/nepenthes`. nepenthes runs in tmux session `nep-session` (`uv run nepenthes.py`); it is not a systemd service.
- Cron (`crontab -l`): `healthcheck.py` every minute, `auto_update.py` every 30 minutes.
- The "post-quantum key exchange" SSH warning is expected: bullseye ships OpenSSH 8.4. Only an OS release upgrade (bookworm+) removes it; patching does not.

### Things that reboot the Pi

Anything long-running on the Pi (apt upgrades, compiling wheels) can be killed mid-way by these:

- **healthcheck.py** reboots when the heartbeat is stale (with backoff 3/5/10/30/60 min, see `data/reboot_history.json`). It also runs `uv sync` + `setcap` when it (re)starts nepenthes.
- **auto_update.py** pulls `origin/main` and reboots when there are new commits. So pushing to `main` deploys to the Pi and reboots it within 30 minutes.

**Before any maintenance, enable maintenance mode on the Pi's working copy only** (do not commit it):

```
ssh pi0 'cd ~/bin/nepenthes && sed -i "s/^MAINTANECE_MODE = False$/MAINTANECE_MODE = True/" healthcheck.py'
# ...maintenance...
ssh pi0 'cd ~/bin/nepenthes && git checkout healthcheck.py'
```

Restore it before pushing anything to `main`, otherwise `auto_update`'s `git pull` may conflict on `healthcheck.py`.

### OS patching

Run apt detached with `nohup` so a dropped SSH session (e.g. openssh-server restarting) cannot kill it, and keep existing config files:

```
ssh pi0 'nohup sh -c "sudo apt-get update && sudo apt-get -y -o Dpkg::Options::=--force-confdef -o Dpkg::Options::=--force-confold upgrade; echo EXIT=\$?" </dev/null > ~/apt-upgrade.log 2>&1 &'
```

Poll for `^EXIT=` in the log. ~130 packages took well over 30 minutes.

If dpkg was interrupted (e.g. by a reboot):

```
sudo dpkg --configure -a --force-confold
sudo apt-get -y --fix-broken install    # needed when half-unpacked packages have mismatched deps
sudo apt-get -y upgrade
```

Verify: `apt list --upgradable` is empty, `sudo apt-get check` is clean, and check `/var/run/reboot-required` (only a kernel/firmware update needs a reboot).

### Python dependencies

- `uv` resolves from PyPI only (it ignores the piwheels entry in `/etc/pip.conf`). PyPI has no armv6l wheels for `awscrt`, so the Pi **compiles awscrt from source** whenever its version changes. That takes a long time and lots of memory.
- `awsiotsdk` pins an exact `awscrt` version (e.g. 1.31.0 -> `awscrt==0.36.1`).

To upgrade:

1. Locally: `uv lock --upgrade && uv sync && uv run pytest`.
2. With maintenance mode on, pre-build on the Pi in a scratch copy so the live `.venv` is untouched and the built wheel lands in the shared uv cache:
   ```
   ssh pi0 'mkdir -p ~/nep-prebuild'
   scp pyproject.toml uv.lock pi0:nep-prebuild/
   ssh pi0 'cd ~/nep-prebuild && nohup sh -c "export PATH=\$HOME/.local/bin:\$PATH CMAKE_BUILD_PARALLEL_LEVEL=1; uv sync --frozen --no-dev --no-install-project; echo EXIT=\$?" </dev/null > ~/awscrt-build.log 2>&1 &'
   ```
   `CMAKE_BUILD_PARALLEL_LEVEL=1` avoids running out of RAM.
3. Commit and push `uv.lock` (ask the user first). `auto_update` pulls and reboots. On restart, healthcheck runs `uv sync` (fast, from the cache) and re-applies `setcap` to `bluepy-helper`.
4. Delete `~/nep-prebuild` and turn maintenance mode off.

### Heartbeat / reboot loops

The heartbeat (`evaluators/heartbeat.py`) needs **every plug** to be `Valid` with a successful toggle, and **at least one meter** to be `Valid`. An invalid meter is tolerated because the cooler/heater and fogger logic fall back to the remaining valid meters (max temperature, min humidity). If the heartbeat goes stale, healthcheck reboots the Pi every ~60 minutes. To find the culprit, look at the last JSON block in `data/nepenthes_state.log` for a device with `"Valid": false` and no `Datetime`/`BatteryVoltage`. Usually it is a flat battery or a device out of BLE range.

### Security

- **OS end of life:** bullseye (Debian 11) lost security support on 2026-08-31, and the Raspbian repo stopped updating 2026-09-04. `apt upgrade` will not bring new security fixes. The fix is a fresh install of a current Raspberry Pi OS, not an in-place patch.
- **Dev dependencies stay off the Pi:** crontab sets `UV_NO_DEV=1`, so `uv run`/`uv sync` skip the dev group (pytest etc.). Dependabot alerts with `scope: development` therefore don't affect the Pi.
- **Secrets:** `.env` and the AWS IoT key/cert in `~/.config/` should be mode 600.
- **SSH:** key-only (`/etc/ssh/sshd_config.d/10-hardening.conf`: `PasswordAuthentication no`, `PermitRootLogin no`).
- To audit: `uv export --frozen --all-groups --no-hashes --no-emit-project -o req.txt && uvx pip-audit -r req.txt --no-deps --disable-pip`. pip-audit evaluates environment markers for the *local* Python, so also audit the Python 3.9-only pins (e.g. pytest 8.4.2) explicitly. For code, run `uvx bandit -r . -x ./.venv,./tests,./htmlcov`.
