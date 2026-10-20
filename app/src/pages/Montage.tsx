import { useMemo, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { ApiError } from "../api/client";
import { useMontage, useReplanMontage, useSaveTimeline } from "../api/hooks";
import type { Job, MontageDetail, MontageTimeline, TextItem, VideoItem } from "../api/types";
import { EdlReport } from "../components/montage/EdlReport";
import { GlobalPanel } from "../components/montage/GlobalPanel";
import { MontagePreview } from "../components/montage/MontagePreview";
import { MontageTrack, type Sel } from "../components/montage/MontageTrack";
import { RenderPanel } from "../components/montage/RenderPanel";
import { TextInspector } from "../components/montage/TextInspector";
import { VideoInspector } from "../components/montage/VideoInspector";
import { ErrorText, JobLine, ProgressBar, QueryState } from "../components/ui";
import { useT, type TFunc } from "../i18n";
import { useHotkeys } from "../lib/hotkeys";
import { clamp, frameMs, itemStarts, newId, normalizeVideo, timelineDuration } from "../lib/montage";
import { useJobs } from "../store/jobs";
import { MontageStatusBadge } from "./Montages";

export function Montage() {
  const t = useT();
  const { id = "" } = useParams();
  const q = useMontage(id);
  if (!q.data) return <QueryState query={q} />;
  const m = q.data;
  return (
    <div className="stack" style={{ gap: 16 }}>
      <div className="page-head">
        <div>
          <Link to="/montages" className="muted">← {t("nav.montages")}</Link>
          <h1>{m.name || m.id}</h1>
        </div>
        <MontageStatusBadge status={m.status} />
      </div>
      {m.status === "planning" && <Planning montageId={m.id} jobId={m.job_id ?? null} />}
      {m.status === "failed" && <Failed montage={m} />}
      {m.status === "ready" && m.timeline && <MontageEditor key={m.id} montage={m} timeline={m.timeline} />}
      {m.status === "ready" && !m.timeline && <span className="error" role="alert">{t("mon.noTimeline")}</span>}
    </div>
  );
}

/** Reja vazifasi progressi (WS orqali jobs do'konidan). */
function Planning({ montageId, jobId }: { montageId: string; jobId: string | null }) {
  const t = useT();
  const job = useJobs((s) => {
    if (jobId && s.jobs[jobId]) return s.jobs[jobId];
    let best: Job | undefined;
    for (const j of Object.values(s.jobs)) {
      if (j.kind === "montage" && j.meta["montage_id"] === montageId && (!best || (j.created_at ?? 0) >= (best.created_at ?? 0))) best = j;
    }
    return best;
  });
  return (
    <section className="card stack" aria-live="polite">
      <h2>{t("mon.planning")}</h2>
      <p className="muted" style={{ margin: 0 }}>{t("mon.planningHint")}</p>
      {job ? <JobLine job={job} /> : <ProgressBar value={0.05} label={t("mon.planning")} />}
    </section>
  );
}

/** Qayta reja: qo'lda tahrirlar bo'lsa 409 -> foydalanuvchi tasdig'i bilan `force`. */
function useReplanFlow(montageId: string, t: TFunc) {
  const replan = useReplanMontage(montageId);
  const run = () =>
    replan.mutate({}, {
      onError: (e) => {
        if (e instanceof ApiError && e.status === 409 && window.confirm(t("mon.replanForce", { msg: e.message }))) {
          replan.mutate({ force: true });
        }
      },
    });
  const error = replan.error instanceof ApiError && replan.error.status === 409 ? null : replan.error;
  return { run, pending: replan.isPending, error };
}

function Failed({ montage }: { montage: MontageDetail }) {
  const t = useT();
  const replan = useReplanFlow(montage.id, t);
  return (
    <section className="card stack">
      <span className="error" role="alert">{t("common.error", { msg: montage.error ?? "" })}</span>
      <div className="row">
        <button type="button" className="btn primary" disabled={replan.pending} onClick={replan.run}>{t("exp.retry")}</button>
        <Link to="/montages/new" className="muted">{t("mon.new")}</Link>
      </div>
      <ErrorText error={replan.error} />
    </section>
  );
}

type Tab = "item" | "global" | "render" | "report";
const TABS: Tab[] = ["item", "global", "render", "report"];

function MontageEditor({ montage, timeline }: { montage: MontageDetail; timeline: MontageTimeline }) {
  const t = useT();
  const save = useSaveTimeline(montage.id);
  const replan = useReplanFlow(montage.id, t);
  const [draft, setDraft] = useState<MontageTimeline | null>(null);
  const [sel, setSel] = useState<Sel>(null);
  const [now, setNow] = useState(0);
  const [tab, setTab] = useState<Tab>("item");
  const [showSafe, setShowSafe] = useState(true);
  const [savedMsg, setSavedMsg] = useState(false);
  const renderRef = useRef<(() => void) | null>(null);

  const tl = draft ?? timeline;
  const dirty = draft !== null;
  const total = timelineDuration(tl);
  const starts = useMemo(() => itemStarts(tl), [tl]);
  const frame = frameMs(tl.format.fps);
  const hasText = tl.text.length > 0 || (tl.captions.enabled && tl.captions.words.length > 0);

  const edit = (fn: (x: MontageTimeline) => MontageTimeline) => {
    setSavedMsg(false);
    setDraft((d) => {
      const next = fn(d ?? timeline);
      return { ...next, video: normalizeVideo(next.video) };
    });
  };
  const seek = (ms: number) => setNow(clamp(Math.round(ms), 0, Math.max(0, total - 1)));

  const vIndex = sel?.type === "video" ? tl.video.findIndex((v) => v.id === sel.id) : -1;
  const vItem = vIndex >= 0 ? tl.video[vIndex] : undefined;
  const tItem = sel?.type === "text" ? tl.text.find((x) => x.id === sel.id) : undefined;

  const setVideo = (it: VideoItem) => edit((x) => ({ ...x, video: x.video.map((v) => (v.id === it.id ? it : v)) }));
  const setText = (it: TextItem) => edit((x) => ({ ...x, text: x.text.map((v) => (v.id === it.id ? it : v)) }));
  const moveVideo = (i: number, d: -1 | 1) =>
    edit((x) => {
      const j = i + d;
      if (j < 0 || j >= x.video.length) return x;
      const v = [...x.video];
      const [it] = v.splice(i, 1);
      if (it) v.splice(j, 0, { ...it, user_edited: true });
      return { ...x, video: v };
    });
  const duplicateVideo = (i: number) =>
    edit((x) => {
      const it = x.video[i];
      if (!it) return x;
      const copy: VideoItem = { ...structuredClone(it), id: newId("v"), user_edited: true };
      const v = [...x.video];
      v.splice(i + 1, 0, copy);
      return { ...x, video: v };
    });
  const deleteSelected = () => {
    if (!sel) return;
    if (sel.type === "video") edit((x) => ({ ...x, video: x.video.filter((v) => v.id !== sel.id) }));
    else edit((x) => ({ ...x, text: x.text.filter((v) => v.id !== sel.id) }));
    setSel(null);
  };
  const addText = () => {
    const id = newId("t");
    edit((x) => ({
      ...x,
      text: [...x.text, { id, start_ms: now, end_ms: Math.min(now + 2000, Math.max(total, now + 500)), text: t("mon.newText"),
        kind: "title", position: "middle", animation: "fade", background: null, font_size: null }],
    }));
    setSel({ type: "text", id });
    setTab("item");
  };

  const doSave = async (): Promise<boolean> => {
    if (!draft) return true;
    try {
      await save.mutateAsync(draft);
      setDraft(null);
      setSavedMsg(true);
      return true;
    } catch {
      return false;
    }
  };
  const cancel = () => {
    setDraft(null);
    save.reset();
  };
  const onReplan = () => {
    if (dirty && !window.confirm(t("mon.replanDiscard"))) return;
    setDraft(null);
    replan.run();
  };

  // Elementlar chegarasi bo'yicha sakrash.
  const jump = (d: -1 | 1) => {
    if (d > 0) {
      const next = starts.find((s) => s > now + 1);
      seek(next ?? total);
    } else {
      const prev = [...starts].reverse().find((s) => s < now - 1);
      seek(prev ?? 0);
    }
  };

  // Kadrli preview - ijro yo'q, shuning uchun Space bog'lanmagan.
  useHotkeys({
    arrowleft: () => seek(now - frame),
    arrowright: () => seek(now + frame),
    "shift+arrowleft": () => jump(-1),
    "shift+arrowright": () => jump(1),
    delete: deleteSelected,
    backspace: deleteSelected,
    escape: () => setSel(null),
    "mod+s": () => void doSave(),
    "mod+e": () => {
      setTab("render");
      renderRef.current?.();
    },
  });

  return (
    <div className="stack" style={{ gap: 16 }}>
      <div className="row toolbar" style={{ justifyContent: "space-between" }}>
        <div className="row">
          {dirty ? <span className="badge warn" role="status">{t("common.unsaved")}</span>
            : savedMsg ? <span className="badge good" role="status">{t("common.saved")}</span> : null}
          <button type="button" className="btn" disabled={!dirty || save.isPending} onClick={cancel}>{t("common.cancel")}</button>
          <button type="button" className="btn primary" disabled={!dirty || save.isPending} onClick={() => void doSave()}>
            {t("common.save")} <kbd>⌘S</kbd>
          </button>
        </div>
        <div className="row">
          <button type="button" className="btn" onClick={addText}>{t("mon.addText")}</button>
          <button type="button" className="btn" disabled={replan.pending} onClick={onReplan}>{t("mon.replan")}</button>
          <button type="button" className="btn primary" onClick={() => { setTab("render"); renderRef.current?.(); }}>
            {t("mon.render")} <kbd>⌘E</kbd>
          </button>
        </div>
      </div>
      <ErrorText error={save.error ?? replan.error} />
      {montage.error && (
        <div className="notice bad" role="alert">{t("mon.replanFailed", { msg: montage.error })}</div>
      )}

      {(timeline.provenance?.notes ?? []).length > 0 && (
        <div className="notice warn" role="note">
          <strong>{t("mon.planNotes")}</strong>
          <ul style={{ margin: "4px 0 0", paddingLeft: 18 }}>
            {(timeline.provenance?.notes ?? []).map((n, i) => <li key={i}>{n}</li>)}
          </ul>
        </div>
      )}

      <div className="montage-editor">
        <div className="stack">
          <MontagePreview montageId={montage.id} tMs={now} tl={tl} dirty={dirty} showSafe={showSafe} />
          <div className="row" style={{ justifyContent: "center" }}>
            <button type="button" className="btn small ghost" onClick={() => jump(-1)} aria-label={t("mon.prevItem")}>⇤</button>
            <button type="button" className="btn small ghost" onClick={() => seek(now - frame)} aria-label={t("mon.prevFrame")}>◂</button>
            <button type="button" className="btn small ghost" onClick={() => seek(now + frame)} aria-label={t("mon.nextFrame")}>▸</button>
            <button type="button" className="btn small ghost" onClick={() => jump(1)} aria-label={t("mon.nextItem")}>⇥</button>
          </div>
          {tl.format.aspect === "9:16" && (
            <label className="row muted check" style={{ justifyContent: "center" }}>
              <input type="checkbox" checked={showSafe} onChange={(e) => setShowSafe(e.target.checked)} />
              {t("ed.safeZone")}
            </label>
          )}
          <span className="muted mono" style={{ textAlign: "center" }}>
            {tl.format.aspect} · {tl.format.w}×{tl.format.h} · {tl.format.fps} fps
          </span>
        </div>

        <div className="card">
          <div className="tabs" role="tablist" aria-label={t("mon.tabs")}>
            {TABS.map((k) => (
              <button key={k} type="button" role="tab" id={`mtab-${k}`} aria-selected={tab === k} aria-controls={`mpanel-${k}`}
                      className={`tab${tab === k ? " active" : ""}`} onClick={() => setTab(k)}>
                {t(`mon.tab.${k}`)}
              </button>
            ))}
          </div>
          <div role="tabpanel" id={`mpanel-${tab}`} aria-labelledby={`mtab-${tab}`} className="montage-panel">
            {tab === "item" && (
              vItem ? (
                <VideoInspector item={vItem} index={vIndex} count={tl.video.length} media={tl.media[vItem.media]} fps={tl.format.fps}
                                onChange={setVideo} onMove={(d) => moveVideo(vIndex, d)} onDelete={deleteSelected}
                                onDuplicate={() => duplicateVideo(vIndex)} />
              ) : tItem ? (
                <TextInspector item={tItem} total={total} onChange={setText} onDelete={deleteSelected} />
              ) : (
                <p className="muted">{t("mon.selectHint")}</p>
              )
            )}
            {tab === "global" && <GlobalPanel tl={tl} edit={edit} montageId={montage.id} />}
            {/* Render paneli doim o'rnatilgan: Cmd/Ctrl+E boshqa tabdan ham ishlaydi. */}
            <div hidden={tab !== "render"}>
              <RenderPanel montage={montage} hasText={hasText} renderRef={renderRef}
                           onBeforeRender={async () => (dirty ? doSave() : true)} />
            </div>
            {tab === "report" && <EdlReport tl={tl} onSelect={(vid) => { setSel({ type: "video", id: vid }); setTab("item"); }} />}
          </div>
        </div>
      </div>

      <section className="card" aria-label={t("tl.title")}>
        {tl.video.length === 0 ? (
          <p className="muted">{t("mon.emptyTimeline")}</p>
        ) : (
          <MontageTrack tl={tl} montageId={montage.id} now={now} onSeek={seek} selected={sel}
                        onSelect={(s) => { setSel(s); setTab("item"); }} />
        )}
      </section>
    </div>
  );
}
