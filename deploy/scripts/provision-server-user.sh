#!/usr/bin/env bash
set -Eeuo pipefail

if [[ "$EUID" -ne 0 ]]; then
  echo "run as root" >&2
  exit 77
fi

admin_public_key_file="${1:-}"
ci_public_key_file="${2:-}"
for key_file in "$admin_public_key_file" "$ci_public_key_file"; do
  if [[ ! -f "$key_file" ]]; then
    echo "missing public key file: $key_file" >&2
    exit 66
  fi
  ssh-keygen -l -f "$key_file" >/dev/null
done

if ! id garment >/dev/null 2>&1; then
  useradd --create-home --shell /bin/bash garment
fi

install -d -m 0700 -o garment -g garment /home/garment/.ssh
authorized_keys="$(mktemp)"
cat "$admin_public_key_file" "$ci_public_key_file" >"$authorized_keys"
sort -u "$authorized_keys" -o "$authorized_keys"
install -m 0600 -o garment -g garment "$authorized_keys" /home/garment/.ssh/authorized_keys
rm -f "$authorized_keys"

install -d -m 0750 -o garment -g garment /srv/garment-buro
install -d -m 0750 -o garment -g garment /srv/garment-buro/production
install -d -m 0750 -o garment -g garment /srv/garment-buro/development
install -d -m 0700 -o garment -g garment /srv/garment-buro/backups

for command_name in newuidmap newgidmap dockerd-rootless-setuptool.sh loginctl runuser; do
  if ! command -v "$command_name" >/dev/null 2>&1; then
    echo "missing rootless Docker prerequisite: $command_name" >&2
    echo "on Debian/Ubuntu install uidmap, dbus-user-session and docker-ce-rootless-extras" >&2
    exit 69
  fi
done

subuid_total="$(awk -F: '$1 == "garment" { total += $3 } END { print total + 0 }' /etc/subuid)"
subgid_total="$(awk -F: '$1 == "garment" { total += $3 } END { print total + 0 }' /etc/subgid)"
if (( subuid_total < 65536 || subgid_total < 65536 )); then
  echo "garment needs at least 65536 non-overlapping subordinate UIDs and GIDs" >&2
  echo "configure /etc/subuid and /etc/subgid, then rerun this script" >&2
  exit 78
fi

# Membership in the docker group would grant root-equivalent access to the
# system daemon. Garment Buro deployments must use the per-user rootless daemon.
if getent group docker >/dev/null 2>&1 \
  && id -nG garment | tr ' ' '\n' | grep -qx docker; then
  gpasswd --delete garment docker >/dev/null
fi

garment_uid="$(id -u garment)"
runtime_dir="/run/user/$garment_uid"
loginctl enable-linger garment
systemctl start "user@$garment_uid.service"

rootless_env=(
  env
  HOME=/home/garment
  USER=garment
  LOGNAME=garment
  XDG_RUNTIME_DIR="$runtime_dir"
  DBUS_SESSION_BUS_ADDRESS="unix:path=$runtime_dir/bus"
)

if [[ ! -f /home/garment/.config/systemd/user/docker.service ]]; then
  runuser --user garment -- "${rootless_env[@]}" \
    dockerd-rootless-setuptool.sh install --force
else
  runuser --user garment -- "${rootless_env[@]}" \
    systemctl --user enable --now docker.service
fi

runuser --user garment -- "${rootless_env[@]}" docker context use rootless >/dev/null
if ! runuser --user garment -- "${rootless_env[@]}" \
  docker info --format '{{json .SecurityOptions}}' | grep -q rootless; then
  echo "garment Docker daemon is not running in rootless mode" >&2
  exit 70
fi

echo "garment user, SSH keys, deployment directories and rootless Docker are ready"
