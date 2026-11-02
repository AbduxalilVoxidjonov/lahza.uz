import { Link } from "react-router-dom";

import { useCancelJob, useExports, useReveal, useRetryJob } from "../api/hooks";
import type { ExportItem, Job } from "../api/types";
import { NoSubsWarning } from "../components/NoSubsWarning";
import { PathPicker } from "../components/PathPicker";
import { Empty, ErrorText, JobLine, QueryState } from "../components/ui";
import { useT } from "../i18n";
import { useJobs } from "../store/jobs";
import { DEFAULT_FILENAME_TEMPLATE, useSettings } from "../store/settings";

const PLACEHOLDERS = ["{shou}", "{epizod}", "{nn}", "{sarlavha}"];

/** Eksport navbati (M2-APP-8): ro'yxat engine'dan, progress WebSocket orqali jobs do'konidan. */
export function Exports() {
  const t = useT();
  const exportsQ = useExports();
  const live = useJobs((s) => s.jobs);
  const retry = useRetryJob();
  const cancel = useCancelJob();
  const reveal = useReveal();

  // WS orqali kelgan holat engine ro'yxatidagidan yangiroq bo'lishi mumkin.
  const items: ExportItem[] = (exportsQ.data ?? []).map((x) => ({ ...x, job: live[x.job.id] ?? x.job }));
  const running = items.filter((x) => x.job.status === "running" || x.job.status === "queued").length;

  return (
    <div className="stack" style={{ gap: 20, maxWidth: 980 }}>
      <div className="page-head">
        <h1>{t("exp.title")}</h1>
        {running > 0 && <span className="badge accent" role="status">{t("exp.running", { n: running })}</span>}
      </div>

      <ExportSettings />

      <QueryState query={exportsQ} />
      <ErrorText error={retry.error ?? cancel.error ?? reveal.error} />
      {exportsQ.data && items.length === 0 && <Empty>{t("exp.empty")}</Empty>}
      <ul className="stack plain-list" aria-label={t("exp.title")}>
        {items.map((x) => (
          <li key={x.job.id} className="card stack">
            <div className="row" style={{ justifyContent: "space-between" }}>
              <ExportTitle item={x} />
              <ExportActions
                job={x.job}
                onRetry={() => retry.mutate(x.job.id)}
                onCancel={() => cancel.mutate(x.job.id)}
                onReveal={(p) => reveal.mutate(p)}
                busy={retry.isPending}
              />
            </div>
            <JobLine job={x.job} />
            {x.job.status === "done" && resultPath(x.job) && (
              <span className="muted mono">{t("exp.done", { path: resultPath(x.job) ?? "" })}</span>
            )}
            {x.job.status === "done" && typeof x.job.result?.["edl"] === "string" && (
              <span className="muted mono">EDL: {x.job.result["edl"] as string}</span>
            )}
            <ResultWarnings job={x.job} />
          </li>
        ))}
      </ul>
    </div>
  );
}

const metaStr = (job: Job, k: string) => (typeof job.meta[k] === "string" ? (job.meta[k] as string) : null);

/** Klip eksporti - klip muharririga, montaj renderi - montaj sahifasiga havola. */
function ExportTitle({ item }: { item: ExportItem }) {
  const t = useT();
  const montageId = item.montage_id || metaStr(item.job, "montage_id");
  const title = item.title || metaStr(item.job, "title");
  if (montageId) {
    return (
      <span className="row" style={{ gap: 6 }}>
        <span className="badge accent">{t("mon.badge")}</span>
        <Link to={`/montages/${montageId}`}>{title || montageId}</Link>
      </span>
    );
  }
  if (item.episode_id && item.clip_id) {
    return <Link to={`/episodes/${item.episode_id}/clips/${item.clip_id}`}>{title || item.clip_id}</Link>;
  }
  return <span>{title || item.job.id}</span>;
}

const resultPath = (job: Job): string | null => {
  const v = job.result?.["video"];
  return typeof v === "string" ? v : null;
};

/** Eksport natijasidagi ogohlantirishlar (masalan, subtitrsiz eksport, encoder almashtirildi). */
function ResultWarnings({ job }: { job: Job }) {
  const t = useT();
  const w = job.result?.["warnings"];
  const list = Array.isArray(w) ? w.filter((x): x is string => typeof x === "string") : [];
  if (!list.length) return null;
  return (
    <div className="notice warn" role="note">
      <strong>{t("exp.warnings")}</strong>
      <ul style={{ margin: "4px 0 0", paddingLeft: 18 }}>
        {list.map((m, i) => <li key={i}>{m}</li>)}
      </ul>
    </div>
  );
}

function ExportActions({
  job,
  onRetry,
  onCancel,
  onReveal,
  busy,
}: {
  job: Job;
  onRetry: () => void;
  onCancel: () => void;
  onReveal: (path: string) => void;
  busy: boolean;
}) {
  const t = useT();
  const path = resultPath(job);
  return (
    <span className="row">
      {(job.status === "running" || job.status === "queued") && (
        <button type="button" className="btn small ghost" onClick={onCancel}>{t("job.cancel")}</button>
      )}
      {(job.status === "failed" || job.status === "cancelled") && (
        <button type="button" className="btn small" disabled={busy} onClick={onRetry}>{t("exp.retry")}</button>
      )}
      {job.status === "done" && path && (
        <button type="button" className="btn small" onClick={() => onReveal(path)}>{t("exp.reveal")}</button>
      )}
    </span>
  );
}

function ExportSettings() {
  const t = useT();
  const { exportDir, setExportDir, filenameTemplate, setFilenameTemplate } = useSettings();
  return (
    <section className="card stack" aria-labelledby="exp-settings">
      <h2 id="exp-settings">{t("exp.settings")}</h2>
      <NoSubsWarning />
      <PathPicker label={t("exp.dir")} value={exportDir ?? ""} onChange={(v) => setExportDir(v.trim() || null)}
                  options={{ directory: true }} />
      <label className="field">
        {t("exp.template")}
        <input className="input mono" value={filenameTemplate} placeholder={DEFAULT_FILENAME_TEMPLATE}
               onChange={(e) => setFilenameTemplate(e.target.value)} />
      </label>
      <span className="muted">
        {t("exp.templateHint", { list: PLACEHOLDERS.join(" ") })}{" "}
        <button type="button" className="btn small ghost" onClick={() => setFilenameTemplate(DEFAULT_FILENAME_TEMPLATE)}>
          {t("common.reset")}
        </button>
      </span>
    </section>
  );
}
