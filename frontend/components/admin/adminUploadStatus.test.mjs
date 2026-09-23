import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

const mediaField = readFileSync(
    new URL('./product-form/ProductMediaField.tsx', import.meta.url),
    'utf8',
);
const variantImage = readFileSync(
    new URL('./variant/VariantImageSlot.tsx', import.meta.url),
    'utf8',
);
const productForm = readFileSync(
    new URL('../../hooks/admin/useAdminProductForm.ts', import.meta.url),
    'utf8',
);

test('legacy administrator uploads expose loading, success, and error states', () => {
    for (const source of [mediaField, variantImage]) {
        assert.match(source, /aria-live="polite"/);
        assert.match(source, /uploading/);
        assert.match(source, /success/);
        assert.match(source, /error/);
    }
    assert.match(mediaField, /Загружаем:/);
    assert.match(mediaField, /Загружено:/);
    assert.match(mediaField, /Не удалось загрузить:/);
    assert.doesNotMatch(variantImage, /alert\('Ошибка загрузки'\)/);
    assert.match(productForm, /throw error/);
    assert.match(productForm, /if \(uploadError\) throw uploadError/);
});
