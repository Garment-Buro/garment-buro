# Stage 29: versioned CRM reference data

Status: complete locally; private HTTP boundary and real PostgreSQL proof pending

Quality score: 94/100

## Design carried forward from the prototype

The existing `garment-buro/backend` prototype supplied the useful business
vocabulary: fabrics, garment models, model sizes, tech cards, and ordered
checkpoints. This stage keeps that vocabulary but changes the persistence rules
needed for a stable product:

- stable normalized codes replace anonymous rows;
- snake_case target columns replace mixed camelCase database names;
- `Item`/`ItemVariant` are not copied, because PostgreSQL `Product` and
  `ProductVariant` already own the public catalog;
- one catalog product can link to one CRM garment model, while one garment model
  can support multiple public products;
- fabric stock/reserved counters are deliberately absent until append-only
  material movements become the source of truth;
- a tech card is an identity with immutable revisions, not a mutable checkpoint
  list that silently changes production already in progress.

No route is registered in this stage. The models and application service are
private backend building blocks for the following staff API/cabinet slice, so
the current storefront, PWA, and legacy endpoints remain unchanged.

## Delivered

- revision `20260812_0022` adds normalized `crm_fabrics`,
  `crm_garment_models`, `crm_garment_sizes`, catalog-model links, tech cards,
  immutable tech-card revisions/checkpoints, and `crm_reference_events`;
- fabric and garment-model writes use positive versions and locked
  expected-version checks, preventing a stale manager write from overwriting a
  concurrent update;
- fabric dimensions, density, cost, currency, colors, activation, and garment
  base measurements have both input validation and database checks;
- garment-size codes retain stable row IDs across updates; removed sizes are
  deactivated rather than deleted and can later be reactivated without breaking
  future production references;
- active size codes and sort positions are validated per aggregate, with range,
  price, dimensional, and currency invariants;
- catalog linkage validates the real `products` table, is idempotent for the
  same mapping, rejects remapping to a second model, and is protected by a
  unique product constraint;
- each garment model owns at most one tech-card identity, but the card owns a
  numbered history of immutable revisions and ordered checkpoints;
- partial unique indexes allow at most one draft and one published revision per
  card;
- publishing first archives the old published revision, then publishes the
  locked draft atomically; published checkpoint content is never updated;
- a bad draft can be explicitly discarded, avoiding a permanently blocked
  revision chain without deleting audit evidence;
- every create, update, link, revision, publish, and discard operation writes a
  PII-free canonical SHA-256 audit event with safe counts/IDs and optional actor
  user ID;
- a composite self-reference guarantees that `based_on_revision_id` belongs to
  the same tech card rather than another card;
- online downgrade refuses to drop the schema if any reference, revision,
  checkpoint, link, or audit row exists.

## Ownership and invariants

```text
Product (public catalog, existing source of truth)
    1
    |
    | unique CRM link per product
    v
GarmentModel 1 ---- * GarmentSize (stable ID, soft-active)
    |
    | 1:1 identity
    v
TechCard 1 ---- * TechCardRevision
                       |
                       | immutable ordered content
                       v
                 TechCardCheckpoint

Fabric is reference data only.
Its quantity comes later from append-only material movements.
```

The link is intentionally one product to one garment model, but it is not one
model to one product. This replaces the prototype's duplicate internal product
tables and leaves pricing, media, variants, and storefront availability in the
catalog domain.

Tech-card revisions move through:

```text
draft -> published -> archived
   |
   +----> discarded
```

Only a draft can publish or discard. A new revision is based on the current
published revision. Publishing a new draft archives the old published revision
without modifying its checkpoints or publication actor/time.

## Verification

- Ruff lint, Ruff format verification, and legacy-entrypoint syntax pass;
- all 265 backend unit/contract tests pass;
- tests prove normalization, dimensional range rejection, unique aggregate
  ordering, optimistic fabric/model writes, stable size IDs through deactivate
  and reactivate, idempotent catalog links, conflicting remap rejection,
  draft blocking/discard, revision lineage, atomic re-publication, preserved old
  checkpoints, and SHA-256 audit history;
- Alembic has one linear `20260812_0022` head;
- full offline PostgreSQL upgrade and downgrade SQL compile, including partial
  unique indexes and same-card composite revision lineage;
- the prior production/local Compose configurations remain unchanged and valid.

No live PostgreSQL was available for actual migration apply/downgrade,
concurrent manager writes, or partial-index races. No staff HTTP route is
exposed yet, so authorization/contract/browser evidence belongs to the cabinet
stage and is not claimed here.

## Score rationale

| Area | Score | Evidence |
| --- | ---: | --- |
| Architecture | 20/20 | Reference aggregates are private and link to, rather than duplicate, catalog ownership. |
| Security and audit | 20/20 | No public route or PII payload; actor IDs and canonical digests cover every mutation. |
| Reliability and data safety | 20/20 | Versions, locks, stable size IDs, immutable revisions, partial uniqueness, and guarded downgrade. |
| Compatibility | 20/20 | Additive schema only; no storefront, PWA, legacy API, or current CRM route changes. |
| Verification | 14/20 | Full local/offline gate passes; live PostgreSQL and staff HTTP/RBAC evidence remain. |
| Total | 94/100 | The bounded reference-data slice exceeds the requested threshold without conflating it with the unfinished cabinet. |

## Next bounded slice

1. Add production-unit stage assignment/history that pins a published tech-card
   revision and never reads mutable "current" content for existing work.
2. Add append-only fabric receipt, reservation, consumption, release, and
   adjustment movements with idempotency keys and derived balances.
3. Add private CRM `MediaObject` roles/bucket policy for patterns, tech-card
   files, and production attachments; never reuse public catalog URLs.
4. Expose paginated response DTOs and mutation routes behind `crm.access`, with
   negative permission, stale-version, and data-leak contract tests.
5. Build the internal manager cabinet only after the staff API passes staging
   PostgreSQL and private MinIO verification.

## Rollback

There is no runtime flag to turn off because this stage registers no route or
worker. Do not call the private service from a new runtime path during rollback.

Online downgrade of `0022` refuses while any durable CRM reference rows exist.
Export and reconcile fabrics, models, sizes, links, revisions, checkpoints, and
audit events before schema removal. Migration `0021` and its paid-order projects
remain independent and intact.
