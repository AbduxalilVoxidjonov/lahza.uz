import { test, after } from 'node:test';
import assert from 'node:assert/strict';
import { createServer } from 'vite';
import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

// PRO-3 "Hook oldinga": chiqish vaqti xaritasi engine Timeline(hook=...) bilan bir xil.
const server = await createServer({ server: { middlewareMode: true }, appType: 'custom' });
after(() => server.close());
const { srcToOut, outToSrc, outDuration, hookPrefixMs, hookPieces } = await server.ssrLoadModule('/src/lib/words.ts');
const { HookFront } = await server.ssrLoadModule('/src/components/editor/HookFront.tsx');

const base = { id: 'c', start_ms: 10000, end_ms: 20000, cuts: [] };

test('without hook mapping is unchanged', () => {
  assert.equal(hookPrefixMs(base), 0);
  assert.equal(srcToOut(base, 12000), 2000);
  assert.equal(outToSrc(base, 2000), 12000);
  assert.equal(outDuration({ ...base, hook: null }), 10000);
});

test('hook prefix shifts body and maps prefix to hook source', () => {
  const clip = { ...base, hook: { start_ms: 15000, end_ms: 18000 } };
  assert.equal(hookPrefixMs(clip), 3000);
  assert.equal(outDuration(clip), 13000);
  assert.equal(srcToOut(clip, 10000), 3000);
  assert.equal(outToSrc(clip, 500), 15500);
  assert.equal(outToSrc(clip, 3000), 10000);
});

test('hook pieces exclude cuts and clip outside', () => {
  const clip = { ...base, cuts: [[16000, 17000]], hook: { start_ms: 15000, end_ms: 22000 } };
  assert.deepEqual(hookPieces(clip), [[15000, 16000], [17000, 20000]]);
  assert.equal(outDuration(clip), 4000 + 9000);
  assert.equal(outToSrc(clip, 1500), 17500);
});

function render(clip) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, enabled: false } } });
  const html = renderToStaticMarkup(createElement(QueryClientProvider, { client },
    createElement(HookFront, { clip, episodeId: 'e', onSeek: () => {} })));
  client.clear();
  return html;
}

test('toggle renders off by default and shows current hook when on', () => {
  const off = render({ ...base, hook: null });
  assert.match(off, /type="checkbox"/);
  assert.doesNotMatch(off, /checked=""/);
  const on = render({ ...base, hook: { start_ms: 15000, end_ms: 18000 } });
  assert.match(on, /checked=""/);
  assert.match(on, /3\.0 s/);
});
