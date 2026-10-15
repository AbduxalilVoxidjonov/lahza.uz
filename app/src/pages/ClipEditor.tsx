import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { mediaUrl } from "../api/client";
import { useClips, useEpisode, usePatchClip, useSpeakers, useTranscript, useWaveform } from "../api/hooks";
import type { Clip, Sentence } from "../api/types";
import { StatusBadge } from "../components/ClipBadges";
import { NoSubsWarning } from "../components/NoSubsWarning";
import { FrameTab } from "../components/editor/FrameTab";
import { InfoTab } from "../components/editor/InfoTab";
import { PreviewPane } from "../components/editor/PreviewPane";
import { StyleTab } from "../components/editor/StyleTab";
import { TextTab } from "../components/editor/TextTab";
import { Timeline } from "../components/Timeline";
import { ErrorText, fmtTime, QueryState } from "../components/ui";
import { useT, type MessageKey } from "../i18n";
import { useHotkeys } from "../lib/hotkeys";
import { useExportAction } from "../lib/useExportAction";
import { usePlayer } from "../lib/usePlayer";
import { flattenWords, outDuration, snapEnd, snapStart, wordsInRange } from "../lib/words";
import { useSettings } from "../store/settings";

type Tab = "text" | "frame" | "style" | "info";
const TABS: Tab[] = ["text", "frame", "style", "info"];
const NO_SENTENCES: Sentence[] = [];

export function ClipEditor() {
  const t = useT();
  const { episodeId = "", clipId = "" } = useParams();
  const clips = useClips(episodeId);
  const clip = clips.data?.find((c) => c.id === clipId);
  if (!clips.data) return <QueryState query={clips} />;
  if (!clip) return <div className="center">{t("ed.notFound")}</div>;
  return <EditorView key={clip.id} clip={clip} episodeId={episodeId} />;
}

function EditorView({ clip, episodeId }: { clip: Clip; episodeId: string }) {
  const t = useT();
  const transcript = useTranscript(episodeId);
  const episode = useEpisode(episodeId);
  const speakers = useSpeakers(episodeId);
  const waveform = useWaveform(episodeId, episode.data?.media?.duration_ms);
  const patch = usePatchClip(episodeId);
  const exporter = useExportAction(episodeId);
  const { style, setStyle, replaceStyle } = useSettings();

  const [tab, setTab] = useState<Tab>("text");
  const [showSafe, setShowSafe] = useState(true);
  const [engineFrame, setEngineFrame] = useState(true);
  const [src, setSrc] = useState<string>();
  const video = useRef<HTMLVideoElement>(null);
  const player = usePlayer(video, clip);

  useEffect(() => {
    void mediaUrl(`/v1/episodes/${episodeId}/proxy`).then(setSrc);
  }, [episodeId]);

  const sentences = transcript.data?.sentences ?? NO_SENTENCES;
  const allWords = useMemo(() => flattenWords(sentences), [sentences]);
  const duration = episode.data?.media?.duration_ms ?? Math.max(clip.end_ms, sentences[sentences.length - 1]?.end_ms ?? 0);
  const pad = Math.max(3000, (clip.end_ms - clip.start_ms) * 0.15);
  const viewStart = Math.max(0, clip.start_ms - pad);
  const viewEnd = Math.min(Math.max(duration, clip.end_ms), clip.end_ms + pad);
  const viewWords = useMemo(() => wordsInRange(allWords, viewStart, viewEnd), [allWords, viewStart, viewEnd]);
  const clipWords = useMemo(() => wordsInRange(allWords, clip.start_ms, clip.end_ms), [allWords, clip.start_ms, clip.end_ms]);
  const viewSentences = useMemo(
    () => sentences.filter((s) => s.end_ms > viewStart && s.start_ms < viewEnd),
    [sentences, viewStart, viewEnd],
  );
  const speakerName = useCallback(
    (label: string) => speakers.data?.find((s) => s.label === label)?.display_name || label,
    [speakers.data],
  );

  const trim = (start_ms: number, end_ms: number) => patch.mutate({ id: clip.id, start_ms, end_ms });

  // Klaviatura (TZ 11): Space, J/K/L, I/O, A/R, Cmd/Ctrl+E.
  useHotkeys({
    space: player.toggle,
    j: player.back,
    k: player.pause,
    l: player.forward,
    i: () => {
      const s = snapStart(viewWords, player.now);
      if (s < clip.end_ms - 500) trim(s, clip.end_ms);
    },
    o: () => {
      const e = snapEnd(viewWords, player.now);
      if (e > clip.start_ms + 500) trim(clip.start_ms, e);
    },
    a: () => patch.mutate({ id: clip.id, status: "qabul" }),
    r: () => patch.mutate({ id: clip.id, status: "rad" }),
    "mod+e": () => void exporter.run([clip.id]),
  });

  return (
    <div className="stack" style={{ gap: 18 }}>
      <div className="page-head">
        <div>
          <Link to={`/episodes/${episodeId}`} className="muted">← {t("tr.backToClips")}</Link>
          <h1>{clip.title || "—"}</h1>
        </div>
        <div className="row">
          <StatusBadge status={clip.status} />
          <button type="button" className="btn small good" onClick={() => patch.mutate({ id: clip.id, status: "qabul" })}>
            {t("clips.accept")} <kbd>A</kbd>
          </button>
          <button type="button" className="btn small bad" onClick={() => patch.mutate({ id: clip.id, status: "rad" })}>
            {t("clips.reject")} <kbd>R</kbd>
          </button>
          <button type="button" className="btn primary" onClick={() => void exporter.run([clip.id])} disabled={exporter.pending}>
            {t("ed.export")} <kbd>⌘E</kbd>
          </button>
        </div>
      </div>
      <NoSubsWarning />
      {exporter.error && (
        <span className="error" role="alert">
          {exporter.error} <Link to="/exports">{t("nav.exports")}</Link>
        </span>
      )}
      {exporter.queued > 0 && !exporter.error && (
        <span className="muted" role="status">{t("exp.queued", { n: exporter.queued })} <Link to="/exports">{t("nav.exports")}</Link></span>
      )}
      <ErrorText error={patch.error} />

      <div className="editor">
        <div className="stack">
          <PreviewPane
            episodeId={episodeId}
            clip={clip}
            src={src}
            video={video}
            videoProps={player.bind}
            now={player.now}
            playing={player.playing}
            style={style}
            words={clipWords}
            showSafe={showSafe}
            engineFrame={engineFrame}
          />
          <div className="row player-bar">
            <button type="button" className="btn small" onClick={player.back} aria-label={t("kbd.back")}>⏪ <kbd>J</kbd></button>
            <button type="button" className="btn small" onClick={player.toggle} aria-label={player.playing ? t("kbd.pause") : t("kbd.play")}>
              {player.playing ? "⏸" : "▶"} <kbd>Space</kbd>
            </button>
            <button type="button" className="btn small" onClick={player.forward} aria-label={t("kbd.forward")}>⏩ <kbd>L</kbd></button>
            <span className="muted mono">
              {fmtTime(clip.start_ms)} – {fmtTime(clip.end_ms)} · {t("common.seconds", { n: Math.round(outDuration(clip) / 1000) })}
            </span>
          </div>
          <div className="row">
            <label className="row muted check">
              <input type="checkbox" checked={showSafe} onChange={(e) => setShowSafe(e.target.checked)} />
              {t("ed.safeZone")}
            </label>
            <label className="row muted check">
              <input type="checkbox" checked={engineFrame} onChange={(e) => setEngineFrame(e.target.checked)} />
              {t("ed.engineFrameToggle")}
            </label>
          </div>
        </div>

        <div className="card">
          <div className="tabs" role="tablist" aria-label={t("ed.tabs")}>
            {TABS.map((k) => (
              <button
                key={k}
                type="button"
                role="tab"
                id={`tab-${k}`}
                aria-selected={tab === k}
                aria-controls={`panel-${k}`}
                className={`tab${tab === k ? " active" : ""}`}
                onClick={() => setTab(k)}
              >
                {t(`ed.${k}` as MessageKey)}
              </button>
            ))}
          </div>
          <div role="tabpanel" id={`panel-${tab}`} aria-labelledby={`tab-${tab}`}>
            {tab === "text" && (
              <>
                <QueryState query={transcript} />
                <TextTab clip={clip} episodeId={episodeId} words={clipWords} onSeek={player.seek} />
              </>
            )}
            {tab === "frame" && <FrameTab clip={clip} episodeId={episodeId} now={player.now} onSeek={player.seek} />}
            {tab === "style" && <StyleTab style={style} onChange={setStyle} onReplace={replaceStyle} />}
            {tab === "info" && <InfoTab clip={clip} episodeId={episodeId} />}
          </div>
        </div>
      </div>

      <section className="card stack">
        <div className="row" style={{ justifyContent: "space-between" }}>
          <h2 style={{ margin: 0 }}>{t("tl.title")}</h2>
          <span className="muted">{t("tl.hint")}</span>
        </div>
        <QueryState query={waveform} />
        <Timeline
          viewStart={viewStart}
          viewEnd={viewEnd}
          clipStart={clip.start_ms}
          clipEnd={clip.end_ms}
          cuts={clip.cuts}
          words={viewWords}
          sentences={viewSentences}
          speakerName={speakerName}
          waveform={waveform.data}
          now={player.now}
          onSeek={player.seek}
          onTrim={trim}
        />
      </section>
    </div>
  );
}
