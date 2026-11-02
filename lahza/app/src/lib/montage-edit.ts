import type { MontageTimeline } from "../api/types";
import { itemStarts, normalizeVideo, outDur } from "./montage";

export type EditFailure = "splitBounds" | "splitTransition" | "splitFx" | "rippleTransition";
export type EditResult = { timeline: MontageTimeline; selectedId?: string } | { error: EditFailure };

export function splitVideo(tl: MontageTimeline, id: string, at: number, rightId: string): EditResult {
  const i = tl.video.findIndex(v => v.id === id);
  const item = tl.video[i];
  if (!item || !Number.isFinite(item.src_in_ms) || !Number.isFinite(item.src_out_ms) || !Number.isFinite(at) || !Number.isFinite(item.speed) || item.speed <= 0) return { error: "splitBounds" };
  const local = at - (itemStarts(tl)[i] ?? 0);
  const duration = outDur(item);
  const source = Math.round(item.src_in_ms + local * item.speed);
  if (local <= 0 || local >= duration || source <= item.src_in_ms || source >= item.src_out_ms ||
      item.src_in_ms < 0 || item.src_out_ms > (tl.media[item.media]?.duration_ms ?? Infinity)) return { error: "splitBounds" };
  const prev = tl.video[i - 1];
  const next = tl.video[i + 1];
  const incoming = prev && item.transition_in ? Math.min(item.transition_in.dur_ms, duration, outDur(prev)) : 0;
  const outgoing = next?.transition_in ? Math.min(next.transition_in.dur_ms, duration, outDur(next)) : 0;
  const leftDur = outDur({ ...item, src_out_ms: source });
  const rightDur = outDur({ ...item, src_in_ms: source });
  if (local <= incoming || local >= duration - outgoing || leftDur < incoming || rightDur < outgoing) return { error: "splitTransition" };
  // Even an FX before the cut may depend on the full clip duration or source origin.
  if (item.fx.length) return { error: "splitFx" };
  // Integer source milliseconds cannot always represent a duration-preserving cut.
  if (leftDur < 1 || rightDur < 1 || leftDur + rightDur !== duration) return { error: "splitBounds" };
  const video = [...tl.video];
  video.splice(i, 1, { ...item, src_out_ms: source, user_edited: true },
    { ...structuredClone(item), id: rightId, src_in_ms: source, transition_in: null, user_edited: true });
  return { timeline: { ...tl, video }, selectedId: rightId };
}

/** Collapse the deleted interval; remove fully consumed overlays, trim crossing ones. */
export function remapTimed<T extends { start_ms: number; end_ms: number }>(items: T[], start: number, end: number): T[] {
  const map = (time: number) => time <= start ? time : time < end ? start : time - (end - start);
  return items.flatMap(item => {
    const start_ms = map(item.start_ms), end_ms = map(item.end_ms);
    return end_ms > start_ms ? [{ ...item, start_ms, end_ms }] : [];
  });
}

export function rippleDelete(tl: MontageTimeline, id: string): EditResult {
  const i = tl.video.findIndex(v => v.id === id), item = tl.video[i];
  if (!item) return { error: "splitBounds" };
  // A transition overlaps surviving material; there is no single removable interval.
  if ((i > 0 && item.transition_in?.dur_ms) || tl.video[i + 1]?.transition_in?.dur_ms) return { error: "rippleTransition" };
  const start = itemStarts(tl)[i] ?? 0, end = start + outDur(item);
  return { timeline: { ...tl, video: normalizeVideo(tl.video.filter(v => v.id !== id)),
    text: remapTimed(tl.text, start, end), stickers: remapTimed(tl.stickers ?? [], start, end),
    captions: { ...tl.captions, words: remapTimed(tl.captions.words, start, end) } } };
}

export interface History<T> { past: T[]; present: T; future: T[] }
export function record<T>(history: History<T>, present: T): History<T> {
  if (JSON.stringify(history.present) === JSON.stringify(present)) return history;
  return { past: [...history.past.slice(-99), history.present], present, future: [] };
}
export function travel<T>(history: History<T>, direction: "undo" | "redo"): History<T> {
  if (direction === "undo") {
    if (!history.past.length) return history;
    return { past: history.past.slice(0, -1), present: history.past[history.past.length - 1] as T, future: [history.present, ...history.future] };
  }
  if (!history.future.length) return history;
  return { past: [...history.past, history.present], present: history.future[0] as T, future: history.future.slice(1) };
}

export interface SyncedHistory<T> {
  history: History<T>;
  baseline: T;
  observed: string;
  saving: boolean;
}
const snapshot = (value: unknown) => JSON.stringify(value);
export function syncSaved<T>(state: SyncedHistory<T>, incoming: T): SyncedHistory<T> {
  const observed = snapshot(incoming);
  if (observed === state.observed) return state;
  // Consume query responses during a save without letting an old response replace work.
  if (state.saving) return { ...state, observed };
  if (snapshot(state.history.present) !== snapshot(state.baseline)) return state;
  if (observed === snapshot(state.baseline)) return { ...state, observed };
  return { history: { past: [], present: incoming, future: [] }, baseline: incoming, observed, saving: false };
}
export function acknowledgeSave<T>(state: SyncedHistory<T>, submitted: T, saved: T): SyncedHistory<T> {
  // The API returns a normalized timeline. Adopt it only if no newer edit was made.
  const history = snapshot(state.history.present) === snapshot(submitted)
    ? { ...state.history, present: saved } : state.history;
  return { ...state, history, baseline: saved, saving: false };
}
