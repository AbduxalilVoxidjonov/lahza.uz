// Engine'ni topish: `<data_dir>/engine.json` ni CEP Node (manifest: --enable-nodejs --mixed-context) bilan o'qish.
// CEP 12 Cookbook: Node yoqilganda global `cep_node` {Buffer, global, process, require} mavjud; mixed context'da
// `require` ham global. Node yo'q bo'lsa (yoki fayl yo'q) — UI port/token'ni qo'lda so'raydi.

import { DISCOVERY_FILE, EngineClient, dataDir, parseDiscovery, type EngineInfo } from "../../../shared/src/engine";

type NodeRequire = (id: string) => unknown;

interface NodeEnv {
  fs: { readFileSync(p: string, enc: "utf8"): string; existsSync(p: string): boolean };
  os: { homedir(): string };
  process: { platform: string; env: Record<string, string | undefined> };
}

export function nodeEnv(g: unknown = globalThis): NodeEnv | null {
  const w = g as { cep_node?: { require?: NodeRequire; process?: NodeEnv["process"] }; require?: NodeRequire; process?: NodeEnv["process"] };
  const req = w.cep_node?.require ?? w.require;
  const proc = w.cep_node?.process ?? w.process;
  if (typeof req !== "function" || !proc) return null;
  try {
    return { fs: req("fs") as NodeEnv["fs"], os: req("os") as NodeEnv["os"], process: proc };
  } catch {
    return null;
  }
}

export function discoveryPath(env: NodeEnv): string {
  const override = env.process.env.LAHZA_DATA_DIR;
  const platform = env.process.platform === "win32" ? "win32" : "darwin";
  const dir = override || dataDir(platform, env.os.homedir(), env.process.env.LOCALAPPDATA);
  return `${dir}${platform === "win32" ? "\\" : "/"}${DISCOVERY_FILE}`;
}

export type Discovery =
  | { kind: "found"; info: EngineInfo; path: string }
  | { kind: "missing"; path: string }
  | { kind: "no-node" }
  | { kind: "invalid"; path: string; error: string };

export function readDiscovery(env: NodeEnv | null = nodeEnv()): Discovery {
  if (!env) return { kind: "no-node" };
  const path = discoveryPath(env);
  if (!env.fs.existsSync(path)) return { kind: "missing", path };
  try {
    return { kind: "found", info: parseDiscovery(env.fs.readFileSync(path, "utf8")), path };
  } catch (e) {
    return { kind: "invalid", path, error: e instanceof Error ? e.message : String(e) };
  }
}

/** engine.json eskirgan bo'lishi mumkin (SIGKILL) — /v1/health va /v1/hostplan/schema bilan tekshiramiz. */
export async function probeEngine(client: EngineClient): Promise<{ version: string; schema: string }> {
  const h = await client.health();
  const s = await client.hostplanSchema();
  return { version: h.version, schema: s.schema };
}

/** Uy papkasi va yo'l ajratgichi (Node bo'lmasa null). */
export function homeDir(env: NodeEnv | null = nodeEnv()): { home: string; sep: "/" | "\\" } | null {
  if (!env) return null;
  try {
    return { home: env.os.homedir(), sep: env.process.platform === "win32" ? "\\" : "/" };
  } catch {
    return null;
  }
}
