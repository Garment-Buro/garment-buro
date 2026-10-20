# Жизненный цикл файлов покупателя

Часть полного рефакторинга, выполняется в текущей рабочей копии без публикации.
Основание: `backend/docs/customer-projects.md`, раздел оставшейся работы.

## Контракт

Источник состояния — PostgreSQL, файлы — частный MinIO bucket проектов.
Worker не использует Redis, браузер и HTTP startup как очередь очистки.
`pending`/`failed` без ссылок удаляются после часа, `ready` без ссылок — после
семи суток с последнего изменения привязки. Аккаунт со статусом `deleted`
теряет проекты/избранное ограниченными пачками, его частные файлы удаляются
без недельного ожидания. Бухгалтерские заказы и аудит этим worker не затрагиваются.

Перед физическим удалением фиксируется `status=deleted`. Сбой MinIO или процесса
оставляет SQL-запись для повторной попытки. SQL-строка удаляется только после
успешного idempotent удаления объекта. Неизвестные namespace, публичные/CRM
bucket и любые файлы с FK-привязками не являются кандидатами.

Запись проекта блокирует строки всех прежних/новых media в порядке ID; worker
использует SKIP LOCKED и повторно проверяет ссылки после блокировки. Удаление
аккаунта и новые записи сериализуются блокировкой user. Upload после durable
pending удерживает блокировку media до завершения PUT/ready — поздний PUT не
может воскресить уже очищенный объект.

## Файлы и шаги

- [x] `backend/tests/integration/test_project_media_lifecycle.py`: RED на настоящих
  PostgreSQL/MinIO: старые неподключённые файлы исчезают, свежие/используемые остаются;
  удалённый аккаунт очищается; ошибка удаления оставляет retry; параллельные worker
  и сохранение не теряют активные файлы.
- [x] `backend/app/modules/customer_projects/lifecycle_repository.py`: bounded
  выборки, блокировки, проверка всех FK, очистка проектов/избранного deleted owners.
- [x] `backend/app/modules/customer_projects/lifecycle.py`: одна попытка очистки,
  durable deleted, retry и результат без личных данных.
- [x] `backend/app/modules/customer_projects/repository.py`, `media_repository.py`,
  `service.py`, `media_service.py`: блокировки владельца и media, timestamp detach,
  отказ поздней записи удалённого аккаунта; GREEN реальных конкурентных сценариев.
- [x] `backend/app/integrations/minio.py`: удаление только private projects bucket.
- [x] `backend/migrations/versions/20261014_0060_private_media_lifecycle.py` и
  `backend/app/modules/media/models.py`: индекс private bucket/status/time/id;
  Alembic upgrade/downgrade и ORM equivalence.
- [x] `backend/scripts/reconcile_project_media.py`: bounded batch, once/dry-run,
  положительные конечные интервалы, проверка схемы, структурированные счётчики.
  `deploy/docker-compose.server.yml`, `docker-compose.local.yml`,
  `deploy/scripts/remote-deploy.sh`: worker вместе с identity, без legacy mounts.
- [x] Targeted Ruff, полные backend tests с PostgreSQL/MinIO, независимое ревью;
  обновление эксплуатационной документации. Проверка контейнерного выпуска
  остаётся отдельным обязательным этапом полного релиза.

Итог: 593 backend tests passed, Ruff/shell syntax/diff checks прошли.
Дополнительные RED/GREEN: все CRM FK, отменённый PUT, 10k fresh SQL scan,
2k referenced archive повторные scans, cached snapshot при prefetched lock.
Ревью закрыто после исправления 3 находок: fresh revalidation, создание нового
bucket и rollback новых worker services. Четыре shell-сценария тестируют командный
протокол с эмуляцией Docker/host tools. Реальные контейнеры, backup restore и
совместимость предыдущего образа с новой схемой остаются release gates.
