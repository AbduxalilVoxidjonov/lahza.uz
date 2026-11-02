// Partiyaviy tahlil navbati (PRO-5): UI'dagi sof mantiq (komponentsiz, node testlari uchun).
import type { Job, JobStatus, QueueItem } from "../api/types";

/** Brauzer rejimida yo'llar matn maydoniga qatorma-qator yoziladi: bo'sh qatorlar, qo'shtirnoq va
 * takrorlar olib tashlanadi, tartib saqlanadi. */
export function parsePathList(text: string): string[] {
  const out: string[] = [];
  for (const raw of text.split(/\r?\n/)) {
    const p = raw.trim().replace(/^["']|["']$/g, "").trim();
    if (p && !out.includes(p)) out.push(p);
  }
  return out;
}

/** Yangi fayllarni mavjud tanlovga qo'shadi (takrorlarsiz). */
export const mergePaths = (current: string[], added: string[]): string[] =>
  [...current, ...added.filter((p, i) => !current.includes(p) && added.indexOf(p) === i)];

export const isActive = (s: JobStatus) => s === "queued" || s === "running";
export const canCancel = isActive;
export const canRemove = (s: JobStatus) => s !== "running";
export const canRetry = (s: JobStatus) => s === "failed" || s === "cancelled";

/** Kutayotgan elementni siljitish: `delta` -1 (yuqoriga), +1 (pastga) yoki "top".
 * Engine'ga yuboriladigan `ids` (kutayotganlar yangi tartibda) yoki o'zgarish bo'lmasa null. */
export function moveQueued(items: QueueItem[], id: string, delta: -1 | 1 | "top"): string[] | null {
  const ids = items
    .filter((x) => x.status === "queued")
    .sort((a, b) => a.position - b.position)
    .map((x) => x.id);
  const i = ids.indexOf(id);
  if (i < 0) return null;
  const j = delta === "top" ? 0 : i + delta;
  if (j < 0 || j >= ids.length || j === i) return null;
  ids.splice(i, 1);
  ids.splice(j, 0, id);
  return ids;
}

/** WebSocket orqali kelgan vazifa holati engine ro'yxatidagidan yangiroq bo'lishi mumkin. */
export function withLiveJob(item: QueueItem, job: Job | undefined): QueueItem {
  if (!job || item.status !== "running" || job.id !== item.job_id) return item;
  return { ...item, progress: job.progress, stage: job.stage };
}

export interface QueueSummary {
  total: number;
  queued: number;
  running: number;
  done: number;
  failed: number;
  cancelled: number;
  /** Tugaganlar ulushi (0..1); ishlayotgan elementning progressi ham hisobga olinadi. */
  progress: number;
}

export function summarize(items: QueueItem[]): QueueSummary {
  const s: QueueSummary = { total: items.length, queued: 0, running: 0, done: 0, failed: 0, cancelled: 0, progress: 0 };
  let acc = 0;
  for (const x of items) {
    s[x.status] += 1;
    acc += x.status === "running" ? x.progress : x.status === "queued" ? 0 : 1;
  }
  s.progress = items.length ? acc / items.length : 0;
  return s;
}
