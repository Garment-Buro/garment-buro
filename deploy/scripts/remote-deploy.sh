#!/usr/bin/env bash
set -Eeuo pipefail
umask 027

environment_name="${1:-}"
backend_image="${2:-}"
frontend_image="${3:-}"

case "$environment_name" in
  production|development) ;;
  *)
    echo "environment must be production or development" >&2
    exit 64
    ;;
esac

if [[ -z "$backend_image" || -z "$frontend_image" ]]; then
  echo "backend and frontend image references are required" >&2
  exit 64
fi

deployment_dir="/srv/garment-buro/$environment_name"
cd "$deployment_dir"

if ! docker info --format '{{json .SecurityOptions}}' | grep -q rootless; then
  echo "deployment must use the garment rootless Docker daemon" >&2
  exit 77
fi

if [[ ! -f .env ]]; then
  echo "missing $deployment_dir/.env" >&2
  exit 78
fi
if grep -q "replace-with-" .env; then
  echo "placeholder values remain in $deployment_dir/.env" >&2
  exit 78
fi
if [[ ! -f legacy/ecommerce.db ]]; then
  echo "missing reviewed legacy database at $deployment_dir/legacy/ecommerce.db" >&2
  exit 78
fi

env_mode="$(stat -c '%a' .env)"
if (( (8#$env_mode & 077) != 0 )); then
  echo ".env must not be readable by group or other users" >&2
  exit 77
fi

if [[ -f docker-compose.next.yml ]]; then
  mv docker-compose.next.yml docker-compose.yml
fi
if [[ -f remote-deploy.next.sh ]]; then
  mv remote-deploy.next.sh remote-deploy.sh
  chmod 0750 remote-deploy.sh
fi
if [[ -f backup-server.next.sh ]]; then
  mv backup-server.next.sh backup-server.sh
  chmod 0750 backup-server.sh
fi

export DEPLOY_ENV="$environment_name"
export BACKEND_IMAGE="$backend_image"
export FRONTEND_IMAGE="$frontend_image"

compose=(
  docker compose
  --project-name "garment-buro-$environment_name"
  --env-file .env
  -f docker-compose.yml
)

"${compose[@]}" config --quiet
"${compose[@]}" pull
"${compose[@]}" up -d --wait --wait-timeout 180 postgres redis minio
"${compose[@]}" run --rm minio-init
"${compose[@]}" run --rm migrate
"${compose[@]}" up -d --remove-orphans

wait_for_url() {
  local label="$1"
  local url="$2"
  local attempts=45
  local index
  for ((index = 1; index <= attempts; index += 1)); do
    if curl --fail --silent --show-error --max-time 5 "$url" >/dev/null; then
      return 0
    fi
    sleep 2
  done
  echo "$label health check failed: $url" >&2
  return 1
}

rollback() {
  if [[ ! -f .release ]]; then
    echo "No previous release is available for image rollback" >&2
    return 1
  fi
  # shellcheck disable=SC1091
  source .release
  if [[ -z "${BACKEND_IMAGE:-}" || -z "${FRONTEND_IMAGE:-}" ]]; then
    echo "Previous release metadata is incomplete" >&2
    return 1
  fi
  export BACKEND_IMAGE FRONTEND_IMAGE
  "${compose[@]}" up -d --remove-orphans
}

frontend_port="$(sed -n 's/^FRONTEND_HOST_PORT=//p' .env | tail -n 1)"
backend_port="$(sed -n 's/^BACKEND_HOST_PORT=//p' .env | tail -n 1)"
if [[ ! "$frontend_port" =~ ^[0-9]+$ || ! "$backend_port" =~ ^[0-9]+$ ]]; then
  echo "invalid frontend/backend host port in .env" >&2
  exit 78
fi

if ! wait_for_url "backend" "http://127.0.0.1:$backend_port/health/ready" \
  || ! wait_for_url "frontend" "http://127.0.0.1:$frontend_port/"; then
  rollback || true
  exit 1
fi

release_tmp="$(mktemp .release.XXXXXX)"
{
  printf 'BACKEND_IMAGE=%q\n' "$backend_image"
  printf 'FRONTEND_IMAGE=%q\n' "$frontend_image"
  printf 'DEPLOYED_AT=%q\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
} >"$release_tmp"
chmod 0640 "$release_tmp"
mv "$release_tmp" .release

"${compose[@]}" ps
curl --fail --silent --show-error "http://127.0.0.1:$backend_port/health/ready"
printf '\nDeployed %s\n' "$environment_name"
