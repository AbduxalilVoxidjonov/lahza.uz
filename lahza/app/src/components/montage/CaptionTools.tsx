import { useT } from "../../i18n";
import { useState } from "react";
import { NumField, TextField } from "./fields";
import { useMutation } from "@tanstack/react-query";
import { PathPicker } from "../PathPicker";
import { post } from "../../api/client";
import type { TextItem, Word } from "../../api/types";
import { useEditorT } from "../../i18n/editor-extra";
import { captionCues } from "../../lib/montage";
import { ErrorText } from "../ui";
export function CaptionImport({ onImport }: { onImport: (items: TextItem[]) => void }) {
  const t = useEditorT();
  const [path, setPath] = useState("");
  const mutation = useMutation({ mutationFn: async (path: string) => {
    const result = await post<unknown>("/v1/interop/inspect", { path });
    const normalized = result && typeof result === "object" && "normalized" in result ? result.normalized : null;
    const cues = normalized && typeof normalized === "object" && "cues" in normalized ? normalized.cues : null;
    const items = captionCues(cues);
    if (!items.length || !Array.isArray(cues) || items.length !== cues.length) throw new Error(t("noCues"));
    onImport(items);
    return true;
  } });
  return <div className="stack"><PathPicker label={t("srt")} value={path} onChange={setPath} options={{ extensions: ["srt"], filterName: "SRT" }} /><button type="button" className="btn" disabled={mutation.isPending || !path.trim()} onClick={() => mutation.mutate(path.trim())}>{mutation.isPending ? t("loading") : t("srt")}</button><ErrorText error={mutation.error} />{mutation.data === true && <span role="status">{t("imported")}</span>}</div>;
}

/** Edit actual ASR words without generating replacement timing. */
export function TranscriptWords({ words, onChange }: {
  words: Word[];
  onChange: (words: Word[]) => void;
}) {
  const t = useEditorT();
  const common = useT();
  const [page, setPage] = useState(0);
  const pages = Math.max(1, Math.ceil(words.length / 40));
  const current = Math.min(page, pages - 1);
  const update = (index: number, patch: Partial<Word>) => onChange(words.map((word, i) => i === index ? {
    ...word, ...patch, edited: true, original_text: word.original_text ?? word.text,
  } : word));
  if (!words.length) return null;
  return <details><summary>{t("transcript")} ({words.length})</summary>
    <div className="stack">
      <div className="row"><button type="button" className="btn small" disabled={current === 0} aria-label={common("mon.prevItem")} onClick={() => setPage(current - 1)}>←</button>
        <span>{current + 1} / {pages}</span><button type="button" className="btn small" disabled={current + 1 >= pages} aria-label={common("mon.nextItem")} onClick={() => setPage(current + 1)}>→</button></div>
      {words.slice(current * 40, current * 40 + 40).map((word, offset) => {
        const index = current * 40 + offset;
        return <div className="row" key={index}>
          <TextField label={`${t("captionText")} ${index + 1}`} value={word.text} onChange={text => update(index, { text })} />
          <NumField label={t("start")} suffix="ms" value={word.start_ms} min={0} max={word.end_ms - 1} onChange={start_ms => update(index, { start_ms: Math.round(start_ms) })} />
          <NumField label={t("end")} suffix="ms" value={word.end_ms} min={word.start_ms + 1} onChange={end_ms => update(index, { end_ms: Math.round(end_ms) })} />
        </div>;
      })}
    </div>
  </details>;
}
