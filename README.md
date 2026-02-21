# Nepenthes Environment Controller

BLE-based environment monitoring and control system for Nepenthes (tropical pitcher plants), running on a Raspberry Pi Zero W. Reads SwitchBot Meter and Plug Mini devices via Bluetooth, evaluates conditions, and toggles plugs to maintain optimal growing conditions.

## Setup

> Note: Everything is SLOW on Raspberry Pi Zero. Feel free to run setup commands in `tmux` to avoid cancellations due to timeouts.

### 1. System Dependencies

```
sudo apt install libglib2.0-dev libusb-dev libdbus-1-dev libcap2-bin tmux git cmake  libbluetooth-dev libboost-python-dev libboost-thread-dev  python3-gattlib
sudo usermod -G bluetooth -a $(whoami)
sudo reboot
```

### 2. Clone and Install

```
git clone https://github.com/MojamojaK/sb-nepenthes-environment.git ~/bin/nepenthes
cd ~/bin/nepenthes
```

Install [uv](https://docs.astral.sh/uv/getting-started/installation/) and sync dependencies:
```
curl -LsSf https://astral.sh/uv/install.sh | sh
uv sync
```

Grant BLE permissions to the `bluepy-helper` binary so it can control the Bluetooth adapter without root:
```
sudo setcap cap_net_raw,cap_net_admin+eip $(find .venv -name bluepy-helper)
```

> Note: Re-run this after every `uv sync` that reinstalls `bluepy`.

### 3. AWS IoT Certificates

Create a Thing and generate certificates in the [AWS IoT Console](https://docs.aws.amazon.com/iot/latest/developerguide/device-certs-create.html), then place them on the Pi (e.g. in `~/certs/`):
- `cert.pem` — device certificate
- `private.key` — private key
- `root-CA.crt` — Amazon root CA

These are referenced by `MQTT_CERT_PATH`, `MQTT_KEY_PATH`, and `MQTT_CA_PATH` in `.env`.

### 4. Environment Variables

```
cp .env.example .env
```

Edit `.env` with your deployment values:

| Variable | Description |
|---|---|
| `MQTT_ENDPOINT` | AWS IoT [device data endpoint](https://docs.aws.amazon.com/iot/latest/developerguide/iot-connect-service.html) (find in IoT Console > Settings, or run `aws iot describe-endpoint --endpoint-type iot:Data-ATS`) |
| `MQTT_PORT` | MQTT port (default: 8883) |
| `MQTT_CLIENT_ID` | MQTT client ID |
| `MQTT_TOPIC` | MQTT publish topic |
| `MQTT_CERT_PATH` | Path to device certificate from step 3 |
| `MQTT_KEY_PATH` | Path to private key from step 3 |
| `MQTT_CA_PATH` | Path to root CA from step 3 |
| `SB_TOKEN` | [SwitchBot API](https://github.com/OpenWonderLabs/SwitchBotAPI#getting-started) token (find in SwitchBot app > Profile > Preferences > Developer Options) |
| `SB_SECRET_KEY` | SwitchBot API secret key (same location as token) |
| `NEPENTHES_SCRIPT_PATH` | Absolute path to nepenthes.py (e.g. `~/bin/nepenthes/nepenthes.py`) |
| `BT_INTERFACE` | Bluetooth adapter (default: hci0) |

### 5. Cron Jobs

```
crontab -e
```

Add the following entries (adjust the `PATH` to include the directory where `uv` is installed):
```
PATH=/home/<YOUR_USERNAME>/.local/bin:/usr/local/bin:/usr/bin:/bin
* * * * * cd ~/bin/nepenthes && uv run healthcheck.py
*/30 * * * * cd ~/bin/nepenthes && uv run auto_update.py
```

- **healthcheck** runs every minute — starts nepenthes if it's not running, reboots if heartbeat is stale
- **auto_update** runs every 30 minutes — pulls from `origin/main` and reboots if there are changes

## Related Repository: [nepenthes-cdk](https://github.com/MojamojaK/nepenthes-cdk)

This repo is the **device-side application** that runs on a Raspberry Pi Zero W. It has a companion repo, [`nepenthes-cdk`](https://github.com/MojamojaK/nepenthes-cdk), which contains the **cloud-side infrastructure** deployed via AWS CDK. Together they form the full Nepenthes monitoring and control system.

### How they connect

```
┌─────────────────────────────────┐          ┌──────────────────────────────────────┐
│   Raspberry Pi  (this repo)     │          │   AWS Cloud  (nepenthes-cdk)         │
│                                 │          │                                      │
│  BLE scan ─► evaluate ─► toggle │  MQTT    │  IoT Core ─► Lambda (log puller)     │
│         │                       │ ──────►  │       │                               │
│         └─► log_push ───────────│──────────│───────┘  ─► CloudWatch metrics       │
│                                 │          │          ─► CloudWatch alarms         │
│  healthcheck (cron, 1 min)      │          │          ─► SNS ─► Pushover / email   │
│  auto_update  (cron, 30 min)    │          │                                      │
│                                 │          │  EventBridge (2 min) ─► Lambda        │
│                                 │          │    └─► SwitchBot API plug status      │
│                                 │          │                                      │
│                                 │          │  CloudWatch alarm ─► Lambda           │
│                                 │          │    └─► SwitchBot API: power on Pi     │
└─────────────────────────────────┘          └──────────────────────────────────────┘
```

### Integration points

| Touchpoint | This repo (device) | nepenthes-cdk (cloud) |
|---|---|---|
| **MQTT telemetry** | `executors/log_push.py` publishes device state JSON to AWS IoT Core via MQTT (topic configured by `MQTT_TOPIC`) | IoT topic rule on `log/nepenthes/nhome` triggers the `nepenthes_log_puller` Lambda, which extracts metrics and pushes them to CloudWatch |
| **Heartbeat** | `evaluators/heartbeat.py` decides whether all devices are healthy; `executors/heartbeat.py` writes a local heartbeat file; the heartbeat flag is included in the MQTT payload | Cloud-side CloudWatch alarm on the Heartbeat metric fires if no heartbeat is received, triggering the `nepenthes_pi_plug_on` Lambda to power-cycle the Pi via SwitchBot API |
| **SwitchBot API credentials** | `SB_TOKEN` / `SB_SECRET_KEY` used to discover device MAC addresses and toggle plugs via BLE + HTTP API | Same credentials used by `nepenthes_online_plug_status` and `nepenthes_pi_plug_on` Lambdas to check plug power and power-cycle the Pi remotely |
| **Device naming** | Device aliases like `N. Meter 1`, `N. Meter 2`, `N. Peltier Upper`, etc. are defined in `config/desired_states.py` and `config/device_aliases.py` | The same device names appear in `lib/constants.ts` as CloudWatch metric dimensions and alarm targets |
| **Monitoring & alerting** | Reads sensors and controls plugs locally; pushes raw state to the cloud | Processes telemetry into CloudWatch metrics/alarms for temperature, humidity, battery, and plug power; sends alerts via Pushover and email through SNS |

## Development

### Testing

Run the test suite (coverage report is included by default):
```
uv sync
uv run pytest
```

To generate an HTML coverage report:
```
uv run pytest --cov-report=html
open htmlcov/index.html
```

Note: `bluepy` is a Linux-only dependency and will not be installed on macOS. The test suite mocks it automatically.

### Logs

Log files are stored in the `data/` directory, rotating hourly and keeping 3 files each.

| File | Contents |
|---|---|
| `nepenthes.log` | Main operational log (BLE errors, device toggles, heartbeat status, evaluator decisions) |
| `nepenthes_state.log` | Full device state JSON dump each scan cycle |
| `healthcheck.log` | Healthcheck and reboot backoff activity |
| `auto_update.log` | Git pull and update activity |

To tail logs in real time:
```
tail -f data/nepenthes.log
tail -f data/nepenthes_state.log
```
