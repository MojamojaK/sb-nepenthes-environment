#!/bin/bash
# First-boot setup for nepenthes on a fresh Raspberry Pi OS Lite (trixie).
# Run once as root by cloud-init (runcmd in /boot/firmware/user-data).
# Expects the secrets and state files next to this script; deletes them when done.
# Staging the SD card is described in CLAUDE.md ("Fresh install").
set -euxo pipefail
exec >>/var/log/nepenthes-setup.log 2>&1
date

U=kazuki_fujita
H=/home/$U
S=/boot/firmware/nepenthes-setup
P=$H/bin/nepenthes
as_user() { runuser -l "$U" -c "$1"; }

# healthcheck/auto_update need sudo from cron (reboot, setcap, hciconfig)
echo "$U ALL=(ALL) NOPASSWD:ALL" >/etc/sudoers.d/010-$U-nopasswd
chmod 440 /etc/sudoers.d/010-$U-nopasswd
visudo -cf /etc/sudoers.d/010-$U-nopasswd

apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y git tmux libcap2-bin bluez libglib2.0-0t64 curl rfkill
usermod -aG bluetooth "$U"
# Fresh images ship with Bluetooth soft-blocked; systemd-rfkill keeps the unblock across reboots
rfkill unblock bluetooth

# AWS IoT cert/key/CA
install -d -m 700 -o "$U" -g "$U" "$H/.config"
install -m 600 -o "$U" -g "$U" "$S/N_home.cert.pem" "$S/N_home.private.key" "$S/root-CA.crt" "$H/.config/"

# uv + project (public repo, HTTPS, no GitHub key needed)
as_user 'curl -LsSf https://astral.sh/uv/install.sh | sh'
as_user "mkdir -p ~/bin && git clone https://github.com/MojamojaK/sb-nepenthes-environment.git $P"
install -m 600 -o "$U" -g "$U" "$S/.env" "$P/.env"
install -d -o "$U" -g "$U" "$P/data"
install -m 644 -o "$U" -g "$U" "$S"/data/*.json "$P/data/"
as_user "cd $P && UV_NO_DEV=1 ~/.local/bin/uv sync"
setcap cap_net_raw,cap_net_admin+eip "$(find "$P/.venv" -name bluepy-helper)"
getcap "$(find "$P/.venv" -name bluepy-helper)"

# Fresh heartbeat so the first healthcheck runs give nepenthes a few minutes before judging it stale
as_user "echo '{\"timestamp\": \"'\$(date +%Y-%m-%dT%H:%M:%S.%6N)'\"}' > $P/data/heartbeat.json"

# Cron takes over from here: healthcheck starts nepenthes in tmux within a minute
as_user 'crontab -' <<'EOF'
PATH=/home/kazuki_fujita/.local/bin:/usr/local/bin:/usr/bin:/bin
UV_NO_DEV=1
UV_NO_SYNC=1
* * * * * cd ~/bin/nepenthes && uv run healthcheck.py
*/30 * * * * cd ~/bin/nepenthes && uv run auto_update.py
EOF

# Secrets no longer needed on the FAT boot partition
rm -rf "$S"
echo "NEPENTHES SETUP DONE"
date
