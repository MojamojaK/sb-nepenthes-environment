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
- Raspberry Pi Zero W (Rev 1.1, not Zero 2 W): armv6l, 429 MB RAM. Hostname `nepenthes`. Raspberry Pi OS Lite 32-bit, Debian 13 (trixie), system Python 3.13. Everything is slow.
- Installed fresh on 2026-10-27 (see "Fresh install"). The previous SD card (Raspbian 11 bullseye) is kept as a rollback.
- Passwordless sudo is available (`/etc/sudoers.d/010-kazuki_fujita-nopasswd`).
- The project lives at `~/bin/nepenthes`, cloned over HTTPS (the repo is public, so the Pi has no GitHub key). nepenthes runs in tmux session `nep-session` (`uv run nepenthes.py`); it is not a systemd service.
- Cron (`crontab -l`): `healthcheck.py` every minute, `auto_update.py` every 30 minutes.
- Network: NetworkManager, static `192.168.176.15/24` set via cloud-init `network-config` on the boot partition.

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

- PyPI has no armv6l wheels for `awscrt` or `bluepy`, so `pyproject.toml` takes both from **piwheels on armv6l only** (`[tool.uv.sources]`). `awscrt` is a direct dependency only so that override applies. Without it the Pi compiles awscrt from source (75+ minutes).
- `awsiotsdk` pins an exact `awscrt` version (e.g. 1.31.0 -> `awscrt==0.36.1`). Before upgrading, check piwheels has a wheel for the new version and the Pi's Python: `https://www.piwheels.org/project/awscrt/`.
- piwheels' armv6l wheels are tagged `linux_armv7l` inside (built on ARMv7, runs fine on the Zero). uv sees the installed packages as mismatched and reinstalls them on every `uv run`, so cron sets `UV_NO_SYNC=1`. healthcheck still runs `uv sync` before it starts nepenthes. `uv sync --dry-run` on the Pi always shows `~ awscrt` / `~ bluepy`; that is expected.
- `bluepy-helper` is hard-linked from the uv cache, so `setcap` survives these reinstalls.

To upgrade:

1. Locally: `uv lock --upgrade && uv sync && uv run pytest`. Check `uv.lock` lists a piwheels `linux_armv6l` wheel for the Pi's Python (cp313) for `awscrt` and `bluepy`.
2. Optionally test on the Pi in a scratch dir (live `.venv` untouched): `scp pyproject.toml uv.lock pi0:nep-test/` then `ssh pi0 'cd nep-test && ~/.local/bin/uv sync --frozen --no-dev --no-install-project'`. It should take seconds and build nothing.
3. Commit and push `uv.lock` (ask the user first). `auto_update` pulls and reboots. On restart, healthcheck runs `uv sync` and re-applies `setcap` to `bluepy-helper`.

### Heartbeat / reboot loops

The heartbeat (`evaluators/heartbeat.py`) needs **every plug** to be `Valid` with a successful toggle, and **at least one meter** to be `Valid`. An invalid meter is tolerated because the cooler/heater and fogger logic fall back to the remaining valid meters (max temperature, min humidity). If the heartbeat goes stale, healthcheck reboots the Pi every ~60 minutes. To find the culprit, look at the last JSON block in `data/nepenthes_state.log` for a device with `"Valid": false` and no `Datetime`/`BatteryVoltage`. Usually it is a flat battery or a device out of BLE range.

### Fresh install

How the Pi was set up on 2026-10-27. Downtime was ~30 minutes, and nothing had to be typed on the Pi.

1. **Flash** a new SD card with Raspberry Pi Imager: device "Raspberry Pi Zero", OS "Raspberry Pi OS Lite (32-bit)" (64-bit will not boot on armv6). Customisation: hostname `nepenthes`, user `kazuki_fujita`, Wi-Fi with country JP, timezone `Asia/Tokyo`, SSH public-key only with the Mac's `~/.ssh/id_ed25519.pub`.
2. **Static IP:** with the card mounted on the Mac (`/Volumes/bootfs`), edit `network-config` so `wlan0` has `dhcp4: false`, `addresses: [192.168.176.15/24]`, `routes: [{to: default, via: 192.168.176.1}]`, `nameservers: {addresses: [192.168.176.1, 1.1.1.1]}`. Never print this file: it holds the Wi-Fi password.
3. **Stage the setup** on the boot partition, copying secrets straight from the running Pi (no copy left on the Mac):
   ```
   D=/Volumes/bootfs/nepenthes-setup; mkdir -p $D/data
   cp pi-setup/firstboot.sh $D/setup.sh
   scp pi0:bin/nepenthes/.env pi0:.config/N_home.cert.pem pi0:.config/N_home.private.key pi0:.config/root-CA.crt $D/
   scp pi0:bin/nepenthes/data/{device_config,cooler_balance_state,cooler_frozen_state}.json $D/data/
   ```
   Then append `  - [ bash, /boot/firmware/nepenthes-setup/setup.sh ]` to `runcmd:` in `user-data`, and eject.
4. **Cut over:** `ssh pi0 sudo shutdown -h now`, swap cards, power on, and `ssh-keygen -R 192.168.176.15`. SSH comes up ~10 minutes after power-on. The setup takes ~5 more and logs to `/var/log/nepenthes-setup.log` (ends with `NEPENTHES SETUP DONE`). It deletes `nepenthes-setup/` from the boot partition when done.
5. **Verify:** `data/heartbeat.json` updates, every device in `data/nepenthes_state.log` is `Valid`, `data/log_push.json` updates (MQTT). Then do a reboot test.

`pi-setup/firstboot.sh` handles two traps from the 2026-10-27 install:
- **Bluetooth is RF-kill soft-blocked on a fresh image.** `hciconfig hci0` shows `DOWN`, every scan fails with `scanend ... Rejected`, no device is ever valid, and healthcheck reboot-loops. Fix: `sudo rfkill unblock bluetooth` (persists across reboots).
- **`UV_NO_SYNC=1` in cron** (see "Python dependencies").

The script also makes the journal persistent (`/etc/systemd/journald.conf.d/50-persistent.conf`: at most 100 MB, at least 2 GB kept free, entries older than a month deleted, synced every minute). Raspberry Pi OS keeps it in RAM by default, which hides the cause of unexpected reboots.

Rollback: power off and put the old card back.

### Unexpected reboots

healthcheck logs `Rebooting...` and auto_update logs `Rebooting after update...` before they reboot. If neither did, check:

- `journalctl -b -1 -n 50`: the last messages before the reset. A log that just stops means a power cut or a hang (systemd runs the 1-minute hardware watchdog).
- `vcgencmd get_throttled`: anything other than `0x0` means under-voltage or throttling since boot.
- The cloud side (`nepenthes-cdk`, AWS us-west-2) power-cycles the Pi through its SwitchBot plug when the heartbeat alarm fires. Check the logs of the `NPiPlugOnLambda` function and `aws cloudwatch describe-alarm-history`.

The Pi has no hardware clock. After an unclean reboot it starts from the last saved time and jumps at the NTP sync, so log timestamps from the two boots can overlap.

### Security

- **OS:** trixie (Debian 13) is supported. When a Debian release reaches end of life, do a fresh install (see "Fresh install") rather than an in-place release upgrade.
- **Dev dependencies stay off the Pi:** crontab sets `UV_NO_DEV=1`, so `uv run`/`uv sync` skip the dev group (pytest etc.). Dependabot alerts with `scope: development` therefore don't affect the Pi.
- **Secrets:** `.env` and the AWS IoT key/cert in `~/.config/` should be mode 600.
- **SSH:** key-only. Raspberry Pi Imager sets `ssh_pwauth: false`; root has no password or key.
- **GitHub:** the Pi has no GitHub credentials. It pulls the public repo over HTTPS.
- To audit: `uv export --frozen --all-groups --no-hashes --no-emit-project -o req.txt && uvx pip-audit -r req.txt --no-deps --disable-pip`. pip-audit evaluates environment markers for the *local* Python, so also audit the Python 3.9-only pins (e.g. pytest 8.4.2) explicitly. For code, run `uvx bandit -r . -x ./.venv,./tests,./htmlcov`.
