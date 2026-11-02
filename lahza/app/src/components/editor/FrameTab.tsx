import { useEffect, useState } from "react";

import { useKeyframes, useSaveKeyframes } from "../../api/hooks";
import type { Clip, Keyframe, Lane, Layout } from "../../api/types";
import { useT } from "../../i18n";
import { outToSrc, srcToOut } from "../../lib/words";
import { Empty, ErrorText, fmtTimePrecise, QueryState } from "../ui";

export const LAYOUTS: Layout[] = ["focus", "split", "fit_blur", "manual"];

/** cx/cy engine'dan `null` kelishi mumkin (avtomatik markaz). */
const fmtCoord = (v: number | null) => (v == null ? "—" : v.toFixed(2));

/** Kadr (M3-RF-4): qo'lda layout va kalit kadrlar; bo'sh ro'yxat = avtomatik reframe. */
export function FrameTab({ clip, episodeId, now, onSeek }: { clip: Clip; episodeId: string; now: number; onSeek: (ms: number) => void }) {
  const q = useKeyframes(episodeId, clip.id);
  if (!q.data) return <QueryState query={q} />;
  return <KeyframeEditor key={clip.id} clip={clip} episodeId={episodeId} initial={q.data} now={now} onSeek={onSeek} />;
}

function KeyframeEditor({
  clip,
  episodeId,
  initial,
  now,
  onSeek,
}: {
  clip: Clip;
  episodeId: string;
  initial: Keyframe[];
  now: number;
  onSeek: (ms: number) => void;
}) {
  const t = useT();
  const save = useSaveKeyframes(episodeId, clip.id);
  const [list, setList] = useState<Keyframe[]>(() => [...initial].sort((a, b) => a.t_ms - b.t_ms));
  const [dirty, setDirty] = useState(false);
  const [draft, setDraft] = useState<{ layout: Layout; cx: number; cy: number; zoom: number; lane: Lane }>({
    layout: initial[0]?.layout ?? "focus",
    cx: 0.5,
    cy: 0.5,
    zoom: 1,
    lane: "a",
  });

  // Engine'dan yangi ma'lumot kelsa va qo'lda o'zgarish bo'lmasa - sinxronlash.
  useEffect(() => {
    if (!dirty) setList([...initial].sort((a, b) => a.t_ms - b.t_ms));
  }, [initial, dirty]);

  const tOut = srcToOut(clip, now);
  const update = (next: Keyframe[]) => {
    setList(next.sort((a, b) => a.t_ms - b.t_ms));
    setDirty(true);
  };
  // Engine bir yo'lakda bir xil t_ms ni rad etadi - o'sha joydagi eskisini almashtiramiz.
  const add = () =>
    update([...list.filter((k) => !(k.t_ms === tOut && k.lane === draft.lane)), { ...draft, t_ms: tOut, source: "qolda" }]);

  const slider = (key: "cx" | "cy" | "zoom", min: number, max: number, step: number) => (
    <label className="field" style={{ flex: 1, minWidth: 120 }}>
      {t(`frame.${key}`)} <span className="mono">{draft[key].toFixed(2)}</span>
      <input type="range" min={min} max={max} step={step} value={draft[key]}
             onChange={(e) => setDraft({ ...draft, [key]: Number(e.target.value) })} />
    </label>
  );

  return (
    <div className="stack">
      <p className="muted">{t("frame.hint")}</p>
      <div className="row">
        <label className="field" style={{ flex: 1 }}>
          {t("ed.layout")}
          <select className="select" value={draft.layout} onChange={(e) => setDraft({ ...draft, layout: e.target.value as Layout })}>
            {LAYOUTS.map((l) => (
              <option key={l} value={l}>{t(`layout.${l}`)}</option>
            ))}
          </select>
        </label>
        {draft.layout === "split" && (
          <label className="field" style={{ width: 120 }}>
            {t("frame.lane")}
            <select className="select" value={draft.lane} onChange={(e) => setDraft({ ...draft, lane: e.target.value as Lane })}>
              <option value="a">{t("frame.laneTop")}</option>
              <option value="b">{t("frame.laneBottom")}</option>
            </select>
          </label>
        )}
      </div>
      <div className="row">
        {slider("cx", 0, 1, 0.01)}
        {slider("cy", 0, 1, 0.01)}
        {slider("zoom", 0.5, 4, 0.05)}
      </div>
      <div className="row">
        <button type="button" className="btn small" onClick={add}>
          {t("frame.add", { time: fmtTimePrecise(tOut) })}
        </button>
        <button type="button" className="btn small ghost" disabled={!list.length} onClick={() => update([])}>
          {t("frame.clear")}
        </button>
      </div>

      {list.length === 0 ? (
        <Empty>{t("frame.empty")}</Empty>
      ) : (
        <table className="table">
          <thead>
            <tr>
              <th>{t("frame.time")}</th>
              <th>{t("ed.layout")}</th>
              <th>cx / cy / zoom</th>
              <th><span className="sr-only">{t("common.actions")}</span></th>
            </tr>
          </thead>
          <tbody>
            {list.map((k) => (
              <tr key={`${k.lane}-${k.t_ms}`}>
                <td>
                  <button type="button" className="btn small ghost mono" onClick={() => onSeek(outToSrc(clip, k.t_ms))}>
                    {fmtTimePrecise(k.t_ms)}
                  </button>
                </td>
                <td>{t(`layout.${k.layout}`)}{k.layout === "split" ? ` · ${k.lane === "a" ? t("frame.laneTop") : t("frame.laneBottom")}` : ""}</td>
                <td className="mono">{fmtCoord(k.cx)} / {fmtCoord(k.cy)} / {k.zoom.toFixed(2)}</td>
                <td>
                  <button type="button" className="btn small ghost" aria-label={t("frame.remove", { time: fmtTimePrecise(k.t_ms) })}
                          onClick={() => update(list.filter((x) => x !== k))}>
                    ✕
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <div className="row">
        <button
          type="button"
          className="btn primary"
          disabled={!dirty || save.isPending}
          onClick={() => save.mutate(list, { onSuccess: () => setDirty(false) })}
        >
          {t("common.save")}
        </button>
        {dirty && <span className="muted">{t("common.unsaved")}</span>}
        <ErrorText error={save.error} />
      </div>
    </div>
  );
}
