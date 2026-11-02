import { describe, expect, it } from "vitest";

import { EngineClient } from "@shared/engine";
import { connectEngine } from "../src/connection";
import { discoveryPath, hostOutDir, locateEngine, manualEngine, toUxpFileUrl, type LocatorEnv } from "../src/engineLocator";
import { analyzeMedia, makeMontage, makeReel } from "../src/flow";
import { FakeAdapter } from "../src/host/fake";
import { fallbackFetch, fileIpcFetch, type IpcFs, type IpcRequest } from "../src/transport";
import { clipPlan, montagePlan } from "./fixtures";

const macEnv = (files: Record<string, string>): LocatorEnv => ({
  platform: "darwin",
  home: "/Users/ali",
  readText: async (p) => {
    if (!(p in files)) throw new Error("ENOENT");
    return files[p];
  },
});

const json = (status: number, body: unknown) =>
  ({ ok: status >= 200 && status < 300, status, statusText: "", json: async () => body }) as unknown as Response;

describe("engineLocator", () => {
  const path = "/Users/ali/Library/Application Support/Lahza Studio/engine.json";

  it("engine.json yo'li (macOS va Windows)", () => {
    expect(discoveryPath({ platform: "darwin", home: "/Users/ali" })).toBe(path);
    expect(discoveryPath({ platform: "win32", home: "C:\\Users\\ali", localAppData: "C:\\Users\\ali\\AppData\\Local" })).toBe(
      "C:\\Users\\ali\\AppData\\Local\\Lahza Studio\\engine.json",
    );
  });

  it("UXP file: URL", () => {
    expect(toUxpFileUrl(path)).toBe(`file:${path}`);
    expect(toUxpFileUrl("C:\\Users\\ali\\x.json")).toBe("file:/C:/Users/ali/x.json");
  });

  it("topadi, yo'q va yaroqsiz holatlarni ajratadi", async () => {
    const ok = await locateEngine(macEnv({ [path]: '{"port": 51234, "token": "tkn", "pid": 9, "version": "0.1.0"}' }));
    expect(ok).toMatchObject({ ok: true, source: "discovery", info: { port: 51234, token: "tkn" } });
    expect(await locateEngine(macEnv({}))).toMatchObject({ ok: false, reason: "not_found", path });
    expect(await locateEngine(macEnv({ [path]: '{"port": "x"}' }))).toMatchObject({ ok: false, reason: "invalid" });
    expect(await locateEngine(null)).toMatchObject({ ok: false, reason: "no_env" });
  });

  it("qo'lda kiritish tekshiruvi", () => {
    expect(manualEngine(" 47600 ", " abc ")).toEqual({ port: 47600, token: "abc" });
    expect(() => manualEngine("0", "a")).toThrow();
    expect(() => manualEngine("80", " ")).toThrow();
  });

  it("chiqish papkasi absolyut", () => {
    expect(hostOutDir({ platform: "darwin", home: "/Users/ali" }, "e1_c/2")).toBe(
      "/Users/ali/Library/Application Support/Lahza Studio/premiere/e1_c_2",
    );
  });
});

describe("transport", () => {
  function memFs() {
    const files = new Map<string, string>();
    const fs: IpcFs = {
      writeText: async (p, t) => void files.set(p, t),
      readText: async (p) => {
        const v = files.get(p);
        if (v === undefined) throw new Error("ENOENT");
        return v;
      },
      rename: async (a, b) => {
        files.set(b, files.get(a)!);
        files.delete(a);
      },
      remove: async (p) => void files.delete(p),
      mkdirp: async () => undefined,
    };
    return { files, fs };
  }

  it("fayl-IPC: so'rov yoziladi, engine javobi o'qiladi va o'chiriladi", async () => {
    const { files, fs } = memFs();
    // soxta engine: sleep vaqtida so'rovni o'qib javob yozadi
    const sleep = async () => {
      for (const [p, t] of [...files]) {
        if (p.startsWith("/d/ipc/requests/") && p.endsWith(".json")) {
          const r = JSON.parse(t) as IpcRequest;
          files.delete(p);
          files.set(`/d/ipc/responses/${r.id}.json`, JSON.stringify({ v: 1, id: r.id, status: 200, body: { echo: r } }));
        }
      }
    };
    const f = fileIpcFetch(fs, { ipcDir: "/d/ipc", sleep, newId: () => "req-12345678", now: () => new Date(0) });
    const res = await f("http://127.0.0.1:1/v1/projects?x=1", {
      method: "POST",
      headers: { Authorization: "Bearer t" },
      body: JSON.stringify({ name: "P" }),
    });
    expect(res.ok).toBe(true);
    const body = (await res.json()) as { echo: IpcRequest };
    expect(body.echo).toEqual({
      v: 1,
      id: "req-12345678",
      method: "POST",
      path: "/v1/projects?x=1",
      headers: { Authorization: "Bearer t" },
      body: { name: "P" },
      created_at: "1970-01-01T00:00:00.000Z",
    });
    expect([...files.keys()]).toEqual([]);
  });

  it("fayl-IPC: javob kelmasa so'rov o'chiriladi va xato", async () => {
    const { files, fs } = memFs();
    const f = fileIpcFetch(fs, { ipcDir: "/d/ipc", sleep: async () => undefined, timeoutMs: 300, newId: () => "req-abcdefgh" });
    await expect(f("http://127.0.0.1:1/v1/health")).rejects.toThrow(/javob bermadi/);
    expect(files.size).toBe(0);
  });

  it("HTTP ishlamasa IPC ga o'tadi", async () => {
    const modes: string[] = [];
    let httpCalls = 0;
    const f = fallbackFetch(
      async () => {
        httpCalls++;
        throw new TypeError("Permission denied");
      },
      async () => json(200, { via: "ipc" }),
      (m) => modes.push(m),
    );
    expect(await (await f("http://x/a")).json()).toEqual({ via: "ipc" });
    await f("http://x/b");
    expect(httpCalls).toBe(1);
    expect(modes).toEqual(["ipc", "ipc"]);
  });
});

/** Engine'ning soxta HTTP qatlami (EngineClient yo'llari bo'yicha). */
function mockEngine() {
  const calls: { method: string; path: string; body: unknown }[] = [];
  let jobPolls = 0;
  const fetchFn = async (url: string, init?: RequestInit) => {
    const u = new URL(url);
    const method = init?.method ?? "GET";
    const body = typeof init?.body === "string" ? JSON.parse(init.body) : undefined;
    calls.push({ method, path: u.pathname, body });
    expect((init?.headers as Record<string, string>).Authorization).toBe("Bearer tok");
    const route = `${method} ${u.pathname}`;
    switch (route) {
      case "GET /v1/health":
        return json(200, { version: "0.2.0", ok: true });
      case "GET /v1/hostplan/schema":
        return json(200, { schema: "lahza.hostplan/1", engine: "0.2.0" });
      case "GET /v1/projects":
        return json(200, [{ id: "p0", name: "Boshqa" }]);
      case "POST /v1/projects":
        return json(200, { id: "p1", name: body.name });
      case "POST /v1/media:import":
        return json(200, { episode_id: "e1", job: { id: "j1", status: "queued", progress: 0 } });
      case "GET /v1/jobs/j1":
      case "GET /v1/jobs/j2":
        jobPolls++;
        return json(200, { id: "j1", status: jobPolls % 2 === 0 ? "done" : "running", progress: jobPolls % 2 === 0 ? 1 : 0.5, stage: "asr" });
      case "GET /v1/episodes/e1/clips":
        return json(200, [
          { id: "c1", score: 61, title: "B", start_ms: 0, end_ms: 30000, status: "nomzod", reason: "" },
          { id: "c2", score: 88, title: "A", start_ms: 0, end_ms: 20000, status: "nomzod", reason: "hook" },
        ]);
      case "POST /v1/episodes/e1/clips/c2:hostplan":
        return json(200, clipPlan());
      case "POST /v1/montages":
        return json(200, { montage_id: "mon1", job: { id: "j2", status: "queued", progress: 0 } });
      case "POST /v1/montages/mon1:hostplan":
        return json(200, montagePlan());
      default:
        return json(404, { detail: `yo'q: ${route}` });
    }
  };
  return { calls, fetchFn };
}

describe("to'liq oqim (mock fetch + fake host)", () => {
  const env = macEnv({ "/Users/ali/Library/Application Support/Lahza Studio/engine.json": '{"port": 47600, "token": "tok"}' });

  it("connect -> analyze -> clips -> hostplan -> build", async () => {
    const { calls, fetchFn } = mockEngine();
    const conn = await connectEngine({ env, httpFetch: fetchFn });
    expect(conn.ok).toBe(true);
    if (!conn.ok) return;
    expect(conn.conn.probe).toEqual({ version: "0.2.0", schemaOk: true, schema: "lahza.hostplan/1" });
    expect(conn.conn.client.baseUrl).toBe("http://127.0.0.1:47600");

    const adapter = new FakeAdapter();
    const prepared: string[] = [];
    const deps = {
      client: conn.conn.client,
      adapter,
      outDir: (n: string) => hostOutDir(env, n),
      prepareOutDir: async (d: string) => void prepared.push(d),
      pollMs: 0,
    };
    const jobs: number[] = [];
    const a = await analyzeMedia(deps, "/media/podcast.mp4", (j) => jobs.push(j.progress));
    expect(a.episodeId).toBe("e1");
    expect(a.clips.map((c) => c.id)).toEqual(["c2", "c1"]); // ball bo'yicha
    expect(jobs.at(-1)).toBe(1);
    expect(calls.find((c) => c.path === "/v1/projects" && c.method === "POST")?.body).toEqual({ name: "Premiere" });
    expect(calls.find((c) => c.path === "/v1/media:import")?.body).toEqual({
      project_id: "p1",
      path: "/media/podcast.mp4",
      title: "podcast.mp4",
    });

    const r = await makeReel(deps, "e1", "c2", { aspect: "9:16", orthography: "ascii" });
    const hp = calls.find((c) => c.path.endsWith(":hostplan"))!;
    expect(hp.body).toEqual({
      out_dir: "/Users/ali/Library/Application Support/Lahza Studio/premiere/e1_c2",
      aspect: "9:16",
      orthography: "ascii",
    });
    expect(prepared).toEqual(["/Users/ali/Library/Application Support/Lahza Studio/premiere/e1_c2"]);
    expect(r.result.sequenceName).toBe("Lahza — Mehmon gapi");
    expect(adapter.ops.of("placeVideo")).toHaveLength(3);
  });

  it("montaj: shablon + tanlangan fayllar -> /v1/montages -> hostplan -> build", async () => {
    const { calls, fetchFn } = mockEngine();
    const client = new EngineClient({ port: 47600, token: "tok" }, fetchFn);
    const adapter = new FakeAdapter();
    const tpl = { id: "tpl-podcast", name: { uz: "Podkast" }, category: "x", builtin: true, aspect: "9:16" as const, target_duration_ms: 30000 };
    const r = await makeMontage({ client, adapter, outDir: (n) => `/abs/${n}`, pollMs: 0 }, tpl, ["/m/a.mp4", "/m/b.mp4"]);
    expect(calls.find((c) => c.path === "/v1/montages")?.body).toEqual({
      template_id: "tpl-podcast",
      name: "Podkast · Premiere",
      sources: [
        { kind: "file", path: "/m/a.mp4" },
        { kind: "file", path: "/m/b.mp4" },
      ],
    });
    expect(calls.find((c) => c.path === "/v1/montages/mon1:hostplan")?.body).toEqual({ out_dir: "/abs/montage_mon1" });
    expect(r.result.placedClips).toBe(3);
    await expect(makeMontage({ client, adapter, outDir: (n) => n, pollMs: 0 }, tpl, [])).rejects.toThrow();
  });

  it("engine.json eskirgan (engine o'lik) - ulanish xatosi aniq", async () => {
    const res = await connectEngine({
      env,
      httpFetch: async () => {
        throw new TypeError("ECONNREFUSED");
      },
    });
    expect(res.ok).toBe(false);
    if (!res.ok) expect(res.error).toMatch(/aloqa yo'q/);
  });
});
