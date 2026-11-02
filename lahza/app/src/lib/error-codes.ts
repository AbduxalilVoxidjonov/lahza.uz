// Engine tanigan xato kodlari -> tarjima qilingan matn kaliti.
// Kod uch yo'l bilan keladi: vazifa (`job.meta.error_code` + `job.meta.error_params`), navbat
// elementi (`item.error_code` + `item.error_params`) yoki HTTP javobi
// (`detail: {code, message, ...params}` -> ApiError.code/params).
// Kodlar ro'yxati engine'da: engine/src/lahza_engine/core/errors.py.
// Sof modul (React'siz) - node testlari to'g'ridan-to'g'ri ishlatadi.

export const ERROR_KEYS = {
  unsupported_codec: "err.unsupportedCodec",
  file_not_found: "err.fileNotFound",
  media_invalid: "err.mediaInvalid",
  no_audio: "err.noAudio",
  ffmpeg_failed: "err.ffmpegFailed",
  tool_missing: "err.toolMissing",
  libass_missing: "err.libassMissing",
  model_missing: "err.modelMissing",
  disk_full: "err.diskFull",
  permission_denied: "err.permissionDenied",
  out_of_memory: "err.outOfMemory",
  timeout: "err.timeout",
  network: "err.network",
  download_failed: "err.downloadFailed",
  cancelled: "err.cancelled",
  already_running: "err.alreadyRunning",
} as const;
/** Kod noma'lum yoki umuman yo'q bo'lganda - umumiy matn (xom xabar "batafsil" ichida). */
export const UNKNOWN_ERROR_KEY = "err.unknown" as const;
export type KnownErrorCode = keyof typeof ERROR_KEYS;
export type ErrorKey = (typeof ERROR_KEYS)[KnownErrorCode] | typeof UNKNOWN_ERROR_KEY;

export interface CodedError {
  key: ErrorKey;
  vars: Record<string, string>;
}

const isKnown = (c: unknown): c is KnownErrorCode =>
  typeof c === "string" && Object.prototype.hasOwnProperty.call(ERROR_KEYS, c);

function stringParams(p: unknown): Record<string, string> {
  const out: Record<string, string> = {};
  if (p && typeof p === "object") {
    for (const [k, v] of Object.entries(p as Record<string, unknown>)) {
      if (typeof v === "string" || typeof v === "number") out[k] = String(v);
    }
  }
  return out;
}

/** Matndagi o'zgaruvchilar: yo'q parametr `{x}` ko'rinishida qolib ketmasligi uchun standart qiymat. */
function vars(code: KnownErrorCode, params: Record<string, string>): Record<string, string> {
  switch (code) {
    // Kodek nomi: engine `label` (masalan, "AV1"), bo'lmasa `codec`.
    case "unsupported_codec":
      return { ...params, codec: params["label"] || (params["codec"] ?? "").toUpperCase() || "?" };
    case "file_not_found":
    case "permission_denied":
      return { ...params, path: params["path"] || "—" };
    case "ffmpeg_failed":
      return { ...params, rc: params["rc"] || "?" };
    case "tool_missing":
      return { ...params, tool: params["tool"] || "?" };
    default:
      return params;
  }
}

export function codedError(code: unknown, params?: unknown): CodedError | null {
  if (!isKnown(code)) return null;
  return { key: ERROR_KEYS[code], vars: vars(code, stringParams(params)) };
}

/** Ko'rsatish uchun to'liq tavsif: tarjima kaliti + o'zgaruvchilar + xom xabar ("batafsil"). */
export interface ErrorView extends CodedError {
  /** Engine'dan kelgan xom matn; bo'sh bo'lsa - null. */
  detail: string | null;
}

/** Kod tanilsa - o'z tarjimasi, aks holda `err.unknown`; xom matn har doim `detail`da saqlanadi. */
export function describeError(code: unknown, params: unknown, raw: string | null | undefined): ErrorView {
  const detail = typeof raw === "string" && raw.trim() ? raw.trim() : null;
  const coded = codedError(code, params);
  return coded ? { ...coded, detail } : { key: UNKNOWN_ERROR_KEY, vars: {}, detail };
}

/** Yiqilgan vazifa: `meta.error_code`/`meta.error_params` + `error`. */
export function describeJobError(job: { error?: string | null; meta: Record<string, unknown> }): ErrorView {
  return describeError(job.meta["error_code"], job.meta["error_params"], job.error);
}

/** Tahlil navbati elementi (`/v1/queue`): `error_code`/`error_params` + `error`. */
export function describeQueueError(item: { error: string | null; error_code?: string | null; error_params?: Record<string, string> | null }): ErrorView {
  return describeError(item.error_code, item.error_params, item.error);
}

/** Yiqilgan vazifadan (export, analyze, download ...). */
export function jobCodedError(job: { meta: Record<string, unknown> }): CodedError | null {
  return codedError(job.meta["error_code"], job.meta["error_params"]);
}

/** ApiError (yoki `code`/`params` maydonli istalgan xato) dan. */
export function apiCodedError(e: unknown): CodedError | null {
  if (!e || typeof e !== "object") return null;
  const o = e as { code?: unknown; params?: unknown };
  return codedError(o.code, o.params);
}

/** FastAPI `detail` obyekti: {code, message, ...params} -> ajratilgan qismlar. */
export function parseCodedDetail(detail: unknown): { message: string; code: string; params: Record<string, string> } | null {
  if (!detail || typeof detail !== "object" || Array.isArray(detail)) return null;
  const { code, message, ...rest } = detail as Record<string, unknown>;
  if (typeof code !== "string" || typeof message !== "string") return null;
  return { message, code, params: stringParams(rest) };
}
