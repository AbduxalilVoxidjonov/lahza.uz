import type { ComponentView } from "../../shared/content-download";

export type ComponentRowState =
  | { kind: "installed" }
  | { kind: "pending_upstream" }
  | { kind: "unavailable" }
  | { kind: "downloading"; phase: "resuming" | "downloading" | "verifying" | "extracting"; percent: number }
  | { kind: "queued" }
  | { kind: "error"; message: string }
  | { kind: "offline" }
  | { kind: "idle" };

/** What one Components row shows. Order matters: an unpinned item is never
 *  actionable, a live queue entry beats disk state, and being offline only
 *  matters when nothing is already moving (a running transfer proves a link). */
export function componentRowState(c: ComponentView, online: boolean): ComponentRowState {
  if (c.pendingReason) return { kind: "pending_upstream" };
  if (c.status === "installed") return { kind: "installed" };
  if (c.status === "unavailable") return { kind: "unavailable" };
  const q = c.queue;
  if (q?.state === "error") return { kind: "error", message: q.error ?? "" };
  if (q?.state === "queued") return { kind: "queued" };
  if (q) {
    const percent = q.totalBytes > 0 ? Math.min(100, Math.floor((q.receivedBytes / q.totalBytes) * 100)) : 0;
    const phase = q.state === "resuming" ? "resuming" : q.state === "verifying" ? "verifying" : q.state === "extracting" ? "extracting" : "downloading";
    return { kind: "downloading", phase, percent };
  }
  return online ? { kind: "idle" } : { kind: "offline" };
}
