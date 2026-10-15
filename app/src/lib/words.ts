// So'z/kesim hisob-kitoblari: transkript, matn orqali montaj va timeline uchun umumiy.
import type { Clip, Sentence, Word } from "../api/types";

export type Range = [number, number];

export interface FlatWord extends Word {
  sentenceId: number;
  /** Gap ichidagi tartib raqami (PATCH words uchun). */
  ord: number;
  /** Butun epizod bo'yicha indeks. */
  idx: number;
}

export function flattenWords(sentences: Sentence[]): FlatWord[] {
  const out: FlatWord[] = [];
  for (const s of sentences) {
    s.words.forEach((w, ord) => out.push({ ...w, sentenceId: s.id, ord, idx: out.length }));
  }
  return out;
}

export function wordsInRange(words: FlatWord[], startMs: number, endMs: number): FlatWord[] {
  return words.filter((w) => w.end_ms > startMs && w.start_ms < endMs);
}

/** Eng yaqin so'z boshi (trim boshlanishi uchun). */
export function snapStart(words: readonly Word[], ms: number): number {
  let best = ms;
  let dist = Infinity;
  for (const w of words) {
    const d = Math.abs(w.start_ms - ms);
    if (d < dist) [best, dist] = [w.start_ms, d];
  }
  return best;
}

/** Eng yaqin so'z oxiri (trim tugashi uchun). */
export function snapEnd(words: readonly Word[], ms: number): number {
  let best = ms;
  let dist = Infinity;
  for (const w of words) {
    const d = Math.abs(w.end_ms - ms);
    if (d < dist) [best, dist] = [w.end_ms, d];
  }
  return best;
}

/** Oraliqlarni saralab, ustma-ust tushganlarini birlashtiradi. */
export function normalizeRanges(ranges: readonly Range[]): Range[] {
  const sorted = ranges.filter(([a, b]) => b > a).map(([a, b]) => [a, b] as Range).sort((x, y) => x[0] - y[0]);
  const out: Range[] = [];
  for (const r of sorted) {
    const last = out[out.length - 1];
    if (last && r[0] <= last[1]) last[1] = Math.max(last[1], r[1]);
    else out.push(r);
  }
  return out;
}

export const addCut = (cuts: readonly Range[], r: Range): Range[] => normalizeRanges([...cuts, r]);

/** Kesimlardan oraliqni olib tashlaydi (qayta tiklash). */
export function removeCut(cuts: readonly Range[], [a, b]: Range): Range[] {
  const out: Range[] = [];
  for (const [s, e] of cuts) {
    if (e <= a || s >= b) out.push([s, e]);
    else {
      if (s < a) out.push([s, a]);
      if (e > b) out.push([b, e]);
    }
  }
  return normalizeRanges(out);
}

/** So'z o'rtasi kesim ichida bo'lsa - so'z o'chirilgan hisoblanadi. */
export function isCutWord(cuts: readonly Range[], w: Word): boolean {
  const mid = (w.start_ms + w.end_ms) / 2;
  return cuts.some(([s, e]) => mid >= s && mid < e);
}

/** Manba vaqti kesim ichida bo'lsa - kesim oxiri, aks holda o'zi. */
export function skipCuts(cuts: readonly Range[], ms: number): number {
  for (const [s, e] of cuts) if (ms >= s && ms < e) return e;
  return ms;
}

/** Manba vaqti -> chiqish (klip ichidagi, kesimlardan keyingi) vaqti. */
export function srcToOut(clip: Pick<Clip, "start_ms" | "cuts">, ms: number): number {
  let out = ms - clip.start_ms;
  for (const [s, e] of clip.cuts) {
    if (e <= ms) out -= e - s;
    else if (s < ms) out -= ms - s;
  }
  return Math.max(0, Math.round(out));
}

/** Chiqish vaqti -> manba vaqti. */
export function outToSrc(clip: Pick<Clip, "start_ms" | "cuts">, out: number): number {
  let ms = clip.start_ms + out;
  for (const [s, e] of normalizeRanges(clip.cuts)) {
    if (s <= ms) ms += e - s;
  }
  return ms;
}

export function outDuration(clip: Pick<Clip, "start_ms" | "end_ms" | "cuts">): number {
  return srcToOut(clip, clip.end_ms);
}
