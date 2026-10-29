import { useState } from "react";

import { useAddToQueue } from "../../api/queue";
import { fmt, youtubeDictionaries } from "../../i18n/youtube";
import {
  fmtDuration, initialSelection, queueUrls, selectableIds, toggleAll, toggleOne, totalDuration, type ResolvedUrl,
} from "../../lib/youtube-import";
import { useSettings } from "../../store/settings";
import { ErrorText } from "../ui";

/**
 * YT-1: playlist/kanal ro'yxati - checkbox, "hammasini tanlash", davomiylik. Tanlanganlar partiyaviy
 * navbatga URL elementi sifatida qo'shiladi (har biri: yuklash -> import -> tahlil). Rozilik ro'yxat
 * ochilishidan oldin olingan (`consent: true`). Rasmlar (thumbnail) ko'rsatilmaydi - UI tarmoqqa chiqmaydi.
 */
export function YoutubePlaylistPicker({ data, projectId, focus, lite, onDone }: {
  data: ResolvedUrl; projectId: string; focus: string; lite: boolean; onDone: (n: number) => void;
}) {
  const locale = useSettings((s) => s.locale);
  const y = youtubeDictionaries[locale];
  const add = useAddToQueue();
  const [selected, setSelected] = useState<Set<string>>(() => initialSelection(data.entries));
  const ids = selectableIds(data.entries);
  const allOn = ids.length > 0 && ids.every((id) => selected.has(id));
  const urls = queueUrls(data.entries, selected);
  const skipLabel = (s: string) => y[`skip_${s}` as keyof typeof y] ?? s;

  const submit = () =>
    add.mutate(
      { project_id: projectId, urls, consent: true, focus: focus.trim() || undefined, force_lite: lite },
      { onSuccess: (items) => onDone(items.length) },
    );

  return (
    <div className="stack" style={{ gap: 6 }}>
      <strong>{fmt(y.listTitle, { title: data.title ?? "YouTube", n: data.entries.length })}</strong>
      {data.truncated && <div className="notice warn" role="status">{y.truncated}</div>}
      <label className="row">
        <input type="checkbox" checked={allOn} disabled={!ids.length}
               onChange={() => setSelected((cur) => toggleAll(data.entries, cur))} />
        {y.selectAll}
      </label>
      <ul className="plain-list stack" style={{ gap: 2, maxHeight: 320, overflowY: "auto", margin: 0 }} aria-label={y.url}>
        {data.entries.map((e) => (
          <li key={e.id}>
            <label className={`row${e.skip ? " muted" : ""}`} style={{ justifyContent: "space-between", gap: 8 }}>
              <span className="row" style={{ gap: 8, minWidth: 0 }}>
                <input type="checkbox" checked={!e.skip && selected.has(e.id)} disabled={!!e.skip}
                       onChange={() => setSelected((cur) => toggleOne(data.entries, cur, e.id))} />
                <span style={{ overflow: "hidden", textOverflow: "ellipsis" }}>{e.title ?? y.untitled}</span>
                {e.skip && <span className="badge warn">{skipLabel(e.skip)}</span>}
              </span>
              <span className="mono muted">{fmtDuration(e.duration_s)}</span>
            </label>
          </li>
        ))}
      </ul>
      <div className="row" style={{ justifyContent: "space-between" }}>
        <span className="muted" role="status">
          {fmt(y.selectedSummary, { n: urls.length, dur: fmtDuration(totalDuration(data.entries, selected)) })}
        </span>
        <button className="btn primary" type="button" disabled={!urls.length || add.isPending} onClick={submit}>
          {fmt(y.addToQueue, { n: urls.length })}
        </button>
      </div>
      <ErrorText error={add.error} />
    </div>
  );
}
