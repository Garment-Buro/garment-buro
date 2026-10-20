# Retire the public delivery demo and duplicate provider clients

Confirmed: only `/cdek-test` consumes Next's CDEK/geocoding endpoints.
Its failure path substitutes demo offices and a fixed-parcel demo quote.
Checkout already uses backend `/api/cdek/points` and `/api/cdek/calculate`.
Keep its real directory, quote proof, shared Yandex map and office types.
Keep the agreed 80 RUB placement policy unchanged.

- [x] Remove the lab, its exclusive data/helpers/provider clients/endpoints and
  `/service.php` rewrite; retain the checkout map and backend API boundary.
- [x] Narrow architecture checks so frontend fetch lives only in the browser
  HTTP client or internal backend HTTP client; verify shared office helpers.
- [x] Run frontend checks and production-built HTTP/browser verification of
  retired routes and checkout pickup/quote behavior with synthetic HTTP data.
- [x] Refresh the offline project map and release evidence, distinguishing
  source cleanup from production deployment and live CDEK integration checks.

Evidence:465 frontend tests passed,0 skipped; full ESLint and production build
passed (existing AlumniSansSC fallback warning). Five tests belonged exclusively
to retired demo clients. Production-built Next with a synthetic HTTP backend
passed404 checks for the lab, PHP alias and old GET/POST API; verified actual
Next rewrite traffic, directory error without demo data, retry, selection and
cart-based quote displayed as2000+250=2250 RUB. Widths320/390/736/1280, no JS
errors/overflow. Inspected screenshot. Test-process-only DNS resolved Compose's
backend hostname to loopback; no build files or host DNS changed. Fixture and
Next processes stopped. No orders written or live provider calls. The frontend
map now has185 reachable components and424 file explanations. Production, price
policy and backend unchanged; no Git stage/commit/push/deployment.
