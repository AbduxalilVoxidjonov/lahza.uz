// UI'dan mustaqil yordamchilar (testlanadi).
import { EngineError } from "../../../shared/src/engine";
import type { HostPlan } from "../../../shared/src/hostplan";
import type { Clip } from "../../../shared/src/types";
import { HostError, type BuildResult } from "../host/bridge";
import type { Strings } from "../i18n";

export const AE_PROJECT_NAME = "After Effects";

/** Engine out_dir absolyut va ota papkasi mavjud bo'lishi shart: loyiha papkasi yoki uy papkasi ostida "Lahza". */
export function defaultOutDir(projectDir: string | null, home: string | null, sep: "/" | "\\" = "/"): string {
  const base = projectDir ?? home;
  if (!base) return "";
  return `${base.replace(/[/\\]+$/, "")}${sep}Lahza`;
}

export function isAbsolutePath(p: string): boolean {
  return p.startsWith("/") || /^[A-Za-z]:[/\\]/.test(p) || p.startsWith("\\\\");
}

export function errorText(e: unknown, t: Strings): string {
  if (e instanceof EngineError) {
    if (e.status === 409) return `${t.notAnalyzed}: ${e.message}`;
    return e.status ? `${t.engine} ${e.status}: ${e.message}` : e.message;
  }
  if (e instanceof HostError) return `After Effects: ${e.message}`;
  return e instanceof Error ? e.message : String(e);
}

export function clipDurationS(c: Pick<Clip, "start_ms" | "end_ms" | "cuts">): number {
  if (c.cuts && c.cuts.length) return c.cuts.reduce((s, [a, b]) => s + (b - a), 0) / 1000;
  return (c.end_ms - c.start_ms) / 1000;
}

/** "Nima o'tmadi": host ogohlantirishlari (ular plan.not_translated ni ham o'z ichiga oladi), takrorsiz. */
export function lostItems(plan: HostPlan | null, res: BuildResult | null): string[] {
  const out: string[] = [];
  const add = (s: string) => {
    if (!out.includes(s)) out.push(s);
  };
  if (res) res.warnings.forEach(add);
  else if (plan) plan.not_translated.forEach((s) => add(s));
  return out;
}

export function sortedClips(clips: Clip[]): Clip[] {
  return [...clips].sort((a, b) => b.score - a.score);
}
