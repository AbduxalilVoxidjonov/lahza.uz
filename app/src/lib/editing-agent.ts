import type { MontageTimeline } from "../api/types";
import type { PromptSelection } from "./montage-prompt";

export const object = (v: unknown): v is Record<string, unknown> => !!v && typeof v === "object" && !Array.isArray(v);
const strings = (v: unknown): v is string[] => Array.isArray(v) && v.length <= 1000 && v.every(x => typeof x === "string" && x.length <= 10000);
/** Bound JSON before checking the public contract; the UI never interprets commands. */
export function boundedPlan(v: unknown): v is Record<string, unknown> {
  let nodes = 0;
  const walk = (x: unknown, depth: number): boolean => {
    if (++nodes > 20000 || depth > 24) return false;
    if (x === null || typeof x === "boolean") return true;
    if (typeof x === "number") return Number.isFinite(x);
    if (typeof x === "string") return x.length <= 10000;
    if (Array.isArray(x)) return x.every(y => walk(y, depth + 1));
    return object(x) && Object.entries(x).every(([k, y]) => !["__proto__", "constructor", "prototype"].includes(k) && walk(y, depth + 1));
  };
  return object(v) && walk(v, 0) && JSON.stringify(v).length <= 200000;
}
export function parseStatus(v: unknown) {
  if (!object(v) || typeof v.available !== "boolean" || !(v.reason === null || typeof v.reason === "string") || !(v.model_id === null || typeof v.model_id === "string") || !strings(v.supported_operations)) throw new Error("Invalid editing-agent status response");
  return { available: v.available, reason: v.reason, model_id: v.model_id, supported_operations: v.supported_operations };
}
export function parsePlan(v: unknown) {
  if (!object(v) || !validEditPlan(v.plan) || !strings(v.changes) || !strings(v.warnings) || typeof v.model_id !== "string") throw new Error("Invalid editing-agent plan response");
  const plan: unknown = v.plan;
  return { plan, changes: v.changes, warnings: v.warnings, model_id: v.model_id };
}
export function parsePreview(v: unknown) {
  if (!object(v) || !object(v.timeline) || !strings(v.changes) || !strings(v.warnings)) throw new Error("Invalid editing-agent preview response");
  return { timeline: checkedTimeline(v.timeline), changes: v.changes, warnings: v.warnings };
}
type Check = (v: unknown) => boolean;
const str: Check = v => typeof v === "string";
const num: Check = v => typeof v === "number" && Number.isFinite(v);
const bool: Check = v => typeof v === "boolean";
const one = (...values: string[]): Check => v => typeof v === "string" && values.includes(v);
const optional = (check: Check): Check => v => v === undefined || v === null || check(v);
const list = (check: Check): Check => v => Array.isArray(v) && v.every(check);
const shape = (fields: Record<string, Check>): Check => v => object(v) && Object.entries(fields).every(([key, check]) => check(v[key]));
// Mirrors editing_agent/model.py Strict models, including extra="forbid".
const strictShape = (fields: Record<string, Check>): Check => v =>
  shape(fields)(v) && object(v) && Object.keys(v).every(key => Object.hasOwn(fields, key));
const integer = (min: number, max = Number.MAX_SAFE_INTEGER): Check => v =>
  typeof v === "number" && Number.isSafeInteger(v) && v >= min && v <= max;
const boundedString = (min: number, max: number): Check => v => typeof v === "string" && Array.from(v).length >= min && Array.from(v).length <= max;
const commandArgs: Record<string, Check> = {
  set_format: strictShape({ profile: one("instagram_reels", "youtube_shorts", "youtube_video") }),
  set_captions: strictShape({ enabled: bool, font_size: optional(integer(24, 200)) }),
  add_caption: strictShape({
    text: v => boundedString(1, 500)(v) && typeof v === "string" && !/[{}\\\x00-\x08\x0b-\x1f]/.test(v),
    start_ms: integer(0), end_ms: integer(1),
  }),
  set_color: strictShape({ preset: one("warm", "cool", "bw", "vivid", "film") }),
  freeze_clip: strictShape({ clip_id: boundedString(1, 128), at_ms: integer(0), duration_ms: integer(100, 5000) }),
};
const command: Check = v => object(v) && typeof v.tool === "string" &&
  Object.hasOwn(commandArgs, v.tool) && strictShape({ tool: one(v.tool), args: commandArgs[v.tool] ?? (() => false) })(v);
const editPlanShape = strictShape({
  schema: one("lahza.edit-plan/1"),
  base_revision: v => typeof v === "string" && v.length === 64 && /^[a-f0-9]{64}$/.test(v),
  commands: v => Array.isArray(v) && v.length <= 12 && v.every(command),
  unresolved: v => Array.isArray(v) && v.length <= 12 && v.every(boundedString(1, 500)),
});
export function validEditPlan(value: unknown): boolean { return boundedPlan(value) && editPlanShape(value); }
const position = one("upper", "middle", "lower");
const logo = one("top_left", "top_right", "bottom_left", "bottom_right");
const fx = shape({ plugin: str, at_ms: num, dur_ms: optional(num), params: object, source: one("shablon", "qolda") });
const transition = shape({ plugin: str, dur_ms: num, params: v => v === undefined || object(v) });
const style = shape({
  name: str, font_family: str, font_size: num, bold: bool, primary_color: str, highlight_color: str,
  outline_color: str, outline_width: num, shadow: num, box: bool, box_color: str, box_opacity: num,
  position, uppercase: bool, animation: one("karaoke", "pop", "none"), max_words: num, max_lines: num,
  orthography: one("official", "ascii", "new"), script: optional(one("latin", "cyrillic")), pop_scale: num, keywords: list(str), remove_fillers: bool,
  filler_words: list(str), mask_profanity: bool, profanity_words: list(str), logo_path: v => v === null || str(v), logo_position: logo, logo_opacity: num,
});
const timelineShape = shape({
  schema: one("lahza.timeline/1"), target_platform: v => v === undefined || one("instagram_reels", "youtube_shorts", "youtube_video", "custom")(v),
  format: shape({ aspect: one("9:16", "1:1", "16:9"), w: num, h: num, fps: num, audio_hz: num }),
  media: v => object(v) && Object.values(v).every(shape({ id: str, path: str, hash: optional(str), duration_ms: num, width: num, height: num, fps: num, has_audio: bool, origin: str })),
  video: list(shape({ id: str, media: str, src_in_ms: num, src_out_ms: num, reframe: one("auto", "focus", "fit_blur", "center"), crop: optional(shape({ cx: num, cy: num, zoom: num })), speed: num, volume_db: num, mute: bool, transition_in: optional(transition), fx: list(fx), role: optional(str), reason: str, user_edited: bool })),
  text: list(shape({ id: str, start_ms: num, end_ms: num, text: str, kind: one("card", "title", "hook", "cta", "lower_third"), background: optional(str), position, animation: one("none", "fade", "pop", "slide_up"), font_size: optional(num) })),
  music: list(shape({ media: str, src_in_ms: num, start_ms: num, end_ms: optional(num), gain_db: num, duck: bool, fade_in_ms: num, fade_out_ms: num })),
  stickers: v => v === undefined || list(shape({ id: str, path: str, start_ms: num, end_ms: num, x: num, y: num, width: num, height: num, rotation: num, opacity: num, layer: num, animation: one("none", "fade", "pop") }))(v),
  captions: shape({ enabled: bool, style, words: list(shape({ text: str, start_ms: num, end_ms: num, conf: v => v === null || num(v), speaker: v => v === null || str(v), edited: bool, original_text: optional(str) })) }),
  brand: shape({ logo_path: optional(str), logo_position: logo, logo_opacity: num }),
  audio: shape({ source_gain_db: num, loudnorm_lufs: optional(num), fade_ms: num }),
  color: optional(fx), provenance: shape({ template_id: optional(str), template_version: optional(str), engine: optional(str), created_at: optional(str), planner: optional(str), notes: list(str) }),
});
export function isAgentTimeline(value: unknown): value is MontageTimeline { return timelineShape(value); }
export function checkedTimeline(value: unknown): MontageTimeline {
  if (!isAgentTimeline(value)) throw new Error("Invalid editing-agent preview timeline");
  return value;
}
export type AgentContext = { prompt: string; timeline: MontageTimeline; selection: PromptSelection; mode: string };
export const contextStamp = (c: AgentContext) => JSON.stringify([c.prompt, c.timeline, c.selection, c.mode]);
export const selectedVideoId = (selection: PromptSelection) => selection?.type === "video" ? selection.id : null;
/** Revision catches change-and-revert, while stamp also checks the functional edit's draft. */
export class RequestGate {
  private stamp = "";
  private revision = 0;
  update(stamp: string) { if (stamp !== this.stamp) { this.stamp = stamp; this.revision++; } }
  capture() { return { stamp: this.stamp, revision: this.revision }; }
  current(ticket: { stamp: string; revision: number }, stamp = this.stamp) { return ticket.revision === this.revision && ticket.stamp === stamp; }
}

/** Refusals are valid plans, but must never be sent to the preview executor. */
export function planRefusal(plan: unknown): string[] {
  if (!validEditPlan(plan) || !object(plan) || !strings(plan.unresolved)) throw new Error("Invalid editing-agent plan response");
  return plan.unresolved;
}
/** Keep refused plans out of the executor and forward resolved plans unchanged. */
export async function reviewAgentPlan<T>(plan: unknown, preview: (plan: unknown) => Promise<T>): Promise<
  { kind: "refused"; unresolved: string[] } | { kind: "ready"; preview: T }
> {
  const unresolved = planRefusal(plan);
  if (unresolved.length) return { kind: "refused", unresolved };
  return { kind: "ready", preview: await preview(plan) };
}
