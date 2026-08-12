# Stage 1: configuration foundation and secret hygiene

Status: complete for the branch

Quality score: 95/100

## Delivered

- one typed `Settings` object for legacy and refactored modules;
- explicit `local`, `test`, `staging`, and `production` environments;
- fail-fast validation of all critical staging/production secrets;
- minimum length validation and masked representation for `JWT_SECRET`;
- deduplicated CORS allowlist with wildcard rejection;
- no CDEK, YooKassa, SMTP, or JWT credential fallback in Python source;
- lazy provider configuration, so importing the application performs no provider request;
- provider use without credentials fails before network access;
- Redis connection logs no longer include its URL;
- payment webhook bodies and recipient addresses are no longer printed;
- Docker Compose passes the same explicit environment contract in local and production;
- `.env.example` documents every setting without supplying secret values;
- the operational SMTP check is outside the pytest suite;
- a reproducible Ruff and pytest gate is available through `make check`;
- legacy FastAPI startup hooks were consolidated into a lifespan;
- Pydantic 2 and naive UTC deprecation warnings were removed from the exercised path;
- email login and Bearer-token round trips remain covered by contract tests.

## Evidence

- `make -C backend check PYTHON=../.venv/bin/python`: passed;
- Ruff lint: passed;
- Ruff format check: passed;
- legacy `main.py` syntax check: passed;
- unit, contract, auth, and image migration tests: 22 passed;
- production Compose configuration with complete settings: valid;
- local Compose configuration with optional providers disabled: valid;
- current backend source scan contains no embedded provider key fallback or live-key prefix.

## Score rationale

| Area | Score | Evidence |
| --- | ---: | --- |
| Architecture | 24/25 | Settings and integration boundaries are centralized; database configuration still initializes the legacy sync engine. |
| Security | 23/25 | Current source and logs are clean; previously exposed provider credentials still require external rotation and history handling. |
| Compatibility | 24/25 | Existing frontend routes and real email-auth token flow are covered; production provider calls are intentionally not executed locally. |
| Verification | 24/25 | Tests, lint, format, syntax, and both Compose variants pass; Docker runtime was unavailable locally. |
| Total | 95/100 | Stage threshold exceeded. |

## Required before production deployment

1. Rotate every provider credential that existed in repository history.
2. Set a new unique `JWT_SECRET` of at least 32 characters per environment.
3. Fill staging with sandbox CDEK/YooKassa credentials and production with live credentials.
4. Decide on coordinated Git-history cleanup; do not rewrite shared history silently.
5. Run the same gate inside the backend container when the Docker runtime is available.

These operational items do not block the next refactoring stage, but they do block deployment of this branch to production.
