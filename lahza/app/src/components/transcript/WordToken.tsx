import { memo, useState } from "react";

import type { FlatWord } from "../../lib/words";
import { fmtTime } from "../ui";
import { useT } from "../../i18n";

export const LOW_CONF = 0.6;

export const isLowConf = (w: { conf: number | null }) => w.conf != null && w.conf < LOW_CONF;

interface Props {
  word: FlatWord;
  selected: boolean;
  editing: boolean;
  match: boolean;
  cut?: boolean;
  onSelect: (idx: number, extend: boolean) => void;
  onEditStart?: (idx: number) => void;
  onEditCommit?: (w: FlatWord, text: string) => void;
  onEditCancel?: () => void;
}

/** Bitta so'z: tugma (tanlash/tahrirlash) yoki tahrir maydoni. */
export const WordToken = memo(function WordToken(p: Props) {
  const t = useT();
  const { word: w } = p;
  if (p.editing && p.onEditCommit) {
    return <WordEditor word={w} onCommit={p.onEditCommit} onCancel={p.onEditCancel} />;
  }
  const cls = [
    "word",
    isLowConf(w) && "low",
    w.edited && "edited",
    p.selected && "selected",
    p.match && "match",
    p.cut && "cut",
  ]
    .filter(Boolean)
    .join(" ");
  const conf = w.conf != null ? ` · ${Math.round(w.conf * 100)}%` : "";
  return (
    <button
      type="button"
      id={`w-${w.idx}`}
      className={cls}
      aria-pressed={p.selected}
      aria-label={`${w.text}, ${fmtTime(w.start_ms)}${isLowConf(w) ? `, ${t("tr.lowConf")}` : ""}${p.cut ? `, ${t("cut.deleted")}` : ""}`}
      title={`${fmtTime(w.start_ms)}${conf}`}
      onClick={(e) => p.onSelect(w.idx, e.shiftKey)}
      onDoubleClick={() => p.onEditStart?.(w.idx)}
      onKeyDown={(e) => {
        if ((e.key === "Enter" || e.key === "F2") && p.onEditStart) {
          e.preventDefault();
          p.onEditStart(w.idx);
        }
      }}
    >
      {w.text}
    </button>
  );
});

function WordEditor({
  word,
  onCommit,
  onCancel,
}: {
  word: FlatWord;
  onCommit: (w: FlatWord, text: string) => void;
  onCancel?: () => void;
}) {
  const t = useT();
  const [text, setText] = useState(word.text);
  return (
    <input
      className="input word-input"
      autoFocus
      aria-label={t("tr.editWord")}
      value={text}
      size={Math.max(3, text.length + 1)}
      onChange={(e) => setText(e.target.value)}
      onKeyDown={(e) => {
        if (e.key === "Enter") {
          e.preventDefault();
          onCommit(word, text.trim());
        } else if (e.key === "Escape") {
          e.preventDefault();
          onCancel?.();
        }
      }}
      onBlur={() => onCancel?.()}
    />
  );
}
