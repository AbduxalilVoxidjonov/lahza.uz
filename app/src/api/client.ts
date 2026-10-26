// Engine bilan aloqa. Port va token Rust yadrodan olinadi (src-tauri/src/engine.rs);
// brauzerda dasturlash uchun VITE_ENGINE_URL / VITE_ENGINE_TOKEN ishlatiladi.

import { invoke, isTauri } from "@tauri-apps/api/core";

import { parseCodedDetail } from "../lib/error-codes";

export interface EngineInfo {
  baseUrl: string;
  token: string;
}

let cached: EngineInfo | null = null;

export async function engineInfo(): Promise<EngineInfo> {
  if (cached) return cached;
  if (isTauri()) {
    // Engine hali tayyor bo'lmasa, Rust "starting" xatosini qaytaradi - qayta urinamiz.
    for (let attempt = 0; attempt < 120; attempt++) {
      try {
        const info = await invoke<{ port: number; token: string }>("engine_info");
        cached = { baseUrl: `http://127.0.0.1:${info.port}`, token: info.token };
        return cached;
      } catch {
        await new Promise((r) => setTimeout(r, 500));
      }
    }
    throw new Error("Engine ishga tushmadi");
  }
  const baseUrl = import.meta.env.VITE_ENGINE_URL as string | undefined;
  const token = import.meta.env.VITE_ENGINE_TOKEN as string | undefined;
  if (!baseUrl || !token) throw new Error("VITE_ENGINE_URL va VITE_ENGINE_TOKEN sozlanmagan");
  cached = { baseUrl, token };
  return cached;
}

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
    /** Engine tanigan xato kodi (`detail.code`, masalan "unsupported_codec") - UI tarjima qiladi. */
    public code: string | null = null,
    public params: Record<string, string> = {},
  ) {
    super(message);
  }
}

async function request(path: string, init: RequestInit): Promise<Response> {
  const { baseUrl, token } = await engineInfo();
  const res = await fetch(baseUrl + path, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
      ...(init.headers ?? {}),
    },
  });
  if (!res.ok) {
    let detail = res.statusText;
    let code: string | null = null;
    let params: Record<string, string> = {};
    try {
      const body = (await res.json()) as { detail?: unknown };
      const coded = parseCodedDetail(body.detail);
      if (typeof body.detail === "string") detail = body.detail;
      else if (Array.isArray(body.detail)) detail = validationText(body.detail);
      else if (coded) ({ message: detail, code, params } = coded);
    } catch {
      /* matnsiz javob */
    }
    throw new ApiError(res.status, detail, code, params);
  }
  return res;
}

/** FastAPI/pydantic 422 javobi: [{loc, msg}] -> "maydon: xabar; ...". */
function validationText(items: unknown[]): string {
  return items
    .map((it) => {
      if (!it || typeof it !== "object") return String(it);
      const o = it as { loc?: unknown; msg?: unknown };
      const loc = Array.isArray(o.loc) ? o.loc.filter((x) => x !== "body").join(".") : "";
      const msg = typeof o.msg === "string" ? o.msg : JSON.stringify(it);
      return loc ? `${loc}: ${msg}` : msg;
    })
    .join("; ");
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await request(path, init);
  return (await res.json()) as T;
}

/** Ikkilik javob (masalan, preview JPEG kadri). */
export async function postBlob(path: string, body: unknown, signal?: AbortSignal): Promise<Blob> {
  const res = await request(path, { method: "POST", body: JSON.stringify(body), signal });
  return await res.blob();
}

/** GET orqali ikkilik javob (masalan, manba thumb kadri) - token sarlavhada. */
export async function getBlob(path: string, signal?: AbortSignal): Promise<Blob> {
  const res = await request(path, { method: "GET", signal });
  return await res.blob();
}

/** Foydalanuvchiga ko'rsatiladigan xato matni (engine `detail` o'zbekcha keladi). */
export function errorText(e: unknown): string {
  if (e instanceof Error) return e.message;
  return String(e);
}

export const get = <T>(path: string) => api<T>(path);
export const post = <T>(path: string, body?: unknown) =>
  api<T>(path, { method: "POST", body: body === undefined ? undefined : JSON.stringify(body) });
export const patch = <T>(path: string, body: unknown) =>
  api<T>(path, { method: "PATCH", body: JSON.stringify(body) });
export const put = <T>(path: string, body: unknown) =>
  api<T>(path, { method: "PUT", body: JSON.stringify(body) });
export const del = <T>(path: string) => api<T>(path, { method: "DELETE" });

/** <video> sarlavha yubora olmaydi - token so'rov parametrida. */
export async function mediaUrl(path: string): Promise<string> {
  const { baseUrl, token } = await engineInfo();
  return `${baseUrl}${path}?t=${encodeURIComponent(token)}`;
}

export async function eventsUrl(): Promise<string> {
  const { baseUrl, token } = await engineInfo();
  return `${baseUrl.replace(/^http/, "ws")}/v1/events?t=${encodeURIComponent(token)}`;
}
