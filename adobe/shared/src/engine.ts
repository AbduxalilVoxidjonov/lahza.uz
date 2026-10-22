// Lahza Engine mijozi - Premiere (UXP) va After Effects (CEP) plaginlari uchun umumiy.
// Engine 127.0.0.1 da ishlaydi; port va token `<data_dir>/engine.json` dan olinadi (`lahza serve --discovery`).
// Fayl o'qish host'ga bog'liq (UXP: localFileSystem, CEP: Node fs), shuning uchun u tashqaridan beriladi.

import { assertHostPlan, type HostPlan } from "./hostplan";
import type { Clip, Job, MontageSource, Template, TranscriptSentence } from "./types";

export interface EngineInfo {
  port: number;
  token: string;
  pid?: number;
  version?: string;
}

export const DISCOVERY_FILE = "engine.json";

/** Ma'lumotlar papkasi (engine config.default_data_dir bilan bir xil qoida). */
export function dataDir(platform: "darwin" | "win32", home: string, localAppData?: string): string {
  if (platform === "win32") return `${localAppData ?? `${home}\\AppData\\Local`}\\Lahza Studio`;
  return `${home}/Library/Application Support/Lahza Studio`;
}

export function parseDiscovery(text: string): EngineInfo {
  const d = JSON.parse(text) as Partial<EngineInfo>;
  if (typeof d.port !== "number" || typeof d.token !== "string" || !d.token) {
    throw new EngineError(0, "engine.json yaroqsiz — Lahza Engine'ni qayta ishga tushiring");
  }
  return { port: d.port, token: d.token, pid: d.pid, version: d.version };
}

export class EngineError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

type FetchFn = (url: string, init?: RequestInit) => Promise<Response>;

export class EngineClient {
  readonly baseUrl: string;

  constructor(
    private info: EngineInfo,
    private fetchFn: FetchFn = (u, i) => fetch(u, i),
  ) {
    this.baseUrl = `http://127.0.0.1:${info.port}`;
  }

  async request<T>(path: string, init: RequestInit = {}): Promise<T> {
    let res: Response;
    try {
      res = await this.fetchFn(this.baseUrl + path, {
        ...init,
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${this.info.token}`, ...(init.headers ?? {}) },
      });
    } catch {
      throw new EngineError(0, "Lahza Engine bilan aloqa yo'q — u ishlayaptimi?");
    }
    if (!res.ok) {
      let detail = res.statusText || `HTTP ${res.status}`;
      try {
        const body = (await res.json()) as { detail?: unknown };
        if (typeof body.detail === "string") detail = body.detail;
        else if (Array.isArray(body.detail)) detail = body.detail.map((d) => (d as { msg?: string }).msg ?? "").join("; ");
      } catch {
        /* matnsiz javob */
      }
      throw new EngineError(res.status, detail);
    }
    return (await res.json()) as T;
  }

  get = <T>(path: string) => this.request<T>(path);
  post = <T>(path: string, body?: unknown) =>
    this.request<T>(path, { method: "POST", body: body === undefined ? undefined : JSON.stringify(body) });

  /** Engine tirikligini tekshiradi. engine.json eskirgan bo'lishi mumkin (SIGKILL) - shuning uchun timeout bilan. */
  async health(timeoutMs = 3000): Promise<{ version: string; ok: boolean }> {
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), timeoutMs);
    try {
      return await this.request<{ version: string; ok: boolean }>("/v1/health", { signal: ctrl.signal });
    } finally {
      clearTimeout(timer);
    }
  }

  hostplanSchema() {
    return this.get<{ schema: string; engine: string }>("/v1/hostplan/schema");
  }

  /** Plagin uchun loyiha (shou) - nomi bo'yicha topadi yoki yaratadi. */
  async ensureProject(name: string): Promise<string> {
    const all = await this.get<{ id: string; name: string }[]>("/v1/projects");
    const found = all.find((p) => p.name === name);
    if (found) return found.id;
    return (await this.post<{ id: string }>("/v1/projects", { name })).id;
  }

  importMedia(projectId: string, path: string, opts: { title?: string; force_lite?: boolean; num_speakers?: number } = {}) {
    return this.post<{ episode_id: string; job: Job }>("/v1/media:import", { project_id: projectId, path, ...opts });
  }

  job(id: string) {
    return this.get<Job>(`/v1/jobs/${id}`);
  }

  cancelJob(id: string) {
    return this.post<Job>(`/v1/jobs/${id}:cancel`);
  }

  /** Vazifa tugaguncha kutadi (polling). `onProgress` har yangilanishda chaqiriladi. */
  async waitJob(id: string, onProgress?: (j: Job) => void, intervalMs = 1000, signal?: AbortSignal): Promise<Job> {
    for (;;) {
      if (signal?.aborted) throw new EngineError(0, "bekor qilindi");
      const j = await this.job(id);
      onProgress?.(j);
      if (j.status === "done") return j;
      if (j.status === "failed") throw new EngineError(500, j.error ?? "vazifa xato bilan tugadi");
      if (j.status === "cancelled") throw new EngineError(0, "vazifa bekor qilindi");
      await new Promise((r) => setTimeout(r, intervalMs));
    }
  }

  clips(episodeId: string) {
    return this.get<Clip[]>(`/v1/episodes/${episodeId}/clips`);
  }

  setClipStatus(episodeId: string, clipId: string, status: Clip["status"]) {
    return this.request<{ ok: boolean }>(`/v1/episodes/${episodeId}/clips/${clipId}`, {
      method: "PATCH",
      body: JSON.stringify({ status }),
    });
  }

  transcript(episodeId: string) {
    return this.get<{ sentences: TranscriptSentence[] }>(`/v1/episodes/${episodeId}/transcript`);
  }

  async clipHostPlan(
    episodeId: string,
    clipId: string,
    body: { out_dir: string; aspect?: "9:16" | "1:1" | "16:9"; orthography?: string; style?: Record<string, unknown> },
  ): Promise<HostPlan> {
    return assertHostPlan(await this.post<unknown>(`/v1/episodes/${episodeId}/clips/${clipId}:hostplan`, body));
  }

  templates() {
    return this.get<Template[]>("/v1/templates");
  }

  createMontage(body: { name?: string; template_id: string; sources: MontageSource[]; overrides?: Record<string, unknown> }) {
    return this.post<{ montage_id: string; job: Job }>("/v1/montages", body);
  }

  async montageHostPlan(montageId: string, outDir: string): Promise<HostPlan> {
    return assertHostPlan(await this.post<unknown>(`/v1/montages/${montageId}:hostplan`, { out_dir: outDir }));
  }
}
