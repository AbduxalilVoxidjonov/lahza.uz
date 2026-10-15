// Timeline (M2-APP-6): to'lqin shakli, so'zlar, spiker lentalari, klip oralig'i, kesimlar va
// so'z chegarasiga yopishadigan trim tutqichlari. SVG, tashqi kutubxonasiz.
import { useEffect, useMemo, useRef, useState, type KeyboardEvent, type PointerEvent as RPointerEvent } from "react";

import type { Sentence, Waveform } from "../api/types";
import { useT } from "../i18n";
import { snapEnd, snapStart, type FlatWord, type Range } from "../lib/words";
import { fmtTimePrecise } from "./ui";

const H = { ruler: 16, wave: 64, words: 22, speakers: 12 } as const;
const TOTAL = H.ruler + H.wave + H.words + H.speakers + 6;
const SPEAKER_COLORS = ["#4f9cf7", "#f76f8e", "#3ecf8e", "#c084fc", "#f5a524", "#22d3ee"];

export interface TimelineProps {
  viewStart: number;
  viewEnd: number;
  clipStart: number;
  clipEnd: number;
  cuts: readonly Range[];
  words: FlatWord[];
  sentences: Sentence[];
  speakerName: (label: string) => string;
  waveform: Waveform | undefined;
  now: number;
  onSeek: (ms: number) => void;
  onTrim: (startMs: number, endMs: number) => void;
}

function useWidth<T extends HTMLElement>() {
  const ref = useRef<T>(null);
  const [w, setW] = useState(800);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const ro = new ResizeObserver(([e]) => e && setW(Math.max(200, Math.floor(e.contentRect.width))));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  return [ref, w] as const;
}

export function Timeline(p: TimelineProps) {
  const t = useT();
  const [wrap, width] = useWidth<HTMLDivElement>();
  const svg = useRef<SVGSVGElement>(null);
  const span = Math.max(1, p.viewEnd - p.viewStart);
  const x = (ms: number) => ((ms - p.viewStart) / span) * width;
  const msAt = (clientX: number) => {
    const r = svg.current?.getBoundingClientRect();
    if (!r) return p.viewStart;
    return p.viewStart + ((clientX - r.left) / r.width) * span;
  };

  // Trim tortish paytidagi vaqtinchalik qiymat (qo'yib yuborilganda engine'ga yuboriladi).
  const [drag, setDrag] = useState<{ edge: "start" | "end"; ms: number } | null>(null);
  const dragged = useRef(false);
  const start = drag?.edge === "start" ? drag.ms : p.clipStart;
  const end = drag?.edge === "end" ? drag.ms : p.clipEnd;

  const speakerIdx = useMemo(() => {
    const m = new Map<string, number>();
    for (const s of p.sentences) if (s.speaker && !m.has(s.speaker)) m.set(s.speaker, m.size);
    return m;
  }, [p.sentences]);

  const bars = useMemo(() => {
    const wf = p.waveform;
    if (!wf || !wf.peaks.length || !wf.duration_ms) return "";
    const per = wf.duration_ms / wf.peaks.length;
    const cols = Math.min(width, 2000);
    const mid = H.ruler + H.wave / 2;
    let d = "";
    for (let c = 0; c < cols; c++) {
      const a = p.viewStart + (c / cols) * span;
      const b = p.viewStart + ((c + 1) / cols) * span;
      let peak = 0;
      for (let i = Math.floor(a / per); i <= Math.floor(b / per); i++) peak = Math.max(peak, wf.peaks[i] ?? 0);
      const h = Math.max(0.5, peak * (H.wave / 2 - 2));
      const px = ((c + 0.5) / cols) * width;
      d += `M${px.toFixed(1)} ${(mid - h).toFixed(1)}V${(mid + h).toFixed(1)}`;
    }
    return d;
  }, [p.waveform, p.viewStart, span, width]);

  const ticks = useMemo(() => {
    const step = [1000, 2000, 5000, 10_000, 30_000, 60_000].find((s) => (span / s) * 60 < width) ?? 60_000;
    const out: number[] = [];
    for (let ms = Math.ceil(p.viewStart / step) * step; ms <= p.viewEnd; ms += step) out.push(ms);
    return out;
  }, [p.viewStart, p.viewEnd, span, width]);

  const snap = (edge: "start" | "end", ms: number) => {
    const clipped = edge === "start" ? Math.min(ms, end - 500) : Math.max(ms, start + 500);
    return edge === "start" ? snapStart(p.words, clipped) : snapEnd(p.words, clipped);
  };

  const onHandleDown = (edge: "start" | "end") => (e: RPointerEvent<SVGRectElement>) => {
    e.stopPropagation();
    e.currentTarget.setPointerCapture(e.pointerId);
    dragged.current = true;
    setDrag({ edge, ms: edge === "start" ? p.clipStart : p.clipEnd });
  };
  const onMove = (e: RPointerEvent<SVGSVGElement>) => {
    if (!drag) return;
    setDrag({ edge: drag.edge, ms: snap(drag.edge, msAt(e.clientX)) });
  };
  const onUp = () => {
    if (!drag) return;
    const s = drag.edge === "start" ? drag.ms : p.clipStart;
    const en = drag.edge === "end" ? drag.ms : p.clipEnd;
    setDrag(null);
    if (s !== p.clipStart || en !== p.clipEnd) p.onTrim(s, en);
  };

  /** Klaviatura: ←/→ qo'shni so'z chegarasiga. */
  const onHandleKey = (edge: "start" | "end") => (e: KeyboardEvent) => {
    if (e.key !== "ArrowLeft" && e.key !== "ArrowRight") return;
    e.preventDefault();
    const dir = e.key === "ArrowLeft" ? -1 : 1;
    const cur = edge === "start" ? p.clipStart : p.clipEnd;
    const bounds = p.words.map((w) => (edge === "start" ? w.start_ms : w.end_ms));
    const next = dir < 0 ? [...bounds].reverse().find((b) => b < cur) : bounds.find((b) => b > cur);
    if (next === undefined) return;
    if (edge === "start" && next < p.clipEnd - 500) p.onTrim(next, p.clipEnd);
    if (edge === "end" && next > p.clipStart + 500) p.onTrim(p.clipStart, next);
  };

  const wordsY = H.ruler + H.wave + 2;
  const spkY = wordsY + H.words + 2;

  return (
    <div ref={wrap} className="timeline">
      <svg
        ref={svg}
        width={width}
        height={TOTAL}
        role="group"
        aria-label={t("tl.label")}
        onPointerMove={onMove}
        onPointerUp={onUp}
        onPointerCancel={() => setDrag(null)}
        onClick={(e) => {
          if (dragged.current) {
            dragged.current = false;
            return;
          }
          p.onSeek(Math.round(msAt(e.clientX)));
        }}
      >
        {/* tashqi qism xira */}
        <rect x={0} y={0} width={Math.max(0, x(start))} height={TOTAL} className="tl-outside" />
        <rect x={x(end)} y={0} width={Math.max(0, width - x(end))} height={TOTAL} className="tl-outside" />
        <rect x={x(start)} y={H.ruler} width={Math.max(0, x(end) - x(start))} height={H.wave} className="tl-clip" />

        {ticks.map((ms) => (
          <g key={ms}>
            <line x1={x(ms)} x2={x(ms)} y1={H.ruler - 4} y2={H.ruler} className="tl-tick" />
            <text x={x(ms) + 2} y={10} className="tl-label">{fmtTimePrecise(ms).replace(/\.\d$/, "")}</text>
          </g>
        ))}

        <path d={bars} className="tl-wave" />

        {p.words.map((w) => {
          const wx = x(w.start_ms);
          const ww = Math.max(1, x(w.end_ms) - wx);
          return (
            <g key={w.idx}>
              <rect x={wx} y={wordsY} width={ww} height={H.words} rx={3} className={`tl-word${w.conf != null && w.conf < 0.6 ? " low" : ""}`} />
              {ww > w.text.length * 6 + 4 && (
                <text x={wx + 3} y={wordsY + 15} className="tl-word-text">{w.text}</text>
              )}
            </g>
          );
        })}

        {p.sentences.map((s) => {
          if (!s.speaker || s.end_ms < p.viewStart || s.start_ms > p.viewEnd) return null;
          const sx = x(s.start_ms);
          const sw = Math.max(1, x(s.end_ms) - sx);
          const color = SPEAKER_COLORS[(speakerIdx.get(s.speaker) ?? 0) % SPEAKER_COLORS.length];
          const name = p.speakerName(s.speaker);
          return (
            <g key={s.id}>
              <rect x={sx} y={spkY} width={sw} height={H.speakers} rx={2} fill={color} opacity={0.75}>
                <title>{name}</title>
              </rect>
              {sw > name.length * 6 + 4 && <text x={sx + 3} y={spkY + 10} className="tl-spk-text">{name}</text>}
            </g>
          );
        })}

        {p.cuts.map(([a, b]) => (
          <rect key={`${a}-${b}`} x={x(a)} y={H.ruler} width={Math.max(1, x(b) - x(a))} height={TOTAL - H.ruler} className="tl-cut">
            <title>{t("cut.deleted")}</title>
          </rect>
        ))}

        {(["start", "end"] as const).map((edge) => {
          const ms = edge === "start" ? start : end;
          return (
            <rect
              key={edge}
              x={x(ms) - (edge === "start" ? 0 : 8)}
              y={H.ruler}
              width={8}
              height={TOTAL - H.ruler}
              rx={2}
              className="tl-handle"
              tabIndex={0}
              role="slider"
              aria-label={edge === "start" ? t("tl.trimStart") : t("tl.trimEnd")}
              aria-valuemin={p.viewStart}
              aria-valuemax={p.viewEnd}
              aria-valuenow={ms}
              aria-valuetext={fmtTimePrecise(ms)}
              onPointerDown={onHandleDown(edge)}
              onClick={(e) => e.stopPropagation()}
              onKeyDown={onHandleKey(edge)}
            />
          );
        })}

        <line x1={x(p.now)} x2={x(p.now)} y1={0} y2={TOTAL} className="tl-playhead" />
      </svg>
      {drag && <div className="tl-drag mono">{fmtTimePrecise(drag.ms)}</div>}
    </div>
  );
}
