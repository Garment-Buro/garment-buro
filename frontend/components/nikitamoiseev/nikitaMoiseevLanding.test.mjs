import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import test from 'node:test';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..');
const read = (...parts) => fs.readFileSync(path.join(root, ...parts), 'utf8');

const pageSource = read('app', 'nikitamoiseev', 'page.tsx');
const landingSource = read('components', 'nikitamoiseev', 'NikitaMoiseevLanding.tsx');
const mobileSource = read('components', 'nikitamoiseev', 'NikitaMobileDrop.tsx');
const desktopSource = read('components', 'nikitamoiseev', 'NikitaDesktopGate.tsx');
const carouselSource = read('components', 'nikitamoiseev', 'NikitaHoodieCarousel.tsx');
const storyRevealSource = read('components', 'nikitamoiseev', 'NikitaStoryReveal.tsx');
const sharedGateSource = read('components', 'landings', 'PartnerLandingDesktopGate.tsx');
const sharedGateCss = read('components', 'landings', 'PartnerLandingDesktopGate.module.css');
const cssSource = read('components', 'nikitamoiseev', 'NikitaMoiseevLanding.module.css');
const splashSource = read('lib', 'browser', 'utils', 'splash.ts');

test('Nikita Moiseev has a dedicated indexed campaign route', () => {
    assert.match(pageSource, /NikitaMoiseevLanding/);
    assert.match(pageSource, /canonical:\s*'\/nikitamoiseev'/);
    assert.match(pageSource, /themeColor:\s*'#E8F1F8'/);
    assert.match(landingSource, /NikitaMobileDrop/);
    assert.match(landingSource, /NikitaDesktopGate/);
    assert.match(splashSource, /'\/nikitamoiseev'/);
});

test('mobile campaign matches the supplied drop and opens the hoodie constructor', () => {
    assert.match(mobileSource, /Nikita Moiseev/);
    assert.match(mobileSource, /DROP&nbsp; 01/);
    assert.match(mobileSource, /MOVING/);
    assert.match(mobileSource, /CASTLE/);
    assert.match(mobileSource, /productId=5&landing=nikitamoiseev/);
    assert.match(mobileSource, /NikitaHoodieCarousel/);
});

test('the hoodie carousel is swipeable and exposes four controls', () => {
    assert.match(carouselSource, /slides = \[/);
    assert.match(carouselSource, /scrollTo/);
    assert.match(carouselSource, /requestAnimationFrame/);
    assert.match(cssSource, /scroll-snap-type:\s*x mandatory/);
    assert.match(cssSource, /clamp\(1059px/);
    assert.match(cssSource, /mix-blend-mode:\s*multiply/);
    assert.match(cssSource, /\.collectionNames\s*\{[\s\S]*?z-index:\s*4;[\s\S]*?width:\s*128%/);
    assert.match(storyRevealSource, /requestAnimationFrame/);
    assert.match(storyRevealSource, /--story-line-hidden/);
});

test('tablet and desktop show the reusable blurred-photo QR gate', () => {
    assert.match(desktopSource, /PartnerLandingDesktopGate/);
    assert.match(desktopSource, /\/api\/qr-code\?path=%2Fnikitamoiseev&size=1024/);
    assert.match(sharedGateSource, /Откройте дроп на телефоне/);
    assert.match(sharedGateCss, /@media \(min-width: 768px\)/);
    assert.match(sharedGateCss, /filter:\s*blur\(20px\)/);
    assert.match(sharedGateCss, /object-fit:\s*cover/);
    assert.match(sharedGateCss, /\.hint p\s*\{[\s\S]*?animation:\s*hintPulse/);
});
