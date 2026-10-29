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

test('parseYoutubeSource: video, playlist va kanal (engine parse_source_url bilan bir xil)', () => {
  const ch = 'UC' + 'a'.repeat(22);
  const cases = [
    [`https://youtu.be/${VID}`, 'video', `https://www.youtube.com/watch?v=${VID}`],
    [`https://www.youtube.com/watch?v=${VID}&list=PL123`, 'video', `https://www.youtube.com/watch?v=${VID}`],
    ['https://www.youtube.com/playlist?list=PLabc_DEF-123', 'playlist', 'https://www.youtube.com/playlist?list=PLabc_DEF-123'],
    ['youtube.com/playlist?si=x&list=OLAK5uy_abc', 'playlist', 'https://www.youtube.com/playlist?list=OLAK5uy_abc'],
    ['https://www.youtube.com/@Kanal.uz', 'channel', 'https://www.youtube.com/@Kanal.uz/videos'],
    ['https://m.youtube.com/@kanal/videos', 'channel', 'https://www.youtube.com/@kanal/videos'],
    [`https://www.youtube.com/channel/${ch}`, 'channel', `https://www.youtube.com/channel/${ch}/videos`],
    ['https://www.youtube.com/c/OldName/featured', 'channel', 'https://www.youtube.com/c/OldName/videos'],
    ['https://www.youtube.com/user/someone', 'channel', 'https://www.youtube.com/user/someone/videos'],
  ];
  for (const [url, kind, canon] of cases) assert.deepEqual(yt.parseYoutubeSource(url), { kind, url: canon }, url);
  for (const url of [
    '', 'https://vimeo.com/playlist?list=PL123', 'https://youtube.com.evil.com/playlist?list=PL123',
    'https://www.youtube.com/playlist', 'https://www.youtube.com/playlist?list=a',
    'https://www.youtube.com/playlist?list=PL1&list=PL2', 'https://www.youtube.com/@kanal/shorts',
    'https://www.youtube.com/channel/UCshort', 'https://youtu.be/playlist?list=PL123',
    'https://user:pw@www.youtube.com/@kanal', 'https://www.youtube.com:8080/@kanal', 'ftp://www.youtube.com/@kanal',
    'https://www.youtube.com/feed/subscriptions',
  ]) assert.equal(yt.parseYoutubeSource(url), null, url);
});

test('playlist ro\'yxati: tanlov, hammasini tanlash, davomiylik, navbat elementlari', () => {
  const entries = [
    { id: 'a', url: 'https://www.youtube.com/watch?v=a', title: 'A', duration_s: 60, skip: null },
    { id: 'b', url: 'https://www.youtube.com/watch?v=b', title: null, duration_s: 30, skip: null },
    { id: 'c', url: 'https://www.youtube.com/watch?v=c', title: 'C', duration_s: null, skip: 'private' },
    { id: 'd', url: 'https://www.youtube.com/watch?v=d', title: 'D', duration_s: 10, skip: 'short' },
  ];
  const sel = yt.initialSelection(entries);
  assert.deepEqual([...sel], ['a', 'b']); // belgilangan (skip) elementlar tanlanmaydi
  assert.equal(yt.totalDuration(entries, sel), 90);
  assert.equal(yt.fmtDuration(yt.totalDuration(entries, sel)), '1:30');
  assert.deepEqual([...yt.toggleAll(entries, sel)], []); // hammasi tanlangan -> tozalash
  assert.deepEqual([...yt.toggleAll(entries, new Set(['a']))], ['a', 'b']);
  assert.deepEqual([...yt.toggleOne(entries, sel, 'a')], ['b']);
  assert.deepEqual([...yt.toggleOne(entries, sel, 'c')], ['a', 'b']); // yopiq video tanlanmaydi
  assert.deepEqual(yt.queueUrls(entries, new Set(['b', 'a', 'c'])), [
    { url: 'https://www.youtube.com/watch?v=a', title: 'A' },
    { url: 'https://www.youtube.com/watch?v=b', title: undefined },
  ]);
  assert.deepEqual([...yt.toggleAll([entries[2]], new Set())], []);
});

test('komponentlar holati: tizimdagi yt-dlp/Deno bilan import ishlaydi - chalkash ko\'rsatilmaydi', () => {
  const base = { installed: true, version: '2026.10.21', js_runtime: 'deno', components_ready: false,
    ytdlp_source: 'system', js_runtime_version: '2.9.6', js_runtime_source: 'system', js_runtime_outdated: [] };
  assert.equal(yt.componentsMode(base), 'system');
  assert.equal(yt.componentsMode({ ...base, components_ready: true }), 'ready');
  assert.equal(yt.componentsMode({ ...base, installed: false }), 'missing');
  assert.equal(yt.componentsMode({ ...base, js_runtime: null }), 'missing');
  const labels = { system: 'tizim', app: 'ilova' };
  assert.equal(yt.componentsInUse(base, labels), 'yt-dlp 2026.10.21 (tizim), deno 2.9.6 (tizim)');
  assert.equal(yt.componentsInUse({ ...base, js_runtime_source: 'components' }, labels),
    'yt-dlp 2026.10.21 (tizim), deno 2.9.6 (ilova)');
  assert.equal(yt.outdatedRuntimes({ ...base, js_runtime_outdated: [{ name: 'deno', version: '2.1.4' }, { name: 'node', version: null }] }),
    'deno 2.1.4, node ?');
  assert.equal(yt.outdatedRuntimes({ installed: true, version: null, js_runtime: null, components_ready: false }), '');
  for (const code of ['js_outdated', 'timeout', 'empty']) assert.ok(yt.isYtErrorCode(code), code);
});

test('boblar: YouTube vaqt havolasi va transkriptdagi so\'z indeksi', () => {
  assert.equal(yt.youtubeAt(`https://www.youtube.com/watch?v=${VID}`, 125_900), `https://www.youtube.com/watch?v=${VID}&t=125s`);
  assert.equal(yt.youtubeAt('https://example.com/x', 1000), 'https://example.com/x');
  const words = [{ start_ms: 0, end_ms: 900 }, { start_ms: 1000, end_ms: 1900 }, { start_ms: 2000, end_ms: 2900 }];
  assert.equal(yt.wordIndexAt(words, 0), 0);
  assert.equal(yt.wordIndexAt(words, 1500), 1);
  assert.equal(yt.wordIndexAt(words, 950), 1);
  assert.equal(yt.wordIndexAt(words, 99_999), 2);
  assert.equal(yt.wordIndexAt([], 10), null);
  assert.equal(yt.wordIndexAt(words, NaN), null);
});

test('i18n: playlist, komponentlar va boblar matnlari to\'rt tilda', () => {
  for (const loc of ['uz', 'uz-Cyrl', 'ru', 'en']) {
    const d = youtubeDictionaries[loc];
    assert.match(fmt(d.addToQueue, { n: 3 }), /3/);
    assert.match(fmt(d.systemComponents, { list: 'yt-dlp X' }), /yt-dlp X/);
    assert.match(fmt(d.jsOutdated, { list: 'deno 2.1' }), /2\.3/);
    for (const s of ['short', 'live', 'upcoming', 'private', 'unavailable']) assert.ok(d[`skip_${s}`], `${loc}.skip_${s}`);
  }
});
