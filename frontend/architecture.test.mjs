import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import test from 'node:test';

const root = process.cwd();
const sourceRoots = ['app', 'components', 'hooks', 'lib', 'providers', 'store'];
const sourceExtensions = new Set(['.ts', '.tsx']);

const collectFiles = (directory) => fs.readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const entryPath = path.join(directory, entry.name);
    if (entry.isDirectory()) return collectFiles(entryPath);
    if (!sourceExtensions.has(path.extname(entry.name)) || entry.name.endsWith('.d.ts')) return [];
    return [entryPath];
});

const files = sourceRoots.flatMap((directory) => collectFiles(path.join(root, directory)));
const importsFrom = (source) => Array.from(
    source.matchAll(/(?:import|export)\s+(?:type\s+)?(?:[^'";]+?\s+from\s+)?['"]([^'"]+)['"]/g),
    (match) => match[1],
);

const resolvesInside = (file, importPath, directory) => {
    if (importPath.startsWith('@/')) {
        return importPath.slice(2).split('/')[0] === directory;
    }
    if (!importPath.startsWith('.')) return false;
    return path.resolve(path.dirname(file), importPath).startsWith(path.join(root, directory));
};

test('architecture keeps domain and state layers independent from UI and routes', () => {
    const violations = [];

    for (const file of files) {
        const relativeFile = path.relative(root, file);
        const source = fs.readFileSync(file, 'utf8');
        const importPaths = importsFrom(source);

        if ((relativeFile.startsWith('lib/') || relativeFile.startsWith('hooks/'))
            && importPaths.some((importPath) => resolvesInside(file, importPath, 'components'))) {
            violations.push(`${relativeFile}: domain/state code imports components`);
        }

        if (!relativeFile.startsWith('app/')
            && importPaths.some((importPath) => resolvesInside(file, importPath, 'app'))) {
            violations.push(`${relativeFile}: feature code imports route implementation`);
        }

        const canCallFetch = relativeFile.startsWith('lib/api/')
            || relativeFile.startsWith('lib/server/');
        if (!canCallFetch && /\bfetch\s*\(/.test(source)) {
            violations.push(`${relativeFile}: fetch must live in lib/api or lib/server`);
        }

        if (!relativeFile.startsWith('lib/server/')
            && !relativeFile.startsWith('app/api/')
            && /\bNEXT_PUBLIC_API_URL\b/.test(source)) {
            violations.push(`${relativeFile}: browser-facing code must call the same-origin /api boundary`);
        }

        if (relativeFile.startsWith('lib/api/')
            && /\bfetch\s*\(\s*[`'"]https?:\/\//.test(source)) {
            violations.push(`${relativeFile}: browser API modules must not call external origins`);
        }

        if (relativeFile !== 'lib/browser/config/vendorScripts.ts'
            && /https:\/\/(?:api-maps\.yandex\.ru|cdn\.jsdelivr\.net)/.test(source)) {
            violations.push(`${relativeFile}: browser SDK origins must be centralized in vendorScripts.ts`);
        }

        if (relativeFile !== 'lib/browser/config/vendorScripts.ts'
            && /dd86a252-8ccc-4407-a540-be0d5228a3a7/.test(source)) {
            violations.push(`${relativeFile}: browser SDK keys must be centralized in vendorScripts.ts`);
        }

        if (relativeFile.startsWith('lib/api/')
            && relativeFile !== 'lib/api/http.ts'
            && /\bfetch\s*\(/.test(source)) {
            violations.push(`${relativeFile}: browser fetch must be centralized in lib/api/http.ts`);
        }

        if (relativeFile.startsWith('components/shared/')
            && importPaths.some((importPath) => resolvesInside(file, importPath, 'store'))) {
            violations.push(`${relativeFile}: shared UI must not own global feature state`);
        }

        if (relativeFile.endsWith('/page.tsx')
            && /\buse(?:State|Effect|LayoutEffect|Memo|Callback|Reducer)\s*\(/.test(source)) {
            violations.push(`${relativeFile}: route page owns React state or effects`);
        }
    }

    assert.deepEqual(violations, []);
});
