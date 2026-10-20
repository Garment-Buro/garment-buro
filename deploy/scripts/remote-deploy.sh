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
deployment_root="${GARMENT_DEPLOY_ROOT:-/srv/garment-buro}"
cd "$deployment_root/$environment_name"
# Both environments share one small host; serialize cutovers across workflows.
exec 9>"$deployment_root/.deploy.lock"
flock -w 1200 9
docker info --format '{{json .SecurityOptions}}' | grep -q rootless || exit 77
[[ -f .env && -f docker-compose.next.yml && -f verify-backup.next.py && -f public-maintenance.next.py ]] || exit 78
env_mode="$(stat -c '%a' .env)"
(( (8#$env_mode & 077) == 0 )) || exit 77
if grep -q 'replace-with-' .env; then echo 'Unconfigured environment' >&2; exit 78; fi

enabled() { grep -Eiq "^${1}=(true|1|yes|on)$" .env; }
profiles=()
workers=()
add_worker() { if enabled "$1"; then profiles+=(--profile "$2"); workers+=("$3"); fi; }
add_worker IDENTITY_API_ENABLED notifications notification-worker
add_worker IDENTITY_API_ENABLED project-media project-media-worker
add_worker PAYMENT_WEBHOOK_V2_ENABLED payments payment-worker
add_worker PAYMENT_RECONCILIATION_ENABLED payment-reconciliation payment-reconciler
add_worker FULFILLMENT_OUTBOX_ENABLED fulfillment fulfillment-worker
add_worker CDEK_CREATION_ENABLED cdek cdek-worker
if enabled PAYMENT_CREATION_ENABLED && enabled PAYMENT_MANAGEMENT_ENABLED; then
  profiles+=(--profile order-workflows)
  workers+=(order-workflow-worker)
fi

export DEPLOY_ENV="$environment_name" BACKEND_IMAGE="$backend_image" FRONTEND_IMAGE="$frontend_image"
compose=(docker compose --project-name "garment-buro-$environment_name" --env-file .env -f docker-compose.next.yml)
if (( ${#profiles[@]} )); then compose+=("${profiles[@]}"); fi
"${compose[@]}" config --quiet
# Storage is built and installed separately. Fail before pulling applications,
# pausing writers or taking a backup when this host lacks the selected image.
storage_image="$("${compose[@]}" config --images minio)"
if [[ -z "$storage_image" || "$storage_image" == *$'\n'* ]]; then
  echo 'Exactly one prepared MinIO image is required before release' >&2
  exit 78
fi
if ! docker image inspect --format '{{.Id}}' "$storage_image" >/dev/null 2>&1; then
  echo 'Prepare the verified MinIO image on this host before release' >&2
  exit 78
fi
# An unprepared public proxy must fail before backups or application changes.
# The dedicated Nginx endpoint cannot be satisfied by a healthy application.
python3 public-maintenance.next.py "$environment_name" check-open
# Pull immutable application images; PostgreSQL/Redis/MinIO versions and volumes
# are managed separately from this application cutover.
docker pull "$backend_image"
docker pull "$frontend_image"
timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
backup_parent="$deployment_root/backups/$environment_name"
mkdir -p "$backup_parent"
backup_dir="$(mktemp -d "$backup_parent/$timestamp.release.XXXXXX")"
chmod 0700 "$backup_dir"
for file in .env .release docker-compose.yml; do
  [[ ! -f "$file" ]] || install -m 0600 "$file" "$backup_dir/$(basename "$file")"
done
if [[ ! -f .release || ! -f docker-compose.yml ]]; then
  echo 'Existing deployment metadata required; bootstrap is a separate operation' >&2
  exit 78
fi

previous_compose=(docker compose --project-name "garment-buro-$environment_name" --env-file .env -f docker-compose.yml --profile '*')
previous_running="$("${previous_compose[@]}" ps --services --status running)"
previous_available="$("${previous_compose[@]}" config --services)"
previous_workers=()
previous_applications=()
for unstable_status in restarting paused; do
  unstable_services="$("${previous_compose[@]}" ps --services --status "$unstable_status")"
  if [[ -n "$unstable_services" ]]; then
    echo 'Resolve restarting or paused services before release' >&2
    exit 78
  fi
done
while IFS= read -r service; do
  if [[ -n "$service" ]] && ! grep -Fxq "$service" <<< "$previous_available"; then
    echo 'Resolve orphaned services before release' >&2
    exit 78
  fi
  case "$service" in
    backend|frontend) previous_applications+=("$service") ;;
    notification-worker|project-media-worker|payment-worker|payment-reconciler|fulfillment-worker|cdek-worker|order-workflow-worker)
      previous_workers+=("$service")
      ;;
    postgres|redis|minio|'') ;;
    *)
      echo 'Stop unrecognised application writers or active setup jobs before release' >&2
      exit 78
      ;;
  esac
done <<< "$previous_running"

# Validate probe addresses before changing any running application containers.
frontend_port="$(sed -n 's/^FRONTEND_HOST_PORT=//p' .env | tail -n 1)"
backend_port="$(sed -n 's/^BACKEND_HOST_PORT=//p' .env | tail -n 1)"
health_address="$(sed -n 's/^HOST_BIND_ADDRESS=//p' .env | tail -n 1)"
health_address="${health_address:-127.0.0.1}"
[[ "$frontend_port" =~ ^[0-9]+$ && "$backend_port" =~ ^[0-9]+$ ]] || exit 78
[[ "$health_address" =~ ^[0-9]{1,3}(\.[0-9]{1,3}){3}$ ]] || exit 78

switched=false
workers_paused=false
applications_paused=false
candidate_workers_started=false
migration_attempted=false
maintenance_closed=false
deployment_committed=false
maintenance_owner="$revision-$(python3 -c 'import secrets; print(secrets.token_hex(16))')"
migration_container="garment-buro-$environment_name-migrate-$revision"
recovery_probe="garment-buro-$environment_name-schema-check-$revision"
migration_barrier="garment-buro-$environment_name-migration-idle-$revision"
rollback() {
  local code="${1:-$?}"
  trap - ERR INT TERM
  if [[ "$deployment_committed" == true ]]; then
    # Removing the gate is the write-acceptance boundary. A partial public
    # reopening may already have accepted orders; keep the committed runtime.
    echo "Release recorded, but public reopening failed; keep candidate images and maintenance for manual recovery: $backup_dir" >&2
    exit "$code"
  fi
  if [[ ( "$switched" == true || "$workers_paused" == true || "$applications_paused" == true || "$migration_attempted" == true ) && -f "$backup_dir/.release" ]]; then
    echo 'Release failed; restoring previous application images' >&2
    # A new cleanup worker must never run beside an older API that does not
    # coordinate its media locks. Stop candidate workers before restoring apps.
    if [[ "$candidate_workers_started" == true ]] && (( ${#workers[@]} )); then
      if ! "${compose[@]}" stop --timeout 60 "${workers[@]}"; then
        echo "Rollback failed to stop candidate workers; manual recovery required: $backup_dir" >&2
        exit "$code"
      fi
    fi
    if [[ "$switched" == true ]]; then
      # Drain the candidate HTTP processes before any older process resumes.
      # This also keeps a formerly stopped app stopped during recovery.
      if ! "${compose[@]}" stop --timeout 60 frontend backend; then
        echo "Rollback failed to stop candidate applications; manual recovery required: $backup_dir" >&2
        exit "$code"
      fi
      install -m 0600 "$backup_dir/docker-compose.yml" docker-compose.yml
      install -m 0600 "$backup_dir/.release" .release
    fi
    if [[ "$migration_attempted" == true ]]; then
      # An interrupted Compose client does not prove its one-shot container
      # stopped. End this release's exact migration process before any old API
      # or worker can resume. Never stop another release or infrastructure.
      if ! leftover_migration="$(docker ps -a --filter "name=^/$migration_container$" --format '{{.Names}}')"; then
        echo "Cannot verify migration termination; manual recovery required: $backup_dir" >&2
        exit "$code"
      fi
      if [[ -n "$leftover_migration" ]]; then
        if [[ "$leftover_migration" != "$migration_container" ]] || ! docker rm --force "$migration_container" >/dev/null; then
          echo "Cannot stop migration container; manual recovery required: $backup_dir" >&2
          exit "$code"
        fi
      fi
      # Killing a Docker client can leave its PostgreSQL transaction running.
      # Use the candidate's lock protocol before inspecting the old revision.
      # The previous image need not know this protocol or this helper module.
      if ! timeout 60 "${compose[@]}" run --rm --no-deps --pull never \
        --name "$migration_barrier" --entrypoint python migrate \
        -m scripts.wait_for_migration >/dev/null 2>&1; then
        docker rm --force "$migration_barrier" >/dev/null 2>&1 || true
        echo "Cannot confirm PostgreSQL migration completion; applications and workers remain stopped; manual recovery required: $backup_dir" >&2
        exit "$code"
      fi
    fi
    # Database downgrade is intentionally never automatic.
    source "$backup_dir/.release"
    export BACKEND_IMAGE FRONTEND_IMAGE
    if [[ "$migration_attempted" == true ]] && (( ${#previous_applications[@]} + ${#previous_workers[@]} )); then
      # The previous image must accept the actual revision, including after a
      # failed or interrupted migration. This command only reads Alembic state;
      # it starts neither the old ASGI application nor its background workers.
      # Older/missing Alembic support, timeouts and DB errors fail closed.
      if ! timeout 60 "${previous_compose[@]}" run --rm --no-deps --pull never \
        --name "$recovery_probe" --entrypoint python backend \
        -m alembic -c alembic.ini current --check-heads >/dev/null 2>&1; then
        # A timed-out Docker client may leave its read-only probe running.
        docker rm --force "$recovery_probe" >/dev/null 2>&1 || true
        echo "Previous backend did not accept the database schema; applications and workers remain stopped; manual recovery required: $backup_dir" >&2
        exit "$code"
      fi
    fi
    if (( ${#previous_applications[@]} )); then
      if [[ "$switched" == true ]]; then
        if ! "${previous_compose[@]}" up -d --no-deps --pull never --wait --wait-timeout 180 "${previous_applications[@]}"; then
          echo "Rollback failed to restore previous applications; manual recovery required: $backup_dir" >&2
          exit "$code"
        fi
      elif [[ "$applications_paused" == true ]] && ! "${previous_compose[@]}" up -d --no-deps --no-recreate --pull never --wait --wait-timeout 180 "${previous_applications[@]}"; then
        # Candidate apps have not been created; preserve the original images
        # and environment rather than recreating from the current .env.
        echo "Rollback failed to restore previous applications; manual recovery required: $backup_dir" >&2
        exit "$code"
      fi
    fi
    if (( ${#previous_workers[@]} )); then
      if [[ "$candidate_workers_started" == true ]]; then
        if ! "${previous_compose[@]}" up -d --no-deps --pull never --wait --wait-timeout 180 "${previous_workers[@]}"; then
          echo "Rollback failed to restore previous workers; manual recovery required: $backup_dir" >&2
          exit "$code"
        fi
      elif ! "${previous_compose[@]}" up -d --no-deps --no-recreate --pull never --wait --wait-timeout 180 "${previous_workers[@]}"; then
        # No candidate worker was created; retain the paused containers' exact
        # image and environment instead of recreating them from candidate flags.
        echo "Rollback failed to restore previous workers; manual recovery required: $backup_dir" >&2
        exit "$code"
      fi
    fi
  fi
  if [[ "$maintenance_closed" == true ]]; then
    # Healthcheck success alone does not prove the resumed HTTP process works.
    if (( ${#previous_applications[@]} )); then
      for service in "${previous_applications[@]}"; do
        if [[ "$service" == backend ]]; then
          recovery_url="http://$health_address:$backend_port/health/ready"
        else
          recovery_url="http://$health_address:$frontend_port/"
        fi
        if ! curl --fail --silent --show-error --max-time 30 "$recovery_url" -o /dev/null; then
          echo "Previous application HTTP probe failed; maintenance remains active; manual recovery required: $backup_dir" >&2
          exit "$code"
        fi
      done
    fi
    if ! python3 public-maintenance.next.py "$environment_name" open --owner "$maintenance_owner"; then
      echo "Public reopening failed; maintenance remains active; manual recovery required: $backup_dir" >&2
      exit "$code"
    fi
  fi
  echo "Release failed. Recovery metadata: $backup_dir" >&2
  exit "$code"
}
trap rollback ERR
trap 'rollback 130' INT
trap 'rollback 143' TERM

# Establish and verify a continuous public maintenance window before pausing
# any writer. Every configured public origin must see this environment's 503.
maintenance_closed=true
python3 public-maintenance.next.py "$environment_name" close --owner "$maintenance_owner"

# Reconcile running workers, including those disabled by the candidate flags.
# Mark the pause first: a partially failed stop must restore the previous set.
if (( ${#previous_workers[@]} )); then
  workers_paused=true
  "${previous_compose[@]}" stop --timeout 60 "${previous_workers[@]}"
fi
# An older API must not read or write the schema while it is being migrated.
# Record the pause before stop so a partial stop also resumes the exact set.
if (( ${#previous_applications[@]} )); then
  applications_paused=true
  "${previous_compose[@]}" stop --timeout 60 "${previous_applications[@]}"
fi
require_stopped_writers() {
  local running service
  running="$("${previous_compose[@]}" ps --services --status running)"
  while IFS= read -r service; do
    case "$service" in
      postgres|redis|minio|'') ;;
      *) echo 'Application writers remain active; refusing release' >&2; return 78 ;;
    esac
  done <<< "$running"
}
require_stopped_writers

# The parent owns application recovery from this point. The regular backup sees
# only infrastructure running, so it resumes MinIO but never these writers.
# Keep this maintenance window continuous through backup, setup and migration.
# The existing release (not the candidate) defines the volumes being archived.
storage_backup_dir="$(bash backup-server.next.sh "$environment_name")"
[[ "$storage_backup_dir" == "$deployment_root/backups/$environment_name/"* ]] || rollback 78
python3 verify-backup.next.py "$storage_backup_dir"
printf '%s\n' "$storage_backup_dir" >"$backup_dir/storage-backup.path"

# Initialize new buckets and the runtime role after the archive is complete.
timeout 120 "${compose[@]}" run --rm --no-deps minio-init
"${compose[@]}" run --rm --no-deps database-role-init
require_stopped_writers
migration_attempted=true
"${compose[@]}" run --rm --no-deps --name "$migration_container" migrate
switched=true
"${compose[@]}" up -d --no-deps --pull never --wait --wait-timeout 180 backend frontend

curl --fail --silent --show-error --retry 10 --retry-delay 3 --retry-connrefused "http://$health_address:$backend_port/health/ready"
for path in / /production /production/admin /partner; do
  curl --fail --silent --show-error --retry 5 --retry-delay 2 --retry-connrefused \
    "http://$health_address:$frontend_port$path" -o /dev/null
done
# New workers may perform irreversible provider actions. Start only the selected
# set after the candidate API and frontend have passed their HTTP probes.
if (( ${#workers[@]} )); then
  candidate_workers_started=true
  "${compose[@]}" up -d --no-deps --pull never --wait --wait-timeout 180 "${workers[@]}"
fi
# Atomically record only a healthy release. No application secrets in this file.
release_tmp="$(mktemp .release.XXXXXX)"
printf 'BACKEND_IMAGE=%q\nFRONTEND_IMAGE=%q\nSOURCE_REVISION=%q\nDEPLOYED_AT=%q\n' \
  "$backend_image" "$frontend_image" "$revision" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >"$release_tmp"
install -m 0600 docker-compose.next.yml docker-compose.yml
mv "$release_tmp" .release
install -m 0750 backup-server.next.sh backup-server.sh
install -m 0750 verify-backup.next.py verify-backup.py
install -m 0750 public-maintenance.next.py public-maintenance.py
# Commit before allowing public writes. An opening error must not trigger an
# automatic application rollback after any route might have accepted an order.
deployment_committed=true
python3 public-maintenance.next.py "$environment_name" open --owner "$maintenance_owner"
maintenance_closed=false
echo "Deployed $environment_name revision $revision"
