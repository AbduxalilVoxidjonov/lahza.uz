import { test, after } from 'node:test';
import assert from 'node:assert/strict';
import { createServer } from 'vite';
import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { readFileSync } from 'node:fs';

const server = await createServer({ server: { middlewareMode: true }, appType: 'custom' });
after(() => server.close());
const { MontageNew } = await server.ssrLoadModule('/src/pages/MontageNew.tsx');
const { Shell } = await server.ssrLoadModule('/src/components/Shell.tsx');
const { MontagePrompt } = await server.ssrLoadModule('/src/components/montage/MontagePrompt.tsx');
const { resolvePromptMode } = await server.ssrLoadModule('/src/lib/prompt-mode.ts');
const { DEFAULT_STYLE } = await server.ssrLoadModule('/src/api/types.ts');
const template = JSON.parse(readFileSync(new URL('../../engine/src/lahza_engine/templates/builtin/daily-story.json', import.meta.url), 'utf8'));
function render(Component, templates = [template], path = '/montages/new', agentStatus) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, enabled: false } } });
  client.setQueryData(['templates'], templates);
  if (agentStatus) client.setQueryData(['editing-agent', 'status'], agentStatus);
  client.setQueryData(['export-profiles'], { profiles: [{ id: 'instagram_reels', name: 'Instagram Reels', recommended_format: { aspect: '9:16', w: 1080, h: 1920, fps: 30 } }] });
  const html = renderToStaticMarkup(createElement(QueryClientProvider, { client },
    createElement(MemoryRouter, { initialEntries: [path] }, createElement(Component))));
  client.clear();
  return html;
}

test('new user starts with video selection, no project-name prerequisite, and honest browser path guidance', () => {
  const html = render(MontageNew);
  assert.match(html, /Videongizdan boshlaymiz/);
  assert.match(html, /Video tanlang/);
  assert.match(html, /Brauzer rejimida/);
  assert.match(html, /desktop ilovada/);
  assert.match(html, /id="mon-path"/);
  assert.doesNotMatch(html, /type="file"/);
  assert.match(html, /hidden=""[^>]*aria-label="2\. Qayerga joylaysiz/);
});

test('safe ready-made template is preselected and optional controls stay collapsed', () => {
  const html = render(MontageNew);
  assert.match(html, /aria-checked="true"/);
  assert.match(html, /<details class="quick-details"><summary>Shablonni o/);
  assert.match(html, /<details class="quick-details"><summary>Qo/);
  assert.match(html, /value="instagram_reels" selected=""/);
});

test('empty template catalog offers explicit library recovery instead of model onboarding', () => {
  const html = render(MontageNew, []);
  assert.match(html, /Tayyor shablon topilmadi/);
  assert.match(html, /href="\/templates"/);
  assert.doesNotMatch(html, /Boshlash uchun tayyor shablon tanlandi/);
});

test('sidebar exposes start and keeps project, template and model setup in optional library', () => {
  const html = render(Shell);
  assert.match(html, /href="\/montages\/new"/);
  assert.match(html, /<details class="nav-more">/);
  assert.match(html, /href="\/onboarding"/);
});

test('setup stays within branded main content and disabled SSR queries do not fetch', () => {
  const originalFetch = globalThis.fetch;
  let requests = 0;
  globalThis.fetch = () => { requests++; throw new Error('Unexpected SSR fetch'); };
  try {
    const html = render(Shell);
    assert.match(html, /<main[^>]*id="main"[^>]*><section[^>]*aria-label="Lahza siz uchun tayyorlanmoqda"/);
    assert.equal((html.match(/aria-label="Lahza siz uchun tayyorlanmoqda"/g) ?? []).length, 1);
    assert.equal(requests, 0);
  } finally { globalThis.fetch = originalFetch; }
});

const course = JSON.parse(readFileSync(new URL('../../engine/src/lahza_engine/templates/builtin/course-announce.json', import.meta.url), 'utf8'));
function selectedTemplate(html) {
  return html.match(/<button[^>]*role="radio"[^>]*aria-checked="true"[^>]*><article[^>]*aria-label="([^"]+)"/)?.[1]?.replaceAll("&#x27;", "'");
}
test('ordinary video defaults to neutral daily story even when course advertisement is first', () => {
  assert.equal(template.id, 'uz.lahza.tpl.daily-story');
  assert.equal(template.music.required, false);
  assert.equal(selectedTemplate(render(MontageNew, [course, template])), template.name.uz);
});
test('explicit template query preserves the requested course style', () => {
  assert.equal(selectedTemplate(render(MontageNew, [course, template], `/montages/new?template=${encodeURIComponent(course.id)}`)), course.name.uz);
});
test('fallback remains available without daily story and missing explicit choice is not replaced', () => {
  assert.equal(selectedTemplate(render(MontageNew, [course])), course.name.uz);
  assert.equal(selectedTemplate(render(MontageNew, [course, template], '/montages/new?template=missing')), undefined);
});

const timeline = { schema: 'lahza.timeline/1', format: { aspect: '9:16', w: 1080, h: 1920, fps: 30, audio_hz: 48000 }, media: {}, video: [], text: [], music: [], captions: { enabled: false, style: DEFAULT_STYLE, words: [] }, brand: {}, audio: {}, provenance: { notes: [] } };
function Prompt() { return createElement(MontagePrompt, { tl: timeline, selection: null, profiles: [], edit() {} }); }
test('downloaded available assistant is immediately selected without exposing model IDs', () => {
  const html = render(Prompt, [], '/montages/new', { available: true, model_id: 'technical-model-id', reason: null, supported_operations: [] });
  assert.match(html, /value="ai" selected=""/);
  assert.doesNotMatch(html, /technical-model-id/);
  assert.match(html, /<textarea/);
});
test('unavailable or unknown AI falls back to local input', () => {
  for (const available of [false, undefined]) {
    const html = render(Prompt, [], '/montages/new', available === undefined ? undefined : { available, model_id: null, reason: 'missing', supported_operations: [] });
    assert.match(html, /value="local" selected=""/);
  }
});
test('readiness updates only select a mode until typing or explicit choice locks it', () => {
  assert.equal(resolvePromptMode(null, false), 'local');
  assert.equal(resolvePromptMode(null, true), 'ai');
  for (const locked of ['local', 'ai']) {
    assert.equal(resolvePromptMode(locked, false), locked);
    assert.equal(resolvePromptMode(locked, true), locked);
  }
});
