import { useCallback, useState } from "react";

import { usePutCuts } from "../../api/hooks";
import type { Clip } from "../../api/types";
import { useT } from "../../i18n";
import { addCut, isCutWord, removeCut, type FlatWord } from "../../lib/words";
import { WordToken } from "../transcript/WordToken";
import { ErrorText, fmtTime } from "../ui";

/**
 * Matn orqali montaj (M2-APP-5): so'z/gapni belgilab o'chirish -> klip kesimlari (jump-cut);
 * o'chirilganini belgilab qayta tiklash.
 */
export function TextTab({
  clip,
  episodeId,
  words,
  onSeek,
}: {
  clip: Clip;
  episodeId: string;
  words: FlatWord[];
  onSeek: (ms: number) => void;
}) {
  const t = useT();
  const putCuts = usePutCuts(episodeId);
  const [anchor, setAnchor] = useState<number | null>(null);
  const [focus, setFocus] = useState<number | null>(null);

  const sel: readonly [number, number] | null =
    anchor == null || focus == null ? null : [Math.min(anchor, focus), Math.max(anchor, focus)];
  const selected = sel ? words.filter((w) => w.idx >= sel[0] && w.idx <= sel[1]) : [];
  const first = selected[0];
  const last = selected[selected.length - 1];
  const anyCut = selected.some((w) => isCutWord(clip.cuts, w));
  const anyKept = selected.some((w) => !isCutWord(clip.cuts, w));

  const onSelect = useCallback(
    (idx: number, extend: boolean) => {
      setFocus(idx);
      setAnchor((a) => (extend && a != null ? a : idx));
      const w = words.find((x) => x.idx === idx);
      if (w && !extend) onSeek(w.start_ms);
    },
    [words, onSeek],
  );

  const selectSentence = (sid: number) => {
    const sw = words.filter((w) => w.sentenceId === sid);
    const a = sw[0];
    const b = sw[sw.length - 1];
    if (!a || !b) return;
    setAnchor(a.idx);
    setFocus(b.idx);
  };

  const apply = (cuts: [number, number][]) => putCuts.mutate({ clipId: clip.id, cuts });
  const range = (): [number, number] | null => (first && last ? [first.start_ms, last.end_ms] : null);

  const groups: FlatWord[][] = [];
  for (const w of words) {
    const g = groups[groups.length - 1];
    if (g && g[0]?.sentenceId === w.sentenceId) g.push(w);
    else groups.push([w]);
  }

  return (
    <div className="stack">
      <div className="row toolbar" role="toolbar" aria-label={t("cut.toolbar")}>
        <button
          type="button"
          className="btn small bad"
          disabled={!anyKept || putCuts.isPending}
          onClick={() => {
            const r = range();
            if (r) apply(addCut(clip.cuts, r));
          }}
        >
          {t("cut.delete")}
        </button>
        <button
          type="button"
          className="btn small"
          disabled={!anyCut || putCuts.isPending}
          onClick={() => {
            const r = range();
            if (r) apply(removeCut(clip.cuts, r));
          }}
        >
          {t("cut.restore")}
        </button>
        <button type="button" className="btn small ghost" disabled={!clip.cuts.length || putCuts.isPending} onClick={() => apply([])}>
          {t("cut.restoreAll")}
        </button>
        <span className="muted">
          {selected.length ? t("tr.selected", { n: selected.length }) : t("cut.hint")}
        </span>
        <ErrorText error={putCuts.error} />
      </div>
      <div className="clip-text" aria-busy={putCuts.isPending}>
        {groups.map((g) => {
          const s0 = g[0];
          if (!s0) return null;
          return (
            <p key={s0.sentenceId} className="sentence">
              <button type="button" className="sentence-handle mono" onClick={() => selectSentence(s0.sentenceId)}
                      aria-label={t("cut.selectSentence", { time: fmtTime(s0.start_ms) })}>
                {fmtTime(s0.start_ms)}
              </button>
              <span className="words">
                {g.map((w) => (
                  <WordToken
                    key={w.idx}
                    word={w}
                    selected={!!sel && w.idx >= sel[0] && w.idx <= sel[1]}
                    editing={false}
                    match={false}
                    cut={isCutWord(clip.cuts, w)}
                    onSelect={onSelect}
                  />
                ))}
              </span>
            </p>
          );
        })}
      </div>
    </div>
  );
}
