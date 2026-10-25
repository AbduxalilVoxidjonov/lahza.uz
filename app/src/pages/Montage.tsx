import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { ApiError } from "../api/client";
import { useExportProfiles, useMontage, useReplanMontage, useSaveTimeline } from "../api/hooks";
import type { Job, MontageDetail, MontageTimeline, TextItem, StickerItem, VideoItem } from "../api/types";
import { CaptionImport, TranscriptWords } from "../components/montage/CaptionTools";
import { StickerLibrary, StickerInspector, type StickerAsset } from "../components/montage/StickerTools";
import { MontagePrompt } from "../components/montage/MontagePrompt";
import { NumField } from "../components/montage/fields";
import { useEditorT } from "../i18n/editor-extra";
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
import { clamp, normalizeSticker, freezeAt, outDur, frameMs, itemStarts, newId, normalizeVideo, timelineDuration } from "../lib/montage";
import { record, travel, splitVideo, rippleDelete, syncSaved, acknowledgeSave, type SyncedHistory, type History, type EditFailure } from "../lib/montage-edit";
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
  const et = useEditorT();
  const profiles = useExportProfiles();
  const [freezeDuration, setFreezeDuration] = useState(1000);
  const save = useSaveTimeline(montage.id);
  const replan = useReplanFlow(montage.id, t);
  const [editor, setEditor] = useState<SyncedHistory<MontageTimeline>>({
    history: { past: [], present: timeline, future: [] }, baseline: timeline,
    observed: JSON.stringify(timeline), saving: false,
  });
  const { history, baseline } = editor;
  const editorRef = useRef(editor);
  editorRef.current = editor;
  const setHistory = (update: History<MontageTimeline> | ((h: History<MontageTimeline>) => History<MontageTimeline>)) =>
    setEditor(state => ({ ...state, history: typeof update === "function" ? update(state.history) : update }));
  const savingRef = useRef<Promise<boolean> | null>(null);
  const [editError, setEditError] = useState<EditFailure | null>(null);
  const tl = history.present;
  const dirty = JSON.stringify(tl) !== JSON.stringify(baseline);
  const draft = dirty ? tl : null;
  const [sel, setSel] = useState<Sel>(null);
  const [now, setNow] = useState(0);
  const [tab, setTab] = useState<Tab>("render");
  const [advanced, setAdvanced] = useState(false);
  const [showSafe, setShowSafe] = useState(true);
  const [savedMsg, setSavedMsg] = useState(false);
  const renderRef = useRef<(() => void) | null>(null);

  useEffect(() => {
    const next = syncSaved(editor, timeline);
    if (next === editor) return;
    setEditor(next);
    if (next.history !== editor.history) {
      setSel(null); setEditError(null); setSavedMsg(false);
      setNow(value => clamp(value, 0, Math.max(0, timelineDuration(next.history.present) - 1)));
    }
  }, [editor, timeline]);

  const total = timelineDuration(tl);
  const starts = useMemo(() => itemStarts(tl), [tl]);
  const frame = frameMs(tl.format.fps);
  const hasText = tl.text.length > 0 || (tl.captions.enabled && tl.captions.words.length > 0);

  const edit = (fn: (x: MontageTimeline) => MontageTimeline) => {
    setSavedMsg(false);
    setEditError(null);
    setHistory(h => {
      const next = fn(h.present);
      return record(h, { ...next, video: normalizeVideo(next.video) });
    });
  };
  const undoRedo = (direction: "undo" | "redo") => {
    if (save.isPending) return;
    setSavedMsg(false); setEditError(null);
    const next = travel(history, direction);
    setHistory(next);
    setNow(clamp(now, 0, Math.max(0, timelineDuration(next.present) - 1)));
    setSel(null);
  };
  const partialEdit = (action: "split" | "ripple") => {
    if (!vItem || save.isPending) return;
    const result = action === "split" ? splitVideo(tl, vItem.id, now, newId("v")) : rippleDelete(tl, vItem.id);
    if ("error" in result) { setEditError(result.error); return; }
    edit(() => result.timeline);
    setSel(result.selectedId ? { type: "video", id: result.selectedId } : null);
    setNow(clamp(now, 0, Math.max(0, timelineDuration(result.timeline) - 1)));
  };
  const seek = (ms: number) => setNow(clamp(Math.round(ms), 0, Math.max(0, total - 1)));

  const vIndex = sel?.type === "video" ? tl.video.findIndex((v) => v.id === sel.id) : -1;
  const vItem = vIndex >= 0 ? tl.video[vIndex] : undefined;
  const tItem = sel?.type === "text" ? tl.text.find((x) => x.id === sel.id) : undefined;

  const sticker = sel?.type === "sticker" ? (tl.stickers ?? []).find(x => x.id === sel.id) : undefined;
  const setSticker = (item: StickerItem) => edit(x => ({ ...x, stickers: (x.stickers ?? []).map(s => s.id === item.id ? normalizeSticker(item) : s) }));
  const addSticker = (asset: StickerAsset) => {
    const id = newId("sticker");
    edit(x => {
      const width = Math.max(0.02, Math.min(0.3, 0.3 * asset.width / asset.height * x.format.h / x.format.w));
      const height = clamp(width * x.format.w / x.format.h * asset.height / asset.width, 0.02, 2);
      return { ...x, stickers: [...(x.stickers ?? []), { id, path: asset.path, start_ms: now,
        end_ms: Math.max(now + 1, Math.min(now + 2000, total)), x: 0.5, y: 0.5, width, height,
        rotation: 0, opacity: 1, layer: Math.min(1000, Math.max(-1, ...(x.stickers ?? []).map(s => s.layer)) + 1), animation: "none" }] };
    });
    setSel({ type: "sticker", id }); setTab("item");
  };
  const importCaptions = (items: TextItem[]) => {
    edit(x => ({ ...x, text: [...x.text, ...items] }));
    if (items[0]) { setSel({ type: "text", id: items[0].id }); seek(items[0].start_ms); setTab("item"); }
  };
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
    else if (sel.type === "sticker") edit(x => ({ ...x, stickers: (x.stickers ?? []).filter(s => s.id !== sel.id) }));
    else edit((x) => ({ ...x, text: x.text.filter((v) => v.id !== sel.id) }));
    setSel(null);
  };
  const addText = (caption = false) => {
    const id = newId("t");
    edit((x) => ({
      ...x,
      text: [...x.text, { id, start_ms: now, end_ms: Math.min(now + 2000, Math.max(total, now + 500)), text: caption ? et("captionText") : t("mon.newText"),
        kind: "title", position: caption ? "lower" : "middle", animation: caption ? "none" : "fade", background: null, font_size: null }],
    }));
    setSel({ type: "text", id });
    setTab("item");
  };

  const doSave = (): Promise<boolean> => {
    if (savingRef.current) return savingRef.current;
    if (!draft) return Promise.resolve(true);
    const submitted = draft;
    setEditor(state => ({ ...state, saving: true }));
    const pending = (async () => {
      try {
        const response = await save.mutateAsync(submitted);
        setEditor(state => acknowledgeSave(state, submitted, response.timeline));
        setSavedMsg(true);
        return JSON.stringify(editorRef.current.history.present) === JSON.stringify(submitted);
      } catch {
        setEditor(state => ({ ...state, saving: false }));
        return false;
      } finally {
        savingRef.current = null;
      }
    })();
    savingRef.current = pending;
    return pending;
  };
  const cancel = () => {
    if (savingRef.current) return;
    setNow(value => clamp(value, 0, Math.max(0, timelineDuration(baseline) - 1)));
    setSavedMsg(false);
    setHistory({ past: [], present: baseline, future: [] });
    setSel(null); setEditError(null);
    save.reset();
  };
  const onReplan = () => {
    if (savingRef.current) return;
    if (dirty && !window.confirm(t("mon.replanDiscard"))) return;
    setHistory({ past: [], present: baseline, future: [] });
    setSel(null); setEditError(null);
    setNow(value => clamp(value, 0, Math.max(0, timelineDuration(baseline) - 1)));
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
    "mod+z": () => undoRedo("undo"),
    "mod+shift+z": () => undoRedo("redo"),
    "mod+s": () => void doSave(),
    "mod+e": () => {
      setTab("render");
      renderRef.current?.();
    },
  });

  return (
    <div className="stack" style={{ gap: 16 }}>
      <div className="quick-editor-head">
        <div><h2>{t("quick.review")}</h2><p className="lead">{t("quick.reviewHint")}</p></div>
        <button type="button" className="btn" aria-expanded={advanced} onClick={() => {
          setAdvanced(value => !value); setTab("render");
        }}>{t(advanced ? "quick.simple" : "quick.manual")}</button>
      </div>
      <MontagePrompt tl={tl} selection={sel} profiles={profiles.data?.profiles ?? []} edit={edit} />
      {!advanced && <div className="row" aria-live="polite">
        <button type="button" className="btn" disabled={!history.past.length || save.isPending} onClick={() => undoRedo("undo")}>{et("undo")}</button>
        <button type="button" className="btn" disabled={!dirty || save.isPending} onClick={() => void doSave()}>{t("common.save")}</button>
        {dirty ? <span className="badge warn">{t("common.unsaved")}</span>
          : savedMsg ? <span className="badge good">{t("common.saved")}</span> : null}
      </div>}
      <div hidden={!advanced}>
      <div className="row toolbar" style={{ justifyContent: "space-between" }}>
        <div className="row">
          <button type="button" className="btn" disabled={!history.past.length || save.isPending} onClick={() => undoRedo("undo")}>{et("undo")} <kbd>⌘Z</kbd></button>
          <button type="button" className="btn" disabled={!history.future.length || save.isPending} onClick={() => undoRedo("redo")}>{et("redo")} <kbd>⌘⇧Z</kbd></button>
          <button type="button" className="btn" disabled={!vItem || save.isPending} onClick={() => partialEdit("split")}>{et("split")}</button>
          <button type="button" className="btn" disabled={!vItem || save.isPending} onClick={() => partialEdit("ripple")}>{et("ripple")}</button>
          {dirty ? <span className="badge warn" role="status">{t("common.unsaved")}</span>
            : savedMsg ? <span className="badge good" role="status">{t("common.saved")}</span> : null}
          <button type="button" className="btn" disabled={!dirty || save.isPending} onClick={cancel}>{t("common.cancel")}</button>
          <button type="button" className="btn primary" disabled={!dirty || save.isPending} onClick={() => void doSave()}>
            {t("common.save")} <kbd>⌘S</kbd>
          </button>
        </div>
        <div className="row">
          <button type="button" className="btn" onClick={() => addText(true)}>{et("caption")}</button>
          <button type="button" className="btn" onClick={() => addText()}>{t("mon.addText")}</button>
          <button type="button" className="btn" disabled={replan.pending} onClick={onReplan}>{t("mon.replan")}</button>
          <button type="button" className="btn primary" onClick={() => { setTab("render"); renderRef.current?.(); }}>
            {t("mon.render")} <kbd>⌘E</kbd>
          </button>
        </div>
      </div>
      {editError && <div className="notice warn" role="alert">{et(editError)}</div>}
      <div className="muted" role="note">{et("rippleHint")}</div>
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
          <MontagePreview montageId={montage.id} tMs={now} tl={tl} dirty={dirty} showSafe={showSafe} selectedSticker={sticker} onStickerChange={setSticker} />
          <label className="field" style={{ width: "100%" }}>
            {t("quick.frame")}
            <input type="range" min={0} max={Math.max(0, total - 1)} step={Math.max(1, Math.round(frame))}
              value={now} onChange={e => seek(Number(e.target.value))} />
          </label>
          <div className="row" style={{ justifyContent: "center" }}>
            <button type="button" className="btn small ghost" onClick={() => jump(-1)} aria-label={t("mon.prevItem")}>⇤</button>
            <button type="button" className="btn small ghost" onClick={() => seek(now - frame)} aria-label={t("mon.prevFrame")}>◂</button>
            <button type="button" className="btn small ghost" onClick={() => seek(now + frame)} aria-label={t("mon.nextFrame")}>▸</button>
            <button type="button" className="btn small ghost" onClick={() => jump(1)} aria-label={t("mon.nextItem")}>⇥</button>
          </div>
          {(
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
          {!advanced && <div className="quick-export-head"><h2>{t("quick.export")}</h2><p className="lead">{t("quick.exportHint")}</p></div>}
          <div hidden={!advanced}><div className="tabs" role="tablist" aria-label={t("mon.tabs")}>
            {TABS.map((k) => (
              <button key={k} type="button" role="tab" id={`mtab-${k}`} aria-selected={tab === k} aria-controls={`mpanel-${k}`}
                      className={`tab${tab === k ? " active" : ""}`} onClick={() => setTab(k)}>
                {t(`mon.tab.${k}`)}
              </button>
            ))}
          </div>
          </div>
          <div role={advanced ? "tabpanel" : undefined} id={`mpanel-${tab}`} aria-labelledby={advanced ? `mtab-${tab}` : undefined} className="montage-panel">
            {advanced && tab === "item" && (
              vItem ? (
                <div className="stack">
                <div className="notice" role="note">{et("freezeHint")}</div>
                <NumField label={et("duration")} suffix="ms" value={freezeDuration} min={100} max={5000} step={100} onChange={setFreezeDuration} />
                <button type="button" className="btn" disabled={now < (starts[vIndex] ?? 0) || now >= (starts[vIndex] ?? 0) + outDur(vItem)} onClick={() => setVideo(freezeAt(vItem, starts[vIndex] ?? 0, now, freezeDuration))}>{et("freeze")}</button>
                <VideoInspector item={vItem} index={vIndex} count={tl.video.length} media={tl.media[vItem.media]} fps={tl.format.fps}
                                onChange={setVideo} onMove={(d) => moveVideo(vIndex, d)} onDelete={deleteSelected}
                                onDuplicate={() => duplicateVideo(vIndex)} />
                </div>
              ) : sticker ? (
                <StickerInspector key={sticker.id} item={sticker} onChange={setSticker} onDelete={deleteSelected} onDuplicate={() => {
                  const copy = normalizeSticker({ ...sticker, id: newId("sticker"), layer: Math.max(-1, ...(tl.stickers ?? []).map(s => s.layer)) + 1 });
                  edit(x => ({ ...x, stickers: [...(x.stickers ?? []), copy] })); setSel({ type: "sticker", id: copy.id });
                }} />
              ) : tItem ? (
                <TextInspector item={tItem} total={total} onChange={setText} onDelete={deleteSelected} />
              ) : (
                <p className="muted">{t("mon.selectHint")}</p>
              )
            )}
            {advanced && tab === "global" && <GlobalPanel tl={tl} edit={edit} montageId={montage.id} />}
            {/* Render paneli doim o'rnatilgan: Cmd/Ctrl+E boshqa tabdan ham ishlaydi. */}
            <div hidden={advanced && tab !== "render"}>
              <RenderPanel montage={montage} tl={tl} hasText={hasText} renderRef={renderRef}
                           onBeforeRender={async () => (dirty ? doSave() : true)} />
            </div>
            {advanced && tab === "report" && <EdlReport tl={tl} onSelect={(vid) => { setSel({ type: "video", id: vid }); setTab("item"); }} />}
          </div>
        </div>
      </div>

      <div hidden={!advanced} className="stack">
      <section className="card stack">
        <StickerLibrary onAdd={addSticker} />
        {(tl.stickers ?? []).length > 0 && <label className="field">
          {et("stickers")}
          <select className="select" value={sticker?.id ?? ""} onChange={e => {
            const selected = (tl.stickers ?? []).find(s => s.id === e.target.value);
            if (selected) { setSel({ type: "sticker", id: selected.id }); seek(selected.start_ms); setTab("item"); }
            else setSel(null);
          }}>
            <option value="">{t("mon.selectHint")}</option>
            {[...(tl.stickers ?? [])].sort((a, b) => b.layer - a.layer).map(s => <option key={s.id} value={s.id}>{s.layer} · {s.path.split(/[\\/]/).pop()} · {s.start_ms}–{s.end_ms} ms</option>)}
          </select>
        </label>}
        <CaptionImport onImport={importCaptions} />
        <TranscriptWords words={tl.captions.words} onChange={words => edit(x => ({ ...x, captions: { ...x.captions, words } }))} />
      </section>
      <section className="card" aria-label={t("tl.title")}>
        {tl.video.length === 0 && tl.text.length === 0 && !(tl.stickers ?? []).length ? (
          <p className="muted">{t("mon.emptyTimeline")}</p>
        ) : (
          <MontageTrack tl={tl} montageId={montage.id} now={now} onSeek={seek} selected={sel}
                        onSelect={(s) => { setSel(s); setTab("item"); }} />
        )}
      </section>
      </div>
    </div>
  );
}
