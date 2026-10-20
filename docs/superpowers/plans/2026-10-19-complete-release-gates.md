# Полный проверочный прогон перед выпуском

## Проблема

Обычный backend-набор в CI шёл без native-зависимостей и допускал пропуски.
Позднее запускались integration, выбранные storage/concurrency модули и только
PostgreSQL-вариант storefront contract. PostgreSQL-варианты public profiles,
community directory, owner landings и reference directory не были покрыты этим
повторным запуском. Standalone-проверка нового кабинета существовала локально,
но отсутствовала в CI и запускала Next через машинную утилиту `rtk`.

## Изменение

- CI создаёт четыре разные PostgreSQL БД `test_*`: schema/contracts, Tochka,
  production и order workflow; отдельный MinIO с временным приватным конфигом.
- `backend/scripts/check_tests.py` запускает весь `pytest tests` активным Python.
  Отсутствующие/общие БД и открытый или неполный MinIO-конфиг отклоняются до pytest.
  Окружение приложения, `DATABASE_URL` и `PYTEST_ADDOPTS` не наследуются.
- Успех требует нулевого кода pytest и свежего непустого JUnit без skipped,
  failures и errors. Старый отчёт удаляется до запуска.
- Владение зависимостями остаётся у вызывающего окружения: CLI не создаёт и не
  удаляет серверы. В CI service PostgreSQL принадлежит job, а MinIO, volume и
  приватный конфиг удаляет EXIT trap.
- CI frontend собирается с identity, catalog writes и CRM; после установки
  Chromium запускаются analytics и admin-catalog gates. Next запускается напрямую
  активным Node, без зависимости от `rtk` на GitHub runner.
- Нового runtime Provider, бизнес-хранилища и изменения формы «Пресеты» нет.

## Локальная проверка

Полный запуск именно через новый CLI: 1217 backend tests passed, 0 skipped, 437с. Свежие PostgreSQL17, четыре изолированные БД и MinIO из закреплённого исходника; Python3.12.12. Включён21 тест отказов самого gate: отсутствие зависимостей, общая/не тестовая БД, открытый конфиг, устаревший/пустой/пропущенный/ошибочный отчёт и ненулевой exit pytest. После прогона свои процессы, БД, объекты и приватный конфиг удалены. Docker CLI локально отсутствует.

Frontend: 617 тестов, 0 failures/skips, ESLint 0 ошибок и одно прежнее
предупреждение alt-text, TypeScript и production build. Identity, catalog writes
и CRM включены. Оба браузерных gate прошли в отдельной копии исходников и сборки,
с PATH, в котором `rtk` отсутствует. Analytics использовал тестовый SDK.
Admin-catalog подтвердил новый кабинет, redirect старого адреса, owner forms,
130-элементные справочники, конфликт версий, восстановление ошибок и 13 проверок
CSS-сетки. Копия исходников, сборка и временный PATH удалены.

Проверены dependency locks (46 production / 55 development), Ruff, format638,
генерация migration upgrade/downgrade SQL. YAML разбирается; все15 shell-шагов
проходят `bash -n`. Это синтаксическая проверка workflow, не запуск Actions.

Локальная HTML-карта обновлена: 15 offline-проверок, 629 корректных ссылок файл:строка, ширины320/390/736, сохранение выбора, ноль сетевых запросов и JS-ошибок. Раздел «Проверки выпуска» показывает покрытие и ограничения.

## Границы

Локальный native-прогон и проверка YAML не подтверждают выполнение GitHub Actions
или сборку Linux/amd64 контейнеров. Браузерные gates используют standalone Next
с синтетическим HTTP API: они проверяют интерфейс и проксирование, а не реальную
БД в этом браузерном сценарии. Настоящие PostgreSQL/MinIO проверяются backend-набором;
ранее выполненный полный public runtime остаётся отдельным доказательством.
Safari, целевой телефон, нагрузка, внешние провайдеры и production этим этапом
не подтверждаются. Commit, push и deploy не выполняются. Общий релиз в работе.
