#!/usr/bin/env bash
set -euo pipefail

env_file=${1:-/srv/garment-buro/development/.env}
backup_file="${env_file}.partner-backup-$(date -u +%Y%m%dT%H%M%SZ)"

test -f "$env_file"
command -v openssl >/dev/null
cp -p "$env_file" "$backup_file"

upsert() {
  local key=$1
  local value=$2
  local next_file
  next_file=$(mktemp "${env_file}.XXXXXX")
  awk -v key="$key" -v value="$value" '
    BEGIN { replaced = 0 }
    index($0, key "=") == 1 {
      if (!replaced) print key "=" value
      replaced = 1
      next
    }
    { print }
    END { if (!replaced) print key "=" value }
  ' "$env_file" >"$next_file"
  chmod --reference="$env_file" "$next_file"
  mv "$next_file" "$env_file"
}

partner_secret=$(sed -n 's/^PARTNER_ATTRIBUTION_SECRET=//p' "$env_file" | tail -n 1)
if [[ ${#partner_secret} -lt 32 ]]; then
  partner_secret=$(openssl rand -hex 32)
fi

upsert HOST_BIND_ADDRESS 172.17.0.1
upsert IDENTITY_API_ENABLED true
upsert PARTNER_PROGRAM_ENABLED true
upsert PARTNER_ATTRIBUTION_SECRET "$partner_secret"
upsert PARTNER_ATTRIBUTION_DAYS 30
upsert PARTNER_COMMISSION_HOLD_DAYS 14
upsert PARTNER_ATTRIBUTION_COOKIE_NAME gb_partner
upsert PARTNER_VISITOR_COOKIE_NAME gb_partner_visitor
upsert PARTNER_COOKIE_DOMAIN ""
upsert CORS_ORIGINS '["https://dev.garment-buro.ru","https://partner.garment-buro.ru"]'

chmod 0600 "$env_file"
echo "Development partner settings enabled. Backup: $backup_file"
