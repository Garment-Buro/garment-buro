# Linux runtime через Next

Рабочая копия `codex/release-foundation`, 20 октября2026.
Stage, commit, push и deploy не выполнялись; рабочие данные сайта не читались.

## Результат

Полный сценарий `deploy/scripts/smoke-containers.py` успешно выполнен с текущими
образами frontend/backend и новым source-built MinIO. Команда и server Compose
взяты из неизменяемого снимка1577 файлов; Dockerfile и lock-файлы настоящие.
SHA-256 исходников совпал до и после проверки. Локальные node_modules/.next,
приватные env, ключи, БД и uploads в снимок не попадали.

Оба образа собраны для linux/amd64 на отдельной Linux/aarch64 VM с binfmt.
Это эмуляция, а не native amd64 performance-тест. MinIO загружен из проверенного
архива предыдущего этапа; его SHA-256 и image ID совпали.

| Образ | Image ID |
| --- | --- |
| Backend | `sha256:93616f775730311c73f138adf395e3429cb3d8f09e3102a90dfa5c187fb92f96` |
| Frontend | `sha256:66fda7e5ebe600ddcbb722ccaab3fd9ca0e477298ed15dd457d1eac9fe057b12` |
| MinIO | `sha256:155d93e605780eb1c0c6e30101cfaa6fbd760832f09af4eadf8f858dfebba082` |

## Что прошло

- Свежие PostgreSQL17, Redis7 и MinIO; healthchecks, `database-role-init`,
  `minio-init` и Alembic head. Повторный head после записи корзины тоже прошёл.
- Backend и frontend работают с uid10001. API использует отдельную роль
  PostgreSQL: не superuser, без CREATE DATABASE/ROLE, replication и CREATE
  в public schema.
- Readiness подтверждает настоящие PostgreSQL и MinIO. Пустые каталоги товаров,
  людей и сообществ читаются непосредственно и через Next rewrite.
- Закрытые API возвращают401; удалённый `/api/settings` —404.
- `/` и `/catalog` возвращают HTML; все15 указанных JS/CSS-файлов доступны.
  Next image optimizer отклоняет private API, signed storage URL и encoded alias
  с400/no-store, не отражая capability. Публичный PNG оптимизируется.
- Через Next создана настоящая корзина: товар1500₽, надпись80₽, количество2.
  Переданная цена0.01 не принята: сервер сохранил1580₽. Повтор операции даёт
  прежний снимок, устаревшая ревизия —409; ответы no-store.
- API и Redis остановлены вместе; запущен только API. Redis действительно
  оставался exited. Корзина полностью сохранилась в PostgreSQL и прочитана
  непосредственно и через Next. Capability оставалась в памяти и HTTP.

Это тот же полный HTTP gate, который вызывает CI. Его успешный локальный
запуск не означает, что GitHub Actions текущей копии уже выполнены.

## Ресурсы и очистка

VM6GiB/2CPU; Docker подтвердил2CPU и6199009280 байт доступной памяти.
Builder4GiB/2CPU/swap0: параметры Docker и cgroup совпали. Builder удалён
до запуска стека. Образы не использовали source mounts или overlay исходников.
Вся проверка с созданием VM, двумя сборками, runtime и очисткой заняла374 секунды.
Это не замер скорости главной/каталога и не оценка ресурсов production.

Свой Compose project, контейнеры, volumes, сеть и приватный synthetic env удалены;
проверено их отсутствие. Затем удалены собственная VM, её диски, образы и
Docker CLI config. Контекст пользователя не активировался, SSH config и
SSH agent не менялись, host directories в VM не монтировались.
Рабочий сервер сайта в этом этапе не использовался.

## Что остаётся

Нужны актуальный CI, согласованный restore DB/S3, проверенный cutover/возврат
на полном кандидате и публичные браузерные сценарии опубликованной ревизии.
Этот gate проверяет HTTP и сохранность корзины, а не все React-взаимодействия,
реальные внешние платежи или доставку. Прежние неуспешные попытки сборки и
скачивания MinIO остаются историческими результатами.

Отдельная найденная задача: `MinioStorage.startup` использует стандартный
transport SDK; установленный SDK задаёт connect/read timeout по300 секунд и
до5 повторов. Нужны явные ограниченные timeout/retry и проверка медленного S3.
Это источник потенциально долгого ожидания при сбое storage, не доказанная
причина прежних замеров главной/каталога.
