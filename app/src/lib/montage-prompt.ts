import type { ExportProfile, MontageTimeline, TargetPlatform } from "../api/types";
import { applyRecommendedFormat } from "./export-profiles";
import { clamp, freezeAt, newId, outDur, timelineDuration } from "./montage";

export type PromptSelection = { type: "video" | "text" | "sticker"; id: string } | null;
export type PromptIssueCode = "promptUnknown" | "promptAmbiguous" | "promptBounds" | "promptSelectVideo" | "promptProfileMissing" | "promptLimit" | "promptUnchanged";
export interface PromptPlan {
  base: string;
  input: string;
  after: MontageTimeline;
  changes: { kind: "promptFormat" | "promptCaptions" | "promptSize" | "promptFreeze" | "promptCaption" | "promptColor"; detail: string }[];
  issues: { code: PromptIssueCode; command: string }[];
}
const stamp = (tl: MontageTimeline, selection: PromptSelection) => JSON.stringify([tl, selection]);
const normalize = (value: string) => value.toLowerCase().replace(/[‘’ʻʼ`]/g, "'").replace(/\s+/g, " ").trim();
const seconds = (value: string) => Math.round(Number(value.replace(",", ".")) * 1000);

/** Exact, bounded local grammar. No inference, network calls, scripts, or file operations. */
export function planMontagePrompt(input: string, tl: MontageTimeline, selection: PromptSelection, profiles: ExportProfile[]): PromptPlan {
  const plan: PromptPlan = { input, base: stamp(tl, selection), after: structuredClone(tl), changes: [], issues: [] };
  const issue = (code: PromptIssueCode, command: string) => plan.issues.push({ code, command });
  if (input.length > 2000) { issue("promptLimit", input.slice(0, 100)); return plan; }
  // Delimit only outside quotes; numeric decimal commas remain part of a time.
  const commands: string[] = [];
  let quoted = false, current = "";
  for (let i = 0; i < input.length; i++) {
    const char = input[i] ?? "";
    if (char === '\"') quoted = !quoted;
    const boundary = !quoted ? input.slice(i).match(/^\s+(?:keyin|then)\s+/i)?.[0] : undefined;
    const decimal = char === "," && /\d/.test(input[i - 1] ?? "") && /\d/.test(input[i + 1] ?? "");
    if (!quoted && (char === ";" || char === "\n" || (char === "," && !decimal) || boundary)) {
      if (current.trim()) commands.push(current.trim());
      current = "";
      if (boundary) i += boundary.length - 1;
    } else current += char;
  }
  if (current.trim()) commands.push(current.trim());
  if (commands.length > 12 || !commands.length || quoted) {
    issue("promptLimit", input.slice(0, 100)); return plan;
  }
  const seen = new Set<string>();
  const claim = (key: string, command: string) => {
    if (seen.has(key)) { issue("promptAmbiguous", command); return false; }
    seen.add(key); return true;
  };
  for (const command of commands) {
    const text = normalize(command);
    const platformNames: Record<string, TargetPlatform> = {
      "reels format": "instagram_reels", "instagram reels format": "instagram_reels", "reels formati": "instagram_reels",
      "shorts format": "youtube_shorts", "youtube shorts format": "youtube_shorts", "shorts formati": "youtube_shorts",
      "youtube format": "youtube_video", "youtube video format": "youtube_video", "youtube formati": "youtube_video",
    };
    const formatAlias = text.match(/^(?:videoni )?(reels|shorts|youtube) formatida qil$/)?.[1];
    const formatText = formatAlias ? `${formatAlias} format` : text;
    const platform = Object.hasOwn(platformNames, formatText) ? platformNames[formatText] : undefined;
    if (platform) {
      if (!claim("format", command)) continue;
      const profile = profiles.find(p => p.id === platform);
      if (!profile?.recommended_format) { issue("promptProfileMissing", command); continue; }
      plan.after = applyRecommendedFormat({ ...plan.after, target_platform: platform }, profile);
      const f = profile.recommended_format;
      plan.changes.push({ kind: "promptFormat", detail: `${profile.name} · ${f.w}×${f.h} · ${f.fps} fps` });
      continue;
    }
    const toggles: Record<string, boolean> = { "subtitrni yoq": true, "subtitrni o'chir": false, "captionni yoq": true, "captionni o'chir": false, "captions on": true, "captions off": false, "subtitr yoq": true, "subtitr o'chir": false };
    if (Object.hasOwn(toggles, text)) {
      if (!claim("captions", command)) continue;
      plan.after.captions.enabled = toggles[text] ?? false;
      plan.changes.push({ kind: "promptCaptions", detail: String(plan.after.captions.enabled) });
      continue;
    }
    const sizes: Record<string, number> = { "captionni kattalashtir": 8, "captionni kichraytir": -8, "subtitrni kattalashtir": 8, "subtitrni kichraytir": -8, "captions larger": 8, "captions smaller": -8, "subtitr kattaroq": 8, "subtitr kichikroq": -8 };
    if (Object.hasOwn(sizes, text)) {
      if (!claim("size", command)) continue;
      const before = plan.after.captions.style.font_size;
      const after = clamp(before + (sizes[text] ?? 0), 24, 200);
      if (before === after) { issue("promptBounds", command); continue; }
      plan.after.captions.style.font_size = after;
      plan.changes.push({ kind: "promptSize", detail: `${before} → ${after} px` }); continue;
    }
    // Verified builtin IDs: warm/film use the renderer's color backend and kuch parameter.
    const colors: Record<string, string> = { "warm color": "warm", "cinematic color": "film", "iliq rang": "warm", "kino rangi": "film", "rangni iliq qil": "warm", "kino tusini ber": "film" };
    if (Object.hasOwn(colors, text)) {
      if (!claim("color", command)) continue;
      const plugin = `uz.lahza.color.${colors[text]}`;
      plan.after.color = { plugin, at_ms: 0, dur_ms: null, params: { kuch: 1 }, source: "qolda" };
      plan.changes.push({ kind: "promptColor", detail: plugin }); continue;
    }
    // Time is OUTPUT-LOCAL to the selected clip, not source or montage time.
    const defaultFreeze = text.match(/^(?:tanlangan klipning )?(\d+(?:[.,]\d+)?)-soniya(?:si)?da stop-kadr qo'y$/);
    const freeze = text.match(/^freeze selected at (\d+(?:[.,]\d+)?)s for (\d+(?:[.,]\d+)?)s$/)
      ?? text.match(/^tanlangan klipning (\d+(?:[.,]\d+)?)-soniya(?:si)?da (\d+(?:[.,]\d+)?)\s*soniya stop-kadr$/) ?? (defaultFreeze ? [defaultFreeze[0], defaultFreeze[1], "1"] : null);
    if (freeze) {
      if (!claim("freeze", command)) continue;
      const index = selection?.type === "video" ? plan.after.video.findIndex(v => v.id === selection.id) : -1;
      const item = plan.after.video[index];
      if (!item) { issue("promptSelectVideo", command); continue; }
      const at = seconds(freeze[1] ?? ""), duration = seconds(freeze[2] ?? "");
      const sourceAt = item.src_in_ms + at * item.speed;
      const mediaEnd = plan.after.media[item.media]?.duration_ms;
      if (!Number.isFinite(item.src_in_ms) || !Number.isFinite(item.src_out_ms) || !Number.isFinite(item.speed) || item.speed <= 0 || !Number.isFinite(sourceAt) ||
          item.src_in_ms < 0 || item.src_out_ms <= item.src_in_ms || (mediaEnd != null && item.src_out_ms > mediaEnd) ||
          at < 0 || at >= outDur(item) || sourceAt >= item.src_out_ms || duration < 100 || duration > 5000 || at + duration > outDur(item) ||
          item.fx.some(f => f.plugin === "uz.lahza.speed.freeze" && at < f.at_ms + (f.dur_ms ?? (typeof f.params["dur_ms"] === "number" ? f.params["dur_ms"] : 1000)) && at + duration > f.at_ms)) {
        issue("promptBounds", command); continue;
      }
      plan.after.video[index] = freezeAt(item, 0, at, duration);
      plan.changes.push({ kind: "promptFreeze", detail: `${item.id} · ${at / 1000}s · ${duration / 1000}s · source ${Math.round(sourceAt)} ms` }); continue;
    }
    const caption = command.match(/^(?:caption|subtitr) "([^"\r\n]{1,300})" (\d+(?:[.,]\d+)?)s\s*[-–]\s*(\d+(?:[.,]\d+)?)s$/i);
    if (caption) {
      const start = seconds(caption[2] ?? ""), end = seconds(caption[3] ?? "");
      if (!caption[1]?.trim() || end <= start || end > timelineDuration(tl)) { issue("promptBounds", command); continue; }
      plan.after.text.push({ id: newId("caption"), text: caption[1], start_ms: start, end_ms: end, kind: "title", position: "lower", animation: "none", background: null, font_size: null });
      plan.changes.push({ kind: "promptCaption", detail: `“${caption[1]}” · ${start / 1000}s–${end / 1000}s` }); continue;
    }
    issue("promptUnknown", command);
  }
  if (!plan.issues.length && JSON.stringify(plan.after) === JSON.stringify(tl)) issue("promptUnchanged", "");
  return plan;
}

export function promptPlanIsCurrent(plan: PromptPlan, tl: MontageTimeline, selection: PromptSelection): boolean {
  return plan.base === stamp(tl, selection);
}
export function applyMontagePrompt(plan: PromptPlan, tl: MontageTimeline, selection: PromptSelection): MontageTimeline | null {
  if (plan.issues.length || !plan.changes.length || !promptPlanIsCurrent(plan, tl, selection)) return null;
  return structuredClone(plan.after);
}
