import { test, after } from 'node:test';
import assert from 'node:assert/strict';
import { createServer } from 'vite';
import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';

// PRO-1 (shaxsiy lug'at) va PRO-6 (ko'rishlar -> ball vaznlari): sof yordamchilar, ko'rinishlar, i18n.
const server = await createServer({ server: { middlewareMode: true }, appType: 'custom' });
after(() => server.close());
const lib = await server.ssrLoadModule('/src/lib/learning.ts');
const { learningDictionaries, learningUz, fmt } = await server.ssrLoadModule('/src/i18n/learning/index.ts');
const { ClipMetricsView } = await server.ssrLoadModule('/src/components/gallery/ClipMetrics.tsx');
const { DictionaryTable, WeightsView } = await server.ssrLoadModule('/src/components/settings/LearningPanel.tsx');

const m = learningUz;
const info = (o = {}) => ({ scope: 'global', weights: { weight_llm: 0.7, weight_signals: 0.3 },
  defaults: { weight_llm: 0.7, weight_signals: 0.3 }, source: 'default', learned: false, n_samples: 3, min_samples: 8, ...o });

test('parseCount: oddiy, ajratgichli, qisqartmali va yaroqsiz qiymatlar', () => {
  assert.equal(lib.parseCount(''), null);
  assert.equal(lib.parseCount('  '), null);
  assert.equal(lib.parseCount('12500'), 12500);
  assert.equal(lib.parseCount('12 500'), 12500);
  assert.equal(lib.parseCount('12,500'), 12500);
  assert.equal(lib.parseCount('1,250,000'), 1250000);
  assert.equal(lib.parseCount('12.5k'), 12500);
  assert.equal(lib.parseCount('1,2M'), 1200000);
  assert.equal(lib.parseCount('3 млн'), 3000000);
  assert.equal(lib.parseCount('7 ming'), 7000);
  assert.ok(Number.isNaN(lib.parseCount('-5')));
  assert.ok(Number.isNaN(lib.parseCount('abc')));
  assert.ok(Number.isNaN(lib.parseCount('99999999999999')));
});

test('vaznlar: foiz, tiklash faolligi, qolgan namunalar', () => {
  assert.equal(lib.pct(0.7), '70%');
  assert.equal(lib.differsFromDefault(undefined), false);
  assert.equal(lib.differsFromDefault(info()), false);
  assert.equal(lib.differsFromDefault(info({ learned: true, source: 'project' })), true);
  assert.equal(lib.differsFromDefault(info({ source: 'global' })), true);
  assert.equal(lib.samplesLeft(info()), 5);
  assert.equal(lib.samplesLeft(info({ n_samples: 20 })), 0);
});

test('i18n: 4 tilda bir xil kalitlar, bo\'sh matn yo\'q, o\'rinbosarlar saqlangan', () => {
  const keys = Object.keys(learningUz).sort();
  for (const loc of ['uz', 'uz-Cyrl', 'ru', 'en']) {
    const d = learningDictionaries[loc];
    assert.deepEqual(Object.keys(d).sort(), keys, loc);
    for (const k of keys) {
      assert.ok(d[k].trim(), `${loc}.${k}`);
      for (const ph of learningUz[k].match(/\{\w+\}/g) ?? []) assert.ok(d[k].includes(ph), `${loc}.${k} ${ph}`);
    }
  }
  assert.equal(fmt('{a} va {a}', { a: 1 }), '1 va 1');
});

const noop = () => {};
test('klip kartasi: ko\'rishlar maydoni, yaroqsiz va saqlangan holat', () => {
  const props = { m, title: 'Klip', views: '', likes: '', invalid: false, saved: false, busy: false, onViews: noop, onLikes: noop, onSave: noop };
  let html = renderToStaticMarkup(createElement(ClipMetricsView, props));
  assert.match(html, /Ko&#x27;rishlar|Ko'rishlar/);
  assert.match(html, /inputMode="numeric"|inputmode="numeric"/);
  assert.match(html, /<button[^>]*disabled=""[^>]*>Saqlash/); // bo'sh qiymat bilan saqlanmaydi
  html = renderToStaticMarkup(createElement(ClipMetricsView, { ...props, views: 'x', invalid: true }));
  assert.match(html, /role="alert"/);
  assert.match(html, /aria-invalid="true"/);
  html = renderToStaticMarkup(createElement(ClipMetricsView, { ...props, views: '120', saved: true }));
  assert.match(html, /role="status">Saqlandi/);
  assert.doesNotMatch(html, /disabled=""/);
});

test('Sozlamalar: lug\'at jadvali va vaznlar paneli', () => {
  assert.match(renderToStaticMarkup(createElement(DictionaryTable, { m, entries: [], busy: false, onDelete: noop })), /Hali tuzatishlar yo/);
  const entries = [
    { id: 1, wrong: 'laxza', right: 'Lahza', kind: 'ism', count: 3, active: true, last_episode_id: null, updated_at: '' },
    { id: 2, wrong: 'bor', right: 'bir', kind: 'soz', count: 1, active: false, last_episode_id: null, updated_at: '' },
  ];
  const html = renderToStaticMarkup(createElement(DictionaryTable, { m, entries, busy: false, onDelete: noop }));
  assert.match(html, /laxza/);
  assert.match(html, /Qo&#x27;llanadi|Qo'llanadi/);
  assert.match(html, /Yig&#x27;ilmoqda|Yig'ilmoqda/);
  assert.equal((html.match(/<tr>/g) ?? []).length, 3);
  let w = renderToStaticMarkup(createElement(WeightsView, { m, info: info(), busy: false, onReset: noop }));
  assert.match(w, /70%/);
  assert.match(w, /yana 5 ta/);
  assert.match(w, /<button[^>]*disabled=""[^>]*>Vaznlarni standartga/);
  w = renderToStaticMarkup(createElement(WeightsView, { m, info: info({ learned: true, source: 'project', n_samples: 12,
    weights: { weight_llm: 0.55, weight_signals: 0.45 } }), busy: false, onReset: noop }));
  assert.match(w, /55%/);
  assert.match(w, /Loyiha uchun/);
  assert.doesNotMatch(w, /yana/);
  assert.doesNotMatch(w, /disabled=""/);
});
