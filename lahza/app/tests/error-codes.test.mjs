import { test, after } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, readFileSync, writeFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { pathToFileURL } from 'node:url';
import ts from 'typescript';

// Engine xato kodlari (unsupported_codec: AV1 va boshqa dekodlanmaydigan video) -> tarjima kaliti.
const dir = mkdtempSync(join(tmpdir(), 'lahza-err-'));
after(() => rmSync(dir, { recursive: true, force: true }));
const code = ts.transpileModule(readFileSync(new URL('../src/lib/error-codes.ts', import.meta.url), 'utf8'), {
  compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext },
}).outputText;
writeFileSync(join(dir, 'err.mjs'), code);
const err = await import(pathToFileURL(join(dir, 'err.mjs')).href);

test('vazifa meta: unsupported_codec -> err.unsupportedCodec, kodek nomi label dan', () => {
  const job = { meta: { error_code: 'unsupported_codec', error_params: { codec: 'av1', label: 'AV1' } } };
  assert.deepEqual(err.jobCodedError(job), { key: 'err.unsupportedCodec', vars: { codec: 'AV1', label: 'AV1' } });
});

test('label bo\'lmasa kodek katta harfda; noma\'lum kod yoki kodsiz - null', () => {
  assert.equal(err.codedError('unsupported_codec', { codec: 'vp9' }).vars.codec, 'VP9');
  assert.equal(err.codedError('unsupported_codec').vars.codec, '?');
  assert.equal(err.jobCodedError({ meta: { error_code: 'hali_yoq_kod' } }), null);
  assert.equal(err.jobCodedError({ meta: {} }), null);
  assert.equal(err.codedError('toString'), null);
});

test('HTTP detail obyekti ajratiladi; satr/ro\'yxat detail - null', () => {
  const detail = { code: 'unsupported_codec', message: 'Bu video AV1 formatida', codec: 'av1', label: 'AV1' };
  assert.deepEqual(err.parseCodedDetail(detail),
    { message: 'Bu video AV1 formatida', code: 'unsupported_codec', params: { codec: 'av1', label: 'AV1' } });
  assert.equal(err.parseCodedDetail('fayl topilmadi'), null);
  assert.equal(err.parseCodedDetail([{ msg: 'x' }]), null);
  assert.equal(err.parseCodedDetail({ code: 'x' }), null);
  const apiErr = Object.assign(new Error('m'), { code: 'unsupported_codec', params: { codec: 'av1', label: 'AV1' } });
  assert.equal(err.apiCodedError(apiErr).key, 'err.unsupportedCodec');
  assert.equal(err.apiCodedError(new Error('oddiy')), null);
});

test('err.unsupportedCodec to\'rt tilda bor va {codec} hamda H.264 ni o\'z ichiga oladi', () => {
  for (const loc of ['uz', 'uz-Cyrl', 'ru', 'en']) {
    const src = readFileSync(new URL(`../src/i18n/${loc}.ts`, import.meta.url), 'utf8');
    const m = src.match(/"err\.unsupportedCodec":\s*"([^"]+)"/);
    assert.ok(m, `${loc}: kalit yo'q`);
    assert.match(m[1], /\{codec\}/);
    assert.match(m[1], /H\.264/);
  }
});

// ---- navbat/vazifa xato kodlari (engine core/errors.py) -------------------------------------
const ENGINE_CODES = ['unsupported_codec', 'file_not_found', 'media_invalid', 'no_audio', 'ffmpeg_failed',
  'tool_missing', 'libass_missing', 'model_missing', 'disk_full', 'permission_denied', 'out_of_memory',
  'timeout', 'network', 'download_failed', 'cancelled', 'already_running'];

test('engine core/errors.py dagi barcha kodlar ERROR_KEYS da bor', () => {
  const py = readFileSync(new URL('../../engine/src/lahza_engine/core/errors.py', import.meta.url), 'utf8');
  const engine = [...py.matchAll(/^[A-Z_]+ = "([a-z_]+)"/gm)].map((m) => m[1]);
  assert.deepEqual([...engine].sort(), [...ENGINE_CODES].sort());
  for (const c of ENGINE_CODES) assert.ok(err.ERROR_KEYS[c], `${c}: kalit yo'q`);
});

test('har bir xato kaliti to\'rt tilda bor va o\'zgaruvchilar bir xil', () => {
  const keys = [...Object.values(err.ERROR_KEYS), err.UNKNOWN_ERROR_KEY, 'err.details'];
  const src = Object.fromEntries(['uz', 'uz-Cyrl', 'ru', 'en'].map((loc) =>
    [loc, readFileSync(new URL(`../src/i18n/${loc}.ts`, import.meta.url), 'utf8')]));
  const placeholders = (s) => [...s.matchAll(/\{(\w+)\}/g)].map((m) => m[1]).sort();
  for (const key of keys) {
    const re = new RegExp(`"${key.replace('.', '\\.')}":\\s*"([^"]+)"`);
    const base = src.uz.match(re);
    assert.ok(base, `uz: ${key} yo'q`);
    for (const [loc, text] of Object.entries(src)) {
      const m = text.match(re);
      assert.ok(m, `${loc}: ${key} yo'q`);
      assert.deepEqual(placeholders(m[1]), placeholders(base[1]), `${loc}: ${key} o'zgaruvchilari`);
    }
  }
});

test('navbat elementi: kod -> tarjima kaliti, xom xabar batafsil sifatida', () => {
  const item = { error: 'fayl topilmadi: /a/x.mp4', error_code: 'file_not_found', error_params: { path: 'x.mp4' } };
  assert.deepEqual(err.describeQueueError(item),
    { key: 'err.fileNotFound', vars: { path: 'x.mp4' }, detail: 'fayl topilmadi: /a/x.mp4' });
  // parametr yo'q bo'lsa matnda {path} qolib ketmaydi
  assert.equal(err.describeQueueError({ error: 'x', error_code: 'file_not_found' }).vars.path, '—');
  assert.equal(err.describeError('ffmpeg_failed', {}, 'stderr').vars.rc, '?');
  assert.equal(err.describeError('tool_missing', { tool: 'ffprobe' }, null).vars.tool, 'ffprobe');
  assert.deepEqual(err.describeError('disk_full', {}, '[Errno 28] No space left on device'),
    { key: 'err.diskFull', vars: {}, detail: '[Errno 28] No space left on device' });
});

test('noma\'lum yoki yo\'q kod -> err.unknown + xom matn; eski element (kodsiz) ham ishlaydi', () => {
  assert.deepEqual(err.describeQueueError({ error: 'RuntimeError: yiqildi' }),
    { key: 'err.unknown', vars: {}, detail: 'RuntimeError: yiqildi' });
  assert.deepEqual(err.describeQueueError({ error: 'x', error_code: 'kelajak_kodi', error_params: null }).key, 'err.unknown');
  assert.equal(err.describeQueueError({ error: '   ', error_code: null }).detail, null);
  assert.equal(err.describeError('toString', null, 'm').key, 'err.unknown');
});

test('vazifa: meta.error_code + error', () => {
  const job = { error: 'ASR modeli o\'rnatilmagan', meta: { error_code: 'model_missing', error_params: {} } };
  assert.deepEqual(err.describeJobError(job), { key: 'err.modelMissing', vars: {}, detail: 'ASR modeli o\'rnatilmagan' });
  assert.equal(err.describeJobError({ error: null, meta: {} }).key, 'err.unknown');
  // unsupported_codec: vars eskicha (label -> codec)
  assert.deepEqual(err.describeJobError({ error: 'm', meta: { error_code: 'unsupported_codec', error_params: { codec: 'av1', label: 'AV1' } } }).vars,
    { codec: 'AV1', label: 'AV1' });
});
