// Montaj (Lahza Timeline) hisob-kitoblari - engine `montage/model.py` bilan bir xil qoidalar.
import type {
  FxManifest,
  FxParamSpec,
  LocalText,
  MontageTimeline,
  Template,
  TemplateCategory,
  VideoItem,
  TextItem,
  StickerItem,
} from "../api/types";
import { DEFAULT_STYLE } from "../api/types";
import type { Locale } from "../i18n";

export const TEMPLATE_CATEGORIES: TemplateCategory[] = ["podkast", "elon", "tadbir", "mahsulot", "intervyu", "talim", "boshqa"];

/** Element chiqish davomiyligi (tezlik hisobga olingan). */
export const outDur = (it: VideoItem) => Math.round((it.src_out_ms - it.src_in_ms) / it.speed);

/** Har video elementning chiqish vaqtidagi boshi (o'tishlar ustma-ustligi hisobga olingan). */
export function itemStarts(tl: Pick<MontageTimeline, "video">): number[] {
  const starts: number[] = [];
  let t = 0;
  tl.video.forEach((it, i) => {
    const prev = tl.video[i - 1];
    if (i > 0 && prev && it.transition_in) t -= Math.min(it.transition_in.dur_ms, outDur(it), outDur(prev));
    starts.push(t);
    t += outDur(it);
  });
  return starts;
}

export function timelineDuration(tl: MontageTimeline): number {
  const textEnd = Math.max(0, ...tl.text.map((x) => x.end_ms));
  const last = tl.video[tl.video.length - 1];
  if (!last) return textEnd;
  const starts = itemStarts(tl);
  // Engine bilan bir xil: video oxiri yoki undan keyin davom etadigan karta oxiri;
  // video ustidagi oddiy matn davomiylikni uzaytirmaydi.
  const cardEnd = Math.max(0, ...tl.text.filter((x) => x.kind === "card").map((x) => x.end_ms));
  return Math.max((starts[starts.length - 1] ?? 0) + outDur(last), cardEnd);
}

export const frameMs = (fps: number) => 1000 / (fps > 0 ? fps : 30);

/** Lokal matn: joriy til, bo'lmasa `uz`. */
export function localText(lt: LocalText | Record<string, string> | null | undefined, locale: Locale): string {
  if (!lt) return "";
  const rec = lt as Record<string, string | null | undefined>;
  return rec[locale] || rec["uz"] || "";
}

export function fxName(fx: FxManifest[] | undefined, id: string | null | undefined, locale: Locale): string {
  if (!id) return "";
  const m = fx?.find((x) => x.id === id);
  return m ? localText(m.name, locale) || id : id.replace(/^uz\.lahza\.[a-z]+\./, "");
}

export const clamp = (v: number, min: number, max: number) => Math.max(min, Math.min(max, v));

export function newId(prefix: string): string {
  const rnd = typeof crypto !== "undefined" && "randomUUID" in crypto ? crypto.randomUUID().slice(0, 8) : Math.random().toString(36).slice(2, 10);
  return `${prefix}${rnd}`;
}

/** Birinchi elementda o'tish bo'lmaydi (engine validatsiyasi). */
export function normalizeVideo(video: VideoItem[]): VideoItem[] {
  const first = video[0];
  if (first && first.transition_in) return [{ ...first, transition_in: null }, ...video.slice(1)];
  return video;
}

/** Manifest parametrlari standart qiymatlari. */
export function defaultParams(specs: FxParamSpec[] | undefined): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  for (const p of specs ?? []) {
    if (p.default !== undefined && p.default !== null) out[p.id] = p.default;
  }
  return out;
}

/** Yangi foydalanuvchi shabloni. */
export function blankTemplate(): Template {
  return {
    schema: "lahza.template/1",
    id: newId("user."),
    version: "1.0.0",
    name: { uz: "Yangi shablon" },
    category: "boshqa",
    builtin: false,
    aspect: "9:16",
    fps: 30,
    target_duration_ms: 30_000,
    min_shot_ms: 1500,
    max_shot_ms: 8000,
    selection: "scenes",
    order: "berilgan",
    max_per_source: null,
    respect_sentences: true,
    reframe: "auto",
    transition: { plugin: "uz.lahza.tr.dissolve", dur_ms: 400, params: {} },
    fx: [],
    color: null,
    captions: false,
    caption_style: null,
    intro: null,
    hook_text: null,
    outro: null,
    music: null,
    source_gain_db: 0,
    mute_sources: false,
    loudnorm_lufs: null,
    logo: false,
  };
}

/** Engine `exclude_none` bilan qaytaradi - yetishmagan maydonlarni standart bilan to'ldiramiz. */
export function withTemplateDefaults(t: Template): Template {
  const base = blankTemplate();
  return {
    ...base,
    ...t,
    transition: t.transition ?? null,
    fx: t.fx ?? [],
    caption_style: t.caption_style ? { ...DEFAULT_STYLE, ...t.caption_style } : null,
  };
}

/** Shablonni mijoz tomonida tekshirish (engine ham tekshiradi). Xato kalitlari i18n'da. */
export function templateProblems(t: Template): ("tpl.err.name" | "tpl.err.shots" | "tpl.err.everyN" | "tpl.err.duration")[] {
  const out: ("tpl.err.name" | "tpl.err.shots" | "tpl.err.everyN" | "tpl.err.duration")[] = [];
  if (!t.name.uz.trim()) out.push("tpl.err.name");
  if (t.max_shot_ms < t.min_shot_ms) out.push("tpl.err.shots");
  if (t.fx.some((r) => r.trigger === "every_n" && !r.every_n)) out.push("tpl.err.everyN");
  if (t.target_duration_ms < 5000 || t.target_duration_ms > 600_000) out.push("tpl.err.duration");
  return out;
}

/** Saqlangan timeline'ning qisqa izi (preview keshi kaliti uchun). */
export function timelineRev(tl: MontageTimeline | null | undefined): string {
  if (!tl) return "";
  const s = JSON.stringify([tl.target_platform ?? "custom", tl.format, tl.video, tl.text, tl.stickers ?? [], tl.music, tl.color, tl.brand, tl.captions.enabled, tl.captions.style, tl.captions.words, tl.audio]);
  let h = 0;
  for (let i = 0; i < s.length; i++) h = (Math.imul(31, h) + s.charCodeAt(i)) | 0;
  return `${s.length}:${h}`;
}

/** Output-local freeze time: speed is already reflected by outDur/itemStarts. */
export function freezeAt(item: VideoItem, start: number, playhead: number, duration: number): VideoItem {
  const local = Math.round(playhead - start);
  if (local < 0 || local >= outDur(item)) return item;
  const dur = Math.round(clamp(duration, 100, 5000));
  return { ...item, user_edited: true, fx: [...item.fx, {
    plugin: "uz.lahza.speed.freeze", at_ms: local, dur_ms: dur, params: { dur_ms: dur }, source: "qolda",
  }] };
}

/** SRT cues remain phrases; never manufacture per-word/karaoke timing. */
export function captionCues(value: unknown): TextItem[] {
  if (!Array.isArray(value)) return [];
  return value.flatMap((cue: unknown) => {
    if (!cue || typeof cue !== "object") return [];
    const c = cue as Record<string, unknown>;
    if (typeof c.start_ms !== "number" || !Number.isInteger(c.start_ms) || c.start_ms < 0 ||
        typeof c.end_ms !== "number" || !Number.isInteger(c.end_ms) || c.end_ms <= c.start_ms || typeof c.text !== "string" || !c.text.trim()) return [];
    return [{ id: newId("caption"), start_ms: c.start_ms, end_ms: c.end_ms, text: c.text,
      kind: "title" as const, position: "lower" as const, animation: "none" as const, background: null, font_size: null }];
  });
}

/** Match the engine bounds for every numeric sticker edit, including non-finite input. */
export function normalizeSticker(item: StickerItem): StickerItem {
  const bounded = (v: number, min: number, max: number, fallback: number) => clamp(Number.isFinite(v) ? v : fallback, min, max);
  const start_ms = Math.round(bounded(item.start_ms, 0, Number.MAX_SAFE_INTEGER - 1, 0));
  return { ...item, start_ms,
    end_ms: Math.round(bounded(item.end_ms, start_ms + 1, Number.MAX_SAFE_INTEGER, start_ms + 1)),
    x: bounded(item.x, 0, 1, 0.5), y: bounded(item.y, 0, 1, 0.5),
    width: bounded(item.width, 0.02, 2, 0.3), height: bounded(item.height, 0.02, 2, 0.3),
    rotation: bounded(item.rotation, -180, 180, 0), opacity: bounded(item.opacity, 0, 1, 1),
    layer: Math.round(bounded(item.layer, 0, 1000, 0)),
  };
}

/** Uniform scaling stays within the engine box bounds; the renderer fits the image inside. */
export function scaleStickerSize(width: number, height: number, scale: number): { width: number; height: number } {
  const w = clamp(Number.isFinite(width) ? width : 0.3, 0.02, 2);
  const h = clamp(Number.isFinite(height) ? height : 0.3, 0.02, 2);
  const factor = clamp(Number.isFinite(scale) ? scale : 1, Math.max(0.02 / w, 0.02 / h), Math.min(2 / w, 2 / h));
  return { width: clamp(w * factor, 0.02, 2), height: clamp(h * factor, 0.02, 2) };
}
