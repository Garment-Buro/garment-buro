import assert from 'node:assert/strict';
import test from 'node:test';
import { createCatalogQuery, defaultFilters, hasActiveFilters } from './serviceCatalog.ts';

test('selected groups, exact price bounds and order reach the server query', () => {
    assert.deepEqual(createCatalogQuery('Худи', {...defaultFilters, categories:[7,8], colors:['Чёрный'], source:'user', minPrice:8000, maxPrice:8000, sort:'cheap'}), {
        query:'Худи', categoryIds:[7,8], colors:['Чёрный'], source:'user', minPrice:8000, maxPrice:8000, sort:'cheap', limit:24,
    });
});

test('default catalog has no hidden maximum price or active-filter indicator', () => {
    assert.equal(defaultFilters.minPrice, 0);
    assert.equal(defaultFilters.maxPrice, null);
    assert.equal(hasActiveFilters(defaultFilters), false);
    assert.equal(hasActiveFilters({...defaultFilters, source:'user'}), true);
    assert.equal(hasActiveFilters({...defaultFilters, minPrice:4000}), true);
    assert.equal(hasActiveFilters({...defaultFilters, sort:'oldest'}), true);
});
