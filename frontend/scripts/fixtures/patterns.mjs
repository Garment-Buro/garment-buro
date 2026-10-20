import assert from 'node:assert/strict';
import path from 'node:path';

/** Synthetic HTTP data only; native SQL, authority and locking are covered by pytest. */
export function createPatternFixture({ json, modelRecord }) {
    const state = {},
        reads = [],
        sources = [],
        writes = [],
        uploads = [],
        held = [],
        heldSources = [],
        heldWrites = [];
    const prefix = '/api/production/admin/assortment',
        changes = new Map();
    const size = (modelId, id) => ({
        id: id ?? (modelId === 130 ? 2001 : modelId * 10000 + 1),
        code:
            modelId === 130 && id === 2130
                ? 'XL'
                : !id || id === 2001 || modelId !== 130
                  ? 'M'
                  : `OLD-${id - 2001}`,
        is_active: modelId !== 130 || !id || id === 2001 || id === 2130,
        version: state.geometryChanged ? 2 : 1,
        min_width_cm: '50.25',
        max_width_cm: '550.25',
        min_length_cm: '60.35',
        max_length_cm: '560.35',
        allow_standard_sleeve: true,
        allow_height_sleeve: true,
    });
    const choice = (id) => {
        const row = size(
            id >= 2001 && id <= 2130 ? 130 : Math.floor(id / 10000),
            id,
        );
        return {
            id: row.id,
            code: row.code,
            name: row.code,
            is_active: row.is_active,
        };
    };
    const brief = (id) => ({
        id,
        name: modelRecord(id).name,
        code: `MODEL-${id}`,
        is_active: true,
        version: 1,
    });
    const baseFile = (modelId, index) => {
        const s = size(modelId),
            archived = modelId === 130 && index === 131,
            outside = modelId === 130 && index === 130;
        return {
            id: modelId === 130 ? 130000 + index : modelId * 100000 + 1,
            code: `PAT-${String(modelId).padStart(3, '0')}-${String(index).padStart(3, '0')}`,
            name: 'Сохранённое имя файла',
            garment_model_id: modelId,
            garment_size_id: archived ? 2002 : s.id,
            media_object_id: 60000,
            width_cm: outside
                ? '1000.25'
                : (50.25 + (index % 20) * 2).toFixed(2),
            length_cm: outside
                ? '1000.35'
                : (60.35 + Math.floor(index / 20) * 2).toFixed(2),
            sleeve_variant: 'standard',
            grid_key: `M:${index}`,
            is_active: index % 5 !== 0,
            version: 7,
        };
    };
    const initialFiles = Array.from({ length: 132 }, (_, i) =>
        baseFile(130, i),
    );
    const files = (modelId) => [
        ...(modelId === 130 ? initialFiles : [baseFile(modelId, 0)]).map(
            (row) => changes.get(row.id) ?? row,
        ),
        ...Array.from(changes.values()).filter(
            (row) => row.garment_model_id === modelId && row.id >= 90000000,
        ),
    ];
    const find = (id) =>
        changes.get(id) ??
        initialFiles.find((row) => row.id === id) ??
        Array.from({ length: 129 }, (_, i) => baseFile(i + 1, 0)).find(
            (row) => row.id === id,
        );
    const context = (modelId, sizeId) => ({
        model: brief(modelId),
        size: size(modelId, sizeId),
        pattern: null,
    });
    const grid = (modelId, query) => {
        const row = context(modelId, Number(query.size_id) || undefined),
            width = Number(query.width_page ?? 0),
            length = Number(query.length_page ?? 0);
        const axis = (minimum, page) =>
            Array.from(
                { length: Math.max(0, Math.min(6, 251 - page * 6)) },
                (_, i) => (minimum + 2 * (page * 6 + i)).toFixed(2),
            );
        const widths = axis(50.25, width),
            lengths = axis(60.35, length),
            rows = files(modelId).filter(
                (item) =>
                    item.garment_size_id === row.size.id &&
                    Number(item.width_cm) <= 550.25 &&
                    Number(item.length_cm) <= 560.35,
            );
        return {
            ...row,
            step_cm: '2.00',
            width_values: widths,
            length_values: lengths,
            width_page: width,
            length_page: length,
            width_pages: 42,
            length_pages: 42,
            width_count: 251,
            length_count: 251,
            required_count: '126002',
            uploaded_count: rows.length,
            items: rows.filter(
                (item) =>
                    widths.includes(item.width_cm) &&
                    lengths.includes(item.length_cm),
            ),
        };
    };
    function handle(request, response, url) {
        const path = url.pathname,
            query = Object.fromEntries(url.searchParams);
        if (!path.startsWith(prefix + '/')) return false;
        if (
            path === prefix + '/directory/pattern-models' ||
            path === prefix + '/directory/patterns' ||
            path === prefix + '/directory/pattern-sizes'
        ) {
            const kind = path.split('/').at(-1);
            reads.push({ kind, ...query });
            assert.equal(query.limit, '24');
            if (query.cursor && state.failAppend) {
                json(
                    response,
                    { detail: 'Тестовый отказ страницы лекал' },
                    503,
                );
                return true;
            }
            if (query.cursor && state.invalidCursor) {
                json(response, { detail: { code: 'invalid_cursor' } }, 422);
                return true;
            }
            let rows;
            if (kind === 'pattern-models')
                rows = Array.from({ length: 130 }, (_, i) => ({
                    ...brief(i + 1),
                    pattern_count: files(i + 1).length,
                    uploaded_count: i === 129 ? 130 : 1,
                    required_count: i === 129 ? '252004' : '126002',
                }));
            else if (kind === 'pattern-sizes')
                rows =
                    Number(query.model_id) === 130
                        ? Array.from({ length: 130 }, (_, i) =>
                              choice(2001 + i),
                          )
                        : [choice(Number(query.model_id) * 10000 + 1)];
            else
                rows = files(Number(query.model_id) || 130).map((item) => ({
                    ...item,
                    garment_model_name: brief(item.garment_model_id).name,
                    size_code: size(item.garment_model_id, item.garment_size_id)
                        .code,
                    size_is_active: size(
                        item.garment_model_id,
                        item.garment_size_id,
                    ).is_active,
                }));
            const q = (query.query ?? '').toLowerCase();
            rows = rows.filter(
                (row) =>
                    (!query.model_id ||
                        kind !== 'pattern-models' ||
                        row.id === Number(query.model_id)) &&
                    (!q ||
                        [row.name, row.code, row.garment_model_name].some(
                            (value) => value?.toLowerCase().includes(q),
                        )),
            );
            if (kind === 'patterns') rows.sort((a, b) => b.id - a.id);
            const offset = Number(query.cursor ?? 0),
                send = () =>
                    json(response, {
                        items: rows.slice(offset, offset + 24),
                        next_cursor:
                            rows.length > offset + 24
                                ? String(offset + 24)
                                : null,
                    });
            if (
                kind === 'pattern-models' &&
                state.delaySearch &&
                q === 'модель 00'
            )
                held.push(send);
            else send();
            return true;
        }
        const coverage = /\/models\/(\d+)\/pattern-coverage$/.exec(path);
        if (coverage) {
            reads.push({
                kind: 'coverage',
                modelId: Number(coverage[1]),
                ...query,
            });
            const send = () => {
                if (state.failCoverage)
                    return json(
                        response,
                        { detail: 'Тестовый отказ сетки лекал' },
                        503,
                    );
                if (
                    query.expected_size_version &&
                    Number(query.expected_size_version) !==
                        (state.geometryChanged ? 2 : 1)
                )
                    return json(
                        response,
                        {
                            detail: {
                                code: 'pattern_grid_changed',
                                message: 'Размер изменился. Обновите сетку.',
                            },
                        },
                        409,
                    );
                const row = grid(Number(coverage[1]), query);
                if (state.incompleteCoverage) delete row.width_values;
                return json(response, row);
            };
            if (state.delayCoverage) held.push(send);
            else send();
            return true;
        }
        const detail = /\/patterns\/(\d+)$/.exec(path),
            sizeContext = /\/models\/(\d+)\/pattern-size\/(\d+)$/.exec(path);
        if ((detail && request.method === 'GET') || sizeContext) {
            sources.push(path);
            const file = detail ? find(Number(detail[1])) : null;
            const send = () => {
                if (state.failSource)
                    return json(
                        response,
                        { detail: 'Тестовый отказ контекста лекала' },
                        503,
                    );
                if (detail && !file)
                    return json(response, { detail: 'Лекало не найдено' }, 404);
                const row = detail
                    ? {
                          ...context(
                              file.garment_model_id,
                              file.garment_size_id,
                          ),
                          pattern: file,
                      }
                    : context(Number(sizeContext[1]), Number(sizeContext[2]));
                if (state.incompleteSource) delete row.size.version;
                return json(response, row);
            };
            if (state.delaySource) heldSources.push(send);
            else send();
            return true;
        }
        if (path === prefix + '/media/pattern') {
            assert.equal(request.headers.authorization, undefined);
            let bytes = 0;
            request.on('data', (chunk) => {
                bytes += chunk.length;
            });
            request.on('end', () => {
                uploads.push({ bytes });
                if (state.failUpload)
                    return json(
                        response,
                        { detail: 'Тестовый отказ загрузки лекала' },
                        503,
                    );
                if (state.incompleteUpload)
                    return json(response, { filename: 'replacement.pdf' }, 201);
                json(
                    response,
                    {
                        id: 90000 + uploads.length,
                        filename: 'replacement.pdf',
                        content_type: 'application/pdf',
                    },
                    201,
                );
            });
            return true;
        }
        if (
            (request.method === 'PUT' && detail) ||
            (request.method === 'POST' && path === prefix + '/patterns')
        ) {
            let body = '';
            request.on('data', (chunk) => {
                body += chunk;
            });
            request.on('end', () => {
                const payload = JSON.parse(body),
                    id = detail ? Number(detail[1]) : 90000000 + writes.length;
                writes.push({ id, payload, method: request.method });
                const send = () => {
                    if (state.failWrite)
                        return json(
                            response,
                            { detail: 'Тестовый отказ сохранения лекала' },
                            503,
                        );
                    const current = detail ? find(id) : null;
                    if (current && payload.expected_version !== current.version)
                        return json(
                            response,
                            { detail: 'Версия лекала изменилась' },
                            409,
                        );
                    const row = {
                        ...payload,
                        id,
                        version: (current?.version ?? 0) + 1,
                        width_cm: Number(payload.width_cm).toFixed(2),
                        length_cm: Number(payload.length_cm).toFixed(2),
                        grid_key: 'CURRENT',
                    };
                    changes.set(id, row);
                    json(response, row, detail ? 200 : 201);
                };
                if (state.delayWrite) heldWrites.push(send);
                else send();
            });
            return true;
        }
        return false;
    }
    const release = () => {
        held.splice(0).forEach((send) => send());
        heldSources.splice(0).forEach((send) => send());
        heldWrites.splice(0).forEach((send) => send());
    };
    return {
        state,
        reads,
        sources,
        writes,
        uploads,
        held,
        heldSources,
        heldWrites,
        handle,
        choice,
        release,
    };
}

export async function checkPatternFlow({ page, until, fixture, proofDir }) {
    const { state, reads, sources, writes, uploads, held, heldWrites } =
        fixture;
    await page.getByRole('button', { name: 'Лекала', exact: true }).click();
    const models = page.locator('[data-pattern-model]'),
        search = page.getByRole('searchbox', {
            name: 'Поиск по модели или коду лекала',
            exact: true,
        });
    await until(
        async () => (await models.count()) === 24,
        'Pattern model first page missing',
    );
    assert.equal(
        reads.filter(
            (row) =>
                row.kind === 'coverage' ||
                row.kind === 'patterns' ||
                row.kind === 'pattern-sizes',
        ).length,
        0,
        'Closed pattern models must not prefetch files, sizes or grids',
    );
    assert.equal(sources.length, 0);
    state.failAppend = true;
    await page
        .getByRole('button', { name: 'Ещё модели для лекал', exact: true })
        .click();
    await page
        .getByRole('alert')
        .filter({ hasText: 'Тестовый отказ страницы лекал' })
        .waitFor();
    assert.equal(await models.count(), 24);
    state.failAppend = false;
    state.invalidCursor = true;
    await page
        .getByRole('button', { name: 'Ещё модели для лекал', exact: true })
        .click();
    await page
        .getByRole('alert')
        .filter({ hasText: 'Список изменился' })
        .waitFor();
    assert.equal(await models.count(), 24);
    state.invalidCursor = false;
    await page
        .getByRole('button', { name: 'Обновить модели лекал', exact: true })
        .click();
    await until(
        async () => (await models.count()) === 24,
        'Pattern model refresh missing',
    );
    while (
        await page
            .getByRole('button', { name: 'Ещё модели для лекал', exact: true })
            .count()
    ) {
        const before = await models.count();
        await page
            .getByRole('button', { name: 'Ещё модели для лекал', exact: true })
            .click();
        await until(
            async () => (await models.count()) > before,
            'Pattern model continuation missing',
        );
    }
    assert.equal(await models.count(), 130);
    assert.equal(sources.length, 0);
    assert.equal(reads.filter((row) => row.kind === 'coverage').length, 0);
    state.delaySearch = true;
    await search.fill('Модель 00');
    await until(() => held.length === 1, 'Slow pattern search missing');
    await search.fill('Модель 130');
    await until(
        async () => (await models.count()) === 1,
        'New pattern search missing',
    );
    state.delaySearch = false;
    held.splice(0).forEach((send) => send());
    assert.equal(await models.count(), 1);
    const model = page.locator('[data-pattern-model="130"]');
    state.delayCoverage = true;
    await model.locator('summary').click();
    await until(() => held.length === 1, 'Lazy pattern grid read missing');
    await model.locator('summary').click();
    state.delayCoverage = false;
    held.splice(0).forEach((send) => send());
    assert.equal(
        await model.locator('table').count(),
        0,
        'Closed coverage must not return after a late response',
    );
    await model.locator('summary').click();
    await until(
        async () => (await model.locator('table tbody tr').count()) === 6,
        'Pattern grid did not load',
    );
    assert.equal(await model.locator('table tbody button').count(), 72);
    assert.equal(reads.filter((row) => row.kind === 'patterns').length, 0);
    await model
        .getByRole('spinbutton', { name: 'Страница ширины', exact: true })
        .fill('42');
    await model
        .getByRole('button', { name: 'Страница ширины: перейти', exact: true })
        .click();
    await model
        .getByRole('columnheader', { name: '550.25 см', exact: true })
        .waitFor();
    await model
        .getByRole('spinbutton', { name: 'Страница длины', exact: true })
        .fill('42');
    await model
        .getByRole('button', { name: 'Страница длины: перейти', exact: true })
        .click();
    await model
        .getByRole('rowheader', { name: '560.35 см', exact: true })
        .waitFor();
    assert.ok((await model.locator('table tbody button').count()) <= 72);
    state.geometryChanged = true;
    await model
        .getByRole('button', { name: 'Страница ширины: назад', exact: true })
        .click();
    await model
        .getByRole('alert')
        .filter({ hasText: 'Размер изменился' })
        .waitFor();
    assert.equal(await model.locator('table').count(), 0);
    await model
        .getByRole('button', { name: 'Обновить сетку', exact: true })
        .click();
    await model
        .getByRole('columnheader', { name: '50.25 см', exact: true })
        .waitFor();
    for (const [width, height] of [
        [320, 850],
        [390, 850],
        [736, 390],
        [1280, 850],
    ]) {
        await page.setViewportSize({ width, height });
        assert.ok(
            await page.evaluate(
                () => document.documentElement.scrollWidth <= innerWidth + 1,
            ),
            `Pattern coverage overflows at ${width}`,
        );
    }
    await page.setViewportSize({ width: 390, height: 850 });
    const gridRegion = model.getByRole('region', { name: /^Сетка лекал/ });
    await gridRegion.focus();
    await page.keyboard.press('ArrowRight');
    await until(
        async () =>
            await gridRegion.evaluate((element) => element.scrollLeft > 0),
        'Pattern grid is not keyboard-scrollable',
    );
    await gridRegion.evaluate((element) => (element.scrollLeft = 0));
    if (proofDir) {
        await model.locator('table').scrollIntoViewIfNeeded();
        await page.screenshot({
            path: path.join(proofDir, 'pattern-coverage-mobile.png'),
        });
    }
    await page.setViewportSize({ width: 1280, height: 850 });
    if (proofDir) {
        await model.locator('table').scrollIntoViewIfNeeded();
        await page.screenshot({
            path: path.join(proofDir, 'pattern-coverage.png'),
        });
    }
    state.failSource = true;
    await model
        .locator('table')
        .getByRole('button', { name: /PAT-130-000$/ })
        .click();
    const editor = page.getByRole('dialog', {
        name: 'Изменить лекало',
        exact: true,
    });
    await editor
        .getByRole('alert')
        .filter({ hasText: 'Тестовый отказ контекста лекала' })
        .waitFor();
    assert.equal(await editor.locator('form').count(), 0);
    state.failSource = false;
    state.incompleteSource = true;
    await editor
        .getByRole('button', { name: 'Повторить загрузку лекала', exact: true })
        .click();
    await editor
        .getByRole('alert')
        .filter({ hasText: 'Сервер вернул неверный размер лекала' })
        .waitFor();
    assert.equal(await editor.locator('form').count(), 0);
    state.incompleteSource = false;
    await editor
        .getByRole('button', { name: 'Повторить загрузку лекала', exact: true })
        .click();
    const code = editor.getByRole('textbox', { name: /^Код лекала/ });
    await code.fill('PAT-130-RENAMED');
    assert.equal(
        await editor
            .getByRole('spinbutton', {
                name: 'Ширина изделия, см',
                exact: true,
            })
            .inputValue(),
        '50.25',
    );
    assert.equal(
        await editor
            .getByRole('spinbutton', { name: 'Длина изделия, см', exact: true })
            .inputValue(),
        '60.35',
    );
    const pdf = {
        name: 'replacement.pdf',
        mimeType: 'application/pdf',
        buffer: Buffer.from('%PDF-1.4\nsynthetic pattern\n'),
    };
    state.failUpload = true;
    await editor.locator('input[type="file"]').setInputFiles(pdf);
    await editor
        .getByRole('alert')
        .filter({ hasText: 'Тестовый отказ загрузки лекала' })
        .first()
        .waitFor();
    assert.equal(await editor.locator('input[type="file"]').inputValue(), '');
    state.failUpload = false;
    state.incompleteUpload = true;
    await editor.locator('input[type="file"]').setInputFiles(pdf);
    await editor
        .getByRole('alert')
        .filter({ hasText: 'Сервер не подтвердил загрузку файла лекала.' })
        .first()
        .waitFor();
    state.incompleteUpload = false;
    await editor.locator('input[type="file"]').setInputFiles(pdf);
    await editor
        .getByText('replacement.pdf загружен', { exact: true })
        .waitFor();
    assert.equal(uploads.length, 3);
    assert.ok(uploads.every((row) => row.bytes > 0));
    state.delayWrite = true;
    state.failWrite = true;
    await editor
        .getByRole('button', { name: 'Сохранить', exact: true })
        .click();
    await until(() => heldWrites.length === 1, 'Pattern write was not held');
    assert.equal(await code.isDisabled(), true);
    assert.equal(
        await editor
            .getByRole('button', { name: 'Закрыть', exact: true })
            .isDisabled(),
        true,
    );
    assert.equal(
        await page
            .getByRole('button', { name: 'Добавить лекало', exact: true })
            .isDisabled(),
        true,
    );
    state.delayWrite = false;
    heldWrites.splice(0).forEach((send) => send());
    await editor
        .getByRole('alert')
        .filter({ hasText: 'Тестовый отказ сохранения лекала' })
        .waitFor();
    assert.equal(await code.inputValue(), 'PAT-130-RENAMED');
    state.failWrite = false;
    for (const [width, height] of [
        [320, 850],
        [390, 850],
        [736, 390],
        [1280, 850],
    ]) {
        await page.setViewportSize({ width, height });
        assert.ok(
            await page.evaluate(
                () => document.documentElement.scrollWidth <= innerWidth + 1,
            ),
            `Pattern editor overflows at ${width}`,
        );
        assert.ok(
            await editor
                .locator('form')
                .evaluate(
                    (form) =>
                        form.parentElement.scrollWidth <=
                        form.parentElement.clientWidth + 1,
                ),
            `Pattern form overflows at ${width}`,
        );
    }
    if (proofDir) {
        await editor
            .locator('form')
            .evaluate((form) => (form.parentElement.scrollTop = 0));
        await editor.screenshot({
            path: path.join(proofDir, 'pattern-editor.png'),
            animations: 'disabled',
        });
    }
    await editor
        .getByRole('button', { name: 'Сохранить', exact: true })
        .click();
    await editor.waitFor({ state: 'detached' });
    assert.equal(writes.length, 2);
    assert.deepEqual(writes[0].payload, writes[1].payload);
    assert.equal(writes[1].payload.expected_version, 7);
    assert.equal(writes[1].payload.name, 'Сохранённое имя файла');
    assert.equal(writes[1].payload.width_cm, '50.25');
    assert.equal(writes[1].payload.length_cm, '60.35');
    assert.equal(writes[1].payload.media_object_id, 90003);
    assert.equal(
        uploads.length,
        3,
        'Retrying a write must not upload the same confirmed file again',
    );
    await until(
        async () => (await models.count()) === 1,
        'Pattern summary after write missing',
    );
    if (!(await model.evaluate((node) => node.open)))
        await model.locator('summary').click();
    await model
        .getByRole('button', { name: 'Все файлы модели', exact: true })
        .click();
    const fileList = model.getByRole('region', {
            name: 'Файлы лекал модели',
            exact: true,
        }),
        fileButtons = fileList.getByRole('button', {
            name: /^Изменить лекало/,
        });
    await until(
        async () => (await fileButtons.count()) === 24,
        'Pattern file page missing',
    );
    state.failAppend = true;
    await fileList
        .getByRole('button', { name: 'Ещё файлы лекал', exact: true })
        .click();
    await fileList
        .getByRole('alert')
        .filter({ hasText: 'Тестовый отказ страницы лекал' })
        .waitFor();
    assert.equal(await fileButtons.count(), 24);
    state.failAppend = false;
    while (
        await fileList
            .getByRole('button', { name: 'Ещё файлы лекал', exact: true })
            .count()
    ) {
        const before = await fileButtons.count();
        await fileList
            .getByRole('button', { name: 'Ещё файлы лекал', exact: true })
            .click();
        await until(
            async () => (await fileButtons.count()) > before,
            'Pattern file continuation missing',
        );
    }
    assert.equal(await fileButtons.count(), 132);
    await fileButtons.filter({ hasText: 'архивный' }).waitFor();
    await fileButtons.filter({ hasText: '1000.25' }).waitFor();
    for (const width of [320, 390, 736]) {
        await page.setViewportSize({ width, height: 850 });
        assert.ok(
            await page.evaluate(
                () => document.documentElement.scrollWidth <= innerWidth + 1,
            ),
            `Pattern file list overflows at ${width}`,
        );
    }
    await fileButtons.filter({ hasText: 'PAT-130-131' }).click();
    await editor
        .getByRole('status')
        .filter({ hasText: 'Модель или размер архивные' })
        .waitFor();
    assert.equal(
        await editor
            .getByRole('button', { name: 'Сохранить', exact: true })
            .isDisabled(),
        true,
    );
    await editor.getByRole('button', { name: 'Закрыть', exact: true }).click();
    await page
        .getByRole('button', { name: 'Добавить лекало', exact: true })
        .click();
    const create = page.getByRole('dialog', {
            name: 'Новое лекало',
            exact: true,
        }),
        modelSelect = create.getByRole('combobox', {
            name: 'Модель',
            exact: true,
        });
    assert.equal(await modelSelect.inputValue(), '');
    assert.equal(await create.locator('form').count(), 0);
    await until(
        async () => (await modelSelect.getByRole('option').count()) === 25,
        'Pattern model choices missing',
    );
    while (
        await create
            .getByRole('button', { name: 'Ещё модели для лекала', exact: true })
            .count()
    ) {
        const before = await modelSelect.getByRole('option').count();
        await create
            .getByRole('button', { name: 'Ещё модели для лекала', exact: true })
            .click();
        await until(
            async () =>
                (await modelSelect.getByRole('option').count()) > before,
            'Pattern model choice continuation missing',
        );
    }
    assert.equal(await modelSelect.getByRole('option').count(), 131);
    await modelSelect.selectOption('130');
    const sizeSelect = create.getByRole('combobox', {
        name: 'Размер',
        exact: true,
    });
    await until(
        async () => (await sizeSelect.getByRole('option').count()) === 25,
        'Pattern sizes missing',
    );
    while (
        await create
            .getByRole('button', { name: 'Ещё размеры лекала', exact: true })
            .count()
    ) {
        const before = await sizeSelect.getByRole('option').count();
        await create
            .getByRole('button', { name: 'Ещё размеры лекала', exact: true })
            .click();
        await until(
            async () => (await sizeSelect.getByRole('option').count()) > before,
            'Pattern size continuation missing',
        );
    }
    assert.equal(await sizeSelect.getByRole('option').count(), 131);
    await sizeSelect.selectOption('2130');
    await create
        .getByRole('spinbutton', { name: 'Ширина изделия, см', exact: true })
        .waitFor();
    await create
        .getByRole('searchbox', { name: 'Найти модель лекала', exact: true })
        .fill('не найдено');
    await create
        .getByRole('searchbox', { name: 'Найти размер лекала', exact: true })
        .fill('не найдено');
    await until(
        async () =>
            (await create
                .getByRole('status')
                .filter({ hasText: 'По этому запросу ничего не найдено.' })
                .count()) === 2,
        'Pattern choices did not retain both selected identities',
    );
    assert.equal(await modelSelect.inputValue(), '130');
    assert.equal(await sizeSelect.inputValue(), '2130');
    await create
        .getByRole('spinbutton', { name: 'Ширина изделия, см', exact: true })
        .fill('51.25');
    assert.equal(
        await create
            .getByRole('button', { name: 'Сохранить', exact: true })
            .isDisabled(),
        true,
    );
    await create
        .getByRole('spinbutton', { name: 'Ширина изделия, см', exact: true })
        .fill('52.25');
    await create
        .getByRole('spinbutton', { name: 'Длина изделия, см', exact: true })
        .fill('62.35');
    await create.getByText('Рукав по росту', { exact: true }).click();
    await create
        .getByRole('button', { name: 'Сохранить', exact: true })
        .click();
    await create
        .getByRole('alert')
        .filter({ hasText: 'Загрузите файл лекала.' })
        .waitFor();
    assert.equal(writes.length, 2);
    await create.locator('input[type="file"]').setInputFiles(pdf);
    await create
        .getByText('replacement.pdf загружен', { exact: true })
        .waitFor();
    for (const [width, height] of [
        [320, 850],
        [390, 850],
        [736, 390],
        [1280, 850],
    ]) {
        await page.setViewportSize({ width, height });
        assert.ok(
            await page.evaluate(
                () => document.documentElement.scrollWidth <= innerWidth + 1,
            ),
            `New pattern form overflows at ${width}`,
        );
    }
    if (proofDir) {
        await create
            .locator('form')
            .evaluate((form) => (form.parentElement.scrollTop = 0));
        await create.screenshot({
            path: path.join(proofDir, 'pattern-new.png'),
            animations: 'disabled',
        });
    }
    await create
        .getByRole('button', { name: 'Сохранить', exact: true })
        .click();
    await create.waitFor({ state: 'detached' });
    const added = writes.at(-1).payload;
    assert.equal(added.garment_model_id, 130);
    assert.equal(added.garment_size_id, 2130);
    assert.equal(added.width_cm, '52.25');
    assert.equal(added.length_cm, '62.35');
    assert.equal(added.sleeve_variant, 'height');
    assert.equal(added.expected_version, undefined);
    assert.equal(added.media_object_id, 90004);
    assert.equal(added.name, added.code);
    assert.ok(
        reads
            .filter((row) => row.kind !== 'coverage')
            .every((row) => row.limit === '24'),
    );
    return {
        patternModels130: true,
        patternFiles132: true,
        patternSizes130: true,
        closedGridNoPrefetch: true,
        closedLateGridIgnored: true,
        patternGridMax72Slots: true,
        patternGridLastPage: true,
        geometryVersionRecovery: true,
        patternContextFailureAndRetry: true,
        patternDecimalNameAndMediaPreserved: true,
        patternUploadRetry: true,
        patternDraftAndWriteRetry: true,
        archivedFilesVisible: true,
        archivedSizeReadonly: true,
        newPatternAfter100: true,
        patternSelectionAcrossEmptySearch: true,
        patternGridStepValidation: true,
    };
}
