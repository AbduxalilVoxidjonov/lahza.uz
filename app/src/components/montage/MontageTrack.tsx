// Montaj timeline'i: video elementlari, matn va musiqa qatlamlari, playhead.
import { memo, useRef, useState, type MouseEvent } from "react";

import { useFx, useObjectUrl, useSourceThumb } from "../../api/hooks";
import type { MontageTimeline, VideoItem } from "../../api/types";
import { useT } from "../../i18n";
import { useInView } from "../../lib/useInView";
import { fxName, itemStarts, outDur, timelineDuration } from "../../lib/montage";
import { useSettings } from "../../store/settings";
import { fmtTime, fmtTimePrecise } from "../ui";

export type Sel = { type: "video" | "text"; id: string } | null;

const pct = (ms: number, total: number) => `${(Math.max(0, ms) / Math.max(1, total)) * 100}%`;

const VideoBlock = memo(function VideoBlock({ item, index, start, total, montageId, selected, onSelect, transitionName }: {
  item: VideoItem;
  index: number;
  start: number;
  total: number;
  montageId: string;
  selected: boolean;
  onSelect: () => void;
  transitionName: string;
}) {
  const t = useT();
  const [ref, seen] = useInView<HTMLButtonElement>();
  const dur = outDur(item);
  const thumb = useSourceThumb({
    montageId,
    mediaId: item.media,
    tMs: Math.round(item.src_in_ms + Math.min(500, (item.src_out_ms - item.src_in_ms) / 2)),
    enabled: seen,
  });
  const url = useObjectUrl(thumb.data);
  const tip = [
    `#${index + 1} · ${fmtTimePrecise(start)}–${fmtTimePrecise(start + dur)}`,
    item.role ? `${t("mon.role")}: ${item.role}` : "",
    item.reason ? `${t("ed.reason")}: ${item.reason}` : "",
    item.user_edited ? t("mon.userEdited") : "",
  ].filter(Boolean).join("\n");
  return (
    <>
      <button
        ref={ref}
        type="button"
        className={`mt-item${selected ? " active" : ""}${item.mute ? " muted-item" : ""}`}
        style={{ left: pct(start, total), width: pct(dur, total), backgroundImage: url ? `url(${url})` : undefined }}
        title={tip}
        aria-pressed={selected}
        aria-label={t("mon.itemLabel", { n: index + 1, dur: fmtTimePrecise(dur), role: item.role ?? "" })}
        onClick={(e) => { e.stopPropagation(); onSelect(); }}
      >
        <span className="mt-item-label">
          {index + 1}{item.role ? ` · ${item.role}` : ""}{item.fx.length ? ` · fx${item.fx.length}` : ""}
          {item.user_edited ? " ✎" : ""}
        </span>
      </button>
      {item.transition_in && (
        <span className="mt-transition" style={{ left: pct(start, total) }} title={`${transitionName} · ${item.transition_in.dur_ms} ms`}
              aria-label={t("mon.transitionMark", { name: transitionName })} role="img">◆</span>
      )}
    </>
  );
});

export function MontageTrack({ tl, montageId, now, onSeek, selected, onSelect }: {
  tl: MontageTimeline;
  montageId: string;
  now: number;
  onSeek: (ms: number) => void;
  selected: Sel;
  onSelect: (s: Sel) => void;
}) {
  const t = useT();
  const fx = useFx();
  const locale = useSettings((s) => s.locale);
  const [zoom, setZoom] = useState(1);
  const inner = useRef<HTMLDivElement>(null);
  const total = Math.max(1, timelineDuration(tl));
  const starts = itemStarts(tl);

  const seekAt = (e: MouseEvent) => {
    const r = inner.current?.getBoundingClientRect();
    if (!r) return;
    onSeek(Math.round(((e.clientX - r.left) / r.width) * total));
  };

  const step = total > 120_000 ? 10_000 : total > 30_000 ? 5000 : 1000;
  const ticks: number[] = [];
  for (let x = 0; x <= total; x += step) ticks.push(x);

  return (
    <div className="stack" style={{ gap: 8 }}>
      <div className="row" style={{ justifyContent: "space-between" }}>
        <span className="mono muted" aria-live="polite">{fmtTimePrecise(now)} / {fmtTime(total)}</span>
        <span className="row" style={{ gap: 4 }}>
          <button type="button" className="btn small ghost" onClick={() => setZoom((z) => Math.max(1, z / 1.5))}
                  aria-label={t("mon.zoomOut")} disabled={zoom <= 1}>−</button>
          <span className="mono muted">{Math.round(zoom * 100)}%</span>
          <button type="button" className="btn small ghost" onClick={() => setZoom((z) => Math.min(20, z * 1.5))}
                  aria-label={t("mon.zoomIn")}>+</button>
        </span>
      </div>
      <div className="mt-scroll">
        <div className="mt-inner" ref={inner} style={{ width: `${zoom * 100}%` }} onClick={seekAt}>
          <div className="mt-ruler" aria-hidden>
            {ticks.map((x) => (
              <span key={x} className="mt-tick" style={{ left: pct(x, total) }}>{fmtTime(x)}</span>
            ))}
          </div>
          <div className="mt-lane" role="group" aria-label={t("mon.trackVideo")}>
            <span className="mt-lane-name">{t("mon.trackVideo")}</span>
            {tl.video.map((it, i) => (
              <VideoBlock key={it.id} item={it} index={i} start={starts[i] ?? 0} total={total} montageId={montageId}
                          selected={selected?.type === "video" && selected.id === it.id}
                          onSelect={() => { onSelect({ type: "video", id: it.id }); onSeek(starts[i] ?? 0); }}
                          transitionName={fxName(fx.data, it.transition_in?.plugin, locale)} />
            ))}
          </div>
          <div className="mt-lane mt-lane-sm" role="group" aria-label={t("mon.trackText")}>
            <span className="mt-lane-name">{t("mon.trackText")}</span>
            {tl.text.map((x) => (
              <button key={x.id} type="button"
                      className={`mt-text${selected?.type === "text" && selected.id === x.id ? " active" : ""}`}
                      style={{ left: pct(x.start_ms, total), width: pct(x.end_ms - x.start_ms, total) }}
                      title={`${t(`txt.kind.${x.kind}`)}: ${x.text}`}
                      aria-pressed={selected?.type === "text" && selected.id === x.id}
                      onClick={(e) => { e.stopPropagation(); onSelect({ type: "text", id: x.id }); onSeek(x.start_ms); }}>
                {x.text}
              </button>
            ))}
            {tl.captions.enabled && tl.captions.words.length > 0 && (
              <span className="mt-captions" aria-label={t("tpl.captions")} title={t("tpl.captions")} />
            )}
          </div>
          <div className="mt-lane mt-lane-sm" role="group" aria-label={t("mon.trackMusic")}>
            <span className="mt-lane-name">{t("mon.trackMusic")}</span>
            {tl.music.map((m, i) => {
              const end = m.end_ms ?? total;
              const path = tl.media[m.media]?.path ?? m.media;
              return (
                <span key={i} className="mt-music" style={{ left: pct(m.start_ms, total), width: pct(end - m.start_ms, total) }}
                      title={`${path} · ${m.gain_db} dB${m.duck ? " · duck" : ""}`}>
                  ♪ {path.split(/[\\/]/).pop()}
                </span>
              );
            })}
          </div>
          <div className="mt-playhead" style={{ left: pct(now, total) }} aria-hidden />
        </div>
      </div>
      <span className="muted" style={{ fontSize: 12 }}>{t("mon.tlHint")}</span>
    </div>
  );
}
