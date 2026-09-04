import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const pageSource = fs.readFileSync(
    path.join(root, "app", "light-running", "page.tsx"),
    "utf8",
);
const componentSource = fs.readFileSync(
    path.join(root, "components", "light-running", "LightRunningIntro.tsx"),
    "utf8",
);
const stylesSource = fs.readFileSync(
    path.join(root, "components", "light-running", "LightRunningIntro.module.css"),
    "utf8",
);
const cartSource = fs.readFileSync(
    path.join(root, "components", "light-running", "LightRunningCartAction.tsx"),
    "utf8",
);
const chromeSource = fs.readFileSync(
    path.join(root, "lib", "browser", "utils", "pageChrome.ts"),
    "utf8",
);

test("Light Running has its own route and supplied assets", () => {
    assert.match(pageSource, /LightRunningIntro/);
    assert.match(componentSource, /Лого-LR\.webp/);
    assert.match(componentSource, /Бегуны-черные\.webp/);
    assert.match(componentSource, /RAUM\.svg/);
});

test("Light Running intro preserves the supplied vertical geometry", () => {
    assert.match(stylesSource, /padding-top:\s*105px/);
    assert.match(stylesSource, /\.logo\s*\{[\s\S]*?width:\s*304px[\s\S]*?height:\s*63px[\s\S]*?margin-bottom:\s*33px/);
    assert.match(stylesSource, /\.brandLine\s*\{[\s\S]*?margin-bottom:\s*137px/);
    assert.match(stylesSource, /\.runners\s*\{[\s\S]*?height:\s*587px[\s\S]*?margin-bottom:\s*55px/);
    assert.match(stylesSource, /\.copy\s*\{[\s\S]*?gap:\s*23px/);
});

test("Light Running interpolates the 370 and 560 pixel widths", () => {
    assert.match(stylesSource, /297px,[\s\S]*?calc\(33\.1579vw \+ 174\.3158px\),[\s\S]*?360px/);
    assert.match(stylesSource, /251px,\s*calc\(23\.1579vw \+ 165\.3158px\),\s*295px/);
});

test("Light Running copy follows the refined marker and edge offsets", () => {
    assert.match(componentSource, /sloganRow[\s\S]*?<TriangleMark \/>/);
    assert.match(stylesSource, /\.triangleRotated\s*\{[\s\S]*?width:\s*7px[\s\S]*?height:\s*4px/);
    assert.match(stylesSource, /\.copy\s*\{[\s\S]*?width:\s*max-content[\s\S]*?margin-right:\s*clamp\(18px,\s*calc\(28\.4211vw - 87\.1579px\),\s*72px\)[\s\S]*?margin-bottom:\s*18px/);
    assert.match(stylesSource, /\.slogan\s*\{[\s\S]*?margin-top:\s*-3px/);
    assert.match(stylesSource, /\.description\s*\{[\s\S]*?padding-left:\s*17px/);
});

test("Light Running continues with the gradient label and supplied model image", () => {
    assert.match(componentSource, /runInLightBand[^>]*\/>[\s\S]*?runInLightLabel[\s\S]*?RUN IN LIGHT/);
    assert.match(componentSource, /Модель-в-майке-расширенно\.webp/);
    assert.match(componentSource, /Модель-в-майке-расширенно\.webp[\s\S]*?unoptimized/);
    assert.match(stylesSource, /\.runInLightBand\s*\{[\s\S]*?height:\s*63px[\s\S]*?linear-gradient\(0deg,\s*#4D4D4D 0%,\s*#141414 100%\)/);
    assert.match(stylesSource, /\.runInLightLabel\s*\{[\s\S]*?margin-left:\s*clamp\(13px,\s*calc\(19\.4737vw - 59\.0526px\),\s*50px\)[\s\S]*?padding-top:\s*12px[\s\S]*?padding-bottom:\s*12px[\s\S]*?gap:\s*9px/);
    assert.match(stylesSource, /\.modelImageBlock\s*\{[\s\S]*?width:\s*100vw[\s\S]*?height:\s*678px[\s\S]*?overflow:\s*hidden/);
    assert.match(stylesSource, /\.modelImage\s*\{[\s\S]*?object-fit:\s*cover/);
    assert.match(stylesSource, /\.modelBottomFade\s*\{[\s\S]*?height:\s*25px[\s\S]*?linear-gradient\(180deg,\s*rgba\(20,\s*20,\s*20,\s*0\.00\) 0%,\s*#141414 100%\)/);
});

test("Light Running serves lightweight WebP assets without cropping the runners", () => {
    assert.match(componentSource, /Бегуны-черные\.webp[\s\S]*?unoptimized/);
    assert.match(stylesSource, /\.runnersImage\s*\{[\s\S]*?object-fit:\s*contain[\s\S]*?object-position:\s*left top/);
});

test("Light Running model CTA straddles the photo and keeps the requested footer space", () => {
    assert.match(componentSource, /customizeButton[\s\S]*?Настроить мерч[\s\S]*?viewBox="0 0 18 14"/);
    assert.match(componentSource, /href="\/constructor\?productId=1"/);
    assert.match(componentSource, /prefetch=\{false\}/);
    assert.match(stylesSource, /\.modelImageBlock\s*\{[\s\S]*?margin-bottom:\s*155px/);
    assert.match(stylesSource, /\.customizeButton\s*\{[\s\S]*?bottom:\s*-22px[\s\S]*?width:\s*clamp\(230px,\s*calc\(50vw \+ 45px\),\s*325px\)[\s\S]*?height:\s*50px[\s\S]*?padding:\s*19px 0[\s\S]*?border-radius:\s*20px[\s\S]*?background:\s*#F1F1F1/);
    assert.match(stylesSource, /\.customizeButtonContent\s*\{[\s\S]*?gap:\s*clamp\(25px,\s*calc\(6\.8421vw - 0\.3158px\),\s*38px\)/);
    assert.match(stylesSource, /\.customizeButtonText\s*\{[\s\S]*?font-size:\s*15px[\s\S]*?font-weight:\s*700[\s\S]*?line-height:\s*150%/);
    assert.match(stylesSource, /\.customizeButtonArrow\s*\{[\s\S]*?width:\s*16px[\s\S]*?height:\s*12px/);
});

test("Light Running model photo carries the supplied centered overlays", () => {
    assert.match(componentSource, /modelLightMessage[\s\S]*?LIGHT[\s\S]*?DRIVES US[\s\S]*?<TriangleMark \/>/);
    assert.match(componentSource, /modelMonogram}>LR/);
    assert.match(stylesSource, /\.modelLightMessage\s*\{[\s\S]*?top:\s*395px[\s\S]*?left:\s*50%[\s\S]*?padding-right:\s*82px[\s\S]*?gap:\s*7px[\s\S]*?font-size:\s*10px[\s\S]*?font-weight:\s*500/);
    assert.match(stylesSource, /\.modelLightMessage > p\s*\{[\s\S]*?margin-top:\s*-3px/);
    assert.match(stylesSource, /\.modelMonogram\s*\{[\s\S]*?top:\s*525px[\s\S]*?left:\s*50%[\s\S]*?padding-left:\s*200px[\s\S]*?font-size:\s*10px[\s\S]*?font-weight:\s*500/);
});

test("Light Running uses an always-visible V2 cart action", () => {
    assert.match(componentSource, /<LightRunningCartAction \/>/);
    assert.match(componentSource, /id="light-running-run-in-light"/);
    assert.match(cartSource, /import \{ CartActionBarV2 \} from "@\/components\/cart\/CartActionBarV2"/);
    assert.match(cartSource, /getActiveCatalogCartItem\(items,\s*activeItemId\)/);
    assert.match(cartSource, /<CartActionBarV2/);
    assert.match(cartSource, /shiftAfterElementId="light-running-run-in-light"/);
    assert.match(cartSource, /router\.push\("\/profile"\)/);
    assert.match(cartSource, /onLogin=\{goToProfile\}/);
    assert.doesNotMatch(cartSource, /visible=\{items\.length > 0\}/);
    assert.match(cartSource, /router\.push\("\/checkout"\)/);
    assert.match(cartSource, /\/constructor\?productId=\$\{activeItem\.product_id\}&editCartItemId=/);
});

test("Light Running owns the dark page chrome without site header or footer", () => {
    assert.match(chromeSource, /page:\s*"light-running"[\s\S]*?topColor:\s*"#141414"[\s\S]*?pageColor:\s*"#141414"/);
    assert.match(chromeSource, /SITE_CHROME_HIDDEN_ROUTES[\s\S]*?'\/light-running'/);
});
