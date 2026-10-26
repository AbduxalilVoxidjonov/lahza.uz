import { test, after } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, readFileSync, writeFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { pathToFileURL } from 'node:url';
import ts from 'typescript';

// "Claude montaj" bo'limi: holat javobini tekshirish, UI holati, xato kodlari, i18n to'liqligi.
// Engine endpointlari hali yo'q - soxta ma'lumotlar API shartnomasiga mos.
const dir = mkdtempSync(join(tmpdir(), 'lahza-claude-'));
after(() => rmSync(dir, { recursive: true, force: true }));
for (const [file, output] of [['lib/claude', 'lib'], ['i18n/claude/index', 'i18n']]) {
  const code = ts.transpileModule(readFileSync(new URL(`../src/${file}.ts`, import.meta.url), 'utf8'), {
    compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext },
  }).outputText;
  writeFileSync(join(dir, `${output}.mjs`), code);
}
const cl = await import(pathToFileURL(join(dir, 'lib.mjs')).href);
const { claudeDictionaries, claudeErrors, fmt, blockKey } = await import(pathToFileURL(join(dir, 'i18n.mjs')).href);

const status = (patch = {}) => ({
  enabled: true,
  cli: { installed: true, path: '/usr/local/bin/claude', version: '2.1.0' },
  desktop: { installed: false, path: null },
  auth: { state: 'ok', detail: null, checked_at: '2026-10-26T10:00:00Z' },
  mcp: { claude_code: false, claude_desktop: false },
  mcp_command: ['/Applications/Lahza.app/Contents/MacOS/lahza-engine', 'mcp'],
  ...patch,
});

test('holat javobi: to\'g\'ri shakl qabul qilinadi, buzuq maydonlar rad etiladi', () => {
  assert.deepEqual(cl.parseClaudeStatus(status()), status());
  // Ixtiyoriy null maydonlar yo'q bo'lsa ham null ga to'ldiriladi.
  const minimal = cl.parseClaudeStatus({ ...status(), cli: { installed: false }, desktop: { installed: false }, auth: { state: 'unknown' }, mcp_command: undefined });
  assert.deepEqual(minimal.cli, { installed: false, path: null, version: null });
  assert.deepEqual(minimal.auth, { state: 'unknown', detail: null, checked_at: null });
  assert.deepEqual(minimal.mcp_command, []);
  for (const bad of [null, [], { ...status(), enabled: 'ha' }, { ...status(), cli: null }, { ...status(), auth: { state: 'maybe' } },
    { ...status(), mcp: { claude_code: true } }, { ...status(), mcp_command: [1] }, { ...status(), cli: { installed: true, path: 5 } }]) {
    assert.throws(() => cl.parseClaudeStatus(bad), /Invalid claude status/);
  }
});

test('connect/disconnect javobi: actions ro\'yxati va ichki holat tekshiriladi', () => {
  const res = cl.parseConnectResult({ actions: ['~/.claude.json ga "lahza" MCP serveri qo\'shiladi'], status: status() });
  assert.equal(res.actions.length, 1);
  assert.equal(res.status.enabled, true);
  assert.throws(() => cl.parseConnectResult({ actions: 'x', status: status() }));
  assert.throws(() => cl.parseConnectResult({ actions: [], status: {} }));
  assert.deepEqual(cl.confirmableActions(['  a ', '', '  ']), { actions: ['a'], empty: false });
  assert.equal(cl.confirmableActions([]).empty, true);
});

test('UI holati: rejalovchi tayyorligi va to\'siq sababi', () => {
  assert.deepEqual([cl.claudeView(status()).plannerReady, cl.claudeView(status()).plannerBlock], [true, null]);
  // "unknown" login - ruxsat (engine o'zi claude_not_logged_in qaytaradi).
  assert.equal(cl.claudeView(status({ auth: { state: 'unknown', detail: null, checked_at: null } })).plannerReady, true);
  assert.equal(cl.claudeView(status({ enabled: false })).plannerBlock, 'disabled');
  assert.equal(cl.claudeView(status({ auth: { state: 'not_logged_in', detail: null, checked_at: null } })).plannerBlock, 'not_logged_in');
  // CLI yo'q - o'chiq bo'lsa ham birinchi sabab "o'rnatilmagan".
  const noCli = cl.claudeView(status({ enabled: false, cli: { installed: false, path: null, version: null } }));
  assert.equal(noCli.plannerBlock, 'not_installed');
  assert.equal(noCli.canCheckAuth, false);
  assert.equal(noCli.showInstallGuide, true);
  assert.equal(noCli.anyInstalled, false);
  const none = cl.claudeView(undefined);
  assert.equal(none.plannerReady, false);
  assert.equal(none.plannerBlock, 'unavailable');
  assert.deepEqual(none.targets, []);
});

test('UI holati: MCP targetlari - o\'rnatilmagan dasturga ulab bo\'lmaydi, ulanganini uzish mumkin', () => {
  const v = cl.claudeView(status({ desktop: { installed: true, path: '/Applications/Claude.app' }, mcp: { claude_code: true, claude_desktop: false } }));
  assert.deepEqual(v.targets.map((t) => [t.target, t.connected, t.canConnect, t.canDisconnect]), [
    ['claude_code', true, false, true],
    ['claude_desktop', false, true, false],
  ]);
  assert.equal(v.showInstallGuide, false);
  const noDesktop = cl.claudeView(status());
  assert.equal(noDesktop.targets[1].canConnect, false);
  assert.equal(noDesktop.showInstallGuide, true);
});

test('rejalovchi tanlovi: Claude tayyor bo\'lmasa har doim lokal; plan javobidagi planner', () => {
  assert.equal(cl.resolvePlanner(null, true), 'local');
  assert.equal(cl.resolvePlanner('claude', true), 'claude');
  assert.equal(cl.resolvePlanner('claude', false), 'local');
  assert.equal(cl.resolvePlanner('local', true), 'local');
  assert.equal(cl.parsePlanner({ plan: {}, planner: 'claude' }), 'claude');
  assert.equal(cl.parsePlanner({ plan: {} }), 'local');
  assert.equal(cl.parsePlanner({ planner: 'gpt' }), 'local');
  assert.equal(cl.parsePlanner(null), 'local');
});

test('xato kodlari: "kod: xabar" satri, tuzilgan ApiError.code va noma\'lum kodlar', () => {
  assert.deepEqual(cl.parseClaudeError(new Error('claude_timeout: 120 soniyada javob yo\'q')), { code: 'claude_timeout', message: '120 soniyada javob yo\'q' });
  assert.deepEqual(cl.parseClaudeError('claude_bad_plan: schema: ko\'p qatorli\nxabar'), { code: 'claude_bad_plan', message: 'schema: ko\'p qatorli\nxabar' });
  assert.deepEqual(cl.parseClaudeError('claude_disabled'), { code: 'claude_disabled', message: '' });
  const apiErr = Object.assign(new Error('Claude hisobiga kirilmagan'), { status: 409, code: 'claude_not_logged_in' });
  assert.deepEqual(cl.parseClaudeError(apiErr), { code: 'claude_not_logged_in', message: 'Claude hisobiga kirilmagan' });
  for (const other of [new Error('unsupported_codec: AV1'), new Error('claude_unknown: x'), new Error('oddiy xato'), 'timeout: x', null, undefined, 42, {}]) {
    assert.equal(cl.parseClaudeError(other), null);
  }
  assert.equal(cl.CLAUDE_ERROR_CODES.length, 5);
});

test('i18n: 4 tilda bir xil kalitlar, bo\'sh matn yo\'q, har xato kodi va to\'siq uchun matn', () => {
  const keys = Object.keys(claudeDictionaries.uz).sort();
  for (const loc of ['uz', 'uz-Cyrl', 'ru', 'en']) {
    assert.deepEqual(Object.keys(claudeDictionaries[loc]).sort(), keys, loc);
    for (const k of keys) assert.ok(claudeDictionaries[loc][k].trim(), `${loc}.${k}`);
    assert.deepEqual(Object.keys(claudeErrors[loc]).sort(), [...cl.CLAUDE_ERROR_CODES].sort(), loc);
    for (const code of cl.CLAUDE_ERROR_CODES) assert.ok(claudeErrors[loc][code].trim(), `${loc}.${code}`);
    for (const b of ['unavailable', 'not_installed', 'disabled', 'not_logged_in']) assert.ok(claudeDictionaries[loc][blockKey(b)], `${loc}.${b}`);
    // O'rinbosarlar barcha tillarda saqlanadi.
    for (const k of ['connectTitle', 'disconnectTitle', 'checkedAt', 'plannerUsed']) {
      assert.deepEqual(claudeDictionaries[loc][k].match(/\{\w+\}/g), claudeDictionaries.uz[k].match(/\{\w+\}/g), `${loc}.${k}`);
    }
  }
  // Maxfiylik matni aynan talab qilingan shaklda.
  assert.equal(claudeDictionaries.uz.privacy, 'Claude onlayn xizmat. Yoqilganda faqat timeline tavsifi va transkript matni yuboriladi; video va audio yuborilmaydi.');
  assert.equal(fmt(claudeDictionaries.en.connectTitle, { target: 'Claude Desktop' }), 'Confirm connecting: Claude Desktop');
  for (const url of Object.values(cl.CLAUDE_INSTALL_LINKS)) assert.match(url, /^https:\/\/(docs\.claude\.com|claude\.ai)\//);
});

test('i18n: yon menyu kaliti nav.claude 4 asosiy lug\'atda', () => {
  for (const loc of ['uz', 'uz-Cyrl', 'ru', 'en']) {
    const src = readFileSync(new URL(`../src/i18n/${loc}.ts`, import.meta.url), 'utf8');
    assert.match(src, /"nav\.claude": "[^"]+"/, loc);
  }
});
