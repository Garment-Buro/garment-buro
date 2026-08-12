# План рефакторинга backend Garment Buro

## Текущий прогресс

| Срез | Статус | Оценка |
| --- | --- | ---: |
| Legacy API contracts | Готово | 94/100 |
| Configuration foundation и secret hygiene | Готово | 95/100 |
| Application/database foundation | Готово | 93/100 |
| Catalog schema + MinIO storage foundation | Готово | 92/100 |
| Catalog migration и guarded read cutover | Готово | 94/100 |
| Identity persistence + security foundation | Готово | 93/100 |
| Encrypted notification outbox foundation | Готово | 94/100 |
| Guarded auth API/profile + ownership bridge | Готово, выключено по умолчанию | 94/100 |
| Web/PWA refresh/logout client compatibility | Готово, выключено по умолчанию | 93/100 |
| Guarded catalog writes/settings + RBAC | Готово, выключено по умолчанию | 93/100 |
| Persistent carts + guarded Redis cutover | Готово, выключено по умолчанию | 92/100 |
| Immutable order creation foundation | Готово, ещё не подключено к HTTP | 92/100 |
| Inventory reservations + order state machine | Готово, ещё не подключено к HTTP | 92/100 |
| Deterministic legacy order migration | Готово, ещё не подключено к HTTP | 93/100 |
| Secure target order reads + guarded cutover | Готово, выключено по умолчанию | 93/100 |
| Immutable CDEK shipment foundation | Готово, выключено по умолчанию | 95/100 |
| Guarded CDEK creation worker | Готово локально, sandbox впереди | 94/100 |
| Identity/catalog staging rehearsal | Следующий | — |
| Guest order capability и integrations | Запланировано | — |

Отчёты по завершённым срезам:

- `docs/refactoring/01-configuration-foundation.md`;
- `docs/refactoring/02-application-database-foundation.md`;
- `docs/refactoring/03-catalog-media-storage-foundation.md`;
- `docs/refactoring/04-catalog-migration-read-cutover.md`;
- `docs/refactoring/05-identity-security-foundation.md`;
- `docs/refactoring/06-notification-outbox-foundation.md`;
- `docs/refactoring/07-identity-api-ownership-bridge.md`;
- `docs/refactoring/08-web-pwa-session-compatibility.md`;
- `docs/refactoring/09-guarded-catalog-writes-content.md`;
- `docs/refactoring/10-persistent-cart-cutover.md`;
- `docs/refactoring/11-order-creation-foundation.md`;
- `docs/refactoring/12-inventory-reservations-state-machine.md`;
- `docs/refactoring/13-legacy-order-migration.md`;
- `docs/refactoring/14-secure-order-read-cutover.md`;
- `docs/refactoring/26-cdek-shipment-foundation.md`;
- `docs/refactoring/27-cdek-creation-worker.md`.

## 1. Исходная точка

Рабочий backend сейчас решает основные задачи магазина, но остаётся MVP:

- приложение, ORM-модели, схемы, admin и бизнес-логика собраны в одном `main.py`;
- основная база — SQLite, изменения схемы выполняются через `ALTER TABLE` при старте;
- товары, варианты, заказы и пользователи хранятся в четырёх таблицах;
- состав заказа хранится JSON-строкой, а настройки сайта — JSON-файлами;
- загруженные файлы лежат на локальном диске и раздаются самим FastAPI;
- Redis используется для корзины и кэша каталога, но корзина не имеет постоянного хранилища;
- интеграции с ЮKassa, СДЭК и SMTP вызываются прямо из HTTP-обработчиков;
- admin и изменяющие каталог endpoints не имеют полноценного RBAC;
- тестовые OTP и тестовая инициализация данных присутствуют в рабочем коде;
- staging и production не разделены по данным, бакетам, секретам и процедуре выкладки.

Отдельный каркас в `/Users/mikitaliudchyk/WorkProjects/garment-buro/backend` уже показывает нужное направление и стиль:

- типизированные SQLAlchemy 2.0 models через `Mapped`;
- Pydantic settings и schemas;
- отдельные API-модули;
- repository/client abstractions;
- PostgreSQL, async sessions и будущие модели внутренней CRM;
- заготовки для MinIO, email и оплаты.

Этот каркас пока нельзя подменить вместо рабочего backend: часть routers и clients пустая, MinIO не реализован, migrations и зависимости не оформлены, а CRM-модель не совпадает с действующим API фронтенда. Поэтому миграция будет выполняться внутри рабочего репозитория постепенно, с сохранением текущего API.

## 2. Целевая архитектура

Backend остаётся модульным монолитом FastAPI. Для каждого бизнес-модуля используется один и тот же путь зависимостей:

```text
router -> service -> repository -> SQLAlchemy model
                   -> integration client
```

Целевая структура:

```text
backend/
  app/
    main.py
    api/
      router.py
      dependencies.py
    core/
      config.py
      errors.py
      logging.py
      security.py
    db/
      base.py
      session.py
    modules/
      catalog/
      media/
      identity/
      carts/
      orders/
      payments/
      delivery/
      notifications/
      crm/
      admin/
      settings/
    integrations/
      minio.py
      cdek.py
      yookassa.py
      smtp.py
    workers/
      outbox.py
      reconcile.py
  migrations/
  scripts/
  tests/
    contract/
    unit/
    integration/
```

Правила архитектуры:

1. Router отвечает только за HTTP, validation и вызов service.
2. Service владеет транзакцией и бизнес-правилами.
3. Repository содержит только SQLAlchemy queries и не возвращает HTTP-ошибки.
4. Integration clients не знают о FastAPI и ORM-моделях.
5. PostgreSQL — единственный источник постоянных данных.
6. Redis — только cache, rate limit и краткоживущая координация; потеря Redis не должна терять заказ или корзину.
7. MinIO/S3 хранит бинарные объекты, PostgreSQL — metadata, связи, MIME, размер и checksum.
8. Внешние побочные действия выполняются после commit через transactional outbox worker.
9. Public API сохраняет текущие пути `/api/...` и форму ответов, пока фронтенд не переведён осознанно.
10. Любая миграция имеет downgrade/backup, dry-run и проверку количества записей и файлов.

## 3. Доменные границы

### Catalog и media

- `products`, `product_variants`, категории и остатки;
- `media_objects` и таблицы связей media с product/variant;
- текущие строки с URL через запятую временно собираются response mapper-ом;
- загрузка проверяет MIME и размер, оптимизирует поддерживаемые изображения, записывает объект в MinIO и metadata в PostgreSQL;
- публичные файлы отдаются через S3 gateway/CDN, приватные CRM-файлы — через короткие presigned URLs.

### Identity и кабинеты

- пользователи, роли, permissions, refresh sessions и audit;
- OTP хранится только в виде hash, имеет срок жизни, число попыток и rate limit;
- OTP никогда не возвращается клиенту вне изолированного test environment;
- короткий access token и отзывная refresh session;
- отдельные роли `customer`, `manager`, `admin`;
- профиль и заказы доступны только владельцу или сотруднику с permission.

### Carts, orders и inventory

- корзина хранится в PostgreSQL; guarded API, importer и очистка expiry готовы,
  Redis после переключения не является source of truth;
- guest cart связывается с account после входа;
- `order_items` содержит snapshot названия, цены, варианта и `customization` в JSONB;
- деньги хранятся как `NUMERIC`, а не `float`;
- создание заказа имеет client idempotency key;
- остаток резервируется транзакционно, затем подтверждается или освобождается по состоянию оплаты/заказа;
- статусы меняются через явную state machine и пишутся в историю.

### Payments

- отдельные `payments`, `payment_attempts` и `payment_events`;
- один idempotency key сохраняется в БД и повторно используется при сетевом retry;
- webhook event дедуплицируется и сохраняется до обработки;
- перед переводом заказа в `paid` состояние платежа перепроверяется через API провайдера;
- поддерживаются `succeeded`, `canceled`, возвраты и повторная сверка зависших платежей;
- ошибка webhook не маскируется успешным ответом до сохранения события.

### Delivery / CDEK

- единый typed client с timeout, retry policy и кэшем OAuth token;
- расчёт тарифа использует фактические размеры и вес всех order items;
- создание отправления идемпотентно относительно заказа;
- provider UUID, номер, тариф, labels и история статусов хранятся отдельно;
- статусы обновляются webhook-ом, а scheduled reconciliation страхует пропущенные события;
- чтение кабинета не делает синхронный запрос в СДЭК для каждого заказа.

### Notifications

- письмо ставится в outbox в той же транзакции, что и изменение заказа/OTP;
- отдельный worker отправляет письма с retry/backoff;
- результат, число попыток и безопасная причина ошибки хранятся в БД;
- шаблоны отделены от SMTP transport и тестируются snapshot-тестами.

Зашифрованный outbox, история попыток, SMTP transport и worker готовы как
изолированный фундамент. Подключение OTP к outbox в одной транзакции выполняется
вместе с HTTP auth/profile cutover, чтобы не менять текущий контракт частично.

### Internal CRM

Storefront catalog не смешивается с производственной CRM. Начатые сущности `Fabric`, `Model`, `TechCard`, `TechCardCheckpoint` и размеры переносятся в отдельный модуль CRM и связываются с catalog через явные IDs. Далее добавляются production orders, движения материалов, комментарии, назначения сотрудников и audit log.

## 4. Этапы миграции

### Этап 0. Безопасность и фиксация контрактов

- заменить и отозвать ключи, которые когда-либо находились в исходниках;
- убрать секретные default values и проверить Git history;
- закрыть admin и изменяющие endpoints;
- сделать backup SQLite и uploads;
- добавить contract tests текущих products, auth, cart, orders, settings и uploads responses;
- зафиксировать frontend API types как переходный контракт.

Результат: текущий продукт защищён, а рефакторинг не может незаметно сломать фронтенд.

### Этап 1. Новый каркас рядом с legacy — завершён

- создать `app/`, единый settings object, logging, error mapping и lifespan;
- добавить Ruff, type checking, pytest и общую команду проверки;
- добавить `/health/live` и `/health/ready`;
- оставить legacy endpoints подключёнными до переноса соответствующего модуля.

Результат: новая архитектура запускается без изменения пользовательского поведения.

### Этап 2. PostgreSQL, Alembic, MinIO и окружения — в работе

- добавить PostgreSQL и healthchecks в local compose — готово;
- использовать Alembic вместо `create_all` и `ALTER TABLE` для новых модулей — готово;
- добавить MinIO и проверяемые storage settings — готово;
- разделить configuration для local, test, staging и production;
- развести базы, Redis namespaces и MinIO buckets по окружениям;
- добавить backup/restore runbook.

Результат: инфраструктура готова, но production traffic ещё работает на legacy data path.

### Этап 3. Catalog и media как пилот

- добавить целевые products/variants/media models и MinIO service — готово;
- перенести products/variants read repository и service — готово;
- сохранить текущий JSON-контракт фронтенда — готово для GET;
- мигрировать settings JSON в PostgreSQL — importer, revision history и
  fingerprint guard готовы;
- перенести uploads в MinIO с checksum-отчётом — importer готов, staging apply следующий;
- выполнить dry-run SQLite -> PostgreSQL и сравнить responses старого и нового API — готово на текущем snapshot;
- перенести catalog writes только вместе с RBAC — готово под default-off
  backend/frontend cutover-флагами;
- закрыть прямой SQLAdmin и отдельный variant write — готово при включённом
  write cutover.

Результат: каталог и файлы работают через PostgreSQL/MinIO без изменения UI.

### Этап 4. Авторизация и кабинеты

- перенести users и профиль — guarded HTTP boundary и deterministic importer готовы;
- реализовать безопасный OTP, access/refresh sessions, rate limits и logout/revoke — backend готов;
- добавить customer/manager/admin RBAC — schema, system permissions и guard service готовы;
- закрыть admin API и SQLAdmin — catalog mutations и SQLAdmin готовы; orders/CRM
  admin boundaries переносятся с соответствующими доменами;
- добавить сценарии web, PWA, повторного входа и смены email — guarded client
  refresh/logout готов, isolated staging browser/PWA rehearsal следующий;
- включать `IDENTITY_API_ENABLED` и собранный
  `NEXT_PUBLIC_IDENTITY_SESSION_V2_ENABLED` только одним cutover.

Результат: единая безопасная авторизация для web и установленного PWA.

### Этап 5. Корзина, заказ и остатки

- перенести persistent carts — готово под default-off backend-флагом;
- перенести order items — immutable snapshots и PostgreSQL schema готовы;
- перенести stock reservations — транзакционный reserve/confirm/release/expire
  service, счётчики и фоновые bounded batches готовы;
- добавить idempotent checkout — target order/reservation/guest capability/
  payment attempt теперь готовятся атомарно, deterministic replay продолжает
  частичное состояние, а provider POST идёт только после commit; default-off
  HTTP route и web/PWA key persistence ещё впереди;
- связать guest/account carts;
- реализовать state machine и audit history — явные переходы оплаты, отмены,
  отправки, завершения и истечения с versioned history готовы внутри service;
- мигрировать существующие Redis carts без потери `customization` — deterministic
  dry-run/apply и fingerprint guard готовы, staging rehearsal следующий.
- мигрировать существующие SQLite orders — PII-minimized dry-run, fingerprint
  guard, сохранение ID/items/customization/status/provider refs и count-exact
  apply готовы; target HTTP reads пока не включены.
- включить secure target reads — owner/verified claim и staff RBAC paths готовы
  под default-off fingerprint guard;
- добавить безопасный guest result access — hashed, expiring, revocable opaque
  capability и одинаковый `404` готовы; обязательная выдача из target checkout,
  browser/PWA storage и frontend result path ждут согласованного cutover.

Результат: повторный запрос, restart или потеря Redis не создают дубликат и не теряют заказ.

### Этап 6. ЮKassa, CDEK и email worker

- перенести внешние clients за interfaces — instance-scoped async YooKassa
  GET/create adapter готов; canonical receipt builder, persisted request digest,
  same-key retry и linked-provider reconciliation готовы под default-off флагом;
  CDEK immutable logistics snapshots, encrypted canonical request digest,
  shipment aggregate, prepared event, async provider adapter, claim-before-I/O
  worker and fail-closed unknown quarantine готовы под независимыми default-off
  flags; verified client-number recovery/webhook/sandbox proof ещё впереди;
- добавить payment/delivery events и transactional outbox — durable payment,
  numbered attempts, persisted provider idempotence key, PII-minimized incoming
  events, email outbox foundation и PII-free paid-order commands для email/CDEK/
  CRM готовы; fulfillment consumer и delivery events впереди;
- реализовать verified и idempotent webhook handlers — raw-body parse, official
  IP allowlist, semantic dedup, provider GET verification и bounded worker
  готовы; default-off HTTP boundary, bounded streaming body и explicit trusted
  proxy chain готовы, deployment cutover ещё не выполнялся;
- добавить reconciliation jobs и retry policy — отдельная durable job-модель,
  active/unknown seeding, claim-before-GET, missed-webhook recovery, bounded
  interval/retry и atomic payment/order/inventory apply готовы; staging ещё не
  выполнялся;
- добавить безопасное создание платежа — immutable item/delivery receipt lines,
  явный 54-ФЗ config, commit-before-POST, 23-hour same-key/body recovery,
  terminal create rejection и сохранение provider ID для GET recovery готовы;
  публичный checkout route намеренно не подключён до accounting/sandbox gate;
- отделить post-payment side effects — payment create/webhook/reconciliation
  атомарно публикуют уникальные команды с exact succeeded-attempt evidence;
  crash-safe claim/retry/dead-letter history и encrypted email handoff готовы;
  database-only CDEK shipment handoff и отдельный network worker готовы и
  включаются разными флагами; неоднозначный POST не повторяется автоматически,
  пока client-number recovery не подтвержден sandbox; PII-free CRM paid-order
  intake и versioned project audit готовы под отдельным default-off флагом;
  real SMTP и staging proof впереди;
- прогнать sandbox сценарии успеха, отмены, timeout, duplicate webhook и недоступности провайдера.

Результат: внешние интеграции не блокируют HTTP-транзакцию и восстанавливаются после временных ошибок.

### Этап 7. CRM

- добавить PII-free intake оплаченного заказа — уникальный production project,
  quantity-expanded units, immutable source evidence, optimistic lifecycle и
  append-only events готовы под default-off fulfillment-флагом;
- перенести fabrics, garment models, sizes, tech cards и checkpoints —
  versioned reference aggregates, stable size identities, explicit catalog
  links, immutable tech-card revisions и checksum audit готовы; private staff
  API и live PostgreSQL proof впереди;
- добавить production orders и material movements — paid-order units теперь
  получают immutable plan revisions, pinned published tech cards/sizes,
  optimistic unit workflow и append-only events; fabric receipt/reserve/
  release/consume/adjustment ledger, idempotent commands и derived locked
  balances готовы; private API и live PostgreSQL proof впереди;
- добавить manager permissions, audit и приватные CRM-файлы в MinIO;
- связать CRM-модель с catalog/order items без публикации внутренних данных наружу.

Результат: CRM развивается независимо от публичного магазина.

### Этап 8. Staging, production и удаление legacy

- развернуть staging на отдельной БД, buckets, домене и provider sandbox credentials;
- выполнить migration rehearsal на копии production data;
- сделать blue/green cutover с проверкой counts, checksums и API-contract tests;
- настроить JSON logs, request IDs, alerts, DB/MinIO backups и restore drill;
- после периода стабильности удалить SQLite, local uploads, startup migrations, mock injection и legacy `main.py`.

Результат: production переключён с проверяемым rollback, legacy удалён только после подтверждения стабильности.

## 5. Порядок первых коммитов

1. `test(backend): capture legacy API contracts`
2. `security(backend): remove embedded credentials and protect admin writes`
3. `refactor(backend): add application and configuration foundation`
4. `feat(infra): add postgres minio and migration tooling`
5. `refactor(catalog): move products behind service and repository`
6. `feat(storage): migrate media to minio`

Каждый коммит должен проходить общий check и не менять API-контракт без отдельной согласованной миграции фронтенда.

## 6. Definition of Done для каждого модуля

- router не содержит SQLAlchemy queries и provider SDK calls;
- service покрыт unit tests;
- repository покрыт PostgreSQL integration tests;
- API покрыт contract tests;
- migrations проверены upgrade и downgrade;
- authorization и ownership проверены негативными тестами;
- retries и duplicate events проверены отдельно;
- PII и secrets отсутствуют в logs;
- staging сценарий пройден через реальный HTTP path;
- документация и environment example обновлены;
- rollback описан и проверяем.

## 7. Первая рабочая итерация

Начинаем с Этапа 0 и первого коммита: фиксируем действующие API-контракты, готовим изолированную test database и исключаем сетевые вызовы из тестов. После этого можно безопасно выносить application/config/database foundation, не ломая ветку `refactoring` фронтенда.
