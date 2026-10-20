# Границы редактора модели и операции пресета

Дата: 19 октября 2026. Ветка `codex/release-foundation`. Изменения локальны, без stage/commit/push/deploy. Общий выпуск продолжается. Основной интерфейс товаров — производство → «Пресеты», как выбрал пользователь.

## Проблема

`AdminModels` соединял список/фильтры, чтение source, черновик, загрузку медиа, payload и большую форму. Upload не блокировал закрытие, поздний callback мог изменить другую открытую модель, input не сбрасывался для того же файла. Подтверждение upload доверяло любому `id`, preview пропускал префикс `/api`. React state не гарантировал одиночную запись до rerender. `Number` в payload был лишним преобразованием точных Decimal строк.

Пресет имел похожую state-only защиту записи. Несколько фотографий передавались отдельными операциями, между ними parent переставал считать upload активным. Матрица размеров×тканей не учитывала серверный предел200 до построения массива. Повтор чтения ссылок мог показывать прежний ответ/ошибку, а отсутствующая выбранная ткань считалась успешным пустым ответом.

## Архитектура

- `AdminModels` — только страницы списка/категорий и ID открываемой модели.
- `ModelEditorDialog` — состояния source/error/retry, рамка, дочерние поля и действия.
- `ModelIdentityFields` — основные поля и таблица размеров; `ModelSizesEditor` — размерная сетка и один открытый размер.
- `useModelEditor` — владелец source/AbortController, черновика и операций. `modelEditor.ts` — чистые преобразования и whitelist payload.
- Оболочка: ProductionTerminal → workspace с ключом сессии → AdminAssortment → AdminModels → ModelEditorDialog → поля. AssortmentDialog — визуальная рамка; новые hooks не создают Provider. Новых Provider/бизнес-хранилищ в localStorage нет.
- Пресет остаётся явным production UI. Общий low-level catalog adapter не переносит права производства в публичный кабинет.

## Гарантии модели

GET проходит существующий полный decoder и проверяет ID запроса. Неполный/чужой ответ не открывает пустую форму. В черновик входят активные размеры; архивные ID и геометрия остаются в БД. Предельные100 активных размеров проверяются при добавлении и payload; историческая модель сверх предела не обрезается молча.

Размеры и цены идут как десятичные строки: например64.25×72.35см и надбавка3.25. Whitelist не включает read-only поля размеров и preview URL. Геометрические поля имеют положительный минимум; рост с шагом1 использует минимум1, а не0.01. Нулевая базовая цена остаётся разрешённой, как в серверной схеме. Правило80₽ за принт/текст не менялось.

Синхронный ref-lock объединяет upload/save; повторный submit до rerender не начинает второй PUT. Поля, закрытие и фон отключены во время операции. Завершённая запись получает отдельный confirmed marker, а onSaved вызывается вне catch записи. Callback после unmount не меняет draft.

Upload требует положительный safe integer media ID. Preview строится через `/api/production/admin/assortment/media/public/ID`, соответствующий production cookie path; произвольный URL receipt не используется. File input очищается в finally.503 оставляет черновик и подтверждённый media ID; PUT retry не загружает файл повторно.

`get_garment_model_for_update` обновляет identity map через populate_existing под FOR UPDATE, включая sizes.409 версии получает code `crm_reference_version_conflict` в production и canonical writer. UI блокирует старый PUT, предлагает явное перечитывание с заменой черновика. Если перечитывание отказало, прежний ввод доступен через «Вернуться к черновику», а конфликт остаётся до успешного GET.

## Гарантии пресета

Upload всех файлов галереи — одна операция parent; её ref-lock блокирует save/close на всём batch. Ввод файла сбрасывается после попытки. URLs публикуются после подтверждения всего batch; частичный отказ сохраняет прежние ссылки. Загруженные до отказа файлы могут остаться без связи — их серверный lifecycle/GC ещё требует отдельной проверки.

Повторная запись защищена ref-lock и confirmed marker. Ошибка onSaved не превращает успешную запись в отказ. Variant UI отдаёт partial patch, который применяется к текущему state, а не заменяет строку снимком старого render.

Перед матрицей проверяется произведение размеров×тканей и дополнительное число сохранённых нескольких SKU одной пары. Больше200 — явная ошибка, прежние варианты не меняются. Предел есть и для ручного добавления, и для payload. Исторические SKU не удаляются неявно; ID/медиа/мерки/сырые остатки сохраняются. Ограничение не доказывает bounded server detail/history, это следующий участок.

Model source привязан к запрошенному ID. Все selected fabric IDs обязаны присутствовать в ответе. Reference revision отделяет retry от прежнего результата: старые value/error не разрешают сохранение до свежего ответа.

## Проверки

- Полный backend: **1095 passed,0 skipped**, Python3.12.12, собственные PostgreSQL17/четыре БД и MinIO, elapsed364s вместе с подготовкой. Это native runtime, не Docker.
- Профильные **37/0skip**: source/категории/модели/production admin. Новый тест повторён на SQLite и PostgreSQL: stale identity-map version1 при фактической2 не проходит CAS; HTTP409 возвращает стабильный code и не меняет версию в БД.
- Frontend: **606 passed,0 failed,0 skipped**. Проверены точные Decimal строки, whitelist/архивы/version, malformed media receipts, матрица200 и дубликаты SKU.
- `npm run lint` —0 errors, прежний warning alt у CustomerMediaImage; Next production build/TypeScript прошёл с тремя release flags. Прежнее предупреждение fallback AlumniSansSC не скрывалось.
- Ruff check/format:663 Python-файла. `git diff --check` прошёл.
- Реальный standalone Next/Chromium с синтетическим HTTP backend: неполная модель и неверный ID не открывают form; upload безID — ошибка; тот же файл выбирается повторно; upload/save/close не пересекаются; два forced submit — один PUT;503 сохраняет название/media;409 блокирует старую версию; отказ GET после409 сохраняет ввод и изображение; явное перечитывание получает новую version. PUT retry не повторяет upload. Формы320/390/736/1280, включая736×390.
- Пресет: неполный selected-fabrics блокирует save, retry показывает загрузку до свежего ответа; batch2 files остаётся одной операцией; input reset; два forced submit дают один PUT;503 сохраняет ввод и старую/новые фотографии. Прежние сценарии кабинетов/банка/страниц/складов/лекал/категорий/сессии2tabs также повторены.

Первый полный backend прогон исчез вместе с локальными процессами до итогового XML; он не засчитан. Итоговые данные выше относятся к завершённому `model-editor-verified`.

## Доказательства

Каталог выполнения: `/Users/mikitaliudchyk/.codex/visualizations/2026/10/12/01a131d3-2f27-7762-98e4-da371d9cfc34`.

- `backend-dependencies/model-editor-verified-result.json`, `.log`, `.xml`; runner `run-model-editor-verified.py`.
- `backend-dependencies/model-editor-focused-result.json`, `.log`, `.xml`.
- `model-editor-frontend-final.log`, `model-editor-lint.log`, `model-editor-build.log`, `model-editor-browser-final.log`.
- `model-editor-final.png`, `model-geometry-dialog.png`.
- Browser fixture: `frontend/scripts/fixtures/model-editor.mjs`, входит в `npm run check:admin-catalog`.

## Оставшаяся работа

Полная runtime-валидация DTO и media URL пресета, дальнейшее деление его полей; ограниченные source/history моделей и остальные canonical CRM reads; query plans подстроки и агрегатных сортировок; lifecycle/GC частично загруженных файлов. Схема осталась head0074. Нет доказательства Docker/Actions, production, настоящего телефона, реальной оплаты и внешних writers/backup restore. Общий релиз остаётся активным; этот этап не заменяет полную проверку цели.
