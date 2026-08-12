import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";

const root = process.cwd();
const consentSource = [
    path.join(root, "components", "shared", "CookieConsent.tsx"),
    path.join(root, "hooks", "browser", "useCookieConsent.ts"),
].map(file => fs.readFileSync(file, "utf8")).join("\n");
const consentStyles = fs.readFileSync(path.join(root, "components", "shared", "CookieConsent.module.css"), "utf8");

test("cookie consent stays mounted while its fade out finishes", () => {
    assert.match(consentSource, /const COOKIE_CONSENT_FADE_OUT_MS = 360/);
    assert.match(consentSource, /const \[isMounted, setIsMounted\] = useState\(false\)/);
    assert.match(consentSource, /setIsMounted\(true\)[\s\S]*?window\.requestAnimationFrame\([\s\S]*?setIsVisible\(true\)/);
    assert.match(consentSource, /setIsVisible\(false\)[\s\S]*?window\.setTimeout\([\s\S]*?setIsMounted\(false\)[\s\S]*?COOKIE_CONSENT_FADE_OUT_MS/);
    assert.match(consentSource, /if \(!isMounted\) return null/);
    assert.match(consentStyles, /\.banner\s*\{[\s\S]*?opacity:\s*0;[\s\S]*?transition:\s*opacity 420ms cubic-bezier\(0\.4, 0, 0\.2, 1\)/);
    assert.match(consentStyles, /\.bannerVisible\s*\{[\s\S]*?opacity:\s*1/);
    assert.match(consentStyles, /\.bannerHidden\s*\{[\s\S]*?transition-duration:\s*360ms/);
});

test("cookie consent matches the adaptive category glass surface", () => {
    assert.match(consentStyles, /width:\s*min\(calc\(100vw - 16px\), 624px\)/);
    assert.match(consentStyles, /border-radius:\s*20px/);
    assert.match(consentStyles, /background:\s*rgb\(227 227 227 \/ 85%\)/);
    assert.match(consentStyles, /backdrop-filter:\s*blur\(12px\) saturate\(160%\)/);
    assert.match(consentStyles, /-webkit-backdrop-filter:\s*blur\(12px\) saturate\(160%\)/);
    assert.match(consentStyles, /rgba\(0, 0, 0, 0\.1\) 0 8px 32px/);
});
