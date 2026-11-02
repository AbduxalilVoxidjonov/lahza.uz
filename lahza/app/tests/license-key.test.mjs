import { test, after } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, readFileSync, writeFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { pathToFileURL } from 'node:url';
import ts from 'typescript';

// Oflayn litsenziya paneli (V1-3, ADR-0016): ko'rinish bayrog'i, xato kodlari, i18n to'liqligi.
const dir = mkdtempSync(join(tmpdir(), 'lahza-lic-'));
after(() => rmSync(dir, { recursive: true, force: true }));
for (const [file, output] of [['lib/license-key', 'lib'], ['i18n/license-key/index', 'i18n']]) {
  const code = ts.transpileModule(readFileSync(new URL(`../src/${file}.ts`, import.meta.url), 'utf8'), {
    compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext },
  }).outputText;
  writeFileSync(join(dir, `${output}.mjs`), code);
}
const lib = await import(pathToFileURL(join(dir, 'lib.mjs')).href);
const { licenseKeyDictionaries } = await import(pathToFileURL(join(dir, 'i18n.mjs')).href);

const STATES = ['disabled', 'not_configured', 'unlicensed', 'valid', 'expired', 'not_yet_valid',
  'wrong_version', 'wrong_device', 'clock_rollback', 'invalid'];

test('panel faqat bayroq yoqilganda ko\'rinadi', () => {
  assert.equal(lib.licensePanelVisible(undefined), false);
  assert.equal(lib.licensePanelVisible(null), false);
  assert.equal(lib.licensePanelVisible({ enabled: false, state: 'disabled' }), false);
  assert.equal(lib.licensePanelVisible({ enabled: true, state: 'unlicensed' }), true);
  assert.equal(lib.licensePanelVisible({ enabled: true, state: 'not_configured' }), true);
});

test('engine "kod: xabar" detail\'idan kod ajratiladi', () => {
  assert.equal(lib.licenseErrorCode("bad_signature: imzo noto'g'ri"), 'bad_signature');
  assert.equal(lib.licenseErrorCode('expired: kalit bu qurilmada yaroqsiz: expired'), 'expired');
  assert.equal(lib.licenseErrorCode('Internal Server Error'), null);
  assert.equal(lib.licenseErrorCode(''), null);
});

test('holat rangi va kiritish tayyorligi', () => {
  assert.equal(lib.stateTone('valid'), 'good');
  assert.equal(lib.stateTone('unlicensed'), 'warn');
  assert.equal(lib.stateTone('expired'), 'bad');
  assert.equal(lib.keyInputReady('   '), false);
  assert.equal(lib.keyInputReady('LAHZA-AF4NU-TOOYE-FMEMA'), true);
});

test('4 tilda barcha holat va xato kodlari tarjima qilingan', () => {
  const locales = Object.keys(licenseKeyDictionaries).sort();
  assert.deepEqual(locales, ['en', 'ru', 'uz', 'uz-Cyrl']);
  const keys = Object.keys(licenseKeyDictionaries.en).sort();
  for (const loc of locales) {
    const d = licenseKeyDictionaries[loc];
    assert.deepEqual(Object.keys(d).sort(), keys, loc);
    for (const s of STATES) assert.ok(d[`state_${s}`]?.trim(), `${loc} state_${s}`);
    for (const c of lib.LICENSE_ERROR_CODES) assert.ok(d[`err_${c}`]?.trim(), `${loc} err_${c}`);
    for (const [k, v] of Object.entries(d)) assert.ok(v.trim(), `${loc}.${k}`);
  }
});
