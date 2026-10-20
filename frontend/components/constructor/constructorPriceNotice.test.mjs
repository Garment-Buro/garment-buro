import assert from 'node:assert/strict';
import test from 'node:test';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
import {createRequire} from 'node:module';
import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import ts from 'typescript';

// Execute the actual notice function; the other exported component requires
// Next's auth popup runtime, which this notice does not render or depend on.
const file = ts.createSourceFile('notice.tsx', readFileSync(new URL('./ConstructorProjectStatus.tsx', import.meta.url), 'utf8'), ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
const notice = file.statements.find(node => ts.isFunctionDeclaration(node) && node.name?.text === 'ConstructorProjectNotice');
const js = ts.transpileModule(notice.getText(file), {compilerOptions: {jsx: ts.JsxEmit.ReactJSX, module: ts.ModuleKind.CommonJS}}).outputText;
const evaluatedModule = {exports: {}};
vm.runInNewContext(js, {exports: evaluatedModule.exports, module: evaluatedModule, require: createRequire(import.meta.url)});
const controller = {
    projectSession: {status:'idle', account:{sessionReady:true,userId:1}, isExisting:true, document:{id:42,product_id:7}},
    product: {id:7}, saveNotice: 'Сохранено в аккаунте.',
};
test('a saved notice cannot hide price failure recovery while purchase is blocked', () => {
    const markup = renderToStaticMarkup(React.createElement(evaluatedModule.exports.ConstructorProjectNotice, {controller: {
        ...controller, pricing: {error:new TypeError('Offline'), quote:null, retry(){}},
    }}));
    assert.ok(markup.includes('Повторить расчёт'));
    assert.ok(markup.includes('role="alert"'));
});
test('pending reprice takes precedence over a previous save confirmation', () => {
    const markup = renderToStaticMarkup(React.createElement(evaluatedModule.exports.ConstructorProjectNotice, {controller: {
        ...controller, pricing: {error:null, quote:null, retry(){}},
    }}));
    assert.ok(markup.includes('Рассчитываем стоимость'));
});
