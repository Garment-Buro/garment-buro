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
logging_source="$repo_root/deploy/nginx/logging"
logging_target="$legacy_root/garment-nginx-logging"
maintenance_source="$repo_root/deploy/nginx/maintenance/server.conf"
maintenance_target="$legacy_root/garment-nginx-maintenance"
maintenance_state=/srv/garment-buro/maintenance
override_source="$repo_root/deploy/docker-compose.legacy-nginx.override.yml"
widget_override_source="$repo_root/deploy/docker-compose.widget-root.override.yml"
override_target="$legacy_root/docker-compose.override.yml"
backup_dir="/root/garment-buro-nginx-backup-$(date -u +%Y%m%dT%H%M%SZ)"
had_override=false
had_logging=false
had_maintenance=false
widget_changed=false
firewall_rule_added=false
firewall_source=""
firewall_destination=""
firewall_port=""

test -f "$nginx_source"
test -f "$logging_source/http.conf"
test -f "$logging_source/server.conf"
test -f "$maintenance_source"
# Provision this persistent, deployment-user-owned directory before activation.
# Never create a root-owned Docker bind source or replace a retained gate marker.
test -d "$maintenance_state"
test ! -L "$maintenance_state"
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
if [[ -d "$logging_target" ]]; then
  cp -a "$logging_target" "$backup_dir/garment-nginx-logging"
  had_logging=true
fi
if [[ -d "$maintenance_target" ]]; then
  cp -a "$maintenance_target" "$backup_dir/garment-nginx-maintenance"
  had_maintenance=true
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
  if [[ "$had_logging" == true ]]; then
    rm -f "$logging_target/http.conf" "$logging_target/server.conf"
    cp -a "$backup_dir/garment-nginx-logging/." "$logging_target/"
  else
    rm -f "$logging_target/http.conf" "$logging_target/server.conf"
    rmdir "$logging_target" 2>/dev/null || true
  fi
  rm -f "$maintenance_target/server.conf"
  if [[ "$had_maintenance" == true ]]; then
    cp -a "$backup_dir/garment-nginx-maintenance/." "$maintenance_target/"
  else
    rmdir "$maintenance_target" 2>/dev/null || true
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
  -v "$logging_source/http.conf:/etc/nginx/conf.d/00-garment-logging.conf:ro" \
  -v "$logging_source/server.conf:/etc/nginx/garment-buro/server-logging.conf:ro" \
  -v "$maintenance_source:/etc/nginx/garment-buro/maintenance.conf:ro" \
  -v "$maintenance_state:/srv/garment-buro/maintenance:ro" \
  -v "$legacy_root/certbot/conf:/etc/nginx/ssl:ro" \
  nginx:alpine nginx -t

rollback_required=true
install -d -m 0755 "$logging_target"
install -m 0644 "$logging_source/http.conf" "$logging_target/http.conf"
install -m 0644 "$logging_source/server.conf" "$logging_target/server.conf"
install -d -m 0755 "$maintenance_target"
install -m 0644 "$maintenance_source" "$maintenance_target/server.conf"
install -m 0644 "$nginx_source" "$nginx_target"
install -m 0644 "$override_source" "$override_target"
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
