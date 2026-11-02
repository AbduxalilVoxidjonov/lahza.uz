import type { Aspect, ExportProfile, MontageOverrides, MontageTimeline, TargetPlatform } from "../api/types";
import { timelineDuration } from "./montage";

export type ProfileIssue = { severity: "error" | "warning"; code: "durationLimit" | "shapeLimit" | "formatAdvice" | "fpsAdvice" | "durationAdvice" | "stickerAdvice"; value: string };
export function applyRecommendedFormat(tl: MontageTimeline, profile: ExportProfile): MontageTimeline {
  return profile.recommended_format ? { ...tl, format: { ...tl.format, ...profile.recommended_format } } : tl;
}
export function profileIssues(tl: MontageTimeline, p: ExportProfile): ProfileIssue[] {
  const issues: ProfileIssue[] = [];
  const add = (severity: ProfileIssue["severity"], code: ProfileIssue["code"], value = "") => issues.push({ severity, code, value });
  const duration = timelineDuration(tl) / 1000;
  if (p.restrictions.max_duration_s != null && duration > p.restrictions.max_duration_s) add("error", "durationLimit", String(p.restrictions.max_duration_s));
  if (p.restrictions.square_or_vertical && tl.format.w > tl.format.h) add("error", "shapeLimit");
  const f = p.recommended_format;
  if (f && (f.w !== tl.format.w || f.h !== tl.format.h)) add("warning", "formatAdvice", `${f.w}×${f.h}`);
  if (f && f.fps !== tl.format.fps) add("warning", "fpsAdvice", `${f.fps} fps · ${p.recommendations.fps_note}`);
  if (p.recommendations.max_duration_s != null && duration > p.recommendations.max_duration_s) add("warning", "durationAdvice", String(p.recommendations.max_duration_s));
  for (const s of tl.stickers ?? []) {
    const angle = s.rotation * Math.PI / 180;
    const w = s.width * tl.format.w, h = s.height * tl.format.h;
    const rx = (Math.abs(w * Math.cos(angle)) + Math.abs(h * Math.sin(angle))) / 2 / tl.format.w;
    const ry = (Math.abs(w * Math.sin(angle)) + Math.abs(h * Math.cos(angle))) / 2 / tl.format.h;
    const safe = p.safe_zone;
    if (s.x - rx < safe.side_pct || s.x + rx > 1 - safe.side_pct || s.y - ry < safe.top_pct || s.y + ry > 1 - safe.bottom_pct) add("warning", "stickerAdvice", s.id);
  }
  return issues;
}

/** An omitted aspect lets the engine select the profile default (custom uses template). */
export function platformCreationOverrides(platform: TargetPlatform = "custom", aspect: Aspect | "" = ""): MontageOverrides {
  return { target_platform: platform, ...(aspect ? { aspect } : {}) };
}
