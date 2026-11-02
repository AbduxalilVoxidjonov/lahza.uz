// EngineClient uchun transport (shared `EngineClient` ikkinchi argument sifatida `fetchFn` qabul qiladi).
//
// (1) HTTP (asosiy): UXP global `fetch` -> http://127.0.0.1:<port>. Manifestdagi `network.domains` ga kiritilgan
//     bo'lishi shart. ANIQLANSIN: Adobe "macOS http:// ni cheklaydi" deydi (Premiere UXP network recipe),
//     127.0.0.1 istisnosi hujjatda yo'q; github.com/AdobeDocs/uxp-photoshop/issues/321 da bir foydalanuvchi
//     `http://127.0.0.1:11434` (port bilan) ishlaganini yozgan, `localhost` satri ishlamagan.
// (2) ZAXIRA - fayl-asosidagi IPC (tarmoqsiz): HTTP ulanmasa (TypeError/permission) ishlatiladi.
//
// Fayl-IPC protokoli `lahza.ipc/1` (engine tomoni alohida amalga oshiriladi):
//   papka:    <data_dir>/ipc/requests/   va   <data_dir>/ipc/responses/
//   so'rov:   plagin `requests/<id>.json.tmp` yozadi, so'ng atomar `rename` -> `requests/<id>.json`
//             {"v":1,"id":"<id>","method":"GET|POST|PATCH|DELETE","path":"/v1/...",
//              "headers":{"Authorization":"Bearer <token>"},"body":<JSON|null>,"created_at":"<ISO>"}
//   javob:    engine `requests/<id>.json` ni o'qiydi va o'chiradi, xuddi HTTP handler kabi bajaradi (token tekshiruvi
//             majburiy), `responses/<id>.json.tmp` yozib `responses/<id>.json` ga rename qiladi:
//             {"v":1,"id":"<id>","status":200,"body":<JSON|null>}
//   plagin:   `responses/<id>.json` paydo bo'lguncha so'raydi (100 ms -> 500 ms), o'qiydi va o'chiradi;
//             vaqt tugasa (standart 30 s) - so'rov faylini o'chirib, xato beradi.
//   id:       `[A-Za-z0-9-]{8,64}` (boshqa belgilar rad etiladi - yo'l injeksiyasi bo'lmasin).
//   engine:   `.tmp` fayllarni e'tiborsiz qoldiradi; 5 daqiqadan eski so'rov/javoblarni tozalaydi.

import { EngineError } from "@shared/engine";

export type FetchFn = (url: string, init?: RequestInit) => Promise<Response>;

/** Fayl operatsiyalari (UXP `fs` yoki testda xotira). Yo'llar - oddiy absolyut yo'llar. */
export interface IpcFs {
  writeText(path: string, text: string): Promise<void>;
  readText(path: string): Promise<string>;
  rename(from: string, to: string): Promise<void>;
  remove(path: string): Promise<void>;
  mkdirp(path: string): Promise<void>;
}

export interface IpcOptions {
  ipcDir: string; // <data_dir>/ipc
  sep?: "/" | "\\";
  timeoutMs?: number;
  sleep?: (ms: number) => Promise<void>;
  newId?: () => string;
  now?: () => Date;
}

export interface IpcRequest {
  v: 1;
  id: string;
  method: string;
  path: string;
  headers: Record<string, string>;
  body: unknown;
  created_at: string;
}

export interface IpcResponse {
  v: 1;
  id: string;
  status: number;
  body: unknown;
}

const ID_RE = /^[A-Za-z0-9-]{8,64}$/;

/** EngineClient faqat `ok`, `status`, `statusText`, `json()` dan foydalanadi - shu minimal javob. */
function responseLike(status: number, body: unknown): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    statusText: "",
    json: async () => body,
  } as unknown as Response;
}

function headersToRecord(h: RequestInit["headers"]): Record<string, string> {
  const out: Record<string, string> = {};
  if (!h) return out;
  if (Array.isArray(h)) for (const [k, v] of h) out[k] = v;
  else if (typeof Headers !== "undefined" && h instanceof Headers) h.forEach((v, k) => (out[k] = v));
  else Object.assign(out, h as Record<string, string>);
  return out;
}

function randomId(): string {
  const a = "abcdefghijklmnopqrstuvwxyz0123456789";
  let s = "";
  for (let i = 0; i < 24; i++) s += a[Math.floor(Math.random() * a.length)];
  return s;
}

export function fileIpcFetch(fs: IpcFs, opts: IpcOptions): FetchFn {
  const sep = opts.sep ?? "/";
  const sleep = opts.sleep ?? ((ms) => new Promise((r) => setTimeout(r, ms)));
  const timeout = opts.timeoutMs ?? 30_000;
  const reqDir = `${opts.ipcDir}${sep}requests`;
  const resDir = `${opts.ipcDir}${sep}responses`;
  let dirsReady = false;

  return async (url, init = {}) => {
    const u = new URL(url);
    const id = (opts.newId ?? randomId)();
    if (!ID_RE.test(id)) throw new EngineError(0, "IPC id yaroqsiz");
    if (!dirsReady) {
      await fs.mkdirp(reqDir);
      await fs.mkdirp(resDir);
      dirsReady = true;
    }
    const req: IpcRequest = {
      v: 1,
      id,
      method: (init.method ?? "GET").toUpperCase(),
      path: u.pathname + u.search,
      headers: headersToRecord(init.headers),
      body: typeof init.body === "string" && init.body ? JSON.parse(init.body) : null,
      created_at: (opts.now ?? (() => new Date()))().toISOString(),
    };
    const reqPath = `${reqDir}${sep}${id}.json`;
    await fs.writeText(`${reqPath}.tmp`, JSON.stringify(req));
    await fs.rename(`${reqPath}.tmp`, reqPath);

    const resPath = `${resDir}${sep}${id}.json`;
    let waited = 0;
    let delay = 100;
    for (;;) {
      let text: string | null = null;
      try {
        text = await fs.readText(resPath);
      } catch {
        text = null;
      }
      if (text !== null) {
        await fs.remove(resPath).catch(() => undefined);
        const res = JSON.parse(text) as IpcResponse;
        if (res.id !== id) throw new EngineError(0, "IPC javobi boshqa so'rovga tegishli");
        return responseLike(res.status, res.body);
      }
      if (waited >= timeout) {
        await fs.remove(reqPath).catch(() => undefined);
        // EngineClient bu xatoni "aloqa yo'q" ga aylantiradi.
        throw new TypeError("IPC: engine javob bermadi");
      }
      await sleep(delay);
      waited += delay;
      delay = Math.min(500, delay * 2);
    }
  };
}

/**
 * HTTP'ni sinab ko'radi; tarmoq xatosi bo'lsa (UXP permission yoki macOS http cheklovi) keyingi so'rovlardan
 * boshlab fayl-IPC'ga o'tadi. `onMode` - UI'da qaysi transport ishlayotganini ko'rsatish uchun.
 */
export function fallbackFetch(primary: FetchFn, fallback: FetchFn | null, onMode?: (m: "http" | "ipc") => void): FetchFn {
  let mode: "http" | "ipc" = "http";
  return async (url, init) => {
    if (mode === "http") {
      try {
        const r = await primary(url, init);
        onMode?.("http");
        return r;
      } catch (e) {
        if (!fallback) throw e;
        mode = "ipc";
      }
    }
    onMode?.("ipc");
    return fallback!(url, init);
  };
}

/** UXP `fs` ustidagi IpcFs (`file:` URL'lar bilan). */
export function uxpIpcFs(fs: {
  readFile(p: string, o: { encoding: "utf-8" }): Promise<string>;
  writeFile(p: string, d: string, o: { encoding: "utf-8" }): Promise<number>;
  rename(a: string, b: string): Promise<number>;
  unlink(p: string): Promise<number>;
  mkdir(p: string, o?: { recursive?: boolean }): Promise<number>;
}, toUrl: (p: string) => string): IpcFs {
  return {
    readText: (p) => fs.readFile(toUrl(p), { encoding: "utf-8" }),
    writeText: async (p, t) => {
      await fs.writeFile(toUrl(p), t, { encoding: "utf-8" });
    },
    rename: async (a, b) => {
      await fs.rename(toUrl(a), toUrl(b));
    },
    remove: async (p) => {
      await fs.unlink(toUrl(p));
    },
    mkdirp: async (p) => {
      try {
        await fs.mkdir(toUrl(p), { recursive: true });
      } catch {
        /* allaqachon bor */
      }
    },
  };
}
