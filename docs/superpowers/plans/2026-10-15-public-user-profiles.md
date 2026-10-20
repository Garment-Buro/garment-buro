# Public user profiles implementation plan

> **For agentic workers:** Execute inline in the existing working copy with
> superpowers:executing-plans, TDD and independent review at each deliverable.

**Goal:** Replace demo people with published profiles owned and edited by real
users, with safe personal images and bounded server-rendered lists.

**Architecture:** `public_profiles` is separate from identity and partners.
User ownership comes exclusively from the authenticated identity. Public reads
project published fields and join only active users. Customer writes serialize
with account deletion and compare a profile version. Reuse public list hooks
and existing private media storage/lifecycle instead of browser persistence.

**Tech Stack:** FastAPI, SQLAlchemy/Alembic, PostgreSQL, MinIO, Next.js/React.

**Spec:** `docs/superpowers/specs/2026-10-15-public-people-and-communities-design.md`.

## Global constraints

- Preserve existing dirty worktree; no stage, commit, push or deployment.
- Public fields never copy private email, phone, birth date, orders or projects.
- Existing users have no public profile until explicitly created and published.
- Every directory has bounded SQL, literal search and query-bound keyset cursor.
- API DTOs are explicit; unavailable, empty and error remain distinct.
- Profile ownership is unrelated to partner roles and commissions.
- Whole release remains active after any individual task; remaining work stays explicit.

## Task 1: Profile storage, ownership and public reads

**Files:** Create `backend/app/modules/public_profiles/{models,schemas,repository,service,router}.py`;
`backend/migrations/versions/20261015_0063_public_user_profiles.py`;
`backend/tests/contract/test_public_profiles.py`.
Modify `backend/app/db/models.py`, `backend/app/factory.py`, deleted-account
purge in `backend/app/modules/customer_projects/lifecycle_repository.py`;
add migration/schema coverage in `backend/tests/integration/test_public_profile_schema.py`
and use the existing ORM comparison in `backend/tests/integration/test_postgres_schema.py`.

**Interfaces:**

```text
GET /api/people?query=&sort=newest|name&limit=24&cursor=...
  -> {items:[{id,slug,display_name,bio}],next_cursor:string|null}
GET /api/people/{slug} -> {id,slug,display_name,bio} or404
GET /api/profile/public -> {id,slug,display_name,bio,is_published,version} or null
PUT /api/profile/public
  {slug,display_name,bio,is_published,version}
  -> owner DTO; version0 creates, existing version must match; conflicts409
```

- [x] RED through FastAPI on SQLite/PostgreSQL: no automatic profiles, auth,
  own create/read/edit, draft/public/unpublish, private account unchanged,
  duplicate slug409, stale version409, forbidden unknown fields422,
  inactive users404, no private DTO fields. Use seed_favorites only for two
  real OTP accounts; all assertions target real routes and stored rows.
- [x] Implement explicit schemas (lowercase ASCII slug3..64, trimmed public
  name1..120, bio0..2000, NUL excluded, extra fields forbidden), unique user
  and slug constraints, positive version, FK cascade. Write locks active User
  first, then reads its row with fresh SQL and compares version.
- [x] RED directory: newest/name complete traversal, literal `%`/`_`,
  mismatched/malformed/oversized/NUL cursor422, max100, single scalar SELECT
  with LIMIT, active/published policy shared by slug read. Implement query
  fingerprint including directory namespace; cursor max4096.
- [x] RED lifecycle/migration: deleted-account purge bounded/dry-run,
  upgrade/downgrade preserving users and communities, unique constraints and
  user FK cascade, ORM comparison. PostgreSQL concurrent same-version writes
  yield one200 and one409; concurrent first create/slug collision is explicit.
- [x] Focused and authoritative full PostgreSQL/MinIO tests, Ruff, independent
  review. Record concrete evidence and remaining media/frontend tasks.

**Task1 evidence (2026-10-15):** Focused API/PostgreSQL concurrency/migration
and ORM comparison57 passed. Authoritative full backend738 passed, no skips,
real PostgreSQL17/MinIO (193.75s, final run after the no-store404 fix).
The unpublish404 header regression was observed RED, then GREEN on SQLite and
in the full SQLite/PostgreSQL run; independent delta review was also clean.
Ruff app/tests/scripts and new migration
passes;11 touched/new files checked for formatting. Independent backend core
review found no Critical/Important or Minor issues. Existing lifecycle report
expectations now include `public_profiles`; linear head check includes0063.
Four owned test databases removed by the runner; shared services preserved.
No frontend People wiring, avatar implementation, commit or deployment yet.

## Task 2: Safe avatar media and revocation

**Files:** Extend public profile model with MediaObject FK and versioned
owner avatar operations, plus focused photo service/router/repository/tests.
Use shared media validation/intake where it preserves project semantics;
extend existing bounded private media cleanup and its tests.

**Interfaces:** owner multipart upload bounded8MiB, decoded JPEG/PNG/WebP
single frame bounded16M pixels; normalize orientation, drop metadata and
resize avatar512px WebP. Store private object in MinIO. Public avatar URL is
an API endpoint checking publication and active user on every read, no-store;
draft owner preview uses authenticated binary fetch. No raw public bucket URL
or arbitrary remote URL is accepted. Owner mutation compares version.

```text
POST /api/profile/public/avatar?expected_version=N (multipart file)
  -> owner DTO, 201; profile must already exist; avatar_id is read-only
DELETE /api/profile/public/avatar?expected_version=N
  -> owner DTO, 200; no storage dependency needed to remove the attachment
GET /api/profile/public/avatar/{media_id} -> authenticated current draft bytes
GET /api/people/{slug}/avatar/{media_id} -> current published active-user bytes
```

Both photo writes increment the profile version and reject stale edits409.
Binary reads verify size and checksum, use no-store/nosniff and release the SDK
response connection even when reading/closing fails. Replacing/removing an old
photo resets its retention timestamp; referenced draft photos remain protected.

Implementation notes after core review:

- Create the draft profile explicitly before attaching a photo; photo upload
  never creates or publishes an account/profile as a side effect. Compare the
  same profile version again after durable pending creation, before object PUT
  and attachment, so a concurrent text save cannot be overwritten.
- Keep the owner upload in the existing private customer bucket under a
  separate `profiles/{user_id}/{uuid}.webp` namespace. Project-image access must
  continue to reject that namespace. Shared image intake and cancellation-safe
  storage writes belong in media/integrations, not imports from another domain's
  service. Preserve existing project-image quality and dimensions.
- Public photo addresses include the current media ID; old addresses return404
  after replacement. API reads check current publication, account status and
  current attachment before reading bounded bytes, with no redirects to a
  lasting storage URL. Closing the storage response must also release its
  connection on errors and cancellation.
- Add a nullable MediaObject FK to the profile, so existing metadata-driven
  reference checks protect attached photos. Extend cleanup only to the exact
  profiles namespace; replaced photos become unreferenced, while an unpublished
  profile retains its private attachment. No new storage service or public
  bucket is required.

- [x] RED valid/corrupt/oversized/decompression-bomb/animated image cases,
  ownership, private bucket requirement, upload failure, cancellation and
  durable pending recovery. Implement normalized image and durable writes.
- [x] RED public avatar access after publish/unpublish/block/delete and old
  photo replacement. Implement gated reads, immediately revoke public access;
  retain unpublished photo privately for owner, cleanup unreferenced originals.
- [x] Real MinIO upload/read/delete and bounded lifecycle concurrency,
  deleted-account purge; extend migration/metadata coverage, run full checks
  and independent review. No test can silently use fake storage in the full run.

**Task2 evidence (2026-10-15):** Required real PostgreSQL/MinIO integration
proves private raw storage, gated reads across application restart, replacement
retention, deleted-account purge, single/repeated cancellation, post-pending
version recheck and concurrent photo saves. Contract boundary tests explicitly
use a test SDK; integration tests use real storage without fallback. Focused
API/MinIO/core/schema run62 passed; subsequent full run includes the added0064
roundtrip and SDK read/close cleanup checks. Final authoritative full backend
**764 passed**, no skips, real PostgreSQL17/MinIO,763.82s. Ruff app/tests/scripts
and migration passes;24 touched/new files pass formatting. Independent photo
review found no Critical/Important/Minor issues.

The first full run reached762 passed with two pre-existing recovery tests
failing because their module-level NOW preceded actual operator recovery time
by more than five/six minutes. A controlled one-hour operator clock reproduced
both failures RED. Tests now schedule their worker after the stored
available_at; all four recovery tests GREEN and independent delta review clean.
Production order code is unchanged. Full suite was rerun after this repair.
No frontend change, stage, commit, push or deployment in Task2; Task3 remains
required and the whole release remains active.

## Task 3: Public pages, owner editor and real people directory

**Files:** `frontend/lib/{catalog,api,server/backend}/people.ts`,
`frontend/hooks/people/`, `frontend/components/people/`, `frontend/app/people/[slug]/page.tsx`;
replace people branch in platform components and remove servicePeople data/assets
only after checking consumers. Link private ProfileSettings to public editor.

Photo rendering must preserve revocation: use a direct image request to the
gated API (native img or Next Image with optimization disabled), never the Next
image optimizer's lasting cache. Owner draft previews fetch authenticated bytes,
create a temporary blob URL and revoke it on replacement, unmount and session
change; no access token goes into image URLs or browser persistence.

Frontend implementation notes:

- Public profile IDs are not identity user IDs. Determine own controls by
  comparing the authenticated own-profile DTO ID with the public profile ID;
  never add private user IDs to the public DTO for this purpose.
- Keep the public editor separate from private identity settings; link to it
  from ProfileSettings. Do not populate public name/bio from private account
  fields automatically. Reuse account-lifetime guards, not the private form's
  field model.
- A photo mutation advances the same version but must preserve unsaved public
  text. Publication is a separate explicit action on confirmed fields; require
  saving pending text before publishing. Unpublish sends the confirmed fields
  immediately and retains unsaved text privately. A409 retains the draft and offers an explicit
  reload that clearly discards those edits.
- Distinguish a backend404 from network/503 when rendering the server public
  route. Only actual unavailable profiles become404; transient failures offer
  a genuine server refresh rather than a fabricated empty profile.

- [x] RED HTTP boundary, abort/error, account-lifetime editor tests. Implement
  bounded client/server helpers using usePublicCatalog; public route is dynamic
  no-store with server404 and genuine error retry. Explicit avatar fallback.
- [x] Owner editor loads only its authenticated DTO and uses matching version.
  Preserve unsaved fields on errors409; explicit reload and separate publication
  action; own controls only after current session ready, backend is authoritative.
- [x] First people cards load in parallel with clothing/communities on /;
  no duplicate browser GET. People category uses actual search/pages and links.
  Remove demo people arrays and crops after last consumer.
- [x] Browser real backend/storage: SSR without JS, two accounts/guest,
  self-edit versus foreign read, draft/published/revoked avatar, conflict/error,
  query cancellation and24+ pages;320/390/736/1280 screenshots and no JS errors.
- [x] Full tests/lint/build and independent review; update local HTML map,
  offline checks, journal, owned fixture cleanup. Release remains active for
  owner collections/editor, canvas races, pricing, orders and release validation.

**Task3 evidence (2026-10-16):** Five new HTTP/server boundary tests and nine
account-lifetime editor tests pass. Three tests execute the actual service worker
and protect navigation privacy, old-cache eviction and offline assets/API
boundaries. The final full frontend run has **415 passed**, no skips; ESLint and
production build including TypeScript pass. Build retains the existing Alumni
Sans SC fallback warning; Node retains the package module-type warning.
The backend was unchanged in Task3; its latest authoritative run is764 passed
with real PostgreSQL/MinIO from Task2.

Real Chromium → Next/FastAPI/PostgreSQL17/MinIO proves SSR without JavaScript,
no repeated first People GET,33 profiles traversed24+9, literal search, sorting,
initial/next-page/SSR errors and genuine retries, query cancellation, profile404
versus503, direct revocable avatar URLs and initials fallback. Owner checks use
two real synthetic OTP accounts and guest: blank opt-in draft, photo upload and
authenticated blob preview, retained unsaved text, explicit publication,
public-profile-ID self/foreign link, actual stale409 and explicit reload,
503/save retry, dirty unpublish, actual PWA offline shell and cross-tab logout
while a private GET is pending.320/390/736/1280 screenshots have no overflow or
JavaScript errors. Independent reviews have no remaining findings.

Two Important review findings were reproduced RED then fixed: v2 SW saved
no-store navigation HTML and replayed revoked profiles offline; v3 only caches
the generic shell/assets and removes old documents. Dirty unpublish originally
required saving published edits; it now hides confirmed fields while retaining
the draft. Browser inspection also removed the unrelated floating site header
from the two new profile routes, with a route-boundary regression test.

The standalone local map now has186 reachable components,427 TypeScript file
descriptions and16 page shells, including the People catalog/public page/editor.
Four offline harnesses pass at320/390/736: five tabs, source navigation and state
restore, no HTTP/JavaScript errors/overflow. Screenshots inspected.
The owned fixture processes exited; its exact PostgreSQL database, three MinIO
buckets/five synthetic objects, both private login configs and input image are
removed. Shared PostgreSQL/MinIO remain; MinIO health200. No stage, commit, push
or deployment. The whole release remains active for owner collections/landings,
canvas/account races, pricing/hardware, order states/pages, remaining code/assets,
real-phone performance, container release/restore/compatibility and public E2E.
