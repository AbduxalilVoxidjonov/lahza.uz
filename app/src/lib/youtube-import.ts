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
  // Topilgan JS runtime yt-dlp uchun eski (Deno < 2.3, Node < 22); playlist ro'yxati vaqt tugadi/bo'sh.
  "js_outdated", "timeout", "empty",
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

// ---------------------------------------------------------------- playlist va kanal havolalari
// Engine `media/youtube.parse_source_url` bilan bir xil qoidalar.
const LIST_ID_RE = /^[A-Za-z0-9_-]{2,64}$/;
const HANDLE_RE = /^@[A-Za-z0-9._-]{1,100}$/;
const CHANNEL_ID_RE = /^UC[A-Za-z0-9_-]{22}$/;
const CHANNEL_NAME_RE = /^[A-Za-z0-9._-]{1,100}$/;

export type YoutubeSourceKind = "video" | "playlist" | "channel";
export interface YoutubeSource {
  kind: YoutubeSourceKind;
  /** Kanonik havola (engine'ga shu yuboriladi). */
  url: string;
}

/** Video, playlist yoki kanal havolasi; boshqasi - null. Kanaldan faqat "Videolar" bo'limi. */
export function parseYoutubeSource(input: string): YoutubeSource | null {
  const vid = parseYoutubeVideoId(input);
  if (vid) return { kind: "video", url: `https://www.youtube.com/watch?v=${vid}` };
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
  if (!YOUTUBE_HOSTS.has(host)) return null;
  const segs = u.pathname.split("/").filter(Boolean);
  if (segs.length === 1 && segs[0] === "playlist") {
    const vals = u.searchParams.getAll("list");
    const id = vals.length === 1 ? vals[0] ?? "" : "";
    return LIST_ID_RE.test(id) ? { kind: "playlist", url: `https://www.youtube.com/playlist?list=${id}` } : null;
  }
  let base: string[] | null = null;
  let rest: string[] = [];
  if (segs[0] && HANDLE_RE.test(segs[0])) {
    base = segs.slice(0, 1);
    rest = segs.slice(1);
  } else if (segs.length >= 2 && segs[0] === "channel" && CHANNEL_ID_RE.test(segs[1] ?? "")) {
    base = segs.slice(0, 2);
    rest = segs.slice(2);
  } else if (segs.length >= 2 && (segs[0] === "c" || segs[0] === "user") && CHANNEL_NAME_RE.test(segs[1] ?? "")) {
    base = segs.slice(0, 2);
    rest = segs.slice(2);
  }
  if (!base) return null;
  if (!(rest.length === 0 || (rest.length === 1 && (rest[0] === "videos" || rest[0] === "featured")))) return null;
  return { kind: "channel", url: `https://www.youtube.com/${base.join("/")}/videos` };
}

/** `/v1/media:resolve-url` elementi. `skip` bo'lsa - import qilinmaydi (sababi). */
export type EntrySkip = "short" | "live" | "upcoming" | "private" | "unavailable";
export interface ResolvedEntry {
  id: string;
  url: string;
  title: string | null;
  duration_s: number | null;
  thumbnail_url?: string | null;
  skip: EntrySkip | null;
}
export interface ResolvedUrl {
  kind: YoutubeSourceKind;
  title: string | null;
  entries: ResolvedEntry[];
  /** Ro'yxat 50 ta bilan cheklangan (ko'proq video bor). */
  truncated: boolean;
}

export const selectableIds = (entries: ResolvedEntry[]) => entries.filter((e) => !e.skip).map((e) => e.id);

/** Dastlabki tanlov: import qilsa bo'ladigan hamma video. */
export const initialSelection = (entries: ResolvedEntry[]) => new Set(selectableIds(entries));

/** "Hammasini tanlash" belgisi: hammasi tanlangan bo'lsa - tozalaydi, aks holda hammasini tanlaydi. */
export function toggleAll(entries: ResolvedEntry[], selected: ReadonlySet<string>): Set<string> {
  const ids = selectableIds(entries);
  return ids.length > 0 && ids.every((id) => selected.has(id)) ? new Set() : new Set(ids);
}

export function toggleOne(entries: ResolvedEntry[], selected: ReadonlySet<string>, id: string): Set<string> {
  const e = entries.find((x) => x.id === id);
  const next = new Set(selected);
  if (!e || e.skip) return next;
  if (next.has(id)) next.delete(id);
  else next.add(id);
  return next;
}

/** Navbatga yuboriladigan elementlar (ro'yxat tartibida). */
export const queueUrls = (entries: ResolvedEntry[], selected: ReadonlySet<string>) =>
  entries.filter((e) => !e.skip && selected.has(e.id)).map((e) => ({ url: e.url, title: e.title ?? undefined }));

/** Tanlanganlarning umumiy davomiyligi (soniya; noma'lumlar hisobga olinmaydi). */
export const totalDuration = (entries: ResolvedEntry[], selected: ReadonlySet<string>) =>
  entries.reduce((acc, e) => acc + (selected.has(e.id) && !e.skip && e.duration_s ? e.duration_s : 0), 0);

/** 75 -> "1:15", 3725 -> "1:02:05", noma'lum -> "—". */
export const fmtDuration = (s: number | null | undefined) => fmtEta(s);

// ---------------------------------------------------------------- komponentlar holati (UI)
export interface ComponentsLike {
  installed: boolean;
  version: string | null;
  js_runtime: string | null;
  components_ready: boolean;
  ytdlp_source?: "components" | "system" | null;
  js_runtime_version?: string | null;
  js_runtime_source?: "components" | "system" | null;
  js_runtime_outdated?: { name: string; version: string | null }[];
}

/**
 * Komponentlar holati UI uchun:
 * ready - ilovaning o'z komponentlari tayyor; system - import ishlaydi, lekin tizimdagi (venv/PATH)
 * yt-dlp yoki JS runtime ishlatilmoqda (`components_ready=false` xato emas); missing - o'rnatish kerak.
 */
export type ComponentsMode = "ready" | "system" | "missing";

export function componentsMode(st: ComponentsLike): ComponentsMode {
  if (st.components_ready) return "ready";
  return st.installed && !!st.js_runtime ? "system" : "missing";
}

/** "yt-dlp 2026.10.21 (tizim), deno 2.9.6 (tizim)" - qaysi nusxa ishlatilayotgani. */
export function componentsInUse(st: ComponentsLike, labels: { system: string; app: string }): string {
  const tag = (src: string | null | undefined) => (src === "components" ? labels.app : labels.system);
  const parts: string[] = [];
  if (st.installed) parts.push(`yt-dlp ${st.version ?? "?"} (${tag(st.ytdlp_source)})`);
  if (st.js_runtime) parts.push(`${st.js_runtime} ${st.js_runtime_version ?? "?"} (${tag(st.js_runtime_source)})`);
  return parts.join(", ");
}

/** Eski (yt-dlp qo'llamaydigan) runtime'lar: "deno 2.1.4, node 20.11.0". */
export const outdatedRuntimes = (st: ComponentsLike) =>
  (st.js_runtime_outdated ?? []).map((r) => `${r.name} ${r.version ?? "?"}`).join(", ");

// ---------------------------------------------------------------- epizod manbasi va boblar
export interface Chapter {
  start_ms: number;
  end_ms: number;
  title: string;
}

/** Bob boshidagi YouTube havolasi (`&t=123s`); faqat kanonik watch havolasiga qo'shiladi. */
export function youtubeAt(url: string, ms: number): string {
  const vid = parseYoutubeVideoId(url);
  if (!vid) return url;
  return `https://www.youtube.com/watch?v=${vid}&t=${Math.max(0, Math.floor(ms / 1000))}s`;
}

/** Transkriptdagi `?t=` dan keyin birinchi bo'lgan so'z indeksi (yo'q bo'lsa - oxirgisi). */
export function wordIndexAt(words: { start_ms: number; end_ms: number }[], ms: number): number | null {
  if (!words.length || !Number.isFinite(ms)) return null;
  const i = words.findIndex((w) => w.end_ms > ms);
  return i === -1 ? words.length - 1 : i;
}

// ---------------------------------------------------------------- Boshlash sahifasi (montaj manbasi)
/** Boshlash sahifasidan import qilinganda loyiha so'ralmaydi: shu nomdagi loyiha olinadi yoki yaratiladi. */
export const YOUTUBE_PROJECT_NAME = "YouTube";

/** Mavjud "YouTube" loyihasi (nomi katta-kichik harfsiz, bo'shliqsiz solishtiriladi) yoki null. */
export function findYoutubeProject(projects: readonly { id: string; name: string }[] | null | undefined): string | null {
  const want = YOUTUBE_PROJECT_NAME.toLowerCase();
  return projects?.find((p) => p.name.trim().toLowerCase() === want)?.id ?? null;
}

/** Tugagan `download` vazifasi natijasi: yuklangan fayl yo'li, sarlavha, epizod (`routes_youtube.import_url`). */
export interface ImportedVideo {
  path: string;
  title: string | null;
  episodeId: string | null;
}

export function importedVideo(
  job: { status: string; result: Record<string, unknown> | null; meta: Record<string, unknown> } | null | undefined,
): ImportedVideo | null {
  if (!job || job.status !== "done") return null;
  const r = job.result ?? {};
  const path = typeof r["path"] === "string" && r["path"] ? (r["path"] as string) : null;
  if (!path) return null;
  const str = (v: unknown) => (typeof v === "string" && v ? v : null);
  return {
    path,
    title: str(r["title"]) ?? str(job.meta["title"]),
    episodeId: str(r["episode_id"]) ?? str(job.meta["episode_id"]),
  };
}

/**
 * Montaj manbasi (`SourcePicker` `PickedSource` bilan bir xil shakl). Fayl manbasi tanlanadi: epizod tahlili
 * (transkript) tugashini kutmasdan montaj darhol boshlanadi - engine `episode` manbasini tahlilsiz rad etadi.
 * Kalit `sourceKey` bilan bir xil (`file:<yo'l>`), shuning uchun takroriy qo'shilmaydi.
 */
export function importedToSource(v: ImportedVideo, projectId?: string) {
  const source = { kind: "file" as const, path: v.path };
  const base = v.path.split(/[\\/]/).pop() || v.path;
  return { key: `file:${v.path}`, source, label: v.title ?? base, detail: `YouTube · ${base}`, projectId };
}
