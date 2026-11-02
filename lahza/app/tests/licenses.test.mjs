import { test, after } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, readFileSync, writeFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { pathToFileURL } from 'node:url';
import ts from 'typescript';

const dir = mkdtempSync(join(tmpdir(), 'lahza-licenses-'));
after(() => rmSync(dir, { recursive: true, force: true }));
for (const [file, output] of [['lib/licenses', 'lib'], ['i18n/licenses/index', 'i18n']]) {
  const code = ts.transpileModule(readFileSync(new URL(`../src/${file}.ts`, import.meta.url), 'utf8'), {
    compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext },
  }).outputText;
  writeFileSync(join(dir, `${output}.mjs`), code);
}
const lib = await import(pathToFileURL(join(dir, 'lib.mjs')).href);
const { licensesDictionaries, fill } = await import(pathToFileURL(join(dir, 'i18n.mjs')).href);
const data = JSON.parse(readFileSync(new URL('../src/generated/licenses.json', import.meta.url), 'utf8'));

const comp = (over) => ({ id: 'x', group: 'npm', category: 'npm', name: 'react', version: '19.0.0', license: 'MIT', basis: '',
  via: '', url: '', notes: '', attribution: '', risk: '', texts: [], ...over });
const sample = [
  comp({ id: 'npm:react', name: 'react' }),
  comp({ id: 'rust:serde', category: 'rust', group: 'rust', name: 'serde', license: 'MIT OR Apache-2.0' }),
  comp({ id: 'rust:windows', category: 'rust', group: 'rust', name: 'windows-sys', license: 'ANIQLANSIN' }),
  comp({ id: 'model:x', category: 'model', group: 'model', name: 'Model X', license: 'CC-BY-4.0', attribution: 'Author (CC-BY-4.0)' }),
  comp({ id: 'runtime:ffmpeg', category: 'runtime', group: 'runtime', name: 'FFmpeg', version: '7.1.1', license: 'LGPL-2.1-or-later', texts: ['a', 'missing'] }),
];

test('qidiruv: bir nechta so‘z, registrga befarq, atributsiya va litsenziya bo‘yicha', () => {
  assert.deepEqual(lib.filterComponents(sample, 'APACHE serde').map((c) => c.name), ['serde']);
  assert.deepEqual(lib.filterComponents(sample, 'author').map((c) => c.name), ['Model X']);
  assert.equal(lib.filterComponents(sample, '').length, sample.length);
  assert.equal(lib.filterComponents(sample, 'yoq-narsa').length, 0);
});

test('tur filtri va ANIQLANSIN filtri', () => {
  assert.deepEqual(lib.filterComponents(sample, '', 'rust').map((c) => c.name), ['serde', 'windows-sys']);
  assert.deepEqual(lib.filterComponents(sample, '', 'unresolved').map((c) => c.name), ['windows-sys']);
  assert.equal(lib.isUnresolved(comp({ version: 'ANIQLANSIN' })), true);
});

test('sonlar, saralash, statistika', () => {
  const counts = lib.categoryCounts(sample);
  assert.equal(counts.all, 5);
  assert.equal(counts.rust, 2);
  assert.equal(counts.unresolved, 1);
  assert.equal(counts.font, 0);
  assert.deepEqual(lib.sortComponents(sample).map((c) => c.category), ['runtime', 'npm', 'rust', 'rust', 'model']);
  assert.deepEqual(lib.licenseSummary(sample, 2), [['ANIQLANSIN', 1], ['CC-BY-4.0', 1]]);
  assert.equal(lib.ffmpegComponent(sample)?.version, '7.1.1');
});

test('to‘liq matn: pulda yo‘q id tashlab yuboriladi', () => {
  const texts = lib.componentTexts({ texts: { a: { title: 'LICENSE', body: 'text' } } }, sample[4]);
  assert.deepEqual(texts, [{ title: 'LICENSE', body: 'text' }]);
});

test('i18n: barcha tillarda bir xil kalitlar va har bir tur uchun nom', () => {
  const keys = Object.keys(licensesDictionaries.uz).sort();
  for (const loc of ['uz', 'uz-Cyrl', 'ru', 'en']) {
    assert.deepEqual(Object.keys(licensesDictionaries[loc]).sort(), keys, loc);
    for (const cat of lib.CATEGORY_ORDER) assert.ok(licensesDictionaries[loc][`cat_${cat}`], `${loc} cat_${cat}`);
    assert.match(fill(licensesDictionaries[loc].lgplBody, { version: '7.1.1', url: 'u' }), /7\.1\.1/);
  }
});

test('generatsiya qilingan JSON: tuzilma, matn havolalari, asosiy komponentlar', () => {
  assert.equal(data.schema_version, 1);
  const ids = new Set();
  for (const c of data.components) {
    assert.ok(lib.CATEGORY_ORDER.includes(c.category), c.id);
    assert.ok(!ids.has(c.id), `takror: ${c.id}`);
    ids.add(c.id);
    for (const t of c.texts) assert.ok(data.texts[t], `${c.id}: matn ${t} yo‘q`);
  }
  const counts = lib.categoryCounts(data.components);
  for (const cat of ['python', 'npm', 'rust', 'runtime', 'font', 'model']) assert.ok(counts[cat] > 0, cat);
  const ffmpeg = lib.ffmpegComponent(data.components);
  assert.match(ffmpeg.license, /^LGPL/);
  assert.ok(data.components.some((c) => c.category === 'font' && c.license === 'OFL-1.1' && c.texts.length));
});
