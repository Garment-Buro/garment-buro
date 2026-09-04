# Garment Buro deployment

Production and development use the same immutable images but isolated Compose
projects, databases, Redis data, MinIO data and host ports.

| Environment | Branch | Domain | Frontend | Backend | MinIO |
| --- | --- | --- | ---: | ---: | ---: |
| production | `main` | `garment-buro.ru` | 3000 | 8000 | 9000 |
| development | `develop` | `dev.garment-buro.ru` | 3100 | 8100 | 9100 |

`partner.garment-buro.ru` uses the development frontend and backend until the
partner program is promoted separately. `widget.garment-buro.ru` is served by
the standalone widget deployment in the legacy Docker network.

Before the first development deployment, enable the partner feature and expose
the rootless development ports only on the Docker bridge address:

```bash
bash deploy/scripts/enable-partner-development.sh
```

The script preserves existing secrets, creates the attribution secret when it
is absent, writes a timestamped mode-preserving backup, and never prints the
secret value.

The first public-host setup is intentionally a root-only operation because it
expands the trusted certificate and reloads Nginx. From a reviewed checkout run:

```bash
sudo bash deploy/scripts/enable-public-hosts.sh "$(pwd)"
```

The current server still runs the public Nginx and widget in the legacy root
Compose project. The script backs up that Nginx configuration, expands the
existing `garment-buro.ru` certificate to all four hosts, rebuilds the existing
widget at the domain root, validates Nginx, and recreates only the Nginx
container. It does not copy secrets into the repository.

Only Nginx exposes ports 80 and 443 publicly. Application and storage ports
listen on loopback by default; the development deployment binds to the Docker
bridge address so the legacy Nginx container can reach it without opening the
ports on public interfaces.

## What is deployed

- GitHub Actions runs backend, frontend, migration and secret-scanning gates.
- Backend and frontend images are pushed to GHCR with environment and commit tags.
- The server receives only Compose descriptors and pulls immutable images.
- Alembic runs before the new application containers are switched.
- A reviewed legacy SQLite snapshot and uploads are seeded once into rootless
  Docker volumes and remain available during the guarded migration.
- PostgreSQL, Redis and MinIO use separate named volumes per environment.
- Alembic uses the PostgreSQL owner role only during deployment; the API and
  workers use a separate non-superuser role without schema-creation rights.
- Optional workers are activated only through reviewed Compose profiles.
- Deployment enables each worker profile automatically when its owning feature
  flag is enabled (identity notifications, payments, reconciliation,
  fulfillment, or CDEK creation).

## One-time host bootstrap

Run these steps as root from a trusted terminal:

1. Install Docker Engine with the Compose plugin, Nginx, Certbot, curl and the
   Rootless Mode prerequisites. On Debian/Ubuntu these include `uidmap`,
   `dbus-user-session` and `docker-ce-rootless-extras`.
2. Copy the personal and CI public SSH keys to temporary root-only files.
3. Run `provision-server-user.sh <admin.pub> <ci.pub>`.
4. Verify key login as `garment`, `docker info` without sudo and `rootless` in
   its `Security Options`. The script deliberately does not add `garment` to
   the root-equivalent `docker` group.
5. Create a reviewed `.env` in each environment directory from
   `env.server.example`, with mode `0600`. Generate independent values for
   `POSTGRES_PASSWORD` (schema owner) and `DATABASE_APP_PASSWORD` (API/workers).
6. Copy the SQLite snapshot and uploads into each
   `/srv/garment-buro/<environment>/legacy` directory.
7. Install the bootstrap Nginx config, obtain one certificate containing
   `garment-buro.ru`, `www.garment-buro.ru` and
   `dev.garment-buro.ru`, then install the final Nginx config.
8. After both SSH keys are proven, disable SSH password authentication and
   prohibit root password login. Validate with `sshd -t` before reload.
9. Keep the old system Docker daemon only for the backup and transition. After
   the legacy containers are stopped and the new rootless deployment is
   verified, disable `docker.service` and `docker.socket` system-wide.

Do not delete the old deployment until the SQLite snapshot, uploads archive and
container/volume inventory have checksums and have been copied outside the old
project directory.

## GitHub environments

Create `production` and `development` environments with:

Secrets:

- `DEPLOY_HOST`
- `DEPLOY_USER` (normally `garment`)
- `DEPLOY_SSH_PORT`
- `DEPLOY_SSH_KEY`
- `DEPLOY_KNOWN_HOSTS`

Variables:

- `NEXT_PUBLIC_IDENTITY_SESSION_V2_ENABLED`
- `NEXT_PUBLIC_CATALOG_WRITES_ENABLED`
- `NEXT_PUBLIC_CRM_CABINET_ENABLED`
- `NEXT_PUBLIC_YANDEX_MAPS_API_KEY`

Restrict the production environment to `main` and development to `develop`.
Add a required production reviewer when a second trusted repository owner is
available. Integration credentials stay only in the server-side `.env`; they
are not passed as frontend build arguments.

Do not generate `DEPLOY_KNOWN_HOSTS` blindly in CI. Verify the server host-key
fingerprint through the provider console or another trusted channel first, then
store the exact known-hosts line in both GitHub environments.

## Database cutover

The first deploy intentionally keeps all refactored feature flags off. Use this order:

1. Make a SQLite online backup and uploads archive.
2. Start PostgreSQL and apply Alembic head.
3. Run catalog, catalog-content, identity, cart and order migration scripts in
   dry-run mode.
4. Review counts, warnings and SHA-256 fingerprints.
5. Apply each unchanged plan with its exact `--expect-fingerprint` guard.
6. Run `python -m scripts.rehearse_staging`.
7. Enable related backend and frontend flags together in development.
8. Verify browser/PWA login, catalog, cart, order, payment sandbox, CDEK sandbox,
   SMTP delivery, CRM permissions and MinIO private downloads.
9. Repeat from a fresh production backup and promote one feature group at a time.

Never infer or hand-edit migration fingerprints.

## Backup and rollback

Run:

```bash
/srv/garment-buro/<environment>/backup-server.sh <environment>
```

The backup includes a PostgreSQL custom dump, an online SQLite backup, legacy
uploads, deployment metadata and SHA-256 checksums. MinIO data needs a provider
volume snapshot or an independent S3 mirror in addition to this script.

The deploy script restores the previous application image references when the
new readiness checks fail. Alembic migrations must therefore remain backward
compatible with the previous application release.
