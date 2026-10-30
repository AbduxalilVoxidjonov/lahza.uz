// The Lahza panel: Lahza Studio's long-video → Uzbek Reels pipeline inside the
// editor. Analyze a podcast or interview (offline Uzbek ASR, alignment,
// speakers, highlight scoring), browse its highlights best first, and either
// place one on the timeline — 9:16, reframed, with word-timed Uzbek captions,
// every write undoable — or render it straight to a finished Reel with
// Lahza's own exporter. The engine is a sidecar the main process starts the
// first time this panel (or an agent's `lahza_*` tool) needs it.

import { useCallback, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Clapperboard, FileVideo, FolderOutput, Loader2, Play, RefreshCw, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { AppIcon } from "@/components/AppIcon";
import { open as openDialog } from "@/bridge/dialog";
import type { LahzaClip, LahzaEpisode, LahzaJob, LahzaResult, LahzaStatus } from "../../shared/lahza";

const VIDEO_EXTENSIONS = ["mp4", "mov", "mkv", "webm", "m4v", "avi", "mp3", "m4a", "wav"];
const POLL_MS = 1000;

/** Unwrap an IPC answer; a refusal becomes a thrown Error carrying its text. */
async function unwrap<T>(p: Promise<LahzaResult<T>>): Promise<T> {
  const r = await p;
  if (!r.ok) throw new Error(r.error.message);
  return r.value;
}

const seconds = (ms: number) => Math.round(ms / 100) / 10;

export function LahzaPanel({ onMutated }: { onMutated: () => Promise<void> | void }) {
  const { t } = useTranslation();
  const api = window.api.lahza;
  const [status, setStatus] = useState<LahzaStatus | null>(null);
  const [episodes, setEpisodes] = useState<LahzaEpisode[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [clips, setClips] = useState<LahzaClip[]>([]);
  const [job, setJob] = useState<LahzaJob | null>(null);
  const [lite, setLite] = useState(false);
  const [busyClip, setBusyClip] = useState<string | null>(null);
  const [message, setMessage] = useState<{ kind: "info" | "error"; text: string } | null>(null);
  const mounted = useRef(true);
  useEffect(() => () => { mounted.current = false; }, []);

  const fail = useCallback((e: unknown) => {
    if (mounted.current) setMessage({ kind: "error", text: e instanceof Error ? e.message : String(e) });
  }, []);

  const refreshEpisodes = useCallback(async () => {
    const list = await unwrap(api.episodes());
    if (!mounted.current) return;
    setEpisodes(list);
    setSelected((cur) => cur ?? list.find((e) => e.status === "ready")?.id ?? null);
  }, [api]);

  // Opening the panel is the intent to use Lahza: start the engine now so the
  // first analysis does not also wait for it.
  useEffect(() => {
    void (async () => {
      try {
        const s = await unwrap(api.status());
        if (!mounted.current) return;
        setStatus(s);
        if (s.state === "unavailable") return;
        setStatus({ state: "starting" });
        setStatus(await unwrap(api.start()));
        await refreshEpisodes();
      } catch (e) {
        fail(e);
        setStatus(await unwrap(api.status()).catch(() => null));
      }
    })();
  }, [api, fail, refreshEpisodes]);

  useEffect(() => {
    if (!selected) { setClips([]); return; }
    let live = true;
    unwrap(api.highlights(selected)).then((h) => { if (live) setClips(h.clips); }, fail);
    return () => { live = false; };
  }, [api, selected, fail]);

  // Poll the running analysis until it settles, then select its episode.
  useEffect(() => {
    if (!job || job.status === "done" || job.status === "failed" || job.status === "cancelled") return;
    const timer = setTimeout(() => {
      unwrap(api.job(job.id)).then(async (next) => {
        if (!mounted.current) return;
        setJob(next);
        if (next.status === "done") {
          await refreshEpisodes();
          const eid = next.meta?.episode_id;
          if (typeof eid === "string") setSelected(eid);
        } else if (next.status === "failed") {
          setMessage({ kind: "error", text: next.error ?? t("lahza_panel.job_failed") });
        }
      }, fail);
    }, POLL_MS);
    return () => clearTimeout(timer);
  }, [api, job, refreshEpisodes, fail, t]);

  const analyze = async () => {
    setMessage(null);
    const picked = await openDialog({ title: t("lahza_panel.pick_video"), filters: [{ name: t("lahza_panel.video_files"), extensions: VIDEO_EXTENSIONS }] });
    const path = Array.isArray(picked) ? picked[0] : picked;
    if (!path) return;
    try {
      const r = await unwrap(api.analyze({ path, force_lite: lite }));
      setJob({ ...r.job, meta: { ...r.job.meta, episode_id: r.episode_id } });
      await refreshEpisodes();
    } catch (e) { fail(e); }
  };

  const place = async (clip: LahzaClip) => {
    if (!selected) return;
    setBusyClip(clip.id);
    setMessage(null);
    try {
      const r = await unwrap(api.place(selected, clip.id));
      await onMutated();
      setMessage({ kind: "info", text: t("lahza_panel.placed", { count: r.video_layer_ids.length, cues: r.cue_count }) });
    } catch (e) { fail(e); }
    finally { if (mounted.current) setBusyClip(null); }
  };

  const exportReel = async (clip: LahzaClip) => {
    if (!selected) return;
    const picked = await openDialog({ title: t("lahza_panel.pick_folder"), directory: true });
    const dir = Array.isArray(picked) ? picked[0] : picked;
    if (!dir) return;
    setMessage(null);
    try { setJob(await unwrap(api.exportClip(selected, clip.id, dir))); }
    catch (e) { fail(e); }
  };

  const ready = status?.state === "ready";
  const running = job !== null && (job.status === "queued" || job.status === "running");
  const episode = episodes.find((e) => e.id === selected) ?? null;

  return (
    <div className="flex flex-col gap-3 p-2 text-xs" data-testid="lahza-panel">
      <section className="flex flex-col gap-1">
        <p className="text-muted-foreground" data-testid="lahza-status">
          {status === null ? t("lahza_panel.engine_checking")
            : status.state === "unavailable" ? t("lahza_panel.engine_unavailable")
            : status.state === "starting" ? t("lahza_panel.engine_starting")
            : status.state === "ready" ? t("lahza_panel.engine_ready", { version: status.version })
            : status.state === "failed" ? t("lahza_panel.engine_failed", { error: status.error })
            : t("lahza_panel.engine_stopped")}
        </p>
        <div className="flex items-center gap-2">
          <Button size="sm" variant="default" disabled={!ready || running} onClick={() => void analyze()} data-testid="lahza-analyze">
            <AppIcon icon={FileVideo} size="body" aria-hidden="true" />
            {t("lahza_panel.analyze")}
          </Button>
          <label className="flex items-center gap-1 text-muted-foreground" title={t("lahza_panel.lite_hint")}>
            <input type="checkbox" checked={lite} onChange={(e) => setLite(e.target.checked)} />
            {t("lahza_panel.lite")}
          </label>
        </div>
      </section>

      {job && (
        <section className="flex flex-col gap-1" aria-label={t("lahza_panel.job")}>
          <div className="flex items-center justify-between gap-2">
            <span>
              {running && <AppIcon icon={Loader2} size="body" className="mr-1 inline animate-spin" aria-hidden="true" />}
              {t(`lahza_panel.job_${job.status}`, {
                stage: job.stage ? t(`lahza_panel.stage.${job.stage}`, { defaultValue: job.stage }) : "",
                percent: Math.round(job.progress * 100),
              })}
            </span>
            {running && (
              <Button size="icon-xs" variant="ghost" aria-label={t("lahza_panel.cancel")} title={t("lahza_panel.cancel")}
                onClick={() => void unwrap(api.cancelJob(job.id)).catch(fail)}>
                <AppIcon icon={X} size="body" aria-hidden="true" />
              </Button>
            )}
          </div>
          <div className="h-1 w-full overflow-hidden rounded bg-secondary">
            <div className="h-full bg-primary transition-[width]" style={{ width: `${Math.round(job.progress * 100)}%` }} />
          </div>
          {running && job.kind !== "export" && <p className="text-muted-foreground">{t("lahza_panel.time_hint")}</p>}
          {job.kind === "export" && job.status === "done" && typeof (job.result as { video?: unknown } | null)?.video === "string" && (
            <p className="break-all text-muted-foreground">{t("lahza_panel.exported", { path: (job.result as { video: string }).video })}</p>
          )}
        </section>
      )}

      {message && (
        <p className={message.kind === "error" ? "text-destructive" : "text-muted-foreground"} role={message.kind === "error" ? "alert" : "status"}>
          {message.text}
        </p>
      )}

      {ready && (
        <section className="flex flex-col gap-1" aria-label={t("lahza_panel.videos")}>
          <div className="flex items-center justify-between">
            <h3 className="font-medium text-muted-foreground">{t("lahza_panel.videos")}</h3>
            <Button size="icon-xs" variant="ghost" aria-label={t("lahza_panel.refresh")} title={t("lahza_panel.refresh")} onClick={() => void refreshEpisodes().catch(fail)}>
              <AppIcon icon={RefreshCw} size="body" aria-hidden="true" />
            </Button>
          </div>
          {episodes.length === 0 ? (
            // A first-time user lands here: say what the panel is for in
            // three steps instead of an empty list.
            <div className="flex flex-col gap-1 rounded border border-border p-2" data-testid="lahza-guide">
              <p className="font-medium">{t("lahza_panel.guide_title")}</p>
              <p>{t("lahza_panel.guide_1")}</p>
              <p>{t("lahza_panel.guide_2")}</p>
              <p>{t("lahza_panel.guide_3")}</p>
            </div>
          ) : (
            <select className="w-full rounded border border-border bg-transparent px-1 py-0.5" value={selected ?? ""}
              onChange={(e) => setSelected(e.target.value || null)} data-testid="lahza-episode">
              {episodes.map((e) => (
                <option key={e.id} value={e.id} disabled={e.status !== "ready"}>
                  {e.title} — {t(`lahza_panel.episode_${e.status}`, { defaultValue: e.status })}
                </option>
              ))}
            </select>
          )}
        </section>
      )}

      {episode && episode.status === "ready" && (
        <section className="flex flex-col gap-1" aria-label={t("lahza_panel.highlights")}>
          <h3 className="font-medium text-muted-foreground">{t("lahza_panel.highlights")}</h3>
          {clips.length === 0 ? <p className="text-muted-foreground">{t("lahza_panel.no_highlights")}</p> : (
            <ul className="flex flex-col gap-1">
              {clips.map((clip) => (
                <li key={clip.id} className="rounded border border-border p-1.5" data-testid="lahza-clip">
                  <div className="flex items-baseline justify-between gap-2">
                    <span className="font-medium">{clip.title || t("lahza_panel.untitled")}</span>
                    <span className="shrink-0 text-muted-foreground">
                      {t("lahza_panel.clip_meta", { seconds: seconds(clip.end_ms - clip.start_ms), score: Math.round(clip.score) })}
                    </span>
                  </div>
                  {clip.reason && <p className="mt-0.5 text-muted-foreground">{clip.reason}</p>}
                  <div className="mt-1 flex gap-1">
                    <Button size="xs" variant="secondary" disabled={busyClip !== null} onClick={() => void place(clip)} title={t("lahza_panel.place_hint")}>
                      <AppIcon icon={busyClip === clip.id ? Loader2 : Clapperboard} size="body" className={busyClip === clip.id ? "animate-spin" : undefined} aria-hidden="true" />
                      {t("lahza_panel.place")}
                    </Button>
                    <Button size="xs" variant="outline" disabled={running} onClick={() => void exportReel(clip)} title={t("lahza_panel.export_hint")}>
                      <AppIcon icon={FolderOutput} size="body" aria-hidden="true" />
                      {t("lahza_panel.export")}
                    </Button>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </section>
      )}

      {status?.state === "failed" && (
        <Button size="sm" variant="outline" onClick={() => void unwrap(api.start()).then(setStatus, fail)}>
          <AppIcon icon={Play} size="body" aria-hidden="true" />
          {t("lahza_panel.retry")}
        </Button>
      )}
    </div>
  );
}
