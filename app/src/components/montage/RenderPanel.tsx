import { useRef, useState } from "react";
import { Link } from "react-router-dom";

import { useCheckExportProfile, useExportProfiles, useCapabilities, useCancelJob, useRenderMontage, useReveal } from "../../api/hooks";
import type { Job, MontageDetail, MontageTimeline } from "../../api/types";
import { useEditorT } from "../../i18n/editor-extra";
import { ProfileChecks } from "./ExportProfilePanel";
import { useT } from "../../i18n";
import { safeName } from "../../lib/dialog";
import { useJobs } from "../../store/jobs";
import { useSettings } from "../../store/settings";
import { NoSubsWarning } from "../NoSubsWarning";
import { PathPicker } from "../PathPicker";
import { ErrorText, JobLine } from "../ui";

const str = (v: unknown) => (typeof v === "string" && v ? v : null);

/** Montaj uchun eng oxirgi render vazifasi (jobs do'konidan). */
function useLatestRenderJob(montageId: string, ownId: string | null): Job | undefined {
  return useJobs((s) => {
    if (ownId && s.jobs[ownId]) return s.jobs[ownId];
    let best: Job | undefined;
    for (const j of Object.values(s.jobs)) {
      if (j.kind === "export" && j.meta["montage_id"] === montageId && (!best || (j.created_at ?? 0) > (best.created_at ?? 0))) best = j;
    }
    return best;
  });
}

export function PathResult({ label, path }: { label: string; path: string }) {
  const t = useT();
  const reveal = useReveal();
  return (
    <div className="row" style={{ flexWrap: "nowrap" }}>
      <span className="muted" style={{ minWidth: 70 }}>{label}</span>
      <span className="mono" style={{ flex: 1, overflowWrap: "anywhere" }}>{path}</span>
      <button type="button" className="btn small" onClick={() => reveal.mutate(path)}>{t("exp.reveal")}</button>
    </div>
  );
}

export function RenderPanel({ montage, tl, hasText, onBeforeRender, renderRef }: {
  montage: MontageDetail;
  tl: MontageTimeline;
  /** Timeline'da matn yoki subtitr bor-yo'qligi (libass ogohlantirishi uchun). */
  hasText: boolean;
  /** Saqlanmagan o'zgarishlarni saqlash; false - render qilinmaydi. */
  onBeforeRender: () => Promise<boolean>;
  /** Cmd/Ctrl+E yorlig'i uchun render funksiyasi tashqariga beriladi. */
  renderRef: { current: (() => void) | null };
}) {
  const t = useT();
  const et = useEditorT();
  const profiles = useExportProfiles();
  const check = useCheckExportProfile();
  const [preparing, setPreparing] = useState(false);
  const profile = profiles.data?.profiles.find(p => p.id === (tl.target_platform ?? "custom"));
  const latest = useRef(tl);
  latest.current = tl;
  const starting = useRef(false);
  const caps = useCapabilities();
  const { exportDir, setExportDir, allowNoSubs } = useSettings();
  const render = useRenderMontage(montage.id);
  const cancel = useCancelJob();
  const [filename, setFilename] = useState(safeName(montage.name || "montaj"));
  const [jobId, setJobId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const job = useLatestRenderJob(montage.id, jobId);
  const noLibass = caps.data?.libass === false;
  const blocked = noLibass && hasText && !allowNoSubs;
  const running = job && (job.status === "queued" || job.status === "running");

  const run = async () => {
    if (starting.current || render.isPending || running) return;
    starting.current = true;
    setPreparing(true);
    check.reset();
    setError(null);
    const checked = tl;
    try {
      if (blocked) return setError(t("exp.needNoSubs"));
      if (!exportDir) return setError(t("mon.noOutDir"));
      // Refresh dynamic custom safe zones and restrictions immediately before export.
      const fresh = await profiles.refetch();
      const selected = fresh.data?.profiles.find(p => p.id === (checked.target_platform ?? "custom"));
      if (fresh.isError || !selected) return setError(et("profileUnavailable"));
      const evaluation = await check.mutateAsync(checked);
      if (evaluation.errors.length) return setError(et("profileBlocked"));
      if (latest.current !== checked) return setError(et("reviewChanges"));
      if (!(await onBeforeRender())) return;
      if (JSON.stringify(latest.current) !== JSON.stringify(checked)) return setError(et("reviewChanges"));
      render.mutate(
        { out_dir: exportDir, filename: filename.trim() || undefined, allow_no_subs: noLibass && allowNoSubs },
        { onSuccess: (j) => setJobId(j.id) },
      );
    } catch {
      setError(et("profileUnavailable"));
    } finally {
      setPreparing(false);
      starting.current = false;
    }
  };
  renderRef.current = () => void run();

  const res = job?.status === "done" ? job.result : null;
  const warnings = Array.isArray(res?.["warnings"]) ? (res["warnings"] as unknown[]).filter((x): x is string => typeof x === "string") : [];

  return (
    <div className="stack">
      {profile && <ProfileChecks tl={tl} profile={profile} />}
      {!profile && <span className="notice warn">{et("profileUnavailable")}</span>}
      <ErrorText error={profiles.error} />
      <ErrorText error={check.error} />
      {check.data && JSON.stringify(check.variables) === JSON.stringify(tl) && <div className="stack" aria-live="polite">
        {check.data.errors.map((message, i) => <div key={`e${i}`} className="notice bad" role="alert">{message}</div>)}
        {check.data.warnings.map((message, i) => <div key={`w${i}`} className="notice warn" role="note">{message}</div>)}
      </div>}
      {hasText && <NoSubsWarning />}
      <PathPicker label={t("exp.dir")} value={exportDir ?? ""} onChange={(v) => setExportDir(v.trim() || null)}
                  options={{ directory: true }} />
      <label className="field">
        {t("mon.filename")}
        <input className="input mono" value={filename} onChange={(e) => setFilename(e.target.value)} />
      </label>
      <div className="row">
        <button type="button" className="btn primary" disabled={preparing || render.isPending || !!running} onClick={() => void run()}>
          {t("mon.render")} <kbd>⌘E</kbd>
        </button>
        <Link to="/exports" className="muted">{t("nav.exports")}</Link>
      </div>
      {error && <span className="error" role="alert">{error}</span>}
      <ErrorText error={render.error} />
      {job && <JobLine job={job} onCancel={() => cancel.mutate(job.id)} />}
      {res && (
        <div className="stack" style={{ gap: 6 }} role="status">
          <strong>{t("mon.rendered")}</strong>
          {str(res["video"]) && <PathResult label={t("mon.video")} path={str(res["video"]) ?? ""} />}
          {str(res["edl"]) && <PathResult label="EDL" path={str(res["edl"]) ?? ""} />}
          {str(res["srt"]) && <PathResult label="SRT" path={str(res["srt"]) ?? ""} />}
          {str(res["encoder"]) && <span className="muted mono">encoder: {str(res["encoder"])}</span>}
        </div>
      )}
      {warnings.length > 0 && (
        <div className="notice warn" role="note">
          <strong>{t("exp.warnings")}</strong>
          <ul style={{ margin: "4px 0 0", paddingLeft: 18 }}>{warnings.map((w, i) => <li key={i}>{w}</li>)}</ul>
        </div>
      )}
      <PastExports montage={montage} />
    </div>
  );
}

/** Oldingi renderlar (GET montaj `exports`). */
function PastExports({ montage }: { montage: MontageDetail }) {
  const t = useT();
  const list = montage.exports ?? [];
  if (!list.length) return null;
  return (
    <details>
      <summary className="muted" style={{ cursor: "pointer" }}>{t("mon.pastExports", { n: list.length })}</summary>
      <ul className="stack plain-list" style={{ gap: 6, marginTop: 8 }}>
        {list.map((x) => (
          <li key={x.id} className="stack" style={{ gap: 4 }}>
            <span className="row" style={{ gap: 6 }}>
              <span className={`badge ${x.status === "done" ? "good" : x.status === "failed" ? "bad" : ""}`}>{t(`mon.exp.${x.status}`)}</span>
              <span className="muted mono">{x.finished_at ?? x.created_at ?? ""}</span>
            </span>
            {x.path && x.status === "done" && <PathResult label={t("mon.video")} path={x.path} />}
            {x.error && <span className="error">{x.error}</span>}
          </li>
        ))}
      </ul>
    </details>
  );
}
