import assert from 'node:assert/strict';
import test from 'node:test';
import { defaultFilters, filterCatalog, hasActiveFilters } from './serviceCatalog.ts';

const items = [
    { id: 'a', category: 'Майки', color: 'Чёрный', source: 'community', price: 3000, createdOrder: 1 },
    { id: 'b', category: 'Худи', color: 'Серый', source: 'user', price: 8000, createdOrder: 3 },
    { id: 'c', category: 'Майки', color: 'Белый', source: 'user', price: 30000, createdOrder: 2 },
    { id: 'd', category: 'Худи', color: 'Чёрный', source: 'community', price: 8000, createdOrder: 4 },
];
const ids = filters => filterCatalog(items, { ...defaultFilters, ...filters }).map(item => item.id);

test('price bounds are inclusive and filter groups combine', () => {
    assert.deepEqual(ids({}), ['d', 'b', 'c', 'a']);
    assert.deepEqual(ids({ categories: ['Худи'], colors: ['Чёрный'], source: 'community', minPrice: 8000, maxPrice: 8000 }), ['d']);
    assert.deepEqual(ids({ minPrice: 8001, maxPrice: 29999 }), []);
});
test('multiple categories and colors use OR within each group', () => {
    assert.deepEqual(ids({ categories: ['Майки', 'Худи'], colors: ['Чёрный', 'Белый'], source: 'user' }), ['c']);
});
test('each sort mode orders the selected products with a stable date tie-break', () => {
    assert.deepEqual(ids({ sort: 'expensive' }), ['c', 'd', 'b', 'a']);
    assert.deepEqual(ids({ sort: 'cheap' }), ['a', 'd', 'b', 'c']);
    assert.deepEqual(ids({ sort: 'oldest' }), ['a', 'c', 'b', 'd']);
    assert.deepEqual(items.map(item => item.id), ['a', 'b', 'c', 'd']);
});
test('reset values remove the active-filter indicator', () => {
    assert.equal(hasActiveFilters(defaultFilters), false);
    assert.equal(hasActiveFilters({ ...defaultFilters, source: 'user' }), true);
    assert.equal(hasActiveFilters({ ...defaultFilters, minPrice: 4000 }), true);
    assert.equal(hasActiveFilters({ ...defaultFilters, sort: 'oldest' }), true);
});
