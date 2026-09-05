import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";

const root = process.cwd();
const componentSource = fs.readFileSync(
    path.join(root, "components", "presentation", "PresentationSurface.tsx"),
    "utf8",
);
const stylesSource = fs.readFileSync(
    path.join(root, "components", "presentation", "PresentationSurface.module.css"),
    "utf8",
);
const roadmapSource = fs.readFileSync(
    path.join(root, "components", "presentation", "PresentationRoadmap.tsx"),
    "utf8",
);
const roadmapStylesSource = fs.readFileSync(
    path.join(root, "components", "presentation", "PresentationRoadmap.module.css"),
    "utf8",
);
const footerSource = fs.readFileSync(path.join(root, "components", "layout", "Footer.tsx"), "utf8");
const catalogOverlaySource = fs.readFileSync(
    path.join(root, "components", "presentation", "CatalogPresentationOverlay.tsx"),
    "utf8",
);
const homeSource = fs.readFileSync(path.join(root, "app", "page.tsx"), "utf8");
const presentationPageSource = fs.readFileSync(path.join(root, "app", "presentation", "page.tsx"), "utf8");

test("presentation implementation is retained while the catalog surface is paused", () => {
    assert.equal(fs.existsSync(path.join(root, "app", "presentation", "page.tsx")), true);
    assert.equal(fs.existsSync(path.join(root, "app", "@modal", "(.)presentation", "page.tsx")), true);
    assert.doesNotMatch(footerSource, /href:\s*'\/presentation'/);
    assert.match(catalogOverlaySource, /useSearchParams/);
    assert.match(catalogOverlaySource, /searchParams\.get\("presentation"\) !== "open"/);
    assert.match(catalogOverlaySource, /<PresentationSurface isOverlay \/>/);
    assert.match(presentationPageSource, /PUBLIC_CATALOG_ENABLED/);
    assert.match(presentationPageSource, /notFound\(\)/);
    assert.doesNotMatch(homeSource, /CatalogPresentationOverlay|LandingPage/);
});

test("presentation sheet follows the requested viewport geometry and motion", () => {
    assert.match(stylesSource, /\.sheet\s*\{[\s\S]*?right:\s*3px;[\s\S]*?bottom:\s*0;[\s\S]*?left:\s*3px;/);
    assert.match(stylesSource, /height:\s*calc\(100dvh - 95px\)/);
    assert.match(stylesSource, /border-radius:\s*20px 20px 0 0/);
    assert.match(stylesSource, /background:\s*#fff/);
    assert.match(stylesSource, /background-image:\s*url\('\/Шапка\.webp'\)/);
    assert.match(stylesSource, /background-color:\s*rgb\(3 61 100 \/ 22%\)/);
    assert.match(stylesSource, /\.standaloneRoot \.sheet\s*\{[\s\S]*?position:\s*relative;[\s\S]*?height:\s*auto;[\s\S]*?overflow:\s*visible/);
    assert.match(stylesSource, /@keyframes presentation-sheet-in[\s\S]*?translate3d\(0,\s*100%,\s*0\)[\s\S]*?translate3d\(0,\s*0,\s*0\)/);
});

test("presentation hero and roadmap rails follow the requested sticky scroll behavior", () => {
    assert.match(componentSource, /const heroRef = useRef<HTMLDivElement>\(null\)/);
    assert.match(componentSource, /const heroPeekHeight = 97 \+ \(25 \* viewportProgress\)/);
    assert.match(componentSource, /const scrollTop = isOverlay \? sheet\.scrollTop : window\.scrollY/);
    assert.match(componentSource, /hero\.dataset\.heroPeekPinned = String\(scrollTop >= pinThreshold\)/);
    assert.match(componentSource, /data-hero-peek-pinned="false"/);
    assert.match(stylesSource, /\.hero\s*\{[\s\S]*?position:\s*sticky;[\s\S]*?top:\s*0/);
    assert.match(stylesSource, /\.hero\[data-hero-peek-pinned="true"\]\s*\{[\s\S]*?clip-path:\s*inset\(0 0 calc\(100% - var\(--presentation-hero-peek\)\) 0\)/);
    assert.match(stylesSource, /\.content\s*\{[\s\S]*?position:\s*relative;[\s\S]*?padding:\s*30px 0 0/);
    assert.match(roadmapStylesSource, /\.decision\s*\{[\s\S]*?position:\s*sticky;[\s\S]*?top:\s*var\(--presentation-hero-peek\)/);
    assert.match(roadmapStylesSource, /\.mediaColumn\s*\{[\s\S]*?position:\s*sticky;[\s\S]*?top:\s*calc\(var\(--presentation-hero-peek\) \+ 73px\)/);
});

test("presentation interpolates the supplied 370 and 560 pixel hero sizes", () => {
    assert.match(componentSource, /className=\{styles\.heroMedia\}[\s\S]*?src="\/Шапка\.webp"/);
    assert.match(stylesSource, /\.hero\s*\{[\s\S]*?width:\s*100%;[\s\S]*?background:\s*#fff/);
    assert.match(stylesSource, /\.heroMedia\s*\{[\s\S]*?left:\s*50%;[\s\S]*?width:\s*min\(calc\(100% \+ 1px\),\s*555px\);[\s\S]*?height:\s*100%;[\s\S]*?translateX\(-50%\)/);
    assert.match(stylesSource, /height:\s*clamp\(215px,\s*calc\(31\.579vw \+ 98\.158px\),\s*275px\)/);
    assert.match(stylesSource, /\.content\s*\{[\s\S]*?width:\s*100%;[\s\S]*?padding:\s*30px 0 0/);
    assert.match(stylesSource, /\.hero\s*\{[\s\S]*?margin-bottom:\s*0/);
});

test("presentation includes the supplied opening copy and typography roles", () => {
    assert.match(componentSource, /мы/);
    assert.match(componentSource, /GARMENT BURO/);
    assert.match(componentSource, /делаем общий мерч личным для[\s\S]*?каждого/);
    assert.match(componentSource, /Алексей Джипитиев/);
    assert.match(componentSource, /одежда[\s\S]*?это повод собраться/);
    assert.match(componentSource, /src="\/Шапка\.webp"/);
    assert.match(componentSource, /styles\.identityLead}>мы/);
    assert.match(componentSource, /styles\.identityBrand}>GARMENT BURO/);
    assert.match(componentSource, /личным для[\s\S]*?<br \/>[\s\S]*?каждого/);
    assert.match(componentSource, /внутри продукта[\s\S]*?<br \/>[\s\S]*?<br \/>[\s\S]*?styles\.platform/);
    assert.match(componentSource, /className=\{styles\.opening\}[\s\S]*?className=\{styles\.nextTitle\}[\s\S]*?<\/div>[\s\S]*?<PresentationRoadmap \/>/);
    assert.match(stylesSource, /\.content\s*\{[\s\S]*?box-sizing:\s*border-box;[\s\S]*?width:\s*100%;[\s\S]*?padding:\s*30px 0 0/);
    assert.match(stylesSource, /\.opening\s*\{[\s\S]*?width:\s*min\(355px,\s*100%\);[\s\S]*?margin:\s*0 auto/);
    assert.match(stylesSource, /\.identity\s*\{[\s\S]*?display:\s*flex;[\s\S]*?justify-content:\s*center/);
    assert.match(stylesSource, /\.identityLead,[\s\S]*?font-size:\s*15px;[\s\S]*?font-weight:\s*600;[\s\S]*?line-height:\s*22px/);
    assert.match(stylesSource, /\.identityBrand\s*\{[\s\S]*?font-family:\s*var\(--font-alumni-sans-sc\),\s*"Alumni Sans SC",\s*sans-serif;[\s\S]*?font-size:\s*24px;[\s\S]*?font-weight:\s*800;[\s\S]*?line-height:\s*22px;[\s\S]*?text-transform:\s*uppercase/);
    assert.match(stylesSource, /\.intro\s*\{[\s\S]*?font-size:\s*13px;[\s\S]*?font-weight:\s*500;[\s\S]*?line-height:\s*15px/);
    assert.match(stylesSource, /\.intro > p\s*\{[\s\S]*?flex:\s*1 1 0/);
    assert.match(stylesSource, /\.author\s*\{[\s\S]*?text-align:\s*right/);
    assert.match(stylesSource, /\.nextTitle\s*\{[\s\S]*?font-size:\s*32px;[\s\S]*?font-weight:\s*800;[\s\S]*?line-height:\s*30px/);
});

test("presentation roadmap keeps the supplied spacing, labels, and typography", () => {
    assert.match(stylesSource, /\.nextTitle\s*\{[\s\S]*?margin-bottom:\s*55px/);
    assert.match(roadmapSource, /если да то:/);
    assert.match(roadmapSource, /дорожная карта/);
    assert.match(roadmapSource, /captionLines:\s*\["Приходи в общем —",\s*"оставайся в своём!"\]/);
    assert.match(roadmapSource, /src="\/map_arrow\.svg"/);
    assert.match(roadmapStylesSource, /\.decision\s*\{[\s\S]*?margin-bottom:\s*43px;[\s\S]*?font-size:\s*20px;[\s\S]*?font-weight:\s*800;[\s\S]*?line-height:\s*30px;[\s\S]*?text-align:\s*right/);
    assert.match(roadmapStylesSource, /\.heading\s*\{[\s\S]*?margin-bottom:\s*34px;[\s\S]*?gap:\s*10px/);
    assert.match(roadmapStylesSource, /\.title\s*\{[\s\S]*?padding-left:\s*10px;[\s\S]*?font-size:\s*13px;[\s\S]*?font-weight:\s*800;[\s\S]*?line-height:\s*30px;[\s\S]*?white-space:\s*nowrap/);
    assert.match(roadmapStylesSource, /\.mediaCaption\s*\{[\s\S]*?margin-bottom:\s*30px;[\s\S]*?padding-left:\s*5px;[\s\S]*?font-size:\s*11px;[\s\S]*?font-style:\s*italic;[\s\S]*?line-height:\s*15px;[\s\S]*?letter-spacing:\s*1px;[\s\S]*?white-space:\s*nowrap/);
    assert.match(roadmapStylesSource, /\.stepText\s*\{[\s\S]*?font-size:\s*15px;[\s\S]*?font-weight:\s*500;[\s\S]*?line-height:\s*150%;[\s\S]*?text-align:\s*right/);
    assert.match(roadmapSource, /captionLines:\s*\["Участников должно",\s*"быть видно!"\]/);
    assert.match(roadmapSource, /captionLines:\s*\["Возможно вам",\s*"по пути!",\s*"Здесь видно,",\s*"что создают",\s*"другие\."\]/);
    assert.match(roadmapSource, /captionLines:\s*\["Чтобы понять",\s*"сообщество,",\s*"мало увидеть",\s*"его мерч\."\]/);
    assert.match(roadmapSource, /setActiveStepIndex[\s\S]*?activationLine[\s\S]*?isAtScrollEnd[\s\S]*?data-roadmap-caption-index/);
    assert.match(roadmapSource, /className=\{styles\.stepText\}>\{step\.title\}/);
    assert.match(roadmapStylesSource, /\.mediaCaptionLine\s*\{[\s\S]*?display:\s*block/);
});

test("presentation roadmap keeps the supplied media sizing", () => {
    assert.equal((roadmapSource.match(/<video/g) || []).length, 1);
    assert.match(roadmapSource, /data-roadmap-video-stage/);
    assert.equal((roadmapSource.match(/imageSrc:\s*"\/[1-5]\.webp"/g) || []).length, 5);
    assert.match(roadmapSource, /title:\s*"Настрой посадку"[\s\S]*?displayWidth:\s*217,[\s\S]*?displayHeight:\s*298/);
    assert.match(roadmapSource, /title:\s*"Добавь кастом"[\s\S]*?displayWidth:\s*240,[\s\S]*?displayHeight:\s*357/);
    assert.match(roadmapSource, /title:\s*"Создай профиль"[\s\S]*?displayWidth:\s*182,[\s\S]*?displayHeight:\s*295/);
    assert.match(roadmapSource, /title:\s*"Крути каталог"[\s\S]*?displayWidth:\s*195,[\s\S]*?displayHeight:\s*315/);
    assert.match(roadmapSource, /title:\s*"Будь в курсе"[\s\S]*?displayWidth:\s*258,[\s\S]*?displayHeight:\s*435/);
    assert.match(roadmapSource, /data-roadmap-step=\{index\}/);
    assert.match(roadmapStylesSource, /\.section\s*\{[\s\S]*?box-sizing:\s*border-box;[\s\S]*?width:\s*100%;[\s\S]*?padding-right:\s*clamp\(10px,\s*calc\(31\.579vw - 106\.842px\),\s*70px\);[\s\S]*?padding-left:\s*clamp\(10px,\s*calc\(31\.579vw - 106\.842px\),\s*70px\)/);
    assert.match(roadmapStylesSource, /\.layout\s*\{[\s\S]*?grid-template-columns:\s*minmax\(0,\s*1fr\) 258px;[\s\S]*?gap:\s*10px/);
    assert.match(roadmapStylesSource, /\.stepImage\s*\{[\s\S]*?width:\s*var\(--roadmap-step-width\);[\s\S]*?aspect-ratio:\s*var\(--roadmap-step-ratio\)/);
    assert.match(roadmapStylesSource, /\.steps\s*\{[\s\S]*?flex-direction:\s*column/);
    assert.match(roadmapStylesSource, /\.videoStage\s*\{/);
    assert.match(roadmapStylesSource, /\.videoActive\s*\{/);
});

test("presentation roadmap darkens after the custom step and keeps photos above the caption", () => {
    assert.match(roadmapStylesSource, /\.section\s*\{[\s\S]*?padding-bottom:\s*max\(55px,\s*env\(safe-area-inset-bottom\)\)/);
    assert.match(roadmapStylesSource, /\.section::before\s*\{[\s\S]*?z-index:\s*6;[\s\S]*?top:\s*783px;[\s\S]*?bottom:\s*0;[\s\S]*?linear-gradient\(180deg,\s*rgba\(102,\s*102,\s*102,\s*0\.00\) 0%,\s*rgba\(102,\s*102,\s*102,\s*0\.20\) 3\.37%,\s*#000 100%\)/);
    assert.doesNotMatch(roadmapStylesSource, /\.mediaColumn\s*\{[\s\S]*?background:/);
    assert.match(roadmapStylesSource, /\.mediaColumn\s*\{[\s\S]*?z-index:\s*1/);
    assert.match(roadmapStylesSource, /\.steps\s*\{[\s\S]*?z-index:\s*2/);
});

test("presentation roadmap applies the supplied per-step offsets", () => {
    assert.match(roadmapStylesSource, /\.step\[data-roadmap-step="0"\] \.stepImage\s*\{[\s\S]*?margin-top:\s*-10px;[\s\S]*?margin-right:\s*-25px/);
    assert.match(roadmapStylesSource, /\.step\[data-roadmap-step="1"\] \.stepText\s*\{[\s\S]*?padding-right:\s*8px/);
    assert.match(roadmapStylesSource, /\.step\[data-roadmap-step="1"\] \.stepImage\s*\{[\s\S]*?margin-top:\s*-10px;[\s\S]*?margin-right:\s*-10px/);
    assert.match(roadmapStylesSource, /\.step\[data-roadmap-step="2"\] \.stepText\s*\{[\s\S]*?padding-right:\s*10px/);
    assert.match(roadmapStylesSource, /\.step\[data-roadmap-step="2"\] \.stepImage,[\s\S]*?\.step\[data-roadmap-step="3"\] \.stepImage\s*\{[\s\S]*?margin-right:\s*-25px/);
    assert.match(roadmapStylesSource, /\.step\[data-roadmap-step="3"\] \.stepText\s*\{[\s\S]*?padding-right:\s*15px/);
    assert.match(roadmapStylesSource, /\.step\[data-roadmap-step="4"\] \.stepText\s*\{[\s\S]*?padding-right:\s*30px/);
});
