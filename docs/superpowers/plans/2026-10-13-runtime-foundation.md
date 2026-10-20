# Runtime Foundation Implementation Plan

> **For agentic workers:** Execute sequentially in this session; no delegation.

**Goal:** Сделать запуск, остановку и диагностику API проверяемой основой нового релиза.

**Architecture:** Factory собирает приложение. Выделенный runtime управляет
ресурсами через AsyncExitStack. Чистый ASGI middleware связывает запрос, ответ
и лог через request ID; конфигурация логирования применяется на границе процесса.

**Tech Stack:** Python 3.12, FastAPI/Starlette, standard logging/contextvars,
pytest, существующие SQLAlchemy и HTTP transports.

**Spec:** `docs/release-refactoring.md` (этап 1; остальные этапы остаются открыты).

## Ограничения

- Не изменять существующие незакоммиченные функции главной и производства.
- Не выполнять операции с production-данными и не включать провайдеры оплаты.
- Не создавать дополнительное хранилище логов или внешнюю службу.
- Не логировать body, cookies, Authorization, query, фактические path-параметры.
- Сохранить существующие HTTP-контракты на промежуточном этапе.

## Задача 1. Request ID и структурированные логи

Files: новые `backend/app/observability/{__init__,logging,middleware}.py`,
`backend/tests/unit/test_observability.py`; изменения `app/factory.py`,
`app/main.py`, `app/core/config.py`, `.env.example`.

- [x] Добавить тесты запросов через реальный TestClient: ответ содержит request
  ID, лог содержит тот же ID, шаблон маршрута и status; секреты body/query/headers
  не попадают в access event; ошибка возвращает ID; streaming не буферизуется.
- [x] Запустить `rtk proxy .venv/bin/python -m pytest -q tests/unit/test_observability.py`
  из backend и увидеть отсутствие нового поведения.
- [x] Реализовать middleware с ContextVar и ограниченной формой входного ID;
  formatter с разрешёнными полями и без текста исключения; применить logging
  config на process entrypoint, исключить стандартный access log с сырым URL.
- [x] Повторить проверки; проверить конкурентную изоляцию ID и сброс контекста.

## Задача 2. Владение ресурсами

Files: новый `backend/app/runtime.py`, изменения `backend/app/factory.py`,
`backend/tests/unit/test_factory.py`.

- [x] Добавить проверки: storage startup падает после открытия БД — engine
  закрыт; startup БД падает после частичной инициализации — engine закрыт;
  ошибка остановки transport не оставляет другие ресурсы открытыми.
- [x] Запустить эти проверки и зафиксировать текущие сбои.
- [x] Перенести lifespan в runtime, регистрировать освобождение до startup,
  освобождать в обратном порядке, останавливать фоновые задачи до их ресурсов.
  Factory передаёт проверки cutover и собранные transports.
- [x] Проверить обычный lifecycle и существующие контрактные сценарии.

## Задача 3. Проверка и эксплуатационная инструкция

Files: worker entrypoints с `logging.basicConfig`,
`backend/docs/runtime.md`, `docs/release-refactoring.md`.

- [x] Подключить ту же конфигурацию к существующим worker entrypoints.
- [x] Запустить Ruff и backend pytest; отдельно проверить миграции и фактический
  stdout временного локального сервера без обращения к внешним провайдерам.
- [x] Описать поля логов, correlation ID, liveness/readiness и границы проверки.
- [x] Записать результаты этапа и продолжить этап 2. Не объявлять весь релиз
  завершённым по результатам одного набора тестов.

## Результат проверки 13 октября

Этап 1 реализован и проверен; общий релиз ещё не завершён. Полный backend с
включёнными PostgreSQL integration/concurrency сценариями: 502 passed без
пропусков. Ruff и offline SQL upgrade/downgrade прошли. Реальный процесс Uvicorn
проверен на PostgreSQL; correlation, JSON stdout, отсутствие private значений и
освобождение ресурсов подтверждены. Frontend HTTP-клиент сохраняет request ID.

Этап 2 уже начат: импорт старого main удалён из entrypoint, startup сверяет
PostgreSQL revision с Alembic head; fingerprints импорта убраны из обычного
запуска. Новая схема проверена сравнением с ORM и обратимой миграцией дублирующих
индексов. SQLite order bridge удалён; история читается из основной БД. Factory compatibility и legacy mounts/init убраны. Backup согласован с новой
схемой и сохраняет архив предыдущей версии при наличии. Остались прежний корневой
deployment descriptor, полный контейнерный запуск и восстановление backup. Подробный журнал — docs/release-refactoring.md.
