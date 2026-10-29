import { test, after } from 'node:test';
import assert from 'node:assert/strict';
import { createServer } from 'vite';
import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

// YT-1: YouTube havolasi Boshlash sahifasining 1-qadamida (SourcePicker), fayl tanlash bilan teng darajada.
const server = await createServer({ server: { middlewareMode: true }, appType: 'custom' });
after(() => server.close());
const { MontageNew } = await server.ssrLoadModule('/src/pages/MontageNew.tsx');
const { Shell } = await server.ssrLoadModule('/src/components/Shell.tsx');
const { sourceKey } = await server.ssrLoadModule('/src/components/montage/SourcePicker.tsx');
const yt = await server.ssrLoadModule('/src/lib/youtube-import.ts');
const { youtubeDictionaries } = await server.ssrLoadModule('/src/i18n/youtube/index.ts');

const READY = {
  enabled: true, installed: true, version: '2026.10.21', ejs: true, js_runtime: 'deno', ffmpeg: true,
  components_ready: true, components_download_bytes: 0, install_job: null, component_versions: {},
};

function render(Component, { status, path = '/montages/new' } = {}) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, enabled: false } } });
  client.setQueryData(['templates'], []);
  if (status) client.setQueryData(['youtube-import'], status);
  const html = renderToStaticMarkup(createElement(QueryClientProvider, { client },
    createElement(MemoryRouter, { initialEntries: [path] }, createElement(Component))));
  client.clear();
  return html;
}

test('Boshlash sahifasi: 1-qadamda fayl va YouTube havolasi yonma-yon, "yoki" bilan', () => {
  const html = render(MontageNew, { status: READY });
  const files = html.indexOf('id="mon-path"');
  const or = html.indexOf('class="source-or');
  const block = html.indexOf('id="youtube"');
  assert.ok(files > 0 && or > files && block > or, 'tartib: fayl -> yoki -> YouTube');
  assert.match(html, /class="source-choices"/);
  assert.match(html, /id="yt-start-title"[^>]*>YouTube havolasi</);
  assert.match(html, /placeholder="https:\/\/www\.youtube\.com\/watch\?v=…"/);
  assert.match(html, /<button class="btn primary" type="button" disabled="">Qo&#x27;shish<\/button>/);
  // Loyiha so'ralmaydi: blokda loyiha tanlash maydoni yo'q.
  const yBlock = html.slice(block, html.indexOf('</section>', block));
  assert.doesNotMatch(yBlock, /<select/);
  assert.doesNotMatch(yBlock, /Tavsiya: avval asl montaj/, 'ixcham: uzun tavsiya faqat rozilik oynasida');
  // Maydon faol (yoqilgan + o'rnatilgan).
  assert.match(yBlock, /<input class="input" type="url"(?![^>]*disabled)/);
});

test('Sozlamalarda o\'chiq: maydon ko\'rinadi, lekin disabled va "Sozlamalarda yoqing" havolasi bor', () => {
  const html = render(MontageNew, { status: { ...READY, enabled: false } });
  const yBlock = html.slice(html.indexOf('id="youtube"'));
  assert.match(yBlock, /href="\/settings#set-youtube"[^>]*>Sozlamalarda yoqing</);
  assert.match(yBlock, /<input class="input" type="url"[^>]*disabled=""/);
});

test('komponentlar o\'rnatilmagan: shu blokning o\'zida o\'rnatish tugmasi', () => {
  const html = render(MontageNew, {
    status: { ...READY, installed: false, js_runtime: null, components_ready: false, components_download_bytes: 46137344 },
  });
  const yBlock = html.slice(html.indexOf('id="youtube"'));
  assert.match(yBlock, /Komponentlarni o&#x27;rnatish \(44\.0 MB\)/);
});

test('chap menyu: Boshlash ostida YouTube havolasi (maydonga fokus beradi)', () => {
  const html = render(Shell);
  const start = html.indexOf('href="/montages/new"');
  const ytLink = html.indexOf('href="/montages/new?src=youtube"');
  assert.ok(start > 0 && ytLink > start);
  assert.match(html, /YouTube havolasi/);
});

test('loyiha: mavjud "YouTube" loyihasi olinadi, bo\'lmasa null (yaratiladi)', () => {
  assert.equal(yt.YOUTUBE_PROJECT_NAME, 'YouTube');
  assert.equal(yt.findYoutubeProject([{ id: 'a', name: 'Podkast' }, { id: 'b', name: ' youtube ' }]), 'b');
  assert.equal(yt.findYoutubeProject([{ id: 'a', name: 'Podkast' }]), null);
  assert.equal(yt.findYoutubeProject(undefined), null);
});

test('muvaffaqiyatli import natijasi montaj manbasiga aylanadi (fayl, sourceKey bilan bir xil kalit)', () => {
  const job = {
    status: 'done', progress: 1,
    result: { episode_id: 'ep1', analysis_job_id: 'j2', path: '/data/youtube/dQw4w9WgXcQ/video.mp4', title: 'Mening videom', reused: false },
    meta: { title: 'Meta sarlavha', episode_id: 'ep1' },
  };
  assert.equal(yt.importedVideo({ ...job, status: 'running' }), null);
  assert.equal(yt.importedVideo({ ...job, result: null }), null);
  assert.equal(yt.importedVideo(undefined), null);
  const v = yt.importedVideo(job);
  assert.deepEqual(v, { path: '/data/youtube/dQw4w9WgXcQ/video.mp4', title: 'Mening videom', episodeId: 'ep1' });
  // Natijada sarlavha yo'q bo'lsa - meta'dagisi.
  assert.equal(yt.importedVideo({ ...job, result: { path: '/x/a.mp4' } }).title, 'Meta sarlavha');

  const src = yt.importedToSource(v, 'proj-yt');
  assert.deepEqual(src.source, { kind: 'file', path: v.path });
  assert.equal(src.key, sourceKey(src.source));
  assert.equal(src.label, 'Mening videom');
  assert.equal(src.detail, 'YouTube · video.mp4');
  assert.equal(src.projectId, 'proj-yt');
  // Sarlavhasiz - fayl nomi (Windows yo'li ham).
  assert.equal(yt.importedToSource({ path: 'C:\\L\\v.mp4', title: null, episodeId: null }).label, 'v.mp4');

  // MontageNew.addSources: kalit bo'yicha takror qo'shilmaydi.
  const add = (old, items) => [...old, ...items.filter((x) => !old.some((o) => o.key === x.key))];
  const picked = add(add([], [src]), [yt.importedToSource(v, 'proj-yt')]);
  assert.equal(picked.length, 1);
});

test('i18n: yangi kalitlar 4 tilda to\'ldirilgan', () => {
  for (const loc of ['uz', 'uz-Cyrl', 'ru', 'en']) {
    const y = youtubeDictionaries[loc];
    for (const k of ['add', 'preparing', 'openQueue', 'blockHint', 'doneSource', 'navLink', 'sourceUrl', 'or']) {
      assert.ok(typeof y[k] === 'string' && y[k].trim(), `${loc}.${k}`);
    }
  }
  assert.equal(youtubeDictionaries.ru.add, 'Добавить');
  assert.equal(youtubeDictionaries.en.add, 'Add');
});
