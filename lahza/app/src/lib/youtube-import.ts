// YouTube havolasidan import (YT-1, ADR-0010): sof mantiq (React'siz - node testlari uchun).
// Havola tekshiruvi engine'dagi `media/youtube.parse_video_id` bilan bir xil qoidalarda: faqat
// youtube.com/watch?v=, youtube.com/shorts/ (live/), youtu.be/; boshqa domen va playlist rad etiladi.

export const VIDEO_ID_RE = /^[A-Za-z0-9_-]{11}$/;
const YOUTUBE_HOSTS = new Set(["youtube.com", "www.youtube.com", "m.youtube.com"]);
const SHORT_HOSTS = new Set(["youtu.be", "www.youtu.be"]);

/** Video ID yoki null (havola qabul qilinmaydi). */
export function parseYoutubeVideoId(input: string): string | null {
  let raw = (input ?? "").trim();
  if (!raw) return null;
  if (!raw.includes("://")) raw = `https://${raw}`;
  let u: URL;
  try {
    u = new URL(raw);
  } catch {
    return null;
  }
  if (u.protocol !== "https:" && u.protocol !== "http:") return null;
  if (u.username || u.password || (u.port && u.port !== "80" && u.port !== "443")) return null;
  const host = u.hostname.toLowerCase().replace(/\.$/, "");
  const segs = u.pathname.split("/").filter(Boolean);
  let id: string | null = null;
  if (SHORT_HOSTS.has(host)) {
    id = segs.length === 1 ? (segs[0] ?? null) : null;
  } else if (YOUTUBE_HOSTS.has(host)) {
    if (segs.length === 1 && segs[0] === "watch") {
      const vals = u.searchParams.getAll("v");
      id = vals.length === 1 ? (vals[0] ?? null) : null;
    } else if (segs.length === 2 && (segs[0] === "shorts" || segs[0] === "live")) {
      id = segs[1] ?? null;
    }
  } else {
    return null;
  }
  return id && VIDEO_ID_RE.test(id) ? id : null;
}

/** Engine `job.meta.error_code` qiymatlari (media/youtube.py MESSAGES). */
export const YT_ERROR_CODES = [
  "not_installed", "network", "private", "age_restricted", "login_required", "unavailable", "live",
  "js_runtime", "format_unavailable", "ffmpeg", "crashed", "invalid_url",
  // O'rnatilgan yt-dlp ilovaning bu versiyasiga mos emas (yangi Lahza yoki komponentlarni qayta o'rnatish kerak).
  "incompatible",
] as const;
export type YtErrorCode = (typeof YT_ERROR_CODES)[number];

export const isYtErrorCode = (c: unknown): c is YtErrorCode =>
  typeof c === "string" && (YT_ERROR_CODES as readonly string[]).includes(c);

/** Ikkala tasdiq ham belgilangan bo'lsagina import tugmasi faol (API'da `consent: true`). */
export interface ConsentState {
  owner: boolean;
  terms: boolean;
}
export const consentGiven = (c: ConsentState) => c.owner && c.terms;

export function canStart(opts: { enabled: boolean; installed: boolean; url: string; busy: boolean }): boolean {
  return opts.enabled && opts.installed && !opts.busy && parseYoutubeVideoId(opts.url) !== null;
}

export function fmtBytes(n: number | null | undefined): string {
  if (n == null || !Number.isFinite(n) || n < 0) return "—";
  const units = ["B", "KB", "MB", "GB"];
  let v = n;
  let i = 0;
  while (v >= 1024 && i < units.length - 1) {
    v /= 1024;
    i++;
  }
  return `${v.toFixed(i === 0 ? 0 : 1)} ${units[i]}`;
}

export function fmtEta(s: number | null | undefined): string {
  if (s == null || !Number.isFinite(s) || s < 0) return "—";
  const sec = Math.round(s);
  const m = Math.floor(sec / 60);
  const r = sec % 60;
  return m >= 60 ? `${Math.floor(m / 60)}:${String(m % 60).padStart(2, "0")}:${String(r).padStart(2, "0")}` : `${m}:${String(r).padStart(2, "0")}`;
}

interface DownloadMeta {
  downloaded_bytes?: number | null;
  total_bytes?: number | null;
  speed?: number | null;
  eta?: number | null;
}

/** `download` vazifasidan ko'rsatiladigan qiymatlar (foiz, tezlik, qolgan vaqt). */
export function downloadView(job: { progress: number; meta: Record<string, unknown> }) {
  const d = (job.meta["download"] ?? {}) as DownloadMeta;
  return {
    percent: Math.round(Math.max(0, Math.min(1, job.progress)) * 100),
    speed: d.speed ? `${fmtBytes(d.speed)}/s` : "—",
    eta: fmtEta(d.eta),
    size: d.total_bytes ? `${fmtBytes(d.downloaded_bytes ?? 0)} / ${fmtBytes(d.total_bytes)}` : fmtBytes(d.downloaded_bytes ?? null),
    title: typeof job.meta["title"] === "string" ? (job.meta["title"] as string) : null,
    errorCode: isYtErrorCode(job.meta["error_code"]) ? (job.meta["error_code"] as YtErrorCode) : null,
    episodeId: typeof job.meta["episode_id"] === "string" ? (job.meta["episode_id"] as string) : null,
  };
}

/**
 * Import kartasidagi YouTube maydonining holati (maydon har doim ko'rinadi, faqat faolligi o'zgaradi).
 * loading: holat hali kelmagan; disabled: Sozlamalarda o'chirilgan (standart - yoqilgan);
 * notInstalled: yt-dlp yo'q; noJs: ishlaydi, lekin JS runtime yo'q (ogohlantirish); ready: tayyor.
 */
export type YoutubeFieldState = "loading" | "disabled" | "notInstalled" | "noJs" | "ready";

export function youtubeFieldState(
  st: { enabled: boolean; installed: boolean; js_runtime?: string | null } | null | undefined,
): YoutubeFieldState {
  if (!st) return "loading";
  if (!st.enabled) return "disabled";
  if (!st.installed) return "notInstalled";
  return st.js_runtime ? "ready" : "noJs";
}

/** Havola maydoniga yozish mumkinmi (o'chiq yoki holat noma'lum bo'lsa - yo'q). */
export const youtubeInputEnabled = (s: YoutubeFieldState) => s !== "loading" && s !== "disabled";
