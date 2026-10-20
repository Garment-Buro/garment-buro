# Воспроизводимая поставка MinIO

Рабочая копия `codex/release-foundation`, 20 октября 2026 года.
Stage/commit/push/deploy не выполнялись. Рабочие данные не читались.

## Решение

По решению пользователя MinIO остаётся. Архивирование Community upstream не
останавливает установленный сервер. Однако прежняя холодная проверка готового
образа `minio/minio` и архивных бинарников завершалась отказом. Теперь версия
собирается из официального исходного архива с проверкой SHA-256; готовый MinIO
image, стороннее зеркало и mc не требуются.

Выбран последний опубликованный upstream security release от 15 октября 2025,
а не прежняя июльская версия проекта. [Официальное описание](https://github.com/minio/minio/releases/tag/RELEASE.2025-10-15T17-29-55Z)
содержит исправление обхода session policy. Source commit:
`9e49d5e7a648f00e26f2246f4dc28e6b07f8c84a`.
Dockerfile закрепляет его архив, Go1.27.2 по registry digest и проверяет go.sum.
Обновление compiler не изменяет upstream исходники; поведение образа требует
отдельного runtime-подтверждения.

## Изменения запуска

- Local Compose собирает `deploy/minio/Dockerfile`.
- Server Compose требует явный `MINIO_IMAGE`, с `pull_policy: never`.
- Скрипт выпуска заранее проверяет выбранный образ, до pull приложений,
  остановки writers и backup. Ошибка оставляет прежнее окружение работающим.
- CI backend и полный container gate собирают один и тот же source Dockerfile.
- Runtime smoke принимает явный storage image и не наследует его с хоста.
- Статический healthcheck заменяет curl/shell: loopback, только200,
  timeout3 секунды, без redirect. Том и числовой пользователь совместимы
  с прежним образом, рекурсивного изменения владельцев нет.

## Подтверждено

157 тестов без пропусков: 64 release, 34 container smoke, 17 storage bootstrap,
42 backup/verifier. Новые ошибки отсутствующего storage image и подмены образа
с окружения Docker-хоста сначала воспроизведены красными тестами. Ruff и Bash
syntax прошли. Настоящий Compose проверил оба descriptor, CMD healthcheck,
pull policy и выдачу ровно одного образа через `config --images minio`.

Пять входных файлов Docker-контекста сверены по SHA-256. Собран настоящий
linux/amd64 образ из Dockerfile, native arm64 compiler с cross-compilation:
`sha256:155d93e605780eb1c0c6e30101cfaa6fbd760832f09af4eadf8f858dfebba082`.
Архив 66 534 912 байт; SHA-256:
`be176b21ffbb76354a22be588aeaf0a4849e96cd4ce630cbb1d01373d16e7c54`.
Healthcheck Go tests и проверка модулей прошли при сборке. Этот архив — результат
конкретного exporter; другой корректный rebuild может иметь другой digest.

VM6GiB/2CPU, builder4GiB/2CPU/swap0; Docker и cgroup лимиты проверены.
Сборка с экспортом и cleanup завершилась за230 секунд. Собственная VM,
её диски, builder, контейнерные образы внутри VM и CLI config удалены.
Локальный проверочный архив сохранён вне Git для runtime-репетиции.

## Проверка обновления и восстановления

Проверка завершена успешно, только на синтетических данных:
прежний кешированный MinIO → остановка → архив volume → новый source-built
образ на этом volume → повторный запуск → восстановление прежнего архива
в другой volume с прежним сервером. Сохранены байты пяти объектов, две версии
проекта с прежними version ID/ETag, metadata/tags, public GET, private403,
запрет anonymous list/PUT, прежняя signed URL и посторонний бакет.

На свежем native PostgreSQL17 и новом Linux MinIO выполнена настоящая команда
`python -m scripts.check_tests`: **1369 passed, 0 skipped**, 641,39 секунды,
Python3.14.3. Включены четыре auth-обновления/HTTP, барьер миграций и S3 integration.
Одно предупреждение о deprecated httpx в FastAPI TestClient; тесты прошли.
Входной снимок текущих backend/deploy исходников до и после совпал по SHA-256.
Это не CI на Python3.12 и не полный HTTP через Next.

Вся репетиция с очисткой завершилась за710 секунд. Свои контейнеры, два volumes,
сеть, импортированный образ, SSH tunnel, private configs, native PostgreSQL и
его данные удалены. Исходные14 контейнеров совпали по ID/image/StartedAt/restarts;
серверная временная папка удалена. Рабочие бакеты и приложение не переключались.

Первые два запуска остановились до проверки данных: internal network этого
rootless Docker не публикует host port. Они полностью очищены, исходные14
контейнеров совпали по ID/image/StartedAt/restarts. Стенд использует обычный
собственный bridge с публикацией исключительно на loopback, как server descriptor.
Третий запуск подтвердил обновление, restart, полный backend и storage restore.
Возврат проверялся из архива до обновления, не запуском старого бинарника
поверх уже обновлённого volume. Это отдельная проверка storage, а не
согласованное восстановление общей границы записей PostgreSQL и S3.

## Границы

Исходники и способ поставки зафиксированы; upstream maintenance этим не
возобновляется. Изменений хранилища или пользовательских файлов на рабочем сайте
нет. Публикация образа в registry и перенос данных не выполнялись. Нужны
полный Linux Next, актуальный CI, согласованный
DB/S3 restore на рабочем объёме, окно обслуживания и публичные сценарии релиза.
