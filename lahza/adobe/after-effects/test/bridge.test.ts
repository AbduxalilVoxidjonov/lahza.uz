// HostBridge: soxta evalScript bilan; skript haqiqatan host.jsx (vm, soxta AE) da bajariladi — uchidan-uchiga.
import { fileURLToPath } from "node:url";
import vm from "node:vm";
import { describe, expect, it, vi } from "vitest";
import { EVAL_SCRIPT_ERROR, HostBridge, HostError, jsxString, uriToPath, type EvalScriptFn } from "../src/host/bridge";
import { createAE, loadHost } from "./mock-ae";
import { MUSIC, SRC, samplePlan } from "./fixtures";
import { parse } from "acorn";

const JSX = fileURLToPath(new URL("../jsx", import.meta.url));

function aeEval() {
  const ae = createAE({
    [SRC]: { width: 1920, height: 1080, duration: 120, hasAudio: true },
    [MUSIC]: { width: 0, height: 0, duration: 90, hasAudio: true },
  });
  const ctx = loadHost(ae, JSX);
  const scripts: string[] = [];
  // ExtendScript'da $.evalFile bor; vm'da host allaqachon yuklangan, shuning uchun soxta.
  (ctx as Record<string, unknown>).$ = { evalFile: vi.fn() };
  const evalFn: EvalScriptFn = (script, cb) => {
    scripts.push(script);
    let out: string;
    try {
      // ExtendScript singari ES3: skript ham ES3 parse bo'lishi shart
      parse(script, { ecmaVersion: 3 });
      out = String(vm.runInContext(script, ctx));
    } catch {
      out = EVAL_SCRIPT_ERROR;
    }
    setTimeout(() => cb(out), 0);
  };
  return { ae, ctx, scripts, evalFn };
}

describe("jsxString / uriToPath", () => {
  it("ES3 satr literali: qo'shtirnoq, backslash, U+2028, o'zbek harflari", () => {
    const s = 'a"b\\c\u2028d oʻzbek\n';
    const lit = jsxString(s);
    expect(lit).not.toMatch(/\u2028/);
    expect(() => parse(`var x = ${lit};`, { ecmaVersion: 3 })).not.toThrow();
    expect(vm.runInNewContext(lit)).toBe(s);
  });
  it("extension URI -> yo'l (macOS, Windows, %20)", () => {
    expect(uriToPath("file:///Users/me/Library/Application%20Support/Adobe/CEP/extensions/lahza")).toBe(
      "/Users/me/Library/Application Support/Adobe/CEP/extensions/lahza",
    );
    expect(uriToPath("file:///C:/Users/me/AppData/Roaming/Adobe/CEP/extensions/lahza")).toBe("C:/Users/me/AppData/Roaming/Adobe/CEP/extensions/lahza");
  });
});

describe("HostBridge", () => {
  it("buildComp/buildKaraoke host.jsx gacha boradi va natijani qaytaradi", async () => {
    const { ae, scripts, evalFn } = aeEval();
    const b = new HostBridge(evalFn, "/ext/lahza");
    const r = await b.buildComp(samplePlan());
    expect(r.ok).toBe(true);
    expect(r.comp).toBe("Lahza — Hook");
    expect(r.layers).toBe(10);
    const k = await b.buildKaraoke(samplePlan(), r.comp ?? undefined);
    expect(k).toMatchObject({ ok: true, comp: "Lahza — Hook", lines: 3 });
    // birinchi skript — yuklash (json2 + host), bir marta
    expect(scripts[0]).toContain('$.evalFile("/ext/lahza/jsx/json2.jsx")');
    expect(scripts[0]).toContain('$.evalFile("/ext/lahza/jsx/host.jsx")');
    expect(scripts.filter((s) => s.includes("evalFile"))).toHaveLength(1);
    expect(scripts[1]).toMatch(/^lahza_buildComp\("/);
    expect(scripts[2]).toMatch(/^lahza_buildKaraoke\(".*", "Lahza — Hook"\)$/s);
    expect(ae.undoDepth).toBe(0);
  });

  it("host {ok:false} -> HostError xabari bilan", async () => {
    const { evalFn } = aeEval();
    const b = new HostBridge(evalFn, "/ext");
    const p = samplePlan();
    p.captions.lines = [];
    await expect(b.buildKaraoke(p)).rejects.toThrow(/qatorlari yo'q/);
    await expect(b.buildKaraoke(p)).rejects.toBeInstanceOf(HostError);
  });

  it("EvalScript error. / JSON emas / timeout / CEP yo'q", async () => {
    const bad = new HostBridge((_s, cb) => cb(EVAL_SCRIPT_ERROR), null);
    await expect(bad.selectedFootagePaths()).rejects.toThrow(/ExtendScript/);

    let n = 0;
    const junk = new HostBridge((_s, cb) => cb(n++ === 0 ? "ok" : "undefined"), null);
    await expect(junk.projectInfo()).rejects.toThrow(/JSON/);

    vi.useFakeTimers();
    try {
      const hang = new HostBridge(() => undefined, null, 50);
      const pr = expect(hang.eval("1")).rejects.toThrow(/javob bermadi/);
      await vi.advanceTimersByTimeAsync(60);
      await pr;
    } finally {
      vi.useRealTimers();
    }

    const none = new HostBridge(null, null);
    expect(none.available).toBe(false);
    await expect(none.buildComp(samplePlan())).rejects.toBeInstanceOf(HostError);
  });

  it("yuklash xatosidan keyin qayta urinadi; noma'lum funksiya nomi rad etiladi", async () => {
    let fail = true;
    const calls: string[] = [];
    const b = new HostBridge((s, cb) => {
      calls.push(s);
      if (fail) cb(EVAL_SCRIPT_ERROR);
      else cb(s.startsWith("lahza_") ? '{"ok":true,"comp":null,"paths":["/a.mp4"],"warnings":[]}' : "ok");
    }, "/ext");
    await expect(b.selectedFootagePaths()).rejects.toThrow();
    fail = false;
    await expect(b.selectedFootagePaths()).resolves.toMatchObject({ paths: ["/a.mp4"] });
    await expect(b.call("alert")).rejects.toThrow(/noma'lum/);
  });
});
