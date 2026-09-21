#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

environment_name="${1:-}"
case "$environment_name" in production|development) ;; *) exit 64 ;; esac

target="/srv/garment-buro/$environment_name"
cd "$target"
[[ -s .release && -s docker-compose.yml && -s .env ]] || exit 78

# Keep a manual demo seed away from either environment's release cutover.
exec 9>/srv/garment-buro/.deploy.lock
flock -w 1200 9

# The release file contains shell-escaped immutable image references only.
# shellcheck disable=SC1091
source .release
export DEPLOY_ENV="$environment_name" BACKEND_IMAGE FRONTEND_IMAGE

private_dir="$target/private"
install -d -m 0700 "$private_dir"
runtime_dir="$(mktemp -d "$target/.demo-seed.XXXXXX")"
trap 'rm -rf "$runtime_dir"' EXIT

curl --fail --silent --show-error --location --max-time 60 --retry 3 \
  https://garment-buro.ru/nikitamoiseev/hoodie-front.png \
  -o "$runtime_dir/reference.png"
test -s "$runtime_dir/reference.png"

compose=(
  docker compose
  --project-name "garment-buro-$environment_name"
  --env-file .env
  -f docker-compose.yml
)
"${compose[@]}" config --quiet
"${compose[@]}" run --rm --no-deps --user 0:0 \
  -v "$runtime_dir/reference.png:/run/demo-reference.png:ro" \
  -v "$private_dir:/run/private" \
  backend python -m scripts.seed_production_demo \
  --confirm-demo \
  --credentials-file /run/private/production-demo-credentials.json \
  --reference-image /run/demo-reference.png

echo "Safe demo scenarios are ready in $environment_name"
