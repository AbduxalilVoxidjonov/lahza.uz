import { test, after } from 'node:test';
import assert from 'node:assert/strict';
import { createServer } from 'vite';
import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
const server = await createServer({ server: { middlewareMode: true }, appType: 'custom' });
after(() => server.close());
const { SetupSession, parseSetup, formatDownloadSize } = await server.ssrLoadModule('/src/lib/first-run.ts');
const { SetupPanel } = await server.ssrLoadModule('/src/components/FirstRunSetup.tsx');
const { setupMessages } = await server.ssrLoadModule('/src/i18n/setup/index.ts');
const missing = () => ({ ready: false, components: [{ id: 'asr', required: true, ready: false, download_bytes: 2700000000, detail: null }], job: null });
const job = (status) => ({ id: 'setup-1', kind: 'install', status, progress: .42, stage: null, error: null, result: null, meta: {} });
test('first launch claims once across StrictMode replay/remount and shares the in-flight POST', async () => {
  const session = new SetupSession();
  let posts = 0;
  const post = async () => { posts++; return job('running'); };
  assert.equal(session.claim(missing()), true);
  const first = session.start(post);
  assert.equal(session.claim(missing()), false);
  assert.equal(session.start(post), first);
  await first;
  assert.equal(session.claim(missing()), false);
  assert.equal(posts, 1);
});
test('failed POST never automatically restarts, explicit retry works', async () => {
  const s = new SetupSession(); let calls = 0;
  s.claim(missing());
  await assert.rejects(s.start(async () => { calls++; throw Error('offline'); }));
  assert.equal(s.claim(missing()), false);
  await s.start(async () => { calls++; return job('running'); });
  assert.equal(calls, 2);
});
test('backend active/terminal jobs restore without another POST; defer survives remount', () => {
  for (const state of ['queued', 'running', 'failed', 'cancelled', 'done']) {
    const s = new SetupSession();
    assert.equal(s.claim({ ...missing(), job: job(state) }), false);
    assert.equal(s.claim(missing()), false);
  }
  const s = new SetupSession(); s.defer(); assert.equal(s.claim(missing()), false);
});
test('healthy offline startup performs no install; missing shipped runtimes require repair', () => {
  assert.equal(new SetupSession().claim({ ...missing(), ready: true }), false);
  for (const id of ['render', 'llm_runtime']) {
    const status = missing(); status.components[0].id = id;
    assert.equal(new SetupSession().claim(status), false);
  }
});
test('setup boundary rejects malformed responses', () => {
  assert.deepEqual(parseSetup(missing()), missing());
  for (const value of [null, {}, { ...missing(), ready: 'true' }, { ...missing(), job: {} }, { ...missing(), components: [{ ...missing().components[0], download_bytes: -1 }] }]) assert.throws(() => parseSetup(value));
});
const render = (props = {}) => renderToStaticMarkup(createElement(SetupPanel, { status: missing(), loading: false, error: false, startError: false, busy: false, cancelError: false, onRetry() {}, onCheck() {}, onCancel() {}, onDefer() {}, ...props }));
test('visible progress, size, readiness, recovery, cancellation and repair', () => {
  const html = render({ status: { ...missing(), job: job('running') } });
  assert.match(html, /2.7 GB/); assert.match(html, /42%/); assert.match(html, /<progress/); assert.match(html, /Yuklashni to‘xtatish/);
  assert.equal(render({ status: { ...missing(), ready: true } }), '');
  assert.match(render({ error: true }), /Dastur bilan ulana olmadik/);
  assert.match(render({ startError: true }), /Tayyorlash tugamadi/);
  assert.match(render({ status: { ...missing(), job: job('cancelled') } }), /Yuklash to‘xtatildi/);
  const status = missing(); status.components[0].id = 'render';
  assert.match(render({ status }), /qayta o‘rnating/);
  assert.doesNotMatch(render({ status }), /Yuklash hajmi/);
});
test('all four locales supply every setup message', () => {
  for (const locale of ['uz', 'uz-Cyrl', 'ru', 'en']) {
    assert.deepEqual(Object.keys(setupMessages[locale]).sort(), Object.keys(setupMessages.uz).sort());
    assert.ok(Object.values(setupMessages[locale]).every(v => typeof v === 'string' && v.length));
  }
});

test('healthy launches and completed setup leave no permanent card', () => {
  assert.equal(render({ status: { ...missing(), ready: true, job: null } }), '');
  assert.equal(render({ status: { ...missing(), ready: true, job: job('done') } }), '');
});
test('download sizes preserve small VAD downloads and zero without a false GB estimate', () => {
  for (const [bytes, expected] of [[2300000, '2.3 MB'], [2700000000, '2.7 GB'], [0, '0 B'], [800, '800 B'], [2300, '2.3 KB']]) assert.equal(formatDownloadSize(bytes), expected);
  const status = missing(); status.components[0].download_bytes = 2300000;
  assert.match(render({ status }), /2.3 MB/);
  assert.doesNotMatch(render({ status }), /0.0 GB/);
});
test('no install retry exists before successful preflight, including initial loading', () => {
  assert.doesNotMatch(render({ status: undefined, loading: true }), /Qayta urinish/);
  assert.doesNotMatch(render({ status: undefined, loading: false }), /Qayta urinish/);
  assert.match(render({ status: undefined, error: true }), /Qayta tekshirish/);
  assert.match(render(), /Qayta urinish/);
});
