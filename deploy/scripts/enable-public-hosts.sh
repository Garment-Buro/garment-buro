#!/usr/bin/env bash
set -euo pipefail

if [[ ${EUID:-$(id -u)} -ne 0 ]]; then
  echo "Run this script as root." >&2
  exit 1
fi

repo_root=${1:-/srv/garment-buro/public-hosts}
legacy_root=/home/plus2opacity
widget_root=/home/garment-widget
nginx_source="$repo_root/nginx.conf"
nginx_target="$legacy_root/nginx.conf"
override_source="$repo_root/deploy/docker-compose.legacy-nginx.override.yml"
widget_override_source="$repo_root/deploy/docker-compose.widget-root.override.yml"
override_target="$legacy_root/docker-compose.override.yml"
backup_dir="/root/garment-buro-nginx-backup-$(date -u +%Y%m%dT%H%M%SZ)"
had_override=false
widget_changed=false

test -f "$nginx_source"
test -f "$override_source"
test -f "$widget_override_source"
test -f "$legacy_root/docker-compose.yml"
test -f "$widget_root/docker-compose.server.yml"
command -v docker >/dev/null

install -d -m 0700 "$backup_dir"
if [[ -f "$nginx_target" ]]; then
  cp -a "$nginx_target" "$backup_dir/garment-buro.conf"
fi
if [[ -f "$override_target" ]]; then
  cp -a "$override_target" "$backup_dir/docker-compose.override.yml"
  had_override=true
fi

restore_previous_nginx() {
  if [[ "$widget_changed" == true ]]; then
    cd "$widget_root"
    docker compose -f docker-compose.server.yml up -d --build
  fi
  if [[ -f "$backup_dir/garment-buro.conf" ]]; then
    cp -a "$backup_dir/garment-buro.conf" "$nginx_target"
  fi
  if [[ "$had_override" == true ]]; then
    cp -a "$backup_dir/docker-compose.override.yml" "$override_target"
  else
    rm -f "$override_target"
  fi
  cd "$legacy_root"
  docker compose up -d --force-recreate nginx
}

rollback_required=false
trap 'if [[ "$rollback_required" == true ]]; then restore_previous_nginx; fi' ERR

cd "$legacy_root"
docker compose run --rm --entrypoint certbot certbot certonly \
  --webroot -w /var/www/certbot \
  --cert-name garment-buro.ru --expand --non-interactive --agree-tos \
  -m info@garment-buro.ru \
  -d garment-buro.ru \
  -d www.garment-buro.ru \
  -d dev.garment-buro.ru \
  -d partner.garment-buro.ru \
  -d widget.garment-buro.ru

docker run --rm \
  --network plus2opacity_default \
  --add-host host.docker.internal:host-gateway \
  -v "$nginx_source:/etc/nginx/conf.d/default.conf:ro" \
  -v "$legacy_root/certbot/conf:/etc/nginx/ssl:ro" \
  nginx:alpine nginx -t

install -m 0644 "$nginx_source" "$nginx_target"
install -m 0644 "$override_source" "$override_target"
rollback_required=true

cd "$widget_root"
widget_changed=true
docker compose \
  -f docker-compose.server.yml \
  -f "$widget_override_source" \
  up -d --build

cd "$legacy_root"
docker compose up -d --force-recreate nginx
docker compose exec -T nginx nginx -t
rollback_required=false

echo "Configured GARMENT BURO public hosts. Backup: $backup_dir"
