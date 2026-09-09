#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

environment_name="${1:-}"
backend_image="${2:-}"
frontend_image="${3:-}"
revision="${4:-}"
case "$environment_name" in production|development) ;; *) exit 64 ;; esac
[[ "$revision" =~ ^[a-f0-9]{40}$ ]] || exit 64
[[ "$backend_image" == "ghcr.io/garment-buro/garment-buro-backend:$environment_name-$revision" ]] || exit 64
[[ "$frontend_image" == "ghcr.io/garment-buro/garment-buro-frontend:$environment_name-$revision" ]] || exit 64
cd "/srv/garment-buro/$environment_name"
# Both environments share one small host; serialize cutovers across workflows.
exec 9>/srv/garment-buro/.deploy.lock
flock -w 1200 9
docker info --format '{{json .SecurityOptions}}' | grep -q rootless || exit 77
[[ -f .env && -s legacy/ecommerce.db && -f docker-compose.next.yml ]] || exit 78
env_mode="$(stat -c '%a' .env)"
(( (8#$env_mode & 077) == 0 )) || exit 77
if grep -q 'replace-with-' .env; then echo 'Unconfigured environment' >&2; exit 78; fi

enabled() { grep -Eiq "^${1}=(true|1|yes|on)$" .env; }
profiles=()
workers=()
add_worker() { if enabled "$1"; then profiles+=(--profile "$2"); workers+=("$3"); fi; }
add_worker IDENTITY_API_ENABLED notifications notification-worker
add_worker PAYMENT_WEBHOOK_V2_ENABLED payments payment-worker
add_worker PAYMENT_RECONCILIATION_ENABLED payment-reconciliation payment-reconciler
add_worker FULFILLMENT_OUTBOX_ENABLED fulfillment fulfillment-worker
add_worker CDEK_CREATION_ENABLED cdek cdek-worker
if enabled PAYMENT_CREATION_ENABLED && enabled PAYMENT_MANAGEMENT_ENABLED; then
  profiles+=(--profile order-workflows)
  workers+=(order-workflow-worker)
fi

export DEPLOY_ENV="$environment_name" BACKEND_IMAGE="$backend_image" FRONTEND_IMAGE="$frontend_image"
compose=(docker compose --project-name "garment-buro-$environment_name" --env-file .env -f docker-compose.next.yml "${profiles[@]}")
"${compose[@]}" config --quiet
# Do not upgrade databases or re-seed legacy uploads during an application release.
docker pull "$backend_image"
docker pull "$frontend_image"
timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
backup_dir="/srv/garment-buro/backups/$environment_name/$timestamp"
mkdir -p "$backup_dir"
chmod 0700 "$backup_dir"
for file in .env .release docker-compose.yml; do
  [[ ! -f "$file" ]] || install -m 0600 "$file" "$backup_dir/$(basename "$file")"
done
if [[ -f .release && -f docker-compose.yml ]]; then
  # The existing release (not the candidate) defines the volumes being backed up.
  bash backup-server.next.sh "$environment_name"
else
  echo 'Existing deployment metadata required; bootstrap is a separate operation' >&2
  exit 78
fi

switched=false
rollback() {
  local code=$?
  trap - ERR
  if [[ "$switched" == true && -f "$backup_dir/.release" ]]; then
    echo 'Release failed; restoring previous application images' >&2
    # Database downgrade is intentionally never automatic.
    source "$backup_dir/.release"
    export BACKEND_IMAGE FRONTEND_IMAGE
    install -m 0600 "$backup_dir/docker-compose.yml" docker-compose.yml
    docker compose --project-name "garment-buro-$environment_name" --env-file .env \
      -f docker-compose.yml "${profiles[@]}" up -d --no-deps --pull never backend frontend "${workers[@]}" || true
  fi
  echo "Release failed. Recovery metadata: $backup_dir" >&2
  exit "$code"
}
trap rollback ERR

"${compose[@]}" run --rm --no-deps database-role-init
"${compose[@]}" run --rm --no-deps migrate
switched=true
"${compose[@]}" up -d --no-deps --pull never --wait --wait-timeout 180 backend frontend "${workers[@]}"

frontend_port="$(sed -n 's/^FRONTEND_HOST_PORT=//p' .env | tail -n 1)"
backend_port="$(sed -n 's/^BACKEND_HOST_PORT=//p' .env | tail -n 1)"
health_address="$(sed -n 's/^HOST_BIND_ADDRESS=//p' .env | tail -n 1)"
health_address="${health_address:-127.0.0.1}"
[[ "$frontend_port" =~ ^[0-9]+$ && "$backend_port" =~ ^[0-9]+$ ]] || exit 78
[[ "$health_address" =~ ^[0-9]{1,3}(\.[0-9]{1,3}){3}$ ]] || exit 78
curl --fail --silent --show-error --retry 10 --retry-delay 3 --retry-connrefused "http://$health_address:$backend_port/health/ready"
for path in / /production /production/admin /partner; do
  curl --fail --silent --show-error --retry 5 --retry-delay 2 --retry-connrefused \
    "http://$health_address:$frontend_port$path" -o /dev/null
done
# Atomically record only a healthy release. No application secrets in this file.
release_tmp="$(mktemp .release.XXXXXX)"
printf 'BACKEND_IMAGE=%q\nFRONTEND_IMAGE=%q\nSOURCE_REVISION=%q\nDEPLOYED_AT=%q\n' \
  "$backend_image" "$frontend_image" "$revision" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >"$release_tmp"
install -m 0600 docker-compose.next.yml docker-compose.yml
mv "$release_tmp" .release
install -m 0750 backup-server.next.sh backup-server.sh
echo "Deployed $environment_name revision $revision"
