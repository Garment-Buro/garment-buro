import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import test from 'node:test';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const read = (...parts) => fs.readFileSync(path.join(root, ...parts), 'utf8');

const homeSource = read('app', 'page.tsx');
const platformEntrySource = read('components', 'platform', 'PlatformEntry.tsx');
const landingSource = read('components', 'landings', 'CollectionLanding.tsx');
const modelsSource = read('components', 'landings', 'CollectionModels.tsx');
const detailsSource = read('components', 'landings', 'CollectionDetails.tsx');
const revealSource = read('components', 'landings', 'LandingReveal.tsx');
const publicCatalogSource = read('lib', 'catalog', 'public.ts');
const adminSource = read('components', 'admin', 'AdminPartnersScreen.tsx');

test('the public home is platform first and no longer renders the catalog', () => {
    assert.match(homeSource, /PlatformEntry/);
    assert.match(platformEntrySource, /PartnerLandingDesktopGate/);
    assert.match(platformEntrySource, /PresentationSurface/);
    assert.match(platformEntrySource, /matchMedia/);
    assert.doesNotMatch(homeSource, /CatalogScreen|LandingPage|CatalogPresentationOverlay|getCatalogData/);
    assert.match(publicCatalogSource, /PUBLIC_CATALOG_ENABLED = false/);
});

test('partner landings use collection storytelling and send models to the constructor', () => {
    assert.match(landingSource, /CollectionHero/);
    assert.match(landingSource, /CollectionStory/);
    assert.match(landingSource, /CollectionModels/);
    assert.match(landingSource, /CollectionDetails/);
    assert.match(modelsSource, /\/constructor\?productId=\$\{product\.id\}&landing=/);
    assert.doesNotMatch(modelsSource, /\/product\//);
});

test('landing pages include conversion sections and accessible motion', () => {
    assert.match(detailsSource, /Как это работает/);
    assert.match(detailsSource, /<details/);
    assert.match(detailsSource, /href="#models"/);
    assert.match(revealSource, /IntersectionObserver/);
    assert.match(revealSource, /transitionDelay/);
});

test('the admin experience is centered on partners and landing management', () => {
    assert.match(adminSource, /PartnerCreateForm/);
    assert.match(adminSource, /LandingCreateForm/);
    assert.match(adminSource, /LandingList/);
    assert.match(adminSource, /updateLanding/);
});
