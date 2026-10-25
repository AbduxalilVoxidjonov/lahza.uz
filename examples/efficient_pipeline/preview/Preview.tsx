import { useEffect, useRef, useState } from "react";
import type { AssFactory } from "./ass";
import type { MusicBuffers } from "./audio";
import { PreviewEngine, type PreviewState } from "./engine";
import { adaptTimeline, type Interval, type MontageTimeline, type SimpleColor } from "./model";

export interface MontagePreviewProps {
  timeline: MontageTimeline;
  /** Change on every edit, including in-place mutations. Prefer immutable snapshots. */
  revision: string | number;
  mediaURLs: Readonly<Record<string, string>>;
  /** VAD milliseconds in each SOURCE's clock. Adapter maps cuts/repeats/speed. */
  sourceVAD?: Readonly<Record<string, readonly Interval[]>>;
  /** Optional only when timeline.music is empty; see bounded PCM limits in README. */
  musicBuffers?: MusicBuffers;
  createAss?: AssFactory;
  /** Explicit preview-only adjustment; not export parity. Makes video use Canvas2D. */
  color?: SimpleColor;
}
const NO_VAD: Readonly<Record<string, readonly Interval[]>> = {};
const NO_MUSIC: MusicBuffers = new Map();
const seconds = (ms: number): string => `${(ms / 1000).toFixed(2)} s`;

export function MontagePreview({ timeline, revision, mediaURLs, sourceVAD = NO_VAD,
  musicBuffers = NO_MUSIC, createAss, color }: MontagePreviewProps) {
  const container = useRef<HTMLDivElement>(null);
  const playhead = useRef<HTMLInputElement>(null);
  const timeLabel = useRef<HTMLOutputElement>(null);
  const engine = useRef<PreviewEngine | null>(null);
  const [state, setState] = useState<{ kind: PreviewState; message?: string }>({ kind: "seeking" });
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    const root = container.current;
    if (!root) return;
    let alive = true, current: PreviewEngine | undefined;
    // Effect-owned nodes, never reused after StrictMode cleanup/Offscreen transfer.
    const stage = document.createElement("div");
    stage.style.cssText = "position:relative;width:100%;overflow:hidden;background:#000";
    root.append(stage);
    try {
      const plan = adaptTimeline(timeline, mediaURLs, sourceVAD);
      stage.style.aspectRatio = `${plan.width}/${plan.height}`;
      if (playhead.current) { playhead.current.max = String(plan.durationMs); playhead.current.value = "0"; }
      current = new PreviewEngine(stage, { plan, musicBuffers, createAss, color,
        onState(kind, message) { if (alive) setState({ kind, message }); },
        onTime(ms) {
          if (!alive) return;
          if (playhead.current) {
            playhead.current.value = String(ms);
            playhead.current.setAttribute("aria-valuetext", seconds(ms));
          }
          if (timeLabel.current) timeLabel.current.value = seconds(ms);
        },
      });
      engine.current = current;
      void current.seek(0);
    } catch (error) {
      stage.replaceChildren();
      setState({ kind: "error", message: error instanceof Error ? error.message : String(error) });
    }
    return () => {
      alive = false; engine.current = null;
      if (current) void current.dispose().catch(error => console.error("Preview cleanup:", error));
      stage.remove();
    };
  }, [timeline, revision, mediaURLs, sourceVAD, musicBuffers, createAss, color, retry]);
  return <section aria-label="Jonli montaj ko‘rinishi">
    <div ref={container} style={{ maxWidth: 720, marginInline: "auto" }} />
    <div style={{ display: "flex", gap: 8, flexWrap: "wrap", paddingBlock: 8 }}>
      <button type="button" disabled={state.kind === "error"} onClick={() => void engine.current?.play()}>Ijro</button>
      <button type="button" onClick={() => engine.current?.pause()}>Pauza</button>
      <button type="button" onClick={() => setRetry(value => value + 1)}>Qayta ochish</button>
      <output ref={timeLabel} aria-label="Chiqish vaqti">0.00 s</output>
    </div>
    <label>Montaj vaqti <input ref={playhead} type="range" min="0" defaultValue="0" step="1"
      disabled={state.kind === "error"} style={{ width: "100%" }}
      onChange={event => void engine.current?.seek(Number(event.currentTarget.value))} /></label>
    <p role={state.kind === "error" ? "alert" : "status"}>
      {state.message ?? (state.kind === "seeking" ? "Kadr kutilmoqda…" : state.kind === "playing" ? "Ijro" : "Pauza")}
    </p>
  </section>;
}
