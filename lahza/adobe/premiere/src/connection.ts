// Engine'ga ulanish: engine.json (yoki qo'lda port/token) -> EngineClient (HTTP, zaxira fayl-IPC) -> probe.
// engine.json SIGKILL'dan keyin eskirgan bo'lishi mumkin, shuning uchun pid'ga emas, /v1/health ga tayanamiz.

import { EngineClient, dataDir, type EngineInfo } from "@shared/engine";
import { locateEngine, probeEngine, type EngineProbe, type LocateResult, type LocatorEnv } from "./engineLocator";
import { fallbackFetch, fileIpcFetch, type FetchFn, type IpcFs } from "./transport";

export interface Connection {
  client: EngineClient;
  info: EngineInfo;
  probe: EngineProbe;
  transport: () => "http" | "ipc";
}

export type ConnectResult =
  | { ok: true; conn: Connection; locate: LocateResult | null }
  | { ok: false; locate: LocateResult | null; error: string };

export interface ConnectOptions {
  env: LocatorEnv | null;
  manual?: EngineInfo | null;
  httpFetch: FetchFn;
  /** Fayl-IPC zaxirasi (UXP fs). `null` - zaxira yo'q. */
  ipcFs?: IpcFs | null;
  pollMs?: number;
}

export async function connectEngine(o: ConnectOptions): Promise<ConnectResult> {
  let locate: LocateResult | null = null;
  let info: EngineInfo;
  if (o.manual) {
    info = o.manual;
  } else {
    locate = await locateEngine(o.env);
    if (!locate.ok) return { ok: false, locate, error: locate.message };
    info = locate.info;
  }
  let mode: "http" | "ipc" = "http";
  const ipc =
    o.ipcFs && o.env
      ? fileIpcFetch(o.ipcFs, {
          ipcDir: `${dataDir(o.env.platform, o.env.home, o.env.localAppData)}${o.env.platform === "win32" ? "\\" : "/"}ipc`,
          sep: o.env.platform === "win32" ? "\\" : "/",
          timeoutMs: 10_000,
        })
      : null;
  const client = new EngineClient(info, fallbackFetch(o.httpFetch, ipc, (m) => (mode = m)));
  try {
    const probe = await probeEngine(client);
    return { ok: true, conn: { client, info, probe, transport: () => mode }, locate };
  } catch (e) {
    return { ok: false, locate, error: e instanceof Error ? e.message : String(e) };
  }
}
