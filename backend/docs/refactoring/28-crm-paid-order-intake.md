# Stage 28: CRM paid-order production intake

Status: complete locally, default-off; real PostgreSQL concurrency proof pending

Quality score: 94/100

## Boundary chosen from the existing scaffold

The early `garment-buro/backend` scaffold was reviewed before this slice. Its
`Fabric`, garment `Model`, `ModelSize`, `TechCard`, and ordered checkpoint ideas
remain useful for the later internal reference-data module. Its `Item` and
`ItemVariant` types duplicate the now-stabilized storefront catalog, while the
scaffold has no durable paid-order intake, production-order lifecycle, material
movement ledger, migrations, or service/repository boundary.

This stage therefore starts CRM at the real cross-domain event: a successfully
paid storefront order. CRM does not own a second product catalog and does not
copy customer identity, phone, email, delivery address, product title, SKU,
customization, or provider IDs. It owns a PII-free production project and one
production unit per purchased quantity, linked back to immutable order items.

No public or staff HTTP route is exposed yet. `FULFILLMENT_CRM_ENABLED` defaults
to false, so the current storefront, PWA, legacy CRM behavior, and production
traffic remain unchanged.

## Delivered

- revision `20260812_0021` adds `crm_order_projects`,
  `crm_production_units`, and append-only `crm_project_events`;
- one unique project is linked to one paid order and its exact fulfillment job
  and successful payment attempt;
- immutable intake evidence records the order version, line count, expanded
  production-unit count, total/currency, and successful-payment timestamp;
- each order-item quantity is expanded deterministically into numbered units,
  preserving only order-item, product, and optional variant IDs;
- conflict-safe PostgreSQL/SQLite inserts and a locked evidence comparison make
  replay idempotent and reject any changed source snapshot;
- the CRM handoff runs through the existing claim/attempt fulfillment worker,
  so project creation, unit creation, initial audit event, and job completion
  commit atomically;
- the project state machine supports explicit `queued`, `in_progress`,
  `on_hold`, `completed`, and `cancelled` transitions;
- every state change uses optimistic version evidence, a constrained safe
  reason code, optional actor user ID, and a unique append-only event;
- terminal projects cannot be reopened, stale versions cannot overwrite a
  concurrent update, and lifecycle timestamps are protected by database
  constraints;
- the generic fulfillment worker can now run CRM alone or together with email
  and CDEK handoffs;
- production and local Compose configurations pass the independent CRM flag to
  the backend and fulfillment worker.

## Runtime flow

```text
payment transaction marks order paid
        |
        v
unique PII-free crm_order_project job
        |
        v
claim + numbered fulfillment attempt
COMMIT CLAIM
        |
        v
lock paid order + successful payment evidence
        |
        v
insert-or-verify CRM project
expand line quantities into production units
append project version 1 event
mark fulfillment job completed
COMMIT ALL CRM WRITES ATOMICALLY
```

Any missing paid-order/payment evidence or changed immutable projection is a
permanent fulfillment failure. An unexpected infrastructure error follows the
existing bounded retry policy. The handler never makes a network call.

## Data ownership

| Storefront source of truth | CRM-owned data |
| --- | --- |
| Customer identity and delivery details | No copy; accessed later only through an authorized application service when operationally required |
| Product title, SKU, media, price, customization | Immutable `order_item_id` link; no duplicate CRM catalog |
| Product and variant identity at checkout | Numeric source snapshots on each production unit |
| Payment provider evidence | Successful payment-attempt ID and success timestamp only |
| Order lifecycle | Independent, versioned production-project lifecycle |

Fabric stock, garment models/sizes, tech cards/checkpoints, material movements,
unit work stages, comments, assignments, and private MinIO attachments belong to
the next bounded CRM slices. They will reference this aggregate rather than
change its paid-order evidence.

## Configuration and activation order

```dotenv
DATABASE_ENABLED=true
FULFILLMENT_OUTBOX_ENABLED=true
FULFILLMENT_CRM_ENABLED=false
```

Apply migration `0021` first. On staging, enable only the CRM flag and run a
bounded drain before starting continuous processing:

```bash
cd backend
../.venv/bin/python -m scripts.process_fulfillment_jobs --once --max-items 100
```

Inspect exact counts before enabling the continuous Compose profile:

```sql
SELECT count(*) FROM crm_order_projects;
SELECT sum(items_count), sum(units_count) FROM crm_order_projects;
SELECT count(*) FROM crm_production_units;
SELECT count(*) FROM crm_project_events WHERE version = 1;
```

For each project, `units_count` must equal its actual production-unit count and
the global sum must match the unit table count. Do not expose a cabinet route
until RBAC, pagination, response DTOs, and access audit are added.

## Verification

- Ruff lint, Ruff format verification, and legacy-entrypoint syntax pass;
- all 260 backend unit/contract tests pass;
- the CRM tests prove quantity expansion, exact source links, PII absence,
  atomic fulfillment completion, replay idempotence, immutable-evidence
  conflict rejection, optimistic locking, audit history, legal transitions,
  and terminal-state protection;
- Alembic has one linear `20260812_0021` head and offline PostgreSQL upgrade and
  downgrade SQL compile through the full chain;
- both production and local Compose models pass `docker compose config --quiet`.

No live PostgreSQL instance was available for `FOR UPDATE SKIP LOCKED`
multi-worker proof or actual migration apply/downgrade. The flag remains off;
those checks are explicit staging requirements rather than claimed local proof.

## Score rationale

| Area | Score | Evidence |
| --- | ---: | --- |
| Architecture | 20/20 | Paid-order handoff, CRM repository, aggregate models, and lifecycle service are separated. |
| Privacy and authorization boundary | 20/20 | Intake is PII-free, default-off, and exposes no HTTP route before staff RBAC. |
| Reliability and data safety | 20/20 | Unique source links, locked replay comparison, atomic unit/event creation, versions, and DB constraints. |
| Compatibility | 20/20 | No public schema or legacy behavior changes; independent activation flag. |
| Verification | 14/20 | Full local/offline gate passes; real PostgreSQL concurrency and staging data proof remain. |
| Total | 94/100 | The locally verifiable intake slice exceeds the requested threshold without claiming staging evidence. |

## Next bounded slice

1. Add normalized fabrics, garment models, sizes, tech cards, and ordered
   checkpoints as private CRM reference data, reusing the useful scaffold
   concepts without duplicating storefront products.
2. Add unit-stage history, assignments, comments, and actor audit through
   manager/admin application services.
3. Add append-only material receipts/reservations/consumption/adjustments and
   derive balances from movements rather than mutable stock fields alone.
4. Add a private MinIO bucket and authorized attachment metadata for tech cards
   and production projects.
5. Expose paginated staff-only APIs through `crm.access`, response DTOs, and
   negative permission/PII tests, then build the internal cabinet.

## Rollback

Set `FULFILLMENT_CRM_ENABLED=false` and stop/drain the fulfillment worker before
schema rollback. Existing projects remain available for audit and later resume.

Online downgrade of `0021` refuses to discard any CRM project. Export and
reconcile projects, units, and events before removing the schema. The paid
order, payment, and fulfillment evidence remains intact in its owning domains.
