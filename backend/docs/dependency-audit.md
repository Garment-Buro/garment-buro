# Зависимости backend — 18 октября 2026

До обновления полностью разрешённый production-набор для Python3.12 содержал
известные advisories для шести библиотек: AnyIO, idna, PyJWT, python-dotenv,
python-multipart и Starlette. pip-audit вернул49 записей с31 различным
идентификатором: в ответе встречались дубликаты. Это отчёт по версиям пакетов,
а не доказательство31 доступного извне сценария атаки.

Отдельный аудит старой рабочей `.venv` также обнаружил SQLAdmin и старые
транзитивные пакеты. SQLAdmin уже отсутствовал в серверных requirements и
runtime; остаток установленного окружения нельзя считать составом нового
образа. Проверка нового набора выполняется в чистом окружении.

## Изменение версий

| Пакет | До | После |
| --- | --- | --- |
| FastAPI | 0.128.8 | 0.143.3 |
| Starlette | 0.49.3 | 1.8.0 |
| AnyIO | 4.12.1 | 4.14.2 |
| idna | 3.11 | 3.15 |
| PyJWT | 2.10.1 | 2.15.1 |
| python-dotenv | 1.2.1 | 1.2.2 |
| python-multipart | 0.0.20 | 0.0.32 |
| pytest, только разработка | 9.0.2 | 9.0.3 |

Полный resolver также зафиксировал multidict6.9.1 и urllib3 2.8.0. Неиспользуемый
aiofiles удалён из исходного набора. SQLAdmin и прежний SDK YooKassa не входят
в новый lock. Прикладные сервисы и формула цены от80₽ не менялись.

## Воспроизводимая установка

`.in` задаёт версионную политику; `.txt` — сгенерированный полный набор, включая
транзитивные зависимости и SHA256 допустимых дистрибутивов. Universal lock
содержит46 production и55 development entries, включая условный Windows-пакет.
На текущей macOS/Python3.12 устанавливаются54 development-пакета. В Docker
production устанавливается только `requirements.txt` с обязательными хешами.

Из корня репозитория, генератор uv0.10.6:

```sh
uv pip compile backend/requirements.in --universal --python-version 3.12 --generate-hashes --output-file backend/requirements.txt
uv pip compile backend/requirements-dev.in --universal --python-version 3.12 --generate-hashes --output-file backend/requirements-dev.txt
uv pip sync --python backend/.venv/bin/python --require-hashes backend/requirements-dev.txt
cd backend
.venv/bin/python -m scripts.check_dependencies
```

`sync` удаляет пакеты, отсутствующие в lock: использовать выделенную `.venv`
этого проекта. Скрипт сверяет версионную политику с lock и требует одинаковые
production-версии, markers и hashes в development-наборе. Он включён в
`make check`; восемь проверок отклоняют drift, отсутствие хешей, дубликаты,
неполный lock и забытое обновление после изменения `.in`.

## Проверка уязвимостей

```sh
uv tool run --from pip-audit==2.10.1 pip-audit --strict --disable-pip --require-hashes -r backend/requirements.txt
uv tool run --from pip-audit==2.10.1 pip-audit --strict --disable-pip --require-hashes -r backend/requirements-dev.txt
```

Оба набора дают0 известных advisories на18 октября. Исключений `--ignore-vuln`
нет. Auditor читает полный зафиксированный граф без pip resolution; новые
версии не выбираются во время аудита. В CI auditor установлен в отдельную
временную venv, чтобы его собственные зависимости не меняли приложение.
Ошибка сервиса или неполный audit не считаются успешной проверкой.

## Совместимость runtime

Новый FastAPI сохраняет дерево включённых routers. Четыре проверки регистрации
API используют `iter_route_contexts`, а HTTP middleware кеширует эффективные
шаблоны с префиксами. Один router под двумя разными префиксами проверен для200
и405: в журнале остаётся конфигурационный шаблон, без параметров или query.
Повторное сопоставление читает путь только для выбора постоянного шаблона.

Встроенные tracing/metrics/logs/operation spans и автоматическая настройка
exporters явно выключены в factory. Диагностика остаётся в собственном
структурированном middleware без сырых exception messages и request payload.
Добавление OpenTelemetry требует отдельной политики экспорта данных.

Чистая установка Python3.12 с проверкой hashes и `uv pip check` прошла.
Профильные startup/auth/catalog/logging проверки:33 passed; проверки lock:8 passed.
Полный backend:1021 passed,0 skipped за267.64s на Python3.12.12. Созданы
собственный PostgreSQL17 cluster, четыре отдельные БД и MinIO из официального
тега RELEASE.2025-07-23T15-54-02Z. Native MinIO собран локально из этого тега:
прежняя публичная загрузка бинарника возвращает410. Это не официальный Docker
образ или его runtime-проверка. Процессы, БД, объекты и приватный конфиг удалены.
Ruff/format562 файлов и offline SQL upgrade/downgrade прошли. Точный audit step
из CI выполнен локально в отдельной venv с exit0; это не запуск Actions.
Рабочая `backend/.venv` также синхронизирована:54 пакета, прежних SQLAdmin,
YooKassa SDK, WTForms и aiofiles нет; pip check успешен. На её Python3.14.3
повторены41 startup/auth/catalog/logging/lock проверка, все прошли. Полный
прогон1021 относится к Python3.12, соответствующему Docker/CI.
Starlette пока предупреждает об устаревшем httpx для TestClient; используемый
httpx0.28.1 сохранён, переход тестового клиента на httpx2 — отдельное изменение.
Docker/Actions, прежний образ и production этим не подтверждены.

Источники: [pip-audit](https://github.com/pypa/pip-audit),
[FastAPI release notes](https://fastapi.tiangolo.com/release-notes/),
[Starlette release notes](https://starlette.dev/release-notes/).


## Перед production-выпуском, 20 октября 2026

Настоящий Actions-аудит обнаружил три записи для aiohttp 3.14.3 с исправлением
в 3.14.4. Версия в политике обновлена, оба hashed lock пересозданы; остальные
версии пакетов сохранены. Повторный строгий audit production и development
наборов не обнаружил известных уязвимостей. Исключения и отключение gate
не применялись. [Advisory aiohttp](https://github.com/aio-libs/aiohttp/security/advisories/GHSA-2g87-pp6c-29x5).
