#!/usr/bin/env bash
set -euo pipefail

if [[ ${EUID:-$(id -u)} -ne 0 ]]; then
  echo "Run this script as root." >&2
  exit 1
fi

repo_root=${1:-/srv/garment-buro/public-hosts}
legacy_root=/home/plus2opacity
widget_root=/home/garment-widget
development_env=/srv/garment-buro/development/.env
nginx_source="$repo_root/nginx.conf"
nginx_target="$legacy_root/nginx.conf"
override_source="$repo_root/deploy/docker-compose.legacy-nginx.override.yml"
widget_override_source="$repo_root/deploy/docker-compose.widget-root.override.yml"
override_target="$legacy_root/docker-compose.override.yml"
backup_dir="/root/garment-buro-nginx-backup-$(date -u +%Y%m%dT%H%M%SZ)"
had_override=false
widget_changed=false
firewall_rule_added=false
firewall_source=""
firewall_destination=""
firewall_port=""

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
  if [[ "$firewall_rule_added" == true ]]; then
    ufw --force delete allow proto tcp \
      from "$firewall_source" \
      to "$firewall_destination" \
      port "$firewall_port" >/dev/null || true
  fi
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

configure_development_firewall() {
  if ! command -v ufw >/dev/null || ! ufw status | grep -q '^Status: active'; then
    return
  fi

  test -f "$development_env"

  firewall_destination=$(sed -n 's/^HOST_BIND_ADDRESS=//p' "$development_env" | tail -n 1)
  firewall_port=$(sed -n 's/^FRONTEND_HOST_PORT=//p' "$development_env" | tail -n 1)
  firewall_source=$(
    docker network inspect plus2opacity_default \
      --format '{{(index .IPAM.Config 0).Subnet}}'
  )

  if [[ ! "$firewall_destination" =~ ^[0-9]+(\.[0-9]+){3}$ ]]; then
    echo "Invalid HOST_BIND_ADDRESS in $development_env" >&2
    return 1
  fi
  if [[ ! "$firewall_port" =~ ^[0-9]+$ ]]; then
    echo "Invalid FRONTEND_HOST_PORT in $development_env" >&2
    return 1
  fi
  if [[ ! "$firewall_source" =~ ^[0-9]+(\.[0-9]+){3}/[0-9]+$ ]]; then
    echo "Invalid plus2opacity_default subnet: $firewall_source" >&2
    return 1
  fi

  if ufw status | grep -F "$firewall_destination $firewall_port/tcp" \
    | grep -Fq "$firewall_source"; then
    return
  fi

  ufw allow proto tcp \
    from "$firewall_source" \
    to "$firewall_destination" \
    port "$firewall_port" \
    comment 'Garment Buro nginx to development frontend'
  firewall_rule_added=true
}

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
configure_development_firewall

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
