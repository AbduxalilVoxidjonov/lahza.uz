import { test, after } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, readFileSync, writeFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { pathToFileURL } from 'node:url';
import ts from 'typescript';

// YouTube havolasidan import (YT-1, ADR-0010): havola tekshiruvi, rozilik, progress ko'rinishi, i18n.
const dir = mkdtempSync(join(tmpdir(), 'lahza-yt-'));
after(() => rmSync(dir, { recursive: true, force: true }));
for (const [file, output] of [['lib/youtube-import', 'yt'], ['i18n/youtube/index', 'i18n']]) {
  const code = ts.transpileModule(readFileSync(new URL(`../src/${file}.ts`, import.meta.url), 'utf8'), {
    compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext },
  }).outputText;
  writeFileSync(join(dir, `${output}.mjs`), code);
}
const yt = await import(pathToFileURL(join(dir, 'yt.mjs')).href);
const { youtubeDictionaries, youtubeErrors, fmt } = await import(pathToFileURL(join(dir, 'i18n.mjs')).href);

const VID = 'dQw4w9WgXcQ';

test('parseYoutubeVideoId: watch, youtu.be, shorts, live qabul qilinadi', () => {
  for (const url of [
    `https://www.youtube.com/watch?v=${VID}`,
    `https://youtube.com/watch?v=${VID}&list=PL123&t=42s`,
    `http://m.youtube.com/watch?feature=share&v=${VID}`,
    `https://youtu.be/${VID}?si=abc`,
    `youtu.be/${VID}`,
    `https://www.youtube.com/shorts/${VID}`,
    `  https://www.youtube.com/live/${VID}  `,
    `HTTPS://WWW.YOUTUBE.COM/watch?v=${VID}`,
  ]) assert.equal(yt.parseYoutubeVideoId(url), VID, url);
});

test('parseYoutubeVideoId: boshqa domen, playlist, kanal va noto\'g\'ri ID rad etiladi', () => {
  for (const url of [
    '', '   ',
    `https://vimeo.com/watch?v=${VID}`,
    `https://youtube.com.evil.com/watch?v=${VID}`,
    `https://evilyoutube.com/watch?v=${VID}`,
    `https://www.youtube.com/watch?v=${VID}x`,
    'https://www.youtube.com/watch?v=short',
    'https://www.youtube.com/playlist?list=PL1234567890',
    'https://www.youtube.com/@kanal',
    `https://www.youtube.com/watch?v=${VID}&v=aaaaaaaaaaa`,
    `ftp://youtube.com/watch?v=${VID}`,
    `https://user:pw@youtu.be/${VID}`,
    `https://youtu.be:8080/${VID}`,
    `https://youtu.be/${VID}/extra`,
    'file:///etc/passwd',
  ]) assert.equal(yt.parseYoutubeVideoId(url), null, url);
});

test('rozilik: ikkala belgi ham shart; tugma faqat yoqilgan + o\'rnatilgan + to\'g\'ri havola', () => {
  assert.equal(yt.consentGiven({ owner: true, terms: false }), false);
  assert.equal(yt.consentGiven({ owner: false, terms: true }), false);
  assert.equal(yt.consentGiven({ owner: true, terms: true }), true);
  const ok = { enabled: true, installed: true, url: `https://youtu.be/${VID}`, busy: false };
  assert.equal(yt.canStart(ok), true);
  assert.equal(yt.canStart({ ...ok, enabled: false }), false);
  assert.equal(yt.canStart({ ...ok, installed: false }), false);
  assert.equal(yt.canStart({ ...ok, busy: true }), false);
  assert.equal(yt.canStart({ ...ok, url: 'https://vimeo.com/1' }), false);
});

test('youtubeFieldState: maydon har doim ko\'rinadi, o\'chiq/noma\'lum holatda disabled', () => {
  assert.equal(yt.youtubeFieldState(undefined), 'loading');
  assert.equal(yt.youtubeFieldState(null), 'loading');
  // Sozlamalarda o'chirilgan bo'lsa - yt-dlp o'rnatilgan bo'lsa ham maydon disabled.
  assert.equal(yt.youtubeFieldState({ enabled: false, installed: true, js_runtime: 'deno' }), 'disabled');
  assert.equal(yt.youtubeFieldState({ enabled: false, installed: false, js_runtime: null }), 'disabled');
  assert.equal(yt.youtubeFieldState({ enabled: true, installed: false, js_runtime: 'deno' }), 'notInstalled');
  assert.equal(yt.youtubeFieldState({ enabled: true, installed: true, js_runtime: null }), 'noJs');
  assert.equal(yt.youtubeFieldState({ enabled: true, installed: true, js_runtime: 'deno' }), 'ready');
  assert.equal(yt.youtubeInputEnabled('loading'), false);
  assert.equal(yt.youtubeInputEnabled('disabled'), false);
  for (const s of ['notInstalled', 'noJs', 'ready']) assert.equal(yt.youtubeInputEnabled(s), true, s);
});

test('i18n: bitta kartadagi import (fayl / yoki / havola) matnlari', () => {
  assert.equal(youtubeDictionaries.uz.pickFile, 'Fayl tanlash');
  assert.equal(youtubeDictionaries.uz.or, 'yoki');
  assert.match(youtubeDictionaries.uz.enableInSettings, /Sozlamalarda yoqing/);
  for (const loc of ['uz', 'uz-Cyrl', 'ru', 'en']) {
    for (const k of ['pickFile', 'or', 'disabledShort', 'enableInSettings']) assert.ok(youtubeDictionaries[loc][k]?.trim(), `${loc}.${k}`);
  }
});

test('downloadView: foiz, tezlik, qolgan vaqt, xato kodi', () => {
  const v = yt.downloadView({
    progress: 0.4237,
    meta: { download: { downloaded_bytes: 5 * 1024 * 1024, total_bytes: 20 * 1024 * 1024, speed: 1536 * 1024, eta: 75 },
            title: 'Podkast', error_code: 'network', episode_id: 'e1' },
  });
  assert.equal(v.percent, 42);
  assert.equal(v.speed, '1.5 MB/s');
  assert.equal(v.eta, '1:15');
  assert.equal(v.size, '5.0 MB / 20.0 MB');
  assert.equal(v.title, 'Podkast');
  assert.equal(v.errorCode, 'network');
  assert.equal(v.episodeId, 'e1');
  const empty = yt.downloadView({ progress: 0, meta: { error_code: 'boshqa' } });
  assert.equal(empty.speed, '—');
  assert.equal(empty.eta, '—');
  assert.equal(empty.errorCode, null);
  assert.equal(yt.fmtEta(3725), '1:02:05');
  assert.equal(yt.fmtBytes(512), '512 B');
});

test('i18n: to\'rt til, bir xil kalitlar, har xato kodi uchun matn', () => {
  const keys = Object.keys(youtubeDictionaries.uz).sort();
  for (const loc of ['uz', 'uz-Cyrl', 'ru', 'en']) {
    assert.deepEqual(Object.keys(youtubeDictionaries[loc]).sort(), keys, loc);
    for (const k of keys) assert.ok(youtubeDictionaries[loc][k].trim(), `${loc}.${k}`);
    for (const code of yt.YT_ERROR_CODES) assert.ok(youtubeErrors[loc][code], `${loc}.${code}`);
    assert.equal(Object.keys(youtubeErrors[loc]).length, yt.YT_ERROR_CODES.length);
  }
  // Engine: o'rnatilgan yt-dlp ilovaning bu versiyasiga mos emas.
  assert.ok(yt.isYtErrorCode('incompatible'));
  assert.match(youtubeErrors.en.incompatible, /Lahza/);
  // ADR-0010: rozilik "menga tegishli yoki ruxsatim bor" va YouTube shartlari ogohlantirishi.
  assert.match(youtubeDictionaries.uz.consentOwner, /menga tegishli/);
  assert.match(youtubeDictionaries.uz.consentOwner, /ruxsatim bor/);
  assert.match(youtubeDictionaries.uz.consentTerms, /YouTube shartlari/);
  assert.match(youtubeDictionaries.uz.recommend, /YouTube Studio/);
  assert.equal(fmt(youtubeDictionaries.en.downloading, { title: 'X' }), 'Downloading: X');
});
