// Montaj (Lahza Timeline) hisob-kitoblari - engine `montage/model.py` bilan bir xil qoidalar.
import type {
  FxManifest,
  FxParamSpec,
  LocalText,
  MontageTimeline,
  Template,
  TemplateCategory,
  VideoItem,
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
  const s = JSON.stringify([tl.format, tl.video, tl.text, tl.music, tl.color, tl.brand, tl.captions.enabled, tl.captions.style, tl.audio]);
  let h = 0;
  for (let i = 0; i < s.length; i++) h = (Math.imul(31, h) + s.charCodeAt(i)) | 0;
  return `${s.length}:${h}`;
}
