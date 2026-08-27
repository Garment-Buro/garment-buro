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

deployment_dir="/srv/garment-buro/$environment_name"
cd "$deployment_dir"

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
)

timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
backup_dir="/srv/garment-buro/backups/$environment_name/$timestamp"
mkdir -p "$backup_dir"
chmod 0700 "$backup_dir"

# The variables below expand inside the PostgreSQL container.
# shellcheck disable=SC2016
"${compose[@]}" exec -T postgres sh -ec \
  'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' \
  >"$backup_dir/postgresql.dump"

sqlite_tmp="/tmp/garment-buro-legacy-backup.sqlite3"
"${compose[@]}" exec -T backend python -c \
  'import sqlite3; source=sqlite3.connect("/app/legacy/ecommerce.db"); target=sqlite3.connect("/tmp/garment-buro-legacy-backup.sqlite3"); source.backup(target); target.close(); source.close()'
"${compose[@]}" cp "backend:$sqlite_tmp" "$backup_dir/ecommerce.sqlite3"
"${compose[@]}" exec -T backend rm -f "$sqlite_tmp"

"${compose[@]}" exec -T backend tar -C /app/uploads -czf - . \
  >"$backup_dir/legacy-uploads.tar.gz"
install -m 0600 .env "$backup_dir/deployment.env"
install -m 0600 .release "$backup_dir/release"
install -m 0600 docker-compose.yml "$backup_dir/docker-compose.yml"

(
  cd "$backup_dir"
  sha256sum postgresql.dump ecommerce.sqlite3 legacy-uploads.tar.gz >SHA256SUMS
)

printf '%s\n' "$backup_dir"
