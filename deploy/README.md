# Garment Buro deployment

Production and development use the same immutable images but isolated Compose
projects, databases, Redis data, MinIO data and host ports.

Nginx vhosts require the shared safe logging includes. See
[installation, logging limits and native privacy gate](nginx/README.md) before
installing any root or `deploy/nginx` configuration. The public-host installer
backs up and restores these includes together with the vhost and Compose override.

| Environment | Branch | Domain | Frontend | Backend | MinIO |
| --- | --- | --- | ---: | ---: | ---: |
| production | `main` | `garment-buro.ru` | 3000 | 8000 | 9000 |
| development | `develop` | `dev.garment-buro.ru` | 3100 | 8100 | 9100 |

`partner.garment-buro.ru` and `production.garment-buro.ru` use the production
frontend and backend deployed from `main`. Host-based routing in the frontend
opens `/partner` and `/production` respectively. `widget.garment-buro.ru` is a
separate application with its own repository and deployment from that
repository's `main` branch.

Before the first development deployment, enable the partner feature for testing
through `dev.garment-buro.ru` and expose the rootless development ports only on
the Docker bridge address:

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
widget at the domain root through a Compose override, validates Nginx, and
recreates only the Nginx container. It does not copy secrets into the
repository.

When UFW is active, the script also allows only the legacy Docker subnet to
reach the development frontend bind address and port from the development
`.env`. The development port remains unavailable from the public network. The
rule is removed automatically if the host switch rolls back.

Only Nginx exposes ports 80 and 443 publicly. Application and storage ports
listen on loopback by default; the development deployment binds to the Docker
bridge address so the legacy Nginx container can reach it without opening the
ports on public interfaces.

## What is deployed

- GitHub Actions runs backend, frontend, migration and secret-scanning gates.
- Backend and frontend images are pushed to GHCR with environment and commit tags.
- The application release receives Compose descriptors and pulls immutable
  backend/frontend images. MinIO is built separately from pinned upstream source,
  loaded onto the host and selected explicitly with `MINIO_IMAGE`; the server
  never builds or pulls it. See [storage build and transfer](minio/README.md).
- Alembic runs before the new application containers are switched.
- The API and workers use PostgreSQL and MinIO; they do not mount SQLite or
  legacy uploads. The previous release's volumes remain available for recovery
  and are not deleted by deployment.
- PostgreSQL, Redis and MinIO use separate named volumes per environment.
- Storage initialization creates media, crm-private and projects buckets.
  Only media allows anonymous downloads; projects has no bucket policy.
  API readiness and project upload/access reject a projects bucket with a policy.
  Each application cutover runs idempotent `minio-init` with a 120-second limit
  before migrations, so an existing MinIO installation receives new buckets.
- Alembic uses the PostgreSQL owner role only during deployment; the API and
  workers use a separate non-superuser role without schema-creation rights.
- Optional workers are activated only through reviewed Compose profiles.
- Deployment enables each worker profile automatically when its owning feature
  flag is enabled (identity notifications and project media cleanup, payments, reconciliation,
  fulfillment, or CDEK creation).
- Previously running workers and then API/frontend are paused before migrations,
  including workers disabled by candidate flags. A second running-service check
  permits only PostgreSQL, Redis and MinIO before Alembic. Unknown writers,
  orphans, setup jobs and paused/restarting services block the cutover.
  This is a maintenance window. Candidate API/frontend HTTP probes finish before
  the selected new workers start. A release with no enabled workers is valid.
- `project-media-worker` uses profile `project-media`, requires identity,
  PostgreSQL and private MinIO storage, and reconciles bounded batches. Inspect
  candidates with `python -m scripts.reconcile_project_media --dry-run` inside
  its backend image. See `backend/docs/customer-projects.md` for retention,
  durable retries, versioned object deletion and lock guarantees.

## Disposable container runtime check

The reusable CI workflow builds MinIO from `deploy/minio/Dockerfile`, loads both
application images into Docker and runs
`python3 deploy/scripts/smoke-containers.py` before the publishing workflow can
proceed. A build alone does not pass this gate. The command can also check
already built local images:

```bash
python3 deploy/scripts/smoke-containers.py \
  --backend-image garment-buro-backend:ci \
  --frontend-image garment-buro-frontend:ci \
  --minio-image garment-buro-minio:2025-10-15-garment1
```

Prepare the storage image first using [the source build](minio/README.md).
The smoke command uses the explicitly selected image and does not inherit
`MINIO_IMAGE` from the host.

It copies the actual server Compose descriptor into a private temporary folder,
uses a random `garment-smoke-*` project with fresh volumes and random loopback
ports, and generates disposable credentials. It does not read deployment `.env`
files or inherit application feature flags. Docker connection/context settings
are retained so the command can use the configured engine. Payments, external
delivery and notification processing stay disabled.

The check starts PostgreSQL/Redis/MinIO, initializes the runtime role and buckets,
runs Alembic, starts both images, and verifies non-root application users and
the restricted database role. HTTP checks require actual dependency readiness,
empty public catalog/people/community pages both directly and through Next,
401 for private APIs, 404 for retired settings, and compiled JS/CSS referenced
by the standalone home/catalog HTML. Alembic head runs again for idempotence.
The HTTP gate also requires the image optimizer to reject private API, signed
storage URLs and encoded aliases with400/no-store without reflecting the source.
A public PNG must still optimize successfully. This uses synthetic markers,
never customer image capabilities. With `CARTS_V2_ENABLED=true`, the gate then
creates a real catalog product and writes a constructor cart through Next.
It requires server pricing (1500 + 80), idempotent replay, a stale-revision
conflict and uncached responses. After stopping the API and Redis, it starts
only the API and requires the exact saved snapshot through both HTTP paths.
The random cart capability is never printed or passed to container commands.
The generated environment includes MinIO enablement and its container endpoint
for the migration service as well: that service replaces the shared environment
mapping, while catalog flags still arrive from the generated env file.
The expanded gate has unit coverage; its real Docker result is recorded
separately in the release journal. A build or unit test alone is not that result.
This is a clean-environment runtime gate, not a payment/browser E2E or an upgrade
and previous-image rollback rehearsal.

Success, failure and handled INT/TERM remove only the owned Compose project and
its volumes. Cleanup failure fails the command and retains its private folder
for operator recovery; the error identifies the project and folder. SIGKILL or
engine/host failure can require manual cleanup. Credentials, Compose environment
and container logs are not printed.

Local status on 17 October: Docker is unavailable because its executable points
to a missing OrbStack installation. The command's HTTP/failure tests and a native
copied Next standalone package passed; actual Docker execution and the updated
CI workflow have not yet been run. They remain release conditions.

## Production demo scenarios

Run the manual `Seed production demo` workflow from `main` after the production
deployment has finished. It uses the deployed backend image to create only
explicitly marked demo orders for the current production stages. Demo orders
cannot start payments, delivery, notifications, or appear in customer
statistics. Repeating the run preserves scenarios that employees have already
advanced.

Generated employee codes stay in the private deployment directory and are
never printed to CI logs.

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
   Build and load the [pinned MinIO image](minio/README.md) before starting
   infrastructure; set `MINIO_IMAGE` to that prepared image ID or verified tag.
6. Start PostgreSQL/Redis/MinIO, initialize the application role and buckets,
   and apply Alembic head before starting the API. If transferring an existing
   installation, import its reviewed snapshots separately using the procedure
   below. A new installation does not require a SQLite snapshot.
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

`app.main:app` runs only the modern API. There is no SQLite fallback when a
module is disabled. Core catalog, cart, identity and order reads are enabled in
the environment templates; configure their secrets before startup. Ordinary
startup verifies Alembic head and does not require migration fingerprints.

For an existing installation, transfer data before switching its application:

1. Make a SQLite online backup and uploads archive.
2. Start PostgreSQL and apply Alembic head.
3. Run catalog, catalog-content, identity, cart and order migration scripts in
   dry-run mode.
4. Review counts, warnings and SHA-256 fingerprints.
5. Apply each unchanged plan with its exact `--expect-fingerprint` guard.
6. Run `python -m scripts.rehearse_staging`.
7. Verify the related backend and frontend flags together in development.
8. Verify browser/PWA login, catalog, cart, order, payment sandbox, CDEK sandbox,
   SMTP delivery, CRM permissions and MinIO private downloads.
9. Repeat from a fresh production backup and promote one feature group at a time.

Never infer or hand-edit migration fingerprints.

## Backup and rollback

Run:

```bash
/srv/garment-buro/<environment>/backup-server.sh <environment>
```

The backup includes a PostgreSQL custom dump, a MinIO volume archive, deployment
metadata and SHA-256 checksums. It also archives SQLite (using a read-only source
connection) and uploads when they are mounted in the previous release. Their
absence in a modern release is expected; an archive or helper-container failure
still fails the backup. The previous backend stays stopped while network-isolated
helpers read its mounted volumes read-only. Existing legacy volumes and source snapshots are never
deleted by these scripts. `GARMENT_DEPLOY_ROOT` can override `/srv/garment-buro`
for an installation in another directory.

**Backup opens a maintenance window.** It acquires the same host lock as
deployment (reusing the inherited lock when called by deployment), records the
currently running services across all profiles, and refuses active setup jobs,
orphaned, paused or restarting services. It stops application services first,
then MinIO, and requires a clean non-OOM storage exit before reading data.
PostgreSQL remains running for its consistent custom dump; MinIO's stopped
volume is archived. This coordinates the deployment-managed DB/object writers
without copying a changing object store. Do not run host importers, direct DB
clients or other unmanaged writers against this dedicated database/volume during
the window; they are outside the Compose lifecycle controlled by this script.

On success, archive failure or catchable INT/TERM, the script starts the existing
MinIO container and waits for health before starting only the application
services that were running. Recovery uses `up -d --no-deps --no-recreate
--pull never --wait`: it does not rerun completed setup jobs, pull/recreate images
or enable dormant workers. The bundle path is returned only after successful recovery. A failed
restart exits nonzero with the recovery directory; restore MinIO, then the
previously running applications manually before retrying. SIGKILL, host failure
and Docker daemon failure cannot be recovered by shell traps. Keep an operator
present for the first target-host rehearsal and measure the outage at realistic
data volume. Docker documents [stop escalation](https://docs.docker.com/reference/cli/docker/container/stop/)
and [starting selected services without dependencies or recreation](https://docs.docker.com/reference/cli/docker/compose/up/).

Each run creates a separate private `timestamp.random` directory, including
when another backup starts in the same second. `SHA256SUMS` covers the archives
**and** `deployment.env`, `release`, and `docker-compose.yml`. It appears only
after archive checks and a successful checksum reread. A directory without that
completion manifest is an incomplete backup; do not use it for recovery.
Deployment runs the read-only verifier before migrations or application
cutover. A failed check leaves the previous applications in place. Its separate
rollback metadata directory records the exact data bundle in `storage-backup.path`;
both directories have unique names, so recovery does not depend on timestamps
coinciding.

After a successful new deployment, verify a bundle on the server with:

```bash
python3 /srv/garment-buro/<environment>/verify-backup.py /path/to/backup
```

The same read-only tool is available in the checkout at
`deploy/scripts/verify-backup.py`. It requires Python3.10+, uses no third-party
packages, checks private permissions, exact files, checksums, dump headers,
archive paths and gzip integrity, and emits only counts or a generic failure.
It never sources saved configuration or extracts archives. Earlier bundles
whose manifests did not cover metadata deliberately fail this new check;
preserve them for a separate historical recovery review. A matching checksum
does not replace `pg_restore` or an application/storage recovery rehearsal.

Local rehearsal17.10 used real PostgreSQL17 and MinIO with Docker transport
emulated: the actual backup script produced a verified five-file bundle, its
dump was restored to a fresh database, and its MinIO archive to a different
data directory. Contents of106 application tables matched, including10 000
orders; three object hashes and public/private policies matched. The restored
API passed readiness, returned history and the accepted receipt, and the next
order ID was10001. Synthetic source writers/storage were stopped for the copy;
private fixtures and both owned services were removed afterward. This proves
recovery of that synthetic bundle, not a container release, previous-image
compatibility or recovery time at production data volume.

The coordinated procedure was then rehearsed with a synthetic writer actively
updating PostgreSQL rows, MinIO bytes and matching media metadata. The actual
backup script stopped that writer after53 updates, stopped native MinIO with
exit0, archived, restarted storage and allowed another write. Recovery from
the earlier boundary still matched all106 tables,10 000 orders and three object
digests/metadata, public/private access, API history/receipt and next ID10001.
Docker transport was emulated; PostgreSQL, the writer and MinIO lifecycle were
real. All owned infrastructure and private fixtures were removed.46 focused
deployment tests also cover partial stop, dump/archive/restart errors, INT/TERM,
disabled services, concurrent backups and inherited deployment locks. These
checks supplement the earlier integrity/restore proof; they do not replace
the container and production-volume gates below.

The 20.10 rehearsal then used genuine rootless Docker, the actual corrected
backup CLI and server Compose, and separate PostgreSQL/MinIO volumes.
It exposed a real recovery bug: Compose `start` traversed dependencies
and reran completed setup jobs. The corrected no-dependencies recovery
passed 42 focused tests, then the real coordinated backup/restore passed: 111
application tables, 10 000 orders, three objects, two retained versions,
metadata/tags and public/private policies. The active writer resumed;
container IDs, completed jobs and a dormant worker were preserved.
Restored history, receipt, favorites and the server-priced cart passed
direct API and Next HTTP, including API restart with Redis stopped.
The next order ID was 10001. Owned resources, VM and private configuration
were removed. These are synthetic data and amd64 images under binfmt.
The 1406-test Linux suite and image builds preceded this deployment-script
fix; application runtime sources did not change. A subsequent current-source
Linux gate passed 1409 tests without skips and the actual amd64 Compose/Next
HTTP gate after both backup and deployment recovery fixes. See the [coordinated restore evidence](../docs/superpowers/plans/2026-10-20-rootless-coordinated-restore.md).

A restore at production data volume, unmanaged-writer coordination and
a measured acceptable maintenance window remain required. This synthetic
rehearsal does not establish previous-image compatibility or a complete
cutover/rollback.

When new readiness checks fail, the deploy script first stops candidate workers,
then candidate frontend/backend before restoring only the application and worker
services previously running in the saved Compose descriptor. A newly introduced cleanup
worker cannot remain active beside the previous API. Recovery failures are
reported explicitly with the backup directory; automatic schema downgrade is
never attempted.

Before a migration attempt, recovery resumes existing paused containers with
`up -d --no-deps --no-recreate --pull never --wait`, preserving image/environment
and preventing completed setup dependencies from running again. After any migration attempt, recovery first removes
this release's exact named migration container, then waits for PostgreSQL to
finish that session through the candidate image's `scripts.wait_for_migration`
command. Online Alembic holds a session advisory lock until the physical
connection closes after commit/rollback; killing a client alone is insufficient.
The helper uses the migrate service's owner environment, without dependencies or
image pulls. Connection/lock/statement timeouts are 5/30/45 seconds, bounded by
an outer 60 seconds. Failure leaves applications/workers stopped and removes the
exact named waiter container. Only after this barrier does recovery load the
old image variables and run its read-only `alembic current --check-heads` command.
A mismatch, unavailable
database, unsupported CLI or 60-second timeout leaves old applications and workers
stopped and reports the recovery directory. A timed-out probe is removed by its
exact name. Partial stops and catchable INT/TERM are handled too. After candidate workers
have been created, recovery recreates only the previously running set; dormant
services are not activated. Recovery restores the saved Compose descriptor and
`.release` before checking the old schema, including after a late metadata-copy failure. Recovery
errors remain explicit. SIGKILL and host/daemon failure are outside shell traps.

Local19.10:138 focused tests passed without skips:62 deployment,42 backup/verifier,
9 waiter CLI and25 Alembic metadata. The actual Bash3.2 script uses emulated
Docker/Linux host transport. Separately,4 tests ran the current Alembic env and
helper against actual PostgreSQL17:DDL commit, rollback, SIGKILL of a blocked
client, and bounded lock timeout. These clients ran locally through a private
SSH tunnel; a new application image and the full Docker cutover were not tested.
Owned resources were removed,14 pre-existing containers were unchanged.
The protocol covers cooperating current Alembic sessions; external writers and
older migration clients still require coordination. See
[migration completion barrier](../docs/superpowers/plans/2026-10-19-migration-completion-barrier.md).
This does not prove old ASGI/data/config compatibility or provider side effects.
API/frontend are now stopped during migrations; application restart must succeed
before workers resume. Candidate-time recreation uses the current `.env`;
restoring old configuration/secrets requires a separate reviewed procedure.
The deploy script now pauses old writers before backup and owns their recovery.
Backup resumes only MinIO, leaving applications stopped through setup and
migration. A second writer check precedes migration. The maintenance window
therefore includes the whole backup. External writers and actual outage/restore
remain release checks. See [backup boundary](../docs/superpowers/plans/2026-10-19-release-backup-boundary.md).

Local 20.10: the actual release/backup/verifier CLIs passed on genuine rootless
Docker with three scenarios: storage-init failure before migration (exit 41),
unhealthy candidate worker after API/Next HTTP (exit 1), and successful cutover
(exit 0). Early recovery preserved container IDs, actual images/environment
and completed setup jobs. Late recovery stopped candidate services, ran the
migration barrier/schema probe and restored the prior running set. Three
five-file backups verified; 10 000 orders, files/versions, history, receipt,
favorites and cart remained usable. Infrastructure container IDs were preserved.
All owned resources and the VM were removed. 109 focused tests passed (67
release, 42 backup/verifier), plus Ruff and shell syntax.

This is a lifecycle rehearsal: pulls/pushes used a private fixture registry
inside the throwaway VM, workers were synthetic sleeping processes, and both
application variants used the previously verified runtime (the candidate had
a distinct image label/config ID). It does not prove historical-image or new
schema compatibility, actual GHCR/CI, provider effects or production-volume
outage. The earlier 1406-test suite predates these changes; the subsequent
current-source Linux gate passed 1409/0skip and actual amd64 Compose/Next HTTP.
See [current full-gate scope](../docs/superpowers/plans/2026-10-20-current-full-release.md) and
[actual release recovery](../docs/superpowers/plans/2026-10-20-rootless-release-recovery.md).

A separate 20.10 rehearsal used genuine historical backend/Next images and
synthetic native data at head `20261012_0056`. The actual backup CLI produced
a verified six-file bundle (including an empty historical uploads directory).
The current release upgraded the same database to `20261020_0081` and served
the old account/cart/order data through API and Next. The old image accepted
its own head and rejected the new head without changing any table contents.
Restoring the checkpoint into distinct PostgreSQL/MinIO volumes recovered
all 103 historical application tables, 10 000 orders, three objects/two
versions, metadata/tags/public-private access, the exact old images and 22
matching asset digests. Old API and Next passed, including API restart with
Redis stopped and next order ID 10001. Owned resources and VM were removed.
This is checkpoint recovery: writes after the backup are intentionally lost.
It does not prove zero-data-loss automatic rollback, production-volume timing
or a public maintenance gate. See [historical recovery](../docs/superpowers/plans/2026-10-20-historical-checkpoint-recovery.md).

Application rollback requires both backward-compatible schema changes and a
previous image that accepts the resulting Alembic revision. The current strict
revision guard can reject a newer schema even for an additive index. An actual
previous-image rollback rehearsal or a separately reviewed recovery procedure
is therefore a required release gate. The shell tests emulate Docker transport
and prove command ordering/failure behavior, not image/schema compatibility.
The running backend image contains revision `20261012_0056`. Its absence from
this branch originally blocked in-place upgrades; all common migration files
through `20260929_0055` matched by SHA-256. See the historical
[schema recovery checks](../docs/superpowers/plans/2026-10-19-rollback-schema-guard.md).
Separate native Docker/PostgreSQL checks confirmed the previous image accepts
its own revision, rejects the candidate's fresh schema without mutation, and
accepts a restored synthetic database after real `pg_dump`/`pg_restore`.
The candidate migration source used the cached previous image's Python runtime;
this does not prove a new backend image, ASGI startup or the complete DB/S3 restore.
That snapshot rejected an in-place candidate upgrade because the revision was
absent. All owned resources were removed; the 14
pre-existing containers retained their exact IDs, images, start times and restarts.

20.10 follow-up: the deployed auth migration is restored byte-for-byte and
merged with `20261019_0080` at the single head `20261020_0081`. The associated
auth models/services are reconciled without restoring the old SQLite runtime.
A new native Linux backend image was built from the actual Dockerfile/hashed
lock. Four isolated PostgreSQL databases (fresh, common ancestor, deployed auth
branch and prior release branch) upgraded successfully; full schema comparison,
preserved account rows and real uvicorn auth HTTP passed. This does not prove
old-image ASGI compatibility, full DB/S3 restore or Linux Next cutover.
See [auth history reconciliation](../docs/superpowers/plans/2026-10-20-auth-history-reconciliation.md).

MinIO remains the selected storage. The Community repository archive does not
stop the installed server. Its image now builds from the official October2025
security release, pinned by source commit/SHA-256 and Go image digest.
The actual linux/amd64 build passed. Server Compose uses `pull_policy: never`;
the release script verifies image availability before application pulls,
writer suspension and backup. A missing image exits78 without changing the
running application. Storage cutover is a separate operation; changing provider
or moving to a paid edition has not been agreed or performed.
See [source build and runtime evidence](../docs/superpowers/plans/2026-10-20-minio-source-release.md).

20.10 storage rehearsal passed: the source-built image opened a synthetic volume
from the old server, survived restart and retained object bytes, versions,
metadata/tags, policies and an existing signed URL. The pre-upgrade archive
restored to a separate volume with the old server. The complete current backend
suite passed1369 tests without skips on fresh native PostgreSQL17 and the new
Linux MinIO, Python3.14.3. Owned resources were removed; the original14 containers
retained exact IDs/images/start times/restarts. This is storage restore evidence,
not a coordinated DB/S3 restore, working-site cutover or full Linux Next gate.

20.10 Linux/Next follow-up passed the unchanged complete smoke command with
current frontend/backend images and the source-built MinIO. Fresh roles/buckets,
Alembic, API rewrites, private image boundary, home/catalog and 15 assets passed.
The server-priced cart survived API restart while Redis remained stopped and
was read directly and through Next. Both application users and the PostgreSQL
runtime role passed their privilege checks. The 1577-file snapshot matched before
and after; the owned Compose project, VM, disks, images and configs were removed.
This was linux/amd64 under binfmt on Linux/aarch64, not a native performance run,
published CI, full cutover or coordinated DB/S3 restore.
See [current Linux/Next evidence](../docs/superpowers/plans/2026-10-20-linux-next-runtime.md).


## Public maintenance during an application release

The release now requires the shared Nginx maintenance include and
`public-maintenance.next.py` (uploaded by the workflow). An unprepared public
proxy fails before image pulls, writer suspension or backups. The controller
checks the dedicated `/_garment/deployment-gate` endpoint on every public origin:
204 while open, 503/Retry-After 60/no-store while closed, and the exact
environment-specific gate header. Generic upstream errors and redirects cannot
satisfy this check. Requests never bypass TLS verification.

Before any application/worker stops, the release creates a persistent owned
marker and verifies all public origins are closed. Nginx blocks pages, APIs,
uploads and new WebSocket handshakes before proxying. The ordinary container
stop still drains existing requests; direct/unmanaged writers need separate
coordination. The marker stays closed through backup, migrations, internal HTTP
probes, workers and release metadata installation. Its directory is synced to
disk and the flag survives proxy/host restart; another release cannot clear it.

Prepare the proxy once, before using the new deploy script:

1. Provision `/srv/garment-buro/maintenance` as garment:garment, mode 0755.
   The deployment root needs traversal for the Nginx worker (0751 in the
   provisioner); production/development directories stay 0750, secrets 0600.
2. Install `nginx/maintenance/server.conf` as
   `/etc/nginx/garment-buro/maintenance.conf` for host Nginx. Every managed HTTPS
   vhost sets its production/development environment and includes this file.
   Install the dedicated production-domain template only after its DNS and
   certificate are prepared. The independent widget release is excluded.
3. Docker Nginx mounts the entire persistent control directory read-only and
   the snippet using `docker-compose.legacy-nginx.override.yml`. Mounting one
   marker inode would not follow creation/removal. `enable-public-hosts.sh`
   validates the mount source and backs up/restores the new include alongside
   its existing logging policy; it never deletes active control markers.
4. Review every public entry point. Defaults are garment-buro.ru, www,
   partner and production for production; dev for development. A reviewed
   `<environment>/public-origins.txt` may replace this list, one HTTPS origin
   per line without paths, credentials, query strings or redirects. Include
   every alias/CDN entry that can reach these applications. Keep loopback
   application ports and the dedicated DB/storage private. A custom deployment
   root requires the matching Nginx control path/mount as well.
5. Run the controller's `check-open` as the deployment user and review Nginx
   configuration before activation. The actual release also tests closing the
   shared marker, so a readable endpoint with an unmounted directory fails.

Recovery has two boundaries. Before commit, the old schema guard still decides
whether old apps may resume; their direct HTTP probes must also pass before
public reopening. Schema rejection, stopped/incomplete recovery or failed
HTTP leaves maintenance active. After all candidate checks and metadata pass,
the release commits **before** reopening public routes. If any opening check
fails, the controller recloses its marker and keeps the committed runtime:
some origin might already have accepted a new order, so automatic rollback
would be unsafe. Fix the public proxy and verify that committed runtime;
then use the same owner's `open` operation. Do not delete the marker blindly.
An incompatible-schema recovery still needs the separately reviewed complete
DB/MinIO checkpoint procedure and its explicit post-checkpoint data-loss limit.

Local proof: 153 focused tests without skips (Docker/public-probe transport
emulated), actual Nginx 1.28.0 on Darwin/arm64, five repository configurations,
trusted loopback HTTPS, six path/method cases, environment isolation, zero
blocked requests reaching the fixture upstream, marker persistence across
proxy restart, partial-opening reclose and missing-mount rejection. Eight
configurations also passed the real privacy gate, 129 safe access events and
both logging negative controls. The CI deployment job runs both real Nginx
checks, but actual GitHub Actions, a fresh rootless release with this new gate,
the full suite after these changes and production activation remain open.
See [implementation and scope](../docs/superpowers/plans/2026-10-20-public-maintenance.md).


### Combined public gate and actual rootless release

A subsequent isolated Linux rehearsal executed the unchanged release/backup/
verifier/controller scripts with real rootless Docker, real Nginx and trusted
HTTPS. Four scenarios passed: early storage-init failure (41), worker failure
after candidate HTTP probes (1), successful cutover (0), and failure reopening
the second public origin after release metadata committed (78). Continuous
public page/cart GET and cart PUT probes observed 503 with the gate signature
while applications were stopped and while candidate images ran before commit.
The early failure preserved original IDs/images/environment; late recovery
restored only the original running application/worker set. Completed setup jobs
and infrastructure IDs were preserved; four five-file backup bundles verified.

The reopening fault deliberately accepted a real public cart write through the
first HTTPS origin after commit, then made the second origin fail. The controller
reclosed maintenance; candidate images/metadata and that new server-priced cart
write remained intact. After repairing the fixture, the same owner's open
operation restored public pages, catalog, cart and account history. Ten thousand
orders, favorites, accepted receipt, three MinIO objects/two versions, metadata/
tags and public/private policies remained usable. Owned application resources,
native proxy, VM/disks and private CLI configuration were removed.

This is a lifecycle proof: the private fixture registry impersonated the GHCR
hostname only inside the owned network, workers were sleepers, and candidate
images differed by labels while retaining the exact previously verified runtime.
All 1371 selected runtime-source hashes matched before image reuse; all 1702
source hashes matched through execution. Real provider effects, actual GHCR/CI,
production data volume/outage and a full suite after the new gate remain open.
Historical-image/checkpoint recovery is the separate earlier proof. Nginx's
system temporary paths were relocated into the owned fixture after the first
attempt failed under its non-root user; the release sources did not change.
This also exposed the same portability issue in both repository Nginx verification
tools. Before changing the frozen repository, exact proposed copies were tested
on Linux/uid1000: the unpatched gate failed, patched privacy (8 configurations,
129 events and negative controls) and maintenance (5 configurations) passed.
Those two independently verified temp-path fixes were applied only after the
release rehearsal completed; application/release runtime code remained unchanged.
See [combined rehearsal](../docs/superpowers/plans/2026-10-20-public-rootless-release.md).


### Current source gates after the final legacy-setting cleanup

The unused `legacy_database_url` default and obsolete test fixture arguments
were removed; it had no runtime consumers. The first full run was explicitly
stopped for that cleanup, not reported as passed. The final snapshot passed
1445 backend tests without skips, exact locks, Ruff/format, real PostgreSQL/
source-built MinIO migrations and both real Nginx gates as uid10001. Fresh
backend arm64/amd64 builds and the actual amd64 Compose/Next HTTP gate passed,
including 15 assets, private-image rejection, cart replay/409 and restart
without Redis. Frontend separately passed a clean Node 24 npm-ci/626-test/build
and both standalone Chromium gates. All 1705 source hashes matched; owned
resources and VM/disks were removed. This supplements the earlier rootless
release/checkpoint proofs; the release/controller code did not change here.
Actual Actions/GHCR, production volume/outage and provider effects remain
unverified; no working deployment was changed. See
[current source gate](../docs/superpowers/plans/2026-10-20-current-foundation-gates.md).
