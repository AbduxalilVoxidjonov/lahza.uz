import { useEffect, useRef, useState } from "react";

import type { Clip, Job } from "@shared/types";
import { analyzeMedia, baseName, makeReel, type Aspect, type FlowDeps, type Orthography } from "../flow";
import type { BuildResult, BuildStep } from "../host/adapter";
import { BuildProgress, BuildResultView, ErrorLine, ProgressBar, Section, errMsg, store, useT } from "./common";

const ASPECTS: Aspect[] = ["9:16", "1:1", "16:9"];
const ORTHS: Orthography[] = ["official", "ascii", "new"];

function ClipRow({
  clip,
  busy,
  onStatus,
  onMake,
}: {
  clip: Clip;
  busy: boolean;
  onStatus: (s: Clip["status"]) => void;
  onMake: () => void;
}) {
  const t = useT();
  const dur = ((clip.end_ms - clip.start_ms) / 1000).toFixed(1);
  return (
    <li className={`clip ${clip.status === "rad" ? "rejected" : ""}`}>
      <div className="row between">
        <span className="score">{Math.round(clip.score)}</span>
        <span className="clip-title grow">{clip.title}</span>
        <span className="muted small">{t("clips.duration", { s: dur })}</span>
      </div>
      {clip.reason && <div className="muted small">{clip.reason}</div>}
      <div className="row">
        <button className={`btn small ${clip.status === "qabul" ? "good" : ""}`} onClick={() => onStatus("qabul")} disabled={busy}>
          {t("clips.accept")}
        </button>
        <button className={`btn small ${clip.status === "rad" ? "bad" : ""}`} onClick={() => onStatus("rad")} disabled={busy}>
          {t("clips.reject")}
        </button>
        <button className="btn small primary push" onClick={onMake} disabled={busy || clip.status === "rad"}>
          {t("clips.make")}
        </button>
      </div>
    </li>
  );
}

export function ReelsTab({ deps }: { deps: FlowDeps }) {
  const t = useT();
  const [paths, setPaths] = useState<string[]>([]);
  const [job, setJob] = useState<Job | null>(null);
  const [episodeId, setEpisodeId] = useState<string | null>(store.get("episode"));
  const [clips, setClips] = useState<Clip[]>([]);
  const [aspect, setAspect] = useState<Aspect>("9:16");
  const [orth, setOrth] = useState<Orthography>((store.get("orth") as Orthography | null) ?? "official");
  const [step, setStep] = useState<BuildStep | null>(null);
  const [result, setResult] = useState<BuildResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const abort = useRef<AbortController | null>(null);

  const refresh = async () => {
    try {
      setPaths(await deps.adapter.selectedMediaPaths());
    } catch (e) {
      setError(errMsg(e));
    }
  };
  useEffect(() => {
    void refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const analyze = async () => {
    if (!paths[0]) return;
    setBusy(true);
    setError(null);
    setResult(null);
    abort.current = new AbortController();
    try {
      const r = await analyzeMedia(deps, paths[0], setJob, abort.current.signal);
      setEpisodeId(r.episodeId);
      store.set("episode", r.episodeId);
      setClips(r.clips);
    } catch (e) {
      setError(errMsg(e));
    } finally {
      setBusy(false);
      setJob(null);
    }
  };

  const setStatus = async (clip: Clip, status: Clip["status"]) => {
    if (!episodeId) return;
    try {
      await deps.client.setClipStatus(episodeId, clip.id, status);
      setClips((cs) => cs.map((c) => (c.id === clip.id ? { ...c, status } : c)));
    } catch (e) {
      setError(errMsg(e));
    }
  };

  const make = async (clip: Clip) => {
    if (!episodeId) return;
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      const r = await makeReel(deps, episodeId, clip.id, { aspect, orthography: orth }, setStep);
      setResult(r.result);
    } catch (e) {
      setError(errMsg(e));
    } finally {
      setBusy(false);
      setStep(null);
    }
  };

  return (
    <div className="stack">
      <Section
        title={t("analyze.title")}
        aside={
          <button className="btn small ghost" onClick={() => void refresh()} disabled={busy}>
            {t("analyze.refresh")}
          </button>
        }
      >
        <div className="muted small">{t("analyze.selected")}</div>
        {paths[0] ? (
          <div className="mono path" title={paths[0]}>
            {baseName(paths[0])}
          </div>
        ) : (
          <div className="small">{t("analyze.none")}</div>
        )}
        <div className="row">
          <button className="btn primary" onClick={() => void analyze()} disabled={busy || !paths[0]}>
            {t("analyze.run")}
          </button>
          {job && (
            <button className="btn small ghost" onClick={() => abort.current?.abort()}>
              {t("analyze.cancel")}
            </button>
          )}
        </div>
        {job && (
          <div className="stack-sm">
            <div className="muted small">{t("analyze.running", { stage: job.stage ?? job.status })}</div>
            <ProgressBar value={job.progress} />
          </div>
        )}
      </Section>

      <Section title={t("clips.title")}>
        <div className="row">
          <label className="field">
            {t("reel.aspect")}
            <select className="select" value={aspect} onChange={(e) => setAspect(e.currentTarget.value as Aspect)}>
              {ASPECTS.map((a) => (
                <option key={a} value={a}>
                  {a}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            {t("reel.orth")}
            <select
              className="select"
              value={orth}
              onChange={(e) => {
                const v = e.currentTarget.value as Orthography;
                setOrth(v);
                store.set("orth", v);
              }}
            >
              {ORTHS.map((o) => (
                <option key={o} value={o}>
                  {t(`orth.${o}`)}
                </option>
              ))}
            </select>
          </label>
        </div>
        {clips.length === 0 ? (
          <div className="muted small">{t("clips.empty")}</div>
        ) : (
          <ul className="clips">
            {clips.map((c) => (
              <ClipRow key={c.id} clip={c} busy={busy} onStatus={(s) => void setStatus(c, s)} onMake={() => void make(c)} />
            ))}
          </ul>
        )}
        <BuildProgress step={step} />
        <ErrorLine error={error} />
        <BuildResultView result={result} />
      </Section>
    </div>
  );
}
