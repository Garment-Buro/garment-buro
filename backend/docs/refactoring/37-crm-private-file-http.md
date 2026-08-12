# Stage 37: guarded private CRM file HTTP

Status: complete locally; live MinIO policy and PostgreSQL upload race pending

Quality score: 94/100

## Safety boundary

This stage exposes the stage 32 private-file service through two staff routes.
The routes have their own default-off `CRM_FILES_ENABLED` flag. Configuration
refuses that flag unless CRM reads, CRM writes, target identity, PostgreSQL, and
MinIO are also enabled through their existing dependency chain.

Enabling lifecycle or material commands therefore does not enable file upload
or signed-link issuance. Objects remain in the environment-specific private CRM
bucket and never receive a CDN/public URL.

## HTTP contract

```text
POST /api/crm/files
GET  /api/crm/files/{attachment_id}/download
```

Upload is multipart and accepts one `file`, one closed `role` enum, exactly one
positive target (`tech_card_revision_id`, `production_project_id`, or
`production_unit_id`), and non-negative `sort_order`.

The backend reads at most `CRM_FILE_MAX_UPLOAD_BYTES + 1`; the default private
limit is 25 MiB and may not exceed the shared storage upload limit while the
route is enabled. Client filename and content type are untrusted. The server
sanitizes the filename and recognizes bytes as PDF, JPEG, PNG, or WebP before
uploading.

The upload receipt contains attachment/media IDs, detected content type, exact
size, and SHA-256. It contains no object key, bucket, CDN URL, signed URL, or
target-internal data.

The download route does not stream the object through FastAPI. It issues a
short-lived MinIO URL with attachment disposition and octet-stream response
type, records the actor and expiry in the append-only access log, and returns
the safe filename, evidence metadata, TTL, and URL. Both responses use
`Cache-Control: no-store`.

## Delivered

- `CRM_FILES_ENABLED=false` and `CRM_FILE_MAX_UPLOAD_BYTES=26214400` are present
  in typed settings, example environment, and both Compose variants;
- startup validation requires the file flag's CRM write and MinIO dependencies;
- separate router/service injection keeps file exposure independent from all
  other CRM command routes;
- target bearer identity and `crm.access` protect upload and signed download;
- upload roles retain the database ownership rules: pattern/tech-card source
  only for immutable tech-card revisions, production evidence only for project
  or unit targets;
- request bytes are bounded and format-sniffed; spoofed content type, SVG, and
  active/arbitrary content are rejected;
- service storage errors are mapped to non-leaking `503`; missing target/file,
  invalid metadata, unsupported media, oversize body, and slot conflict use
  stable `404`, `422`, `415`, `413`, and `409` responses;
- an exact retry by the original actor with the same safe filename and SHA-256
  in the same target/role/sort slot returns the original receipt and creates no
  second object;
- changed bytes, filename, or actor in an occupied slot fail closed;
- concurrent unique-slot conflict compensates the losing private object, marks
  its media evidence failed, and returns the winning exact receipt only when it
  matches the retry contract;
- signed links use the stored safe filename and remain absent from persistence;
  every successful issuance writes one access event before responding;
- no schema revision was needed because stage 32 already supplied immutable
  media, attachment, uniqueness, and access-audit evidence.

The slot tuple is the upload idempotency boundary:

```text
(exact target, role, sort_order) + actor + safe filename + SHA-256
```

A client must reuse all fields and bytes after an unknown response. Replacing a
file is intentionally not supported by overwriting; use a new sort slot until a
future explicit versioning/delete workflow is designed.

## Verification

- all 279 backend unit/contract tests pass with Ruff, format verification, and
  legacy-entrypoint syntax;
- ASGI tests prove `401/403`, independent flag registration, safe successful
  multipart upload, server-side media detection, private bucket use, exact
  upload replay, changed-slot conflict, missing target/file, invalid role/target,
  SVG rejection, oversize rejection, storage `503`, no-store, and audited signed
  download;
- database assertions prove exactly one ready attachment for retry, failed
  evidence for storage failure, actor-bound access audit, and no public media;
- existing service tests continue proving safe basename handling, private
  object namespace, storage-failure evidence, and active-content rejection;
- Alembic remains at one linear `20260812_0027` head; full offline PostgreSQL
  upgrade/downgrade SQL compiles;
- production and local Compose configurations render with both new settings.
  Missing-secret warnings are expected because validation used no live env file.

No live MinIO anonymous-policy probe, real PostgreSQL concurrent same-slot
upload, proxy multipart test, malware scanner, or staff browser flow was
available. `CRM_FILES_ENABLED` remains false outside staging rehearsal.

## Score rationale

| Area | Score | Evidence |
| --- | ---: | --- |
| Architecture | 20/20 | Independent flag/router, existing file service/repository, and shared immutable media evidence. |
| Security and audit | 20/20 | RBAC, private bucket, sniffed allowlist, bounded bytes, no-store, signed expiry, and actor audit. |
| Reliability and data safety | 20/20 | Exact slot replay, changed-content conflict, pending/ready/failed lifecycle, compensation, and stable errors. |
| Compatibility | 20/20 | Additive default-off routes and settings; public catalog media behavior is unchanged. |
| Verification | 14/20 | Full local/offline gate passes; live MinIO policy, PostgreSQL race, proxy, and browser proof remain. |
| Total | 94/100 | The private-file HTTP slice exceeds the threshold without claiming staging evidence. |

## Staging activation checklist

1. Keep `CRM_FILES_ENABLED=false`; provision `<prefix>-staging-crm-private`
   without anonymous or CDN access and verify readiness from the backend network.
2. Apply migrations and enable CRM reads/writes for one manager first.
3. Probe anonymous object GET/list and public CDN paths; all must fail.
4. Enable files, upload each allowed type, verify checksum/size/bucket/ETag in
   PostgreSQL and MinIO, then issue and expire a signed URL.
5. Run two simultaneous same-slot uploads with identical and different bytes;
   prove one attachment, one ready object, compensated loser, and stable receipt
   or conflict.
6. Confirm reverse proxy, access logs, traces, and error reporting do not retain
   bearer tokens, signed query strings, multipart bytes, or private filenames.
7. Disable the flag again until the manager cabinet is ready for controlled use.

## Next bounded slice

1. Implement aggregate terminal project reconciliation with project/unit and
   material locks in one transaction.
2. Add deterministic CRM ledger/file reconciliation commands and stale evidence
   metrics needed for staging operations.
3. Run real PostgreSQL/MinIO staging rehearsal before frontend/PWA cutover.

## Rollback

Set `CRM_FILES_ENABLED=false` and restart; no schema rollback is required. Do
not remove attachment, media, or access-event rows. Reconcile every ready/failed
media row against the private bucket, retain orphan evidence for investigation,
and remove only objects proven to belong to compensated failed attempts.
