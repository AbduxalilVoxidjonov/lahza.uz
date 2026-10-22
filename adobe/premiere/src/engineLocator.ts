// Lahza Engine'ni topish: `<data_dir>/engine.json` (engine `lahza serve --discovery` bilan yozadi).
// Fayl o'qish host'ga bog'liq, shuning uchun `LocatorEnv` tashqaridan beriladi:
//  * Premiere: UXP `require("fs").readFile("file:/...")` - manifestda `localFileSystem: "fullAccess"` kerak
//    (manba: developer.adobe.com/premiere-pro/uxp/resources/recipes/filesystem-operations - `file:/` sxemasi
//    faqat fullAccess bilan);
//  * testlar: soxta env.
// Zaxira: foydalanuvchi port va tokenni qo'lda kiritadi (Lahza Studio -> Sozlamalar -> Engine).

import { DISCOVERY_FILE, EngineClient, EngineError, dataDir, parseDiscovery, type EngineInfo } from "@shared/engine";
import { HOSTPLAN_SCHEMA } from "@shared/hostplan";
import { hostRequire, type UxpFs, type UxpOs } from "./uxp-env";

export interface LocatorEnv {
  platform: "darwin" | "win32";
  home: string;
  localAppData?: string;
  readText(path: string): Promise<string>;
}

export type LocateResult =
  | { ok: true; info: EngineInfo; source: "discovery" | "manual"; path: string | null }
  | { ok: false; reason: "no_env" | "not_found" | "invalid"; path: string | null; message: string };

export function discoveryPath(env: Pick<LocatorEnv, "platform" | "home" | "localAppData">): string {
  const dir = dataDir(env.platform, env.home, env.localAppData);
  return env.platform === "win32" ? `${dir}\\${DISCOVERY_FILE}` : `${dir}/${DISCOVERY_FILE}`;
}

/** Oddiy yo'lni UXP fs URL'iga aylantiradi: `/Users/a/x` -> `file:/Users/a/x`, `C:\a\x` -> `file:/C:/a/x`. */
export function toUxpFileUrl(path: string): string {
  const p = path.replace(/\\/g, "/");
  return p.startsWith("/") ? `file:${p}` : `file:/${p}`;
}

export async function locateEngine(env: LocatorEnv | null): Promise<LocateResult> {
  if (!env) return { ok: false, reason: "no_env", path: null, message: "Fayl tizimiga kirish yo'q (UXP fs topilmadi)" };
  const path = discoveryPath(env);
  let text: string;
  try {
    text = await env.readText(path);
  } catch {
    return { ok: false, reason: "not_found", path, message: `${path} topilmadi` };
  }
  try {
    return { ok: true, info: parseDiscovery(text), source: "discovery", path };
  } catch (e) {
    return { ok: false, reason: "invalid", path, message: e instanceof Error ? e.message : String(e) };
  }
}

/** Qo'lda kiritilgan port/token (zaxira yo'l). */
export function manualEngine(port: string, token: string): EngineInfo {
  const p = Number(port.trim());
  if (!Number.isInteger(p) || p < 1 || p > 65535) throw new EngineError(0, "Port 1..65535 oralig'idagi butun son bo'lishi kerak");
  const t = token.trim();
  if (!t) throw new EngineError(0, "Token bo'sh");
  return { port: p, token: t };
}

export interface EngineProbe {
  version: string;
  schemaOk: boolean;
  schema: string;
}

/** Engine tirikmi va host-reja sxemasi plagin bilan mosmi. */
export async function probeEngine(client: EngineClient): Promise<EngineProbe> {
  const h = await client.health();
  const s = await client.hostplanSchema();
  return { version: h.version ?? s.engine, schemaOk: s.schema === HOSTPLAN_SCHEMA, schema: s.schema };
}

/** Premiere UXP muhiti uchun env (UXP `os` va `fs` modullari). Node'da `null`. */
export function uxpLocatorEnv(): LocatorEnv | null {
  const os = hostRequire<UxpOs>("os");
  const fs = hostRequire<UxpFs>("fs");
  if (!os || !fs) return null;
  // UXP `os.platform()` "darwin", "win32" yoki "win10" qaytarishi mumkin (hujjatdagi misol).
  const platform = os.platform().startsWith("win") ? "win32" : "darwin";
  const home = os.homedir();
  return {
    platform,
    home,
    // ANIQLANSIN: UXP'da %LOCALAPPDATA% ni o'qish yo'li hujjatda yo'q - `home\AppData\Local` (standart) ishlatiladi.
    readText: (p) => fs.readFile(toUxpFileUrl(p), { encoding: "utf-8" }),
  };
}

/** Engine chiqish papkasi (SRT va words.json uchun `out_dir`). */
export function hostOutDir(env: Pick<LocatorEnv, "platform" | "home" | "localAppData">, name: string): string {
  const dir = dataDir(env.platform, env.home, env.localAppData);
  const safe = name.replace(/[^\w.-]+/g, "_");
  return env.platform === "win32" ? `${dir}\\premiere\\${safe}` : `${dir}/premiere/${safe}`;
}
