// Engine oqimi (UI'dan mustaqil, testlanadi): tahlil -> lahzalar -> host-reja -> host'da qurish; montaj.

import type { EngineClient } from "@shared/engine";
import type { HostPlan } from "@shared/hostplan";
import type { Clip, Job, Template } from "@shared/types";
import type { BuildResult, BuildStep, HostAdapter } from "./host/adapter";

export const ENGINE_PROJECT = "Premiere";

export type Aspect = "9:16" | "1:1" | "16:9";
export type Orthography = "official" | "ascii" | "new";

export interface FlowDeps {
  client: EngineClient;
  adapter: HostAdapter;
  /** `name` uchun absolyut chiqish papkasi (engine `out_dir` absolyut bo'lishini talab qiladi). */
  outDir: (name: string) => string;
  /** Ota papkani yaratish (engine faqat oxirgi papkani yaratadi). */
  prepareOutDir?: (dir: string) => Promise<void>;
  pollMs?: number;
}

export function baseName(path: string): string {
  const parts = path.split(/[\\/]/);
  return parts[parts.length - 1] || path;
}

export async function analyzeMedia(
  deps: FlowDeps,
  path: string,
  onJob?: (j: Job) => void,
  signal?: AbortSignal,
): Promise<{ episodeId: string; clips: Clip[] }> {
  const projectId = await deps.client.ensureProject(ENGINE_PROJECT);
  const { episode_id, job } = await deps.client.importMedia(projectId, path, { title: baseName(path) });
  onJob?.(job);
  await deps.client.waitJob(job.id, onJob, deps.pollMs ?? 1000, signal);
  return { episodeId: episode_id, clips: await loadClips(deps, episode_id) };
}

export async function loadClips(deps: FlowDeps, episodeId: string): Promise<Clip[]> {
  const clips = await deps.client.clips(episodeId);
  return [...clips].sort((a, b) => b.score - a.score);
}

async function outDirFor(deps: FlowDeps, name: string): Promise<string> {
  const dir = deps.outDir(name);
  await deps.prepareOutDir?.(dir);
  return dir;
}

export async function reelPlan(
  deps: FlowDeps,
  episodeId: string,
  clipId: string,
  opts: { aspect: Aspect; orthography: Orthography },
): Promise<HostPlan> {
  const out_dir = await outDirFor(deps, `${episodeId}_${clipId}`);
  return deps.client.clipHostPlan(episodeId, clipId, { out_dir, aspect: opts.aspect, orthography: opts.orthography });
}

export async function makeReel(
  deps: FlowDeps,
  episodeId: string,
  clipId: string,
  opts: { aspect: Aspect; orthography: Orthography },
  onStep?: (s: BuildStep) => void,
): Promise<{ plan: HostPlan; result: BuildResult }> {
  const plan = await reelPlan(deps, episodeId, clipId, opts);
  return { plan, result: await deps.adapter.buildFromPlan(plan, onStep) };
}

export async function makeMontage(
  deps: FlowDeps,
  template: Template,
  paths: string[],
  onJob?: (j: Job) => void,
  onStep?: (s: BuildStep) => void,
  signal?: AbortSignal,
): Promise<{ plan: HostPlan; result: BuildResult }> {
  if (!paths.length) throw new Error("Montaj uchun kamida bitta klip tanlang");
  const { montage_id, job } = await deps.client.createMontage({
    template_id: template.id,
    name: `${template.name.uz} · Premiere`,
    sources: paths.map((path) => ({ kind: "file" as const, path })),
  });
  onJob?.(job);
  await deps.client.waitJob(job.id, onJob, deps.pollMs ?? 1000, signal);
  const plan = await deps.client.montageHostPlan(montage_id, await outDirFor(deps, `montage_${montage_id}`));
  return { plan, result: await deps.adapter.buildFromPlan(plan, onStep) };
}
