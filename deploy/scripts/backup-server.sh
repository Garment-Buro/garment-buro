#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

environment_name="${1:-}"
case "$environment_name" in
  production|development) ;;
  *)
    echo "environment must be production or development" >&2
    exit 64
    ;;
esac

deployment_root="${GARMENT_DEPLOY_ROOT:-/srv/garment-buro}"
deployment_dir="$deployment_root/$environment_name"
cd "$deployment_dir"

# A deployment passes descriptor 9 to its child backup. Reuse that same open
# file description; reopening the lock would deadlock against our parent.
if ! python3 -c '
import os, sys
try:
    matches = os.path.samestat(os.fstat(9), os.stat(sys.argv[1]))
except OSError:
    matches = False
sys.exit(0 if matches else 1)
' "$deployment_root/.deploy.lock"; then
  exec 9>"$deployment_root/.deploy.lock"
fi
flock -w 1200 9

if ! docker info --format '{{json .SecurityOptions}}' | grep -q rootless; then
  echo "backup must use the garment rootless Docker daemon" >&2
  exit 77
fi

if [[ ! -f .release || ! -f .env || ! -f docker-compose.yml ]]; then
  echo "deployment metadata is incomplete in $deployment_dir" >&2
  exit 78
fi

# shellcheck disable=SC1091
source .release
export DEPLOY_ENV="$environment_name"
export BACKEND_IMAGE FRONTEND_IMAGE

compose=(
  docker compose
  --project-name "garment-buro-$environment_name"
  --env-file .env
  -f docker-compose.yml
  --profile '*'
)

previous_running="$("${compose[@]}" ps --services --status running)"
available_services="$("${compose[@]}" config --services)"
for unstable_status in restarting paused; do
  unstable_services="$("${compose[@]}" ps --services --status "$unstable_status")"
  if [[ -n "$unstable_services" ]]; then
    echo 'Resolve restarting or paused services before backup' >&2
    exit 78
  fi
done
writers=()
for required in postgres minio; do
  grep -Fxq "$required" <<<"$previous_running" || {
    echo 'PostgreSQL and MinIO must be running before backup' >&2
    exit 78
  }
done
while IFS= read -r service; do
  if [[ -n "$service" ]] && ! grep -Fxq "$service" <<<"$available_services"; then
    echo 'Resolve orphaned services before backup' >&2
    exit 78
  fi
  case "$service" in
    postgres|redis|minio|'') ;;
    migrate|database-role-init|minio-init)
      echo 'Wait for active deployment setup jobs before backup' >&2
      exit 78
      ;;
    *) writers+=("$service") ;;
  esac
done <<<"$previous_running"
backend_container="$("${compose[@]}" ps -q --all backend)"
minio_container="$("${compose[@]}" ps -q minio)"
[[ -n "$backend_container" && -n "$minio_container" ]] || exit 78

timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
backup_parent="$deployment_root/backups/$environment_name"
mkdir -p "$backup_parent"
# A manual backup may overlap a deploy or another manual invocation. Never
# replace a completed bundle merely because both started in the same second.
backup_dir="$(mktemp -d "$backup_parent/$timestamp.XXXXXX")"
chmod 0700 "$backup_dir"

needs_resume=false
resume_and_exit() {
  local code=$?
  trap - EXIT INT TERM
  if [[ "$needs_resume" == true ]]; then
    # Compose start follows dependencies and can rerun completed setup jobs.
    # Resume the saved containers without dependencies, recreation or pulls.
    if ! "${compose[@]}" up -d --no-deps --no-recreate --pull never --wait --wait-timeout 180 minio >&2; then
      echo "Backup storage restart failed; manual recovery required: $backup_dir" >&2
      exit 1
    fi
    if (( ${#writers[@]} )); then
      if ! "${compose[@]}" up -d --no-deps --no-recreate --pull never --wait --wait-timeout 180 "${writers[@]}" >&2; then
        echo "Backup application restart failed; manual recovery required: $backup_dir" >&2
        exit 1
      fi
    fi
  fi
  if (( code == 0 )); then printf '%s\n' "$backup_dir"; fi
  exit "$code"
}
trap resume_and_exit EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

# Quiesce deployment-managed writers before storage, including custom services
# and workers in disabled Compose profiles that happen to be running. MinIO is
# stopped as well so direct storage traffic and internal housekeeping cannot
# mutate its volume while it is archived. PostgreSQL stays up for pg_dump.
needs_resume=true
if (( ${#writers[@]} )); then
  "${compose[@]}" stop --timeout 60 "${writers[@]}" >&2
fi
"${compose[@]}" stop --timeout 60 minio >&2
storage_state="$(docker inspect --format '{{.State.Running}} {{.State.ExitCode}} {{.State.OOMKilled}}' "$minio_container")"
if [[ "$storage_state" != 'false 0 false' ]]; then
  echo 'MinIO did not stop cleanly; refusing storage backup' >&2
  exit 78
fi
remaining_running="$("${compose[@]}" ps --services --status running)"
while IFS= read -r service; do
  case "$service" in
    postgres|redis|'') ;;
    *) echo 'Application writers remain active; refusing backup' >&2; exit 78 ;;
  esac
done <<<"$remaining_running"

# Legacy data is supported only in the previous release's mounted volumes.
# A helper can read these while the API remains stopped; mounts are read-only
# and there is no network access or application entrypoint.
legacy_python() {
  docker run --rm --user 0:0 --network none --volumes-from "$backend_container:ro" \
    --entrypoint python "$BACKEND_IMAGE" "$@"
}

# The variables below expand inside the PostgreSQL container.
# shellcheck disable=SC2016
"${compose[@]}" exec -T postgres sh -ec \
  'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' \
  >"$backup_dir/postgresql.dump"
test -s "$backup_dir/postgresql.dump"
"${compose[@]}" exec -T postgres pg_restore --list <"$backup_dir/postgresql.dump" >/dev/null

# The previous release may still have SQLite/uploads mounted. Archive them
# during the transition, but do not require or create them in a modern release.
# A failed exec or unreadable/corrupt source must fail the backup, not be treated
# as an absent legacy file.
archives=(postgresql.dump)
legacy_database_present="$(legacy_python -c '
from pathlib import Path
source = Path("/app/legacy/ecommerce.db")
print("present" if source.exists() else "absent")
')"
if [[ "$legacy_database_present" == present ]]; then
  legacy_python -c '
import shutil
import sqlite3
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
with TemporaryDirectory() as directory:
    target = Path(directory) / "legacy.sqlite3"
    with sqlite3.connect("file:/app/legacy/ecommerce.db?mode=ro", uri=True) as source:
        with sqlite3.connect(target) as destination:
            source.backup(destination)
    with target.open("rb") as archive:
        shutil.copyfileobj(archive, sys.stdout.buffer)
' >"$backup_dir/ecommerce.sqlite3"
  test -s "$backup_dir/ecommerce.sqlite3"
  archives+=(ecommerce.sqlite3)
elif [[ "$legacy_database_present" != absent ]]; then
  echo 'Unexpected legacy database archive result' >&2
  exit 78
fi

legacy_uploads_present="$(legacy_python -c '
from pathlib import Path
uploads = Path("/app/uploads")
if uploads.exists() and not uploads.is_dir():
    raise RuntimeError("Legacy uploads path is not a directory")
print("present" if uploads.exists() else "absent")
')"
if [[ "$legacy_uploads_present" == present ]]; then
  docker run --rm --user 0:0 --network none --volumes-from "$backend_container:ro" \
    --entrypoint tar "$BACKEND_IMAGE" -C /app/uploads -czf - . \
    >"$backup_dir/legacy-uploads.tar.gz"
  gzip -t "$backup_dir/legacy-uploads.tar.gz"
  archives+=(legacy-uploads.tar.gz)
elif [[ "$legacy_uploads_present" != absent ]]; then
  echo 'Unexpected legacy uploads archive result' >&2
  exit 78
fi
install -m 0600 .env "$backup_dir/deployment.env"
install -m 0600 .release "$backup_dir/release"
install -m 0600 docker-compose.yml "$backup_dir/docker-compose.yml"
archives+=(deployment.env release docker-compose.yml)

# Preserve public media and private production originals, not only legacy uploads.
docker run --rm --user 0:0 --network none --volumes-from "$minio_container:ro" \
  --entrypoint tar "$BACKEND_IMAGE" -C /data -czf - . >"$backup_dir/minio-data.tar.gz"
gzip -t "$backup_dir/minio-data.tar.gz"
archives+=(minio-data.tar.gz)

(
  cd "$backup_dir"
  sha256sum "${archives[@]}" >.SHA256SUMS.tmp
  sha256sum --check .SHA256SUMS.tmp >/dev/null
  mv .SHA256SUMS.tmp SHA256SUMS
)

# The EXIT handler resumes storage/applications before returning this path.
