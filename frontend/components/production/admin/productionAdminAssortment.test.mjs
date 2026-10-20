import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

const terminal = readFileSync(
    new URL('./ProductionAdminTerminal.tsx', import.meta.url),
    'utf8',
);
const workspace = readFileSync(
    new URL('./AdminAssortment.tsx', import.meta.url),
    'utf8',
);
const types = readFileSync(
    new URL('../../../lib/production/assortmentTypes.ts', import.meta.url),
    'utf8',
);
const api = readFileSync(
    new URL('../../../lib/api/productionAssortment.ts', import.meta.url),
    'utf8',
);
const css = readFileSync(
    new URL('./ProductionAdmin.module.css', import.meta.url),
    'utf8',
);
const patterns = (['AdminPatterns.tsx','PatternCoveragePanel.tsx','PatternEditor.tsx'].map(file=>readFileSync(new URL('./assortment/'+file,import.meta.url),'utf8')).join('\n')+readFileSync(new URL('../../../lib/production/patternEditor.ts',import.meta.url),'utf8')).replace(/\s+/g,' ');
const categoryEditor = readFileSync(new URL('./assortment/CategoryEditor.tsx',import.meta.url),'utf8');
const categoryDirectory = readFileSync(new URL('./assortment/CategoryDirectory.tsx',import.meta.url),'utf8');
const modelScreen = readFileSync(
    new URL('./assortment/AdminModels.tsx', import.meta.url),
    'utf8',
);
const models = modelScreen+'\n'+categoryEditor+'\n'+categoryDirectory+'\n'+['ModelEditorDialog.tsx','ModelIdentityFields.tsx','ModelSizesEditor.tsx'].map(file=>readFileSync(new URL('./assortment/'+file,import.meta.url),'utf8')).join('\n')+'\n'+readFileSync(new URL('../../../lib/production/modelEditor.ts',import.meta.url),'utf8')+'\n'+readFileSync(new URL('../../../hooks/production/useModelEditor.ts',import.meta.url),'utf8');
const dialog = readFileSync(
    new URL('./assortment/AssortmentDialog.tsx', import.meta.url),
    'utf8',
);
const products = readFileSync(
    new URL('./assortment/AdminProducts.tsx', import.meta.url),
    'utf8',
);
const boxes = readFileSync(
    new URL('./assortment/AdminBoxes.tsx', import.meta.url),
    'utf8',
);
const accessories = readFileSync(
    new URL('./assortment/AdminAccessories.tsx', import.meta.url),
    'utf8',
);
const fabrics = readFileSync(
    new URL('./assortment/AdminFabrics.tsx', import.meta.url),
    'utf8',
);
const techCards = readFileSync(
    new URL('./assortment/AdminTechCards.tsx', import.meta.url),
    'utf8',
);
const specification = readFileSync(
    new URL('../SpecificationForm.tsx', import.meta.url),
    'utf8',
);
const numberHelpers = readFileSync(
    new URL('../../../lib/production/numbers.ts', import.meta.url),
    'utf8',
);

test('admin exposes one product and warehouse workspace', () => {
    assert.match(terminal, /assortment: PiStorefront/);
    assert.match(terminal, /<AdminAssortment \/>/);
    for (const label of [
        'Модели',
        'Лекала',
        'Техкарты',
        'Ткани',
        'Фурнитура',
        'Коробки',
    ]) {
        assert.match(types, new RegExp(label));
    }
    assert.match(workspace, /aria-label="Разделы моделей и склада"/);
});

test('assortment uses the shared production administrator session', () => {
    assert.match(api, /\/production\/admin\/assortment/);
    assert.doesNotMatch(api, /Authorization/);
    assert.match(api, /requestJson/);
    assert.match(api, /FormData/);
});

test('assortment remains usable on phones', () => {
    assert.match(css, /\.subnav\s*\{[^}]*overflow-x:\s*auto/s);
    assert.match(
        css,
        /\.assortmentCards,[\s\S]*grid-template-columns:\s*1fr/,
    );
    assert.match(
        css,
        /\.assortmentDialog\s*\{[^}]*height:\s*100dvh/s,
    );
    assert.match(css, /\.measureGrid\s*\{[^}]*repeat\(2, minmax\(0, 1fr\)\)/s);
    assert.match(
        css,
        /\.patternIdentityGrid,[\s\S]*\.patternMeasurements\s*\{[^}]*grid-template-columns:\s*1fr/s,
    );
});

test('pattern editor uses model coverage and sleeve file variants', () => {
    assert.match(patterns, /type="range"/);
    assert.match(patterns, /step="2"/);
    assert.match(patterns, /Лекала по моделям/);
    assert.match(patterns, /Длина ↓ \/ Ширина →/);
    assert.match(patterns, /sleeve_variant/);
    assert.match(patterns, /Стандартный рукав/);
    assert.match(patterns, /Рукав по росту/);
    assert.doesNotMatch(patterns, /field="sleeve_length_cm"/);
    assert.doesNotMatch(patterns, /field="height_cm"/);
    assert.match(patterns, /className=\{styles\.patternFilePicker\}/);
    assert.match(patterns, /PDF, JPEG, PNG или WebP/);
    assert.match(patterns, /headerActions=/);
    assert.match(readFileSync(new URL('../../../lib/production/patternEditor.ts',import.meta.url),'utf8'), /name: editor\.name/);
    assert.doesNotMatch(patterns, />\s*Название\s*</);
    assert.doesNotMatch(patterns, /Ширина и длина должны попадать/);
    assert.match(dialog, />\s*Закрыть\s*</);
    assert.doesNotMatch(dialog, /PiX/);
});

test('model editor explains the flow and keeps one compact size editor open', () => {
    assert.match(models, /1\. Модель/);
    assert.match(models, /2\. Размеры/);
    assert.match(models, /3\. Диапазоны/);
    assert.match(models, /className=\{styles\.sizeCardList\}/);
    assert.match(models, /aria-selected=\{activeSizeIndex === index\}/);
    assert.match(models, /className=\{styles\.sizeDetailCard\}/);
    assert.match(models, /<SizeRangeEditor/);
    assert.match(models, /step="0\.01"/);
    assert.match(models, /Базовый размер/);
    assert.match(models, /Базовая ширина, см/);
    assert.match(models, /Базовая длина, см/);

    assert.match(models, /Имя модели на фото/);
    assert.match(models, /Рост модели на фото, см/);
    assert.match(models, /Длина по росту/);
    assert.match(models, /Стандартный/);
    assert.match(models, /Под рост/);
    assert.match(models, /className=\{styles\.sizeChartPreview\}/);
    assert.doesNotMatch(models, /Базовый рост, см/);
    assert.doesNotMatch(models, /Сначала задайте общие параметры/);
    assert.match(models, /model-categories/);
    assert.match(models, /Категории моделей/);
    assert.match(categoryEditor.replace(/\s+/g,''), /expected_version:draft.version/);
    assert.match(models, /Сохранить категорию/);
    assert.doesNotMatch(models, /code: categoryEditor\.code/);
    assert.doesNotMatch(models, /value=\{categoryEditor\.code\}/);
    assert.doesNotMatch(models, /min="0\.01"[\s\S]{0,80}step="2"/);
    for (const category of ['Майка', 'Худи', 'Штаны']) {
        assert.match(
            readFileSync(
                new URL(
                    '../../../../backend/migrations/versions/20260923_0050_garment_model_categories.py',
                    import.meta.url,
                ),
                'utf8',
            ),
            new RegExp(category),
        );
    }
});

test('tech cards explain model ownership and never create a second draft', () => {
    const text = techCards.replace(/\s+/g, ' ');
    assert.match(text, /Новая техкарта создаётся для модели без карты/);
    assert.match(text, /Для изменений создайте новую версию/);
    assert.match(text, /Сначала опубликуйте текущий черновик/);
    assert.match(text, /!draft \?/);
});

test('every assortment list has search, popup filters, and sorting', () => {
    for (const source of [
        models,
        patterns,
        techCards,
        fabrics,
        accessories,
        boxes,
        products,
    ]) {
        assert.match(source, /type="search"|Поиск /);
        assert.match(source, /<AdminFilters/);
        assert.match(source, /key: 'sorting'/);
    }
});

test('fabric purchase price is stored and shown per kilogram', () => {
    assert.match(types, /cost_per_kg: string \| null/);
    assert.match(fabrics, /Цена за кг/);
    assert.match(fabrics, /₽\/кг/);
    assert.doesNotMatch(fabrics, /Цена за метр/);
});

test('assortment dialog scrolls below an opaque fixed header', () => {
    assert.match(dialog, /className=\{styles\.assortmentDialogBody\}/);
    assert.match(
        css,
        /\.assortmentDialog\s*\{[^}]*overflow:\s*hidden/s,
    );
    assert.match(
        css,
        /\.assortmentDialogBody\s*\{[^}]*overflow-y:\s*auto/s,
    );
    assert.doesNotMatch(
        css,
        /\.dialogHeading\s*\{[^}]*position:\s*sticky/s,
    );
});

test('product cards show catalog images and keep compact mobile structure', () => {
    assert.match(readFileSync(new URL('../../../lib/products/adminCatalog.ts', import.meta.url),'utf8'), /image_url: string \| null/);
    assert.match(products, /safeImage\(product\.image_url\)/);
    assert.match(products, /className=\{styles\.productMedia\}/);
    assert.match(products, /Нет фото/);
    assert.match(products, /className=\{styles\.productFacts\}/);
    assert.match(
        css,
        /\.productCard\s*\{[^}]*grid-template-columns:\s*152px minmax\(0, 1fr\)/s,
    );
    assert.match(
        css,
        /@media \(max-width: 640px\)[\s\S]*\.productCard\s*\{[^}]*grid-template-columns:\s*104px minmax\(0, 1fr\)/s,
    );
});

test('packaging rule explains capacity and selection order', () => {
    assert.match(boxes, /Модель[\s\S]*Коробка[\s\S]*Количество/);
    assert.match(boxes, /Максимум изделий этой модели/);
    assert.match(boxes.replace(/\s+/g, ' '), /0 — основная коробка, 1 и далее — запасные/);
    assert.match(boxes, /меньшее число означает более высокий приоритет/);
    assert.doesNotMatch(boxes, /Фото коробки/);
    assert.doesNotMatch(boxes, /type="file"/);
});

test('products open as blanks and community landing card workspaces', () => {
    assert.match(products, /Garment Buro/);
    assert.match(products, />Пресеты по лендингам</);
    assert.match(products, /useAdminLandingDirectory/);
    assert.match(products, /className=\{styles\.catalogHubCard\}/);
    assert.match(products, /className=\{styles\.communityCard\}/);
    assert.match(categoryEditor, /categorySlug/);
});

test('stored decimal values remain compact across editors', () => {
    assert.match(numberHelpers, /replace\(\/0\+\$\//);
    for (const source of [models, patterns, boxes, accessories, fabrics, specification]) {
        assert.match(source, /compactDecimal/);
    }
});

test('every assortment file input exposes upload progress and outcome', () => {
    for (const source of [models, patterns, accessories]) {
        assert.match(source, /state:\s*'uploading'/);
        assert.match(source, /state:\s*'success'/);
        assert.match(source, /state:\s*'error'/);
        assert.match(source, /<FileUploadStatus value=\{uploadStatus\}\s*\/>/);
    }
    assert.match(dialog, /aria-live="polite"/);
    assert.match(dialog, /role=\{value\.state === 'error' \? 'alert' : 'status'\}/);
});
