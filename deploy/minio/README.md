# MinIO для Garment Buro

MinIO остаётся хранилищем media, CRM и проектов. Готовый upstream image больше
не требуется: Dockerfile собирает официальный security release
[`RELEASE.2025-10-15T17-29-55Z`](https://github.com/minio/minio/releases/tag/RELEASE.2025-10-15T17-29-55Z).
Он содержит исправление обхода session policy, опубликованное после прежней
версии проекта от 23 июля 2025 года.

## Зафиксированные входы сборки

Dockerfile содержит полный commit upstream, SHA-256 архива исходников и digest
multi-architecture образа Go. `go.mod` / `go.sum` берутся из этого архива;
`go mod verify` проверяет загруженные модули, `-mod=readonly` запрещает менять
список зависимостей. `GOTOOLCHAIN=local` исключает неявное скачивание другого Go.
`latest` и готовые бинарники MinIO не используются. Runtime содержит сам MinIO,
небольшую healthcheck-команду, CA, данные часовых поясов, upstream LICENSE и
исходный архив `/usr/share/minio/source.tar.gz`.

Это воспроизводимый путь установки из зафиксированных входов, а не обещание
побитового совпадения всего OCI-архива: metadata экспортёра и build provenance
могут различаться. Сохраняйте digest образа и SHA-256 экспортированного архива.

## Сборка и перенос

Из корня репозитория, на сборочном Docker-хосте с Buildx:

```bash
docker buildx build --platform linux/amd64 --load \
  --tag garment-buro-minio:2025-10-15-garment1 deploy/minio
docker image save --output garment-buro-minio.tar \
  garment-buro-minio:2025-10-15-garment1
shasum -a 256 garment-buro-minio.tar
```

Сверьте SHA-256 после доставки архива на сервер, затем загрузите образ:

```bash
sha256sum garment-buro-minio.tar
docker image load --input garment-buro-minio.tar
docker image inspect --format '{{.Id}}' garment-buro-minio:2025-10-15-garment1
```

Значение `MINIO_IMAGE` в серверном окружении должно указывать на подготовленный
образ. Можно использовать загруженный image ID или заранее проверенный registry
digest. Server Compose имеет `pull_policy: never`; автоматического fallback на
Docker Hub или сборки на production нет. Скрипт выпуска проверяет наличие образа
до загрузки приложений, остановки writers и backup. Сборка/публикация образа и
сам storage cutover остаются отдельными операциями выпуска.

Local Compose собирает тот же Dockerfile через `docker compose up --build`.
CI backend и container gate собирают его перед тестами, без публикации в registry.
Runtime smoke принимает `--minio-image`, поэтому подготовленный digest можно
проверить явно; окружение случайного Docker-хоста не подменяет выбранный образ.

## Данные и здоровье

Volume `/data`, root credentials, S3 endpoint9000 и console9001 сохраняют прежний
контракт. Номер пользователя остаётся 0 для совместимости с существующими
файлами; серверный deploy требует rootless Docker. Рекурсивного `chown` при старте
нет. Healthcheck использует только loopback `/minio/health/live`, принимает
только HTTP200, не следует redirect и имеет timeout. В runtime не нужны curl,
shell или отдельный mc. Healthcheck проверяет живость процесса; доступность и
приватность конкретных бакетов проверяют backend readiness и S3 integration tests.

Перед переключением нужен согласованный backup с остановленными writers и
MinIO. Старый бинарник не запускают поверх уже обновлённого volume в расчёте на
автоматический downgrade: возврат проверяют на отдельном volume из прежнего
архива. Полный restore БД и файлов должен сохранять их общую границу записей.

Проверка сборки сама по себе не подтверждает сохранность данных, запуск Next или
доступность production. Текущие доказательства находятся в
[журнале рефакторинга](../../docs/release-refactoring.md).
