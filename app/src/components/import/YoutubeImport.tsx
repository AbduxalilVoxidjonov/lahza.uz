import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";

import { useCancelJob } from "../../api/hooks";
import { useImportUrl, useYoutubeImportStatus } from "../../api/youtube";
import { translate } from "../../i18n";
import { fmt, youtubeDictionaries, youtubeErrors } from "../../i18n/youtube";
import { jobCodedError } from "../../lib/error-codes";
import {
  canStart, consentGiven, downloadView, parseYoutubeVideoId, youtubeFieldState, youtubeInputEnabled, type ConsentState,
} from "../../lib/youtube-import";
import { useJobs } from "../../store/jobs";
import { useSettings } from "../../store/settings";
import { ErrorText, ProgressBar, QueryState } from "../ui";
import { YoutubeComponentsInstall } from "./YoutubeComponentsInstall";

/** YT-1 (ADR-0010): havola -> rozilik oynasi -> alohida jarayonda yuklash -> oddiy tahlil oqimi. */
export function YoutubeImport({ projectId, focus, lite }: { projectId: string; focus: string; lite: boolean }) {
  const locale = useSettings((s) => s.locale);
  const y = youtubeDictionaries[locale];
  const status = useYoutubeImportStatus();
  const importUrl = useImportUrl();
  const cancel = useCancelJob();
  const [url, setUrl] = useState("");
  const [asking, setAsking] = useState(false);
  const [jobId, setJobId] = useState<string | null>(null);
  const job = useJobs((s) => (jobId ? s.jobs[jobId] : undefined));
  const st = status.data;
  const busy = importUrl.isPending || job?.status === "queued" || job?.status === "running";
  const validUrl = parseYoutubeVideoId(url) !== null;

  const start = () => {
    setAsking(false);
    importUrl.mutate(
      { project_id: projectId, url: url.trim(), consent: true, focus: focus || undefined, force_lite: lite },
      { onSuccess: (res) => setJobId(res.job.id) },
    );
  };

  const view = job ? downloadView(job) : null;
  const coded = job ? jobCodedError(job) : null; // masalan, yuklangan video AV1 (unsupported_codec)
  // Maydon har doim ko'rinadi; Sozlamalarda o'chiq bo'lsa disabled + "Sozlamalarda yoqing" havolasi.
  const field = youtubeFieldState(st);
  return (
    <div className="stack">
      <QueryState query={status} />
      {field === "disabled" && (
        <div className="notice warn row" role="status" id="yt-disabled-note" style={{ justifyContent: "space-between" }}>
          <span>{y.disabledShort}</span>
          <Link className="btn small" to="/settings#set-youtube">{y.enableInSettings}</Link>
        </div>
      )}
      {field !== "disabled" && field !== "loading" && <div className="notice">{y.recommend}</div>}
      {field === "notInstalled" && <div className="notice bad" role="alert">{y.notInstalled}</div>}
      {field === "noJs" && <div className="notice warn">{y.noJs}</div>}
      {st && field !== "disabled" && <YoutubeComponentsInstall st={st} />}
      <div className="row">
        <label className="field" style={{ flex: 1, minWidth: 260 }}>
          {y.url}
          <input className="input" type="url" inputMode="url" placeholder={y.urlPlaceholder} value={url}
                 aria-invalid={url.trim() !== "" && !validUrl} disabled={!youtubeInputEnabled(field)}
                 aria-describedby={field === "disabled" ? "yt-disabled-note" : undefined}
                 onChange={(e) => setUrl(e.target.value)} />
        </label>
        <button className="btn primary" type="button" onClick={() => setAsking(true)}
                disabled={!canStart({ enabled: !!st?.enabled, installed: !!st?.installed, url, busy })}>
          {y.start}
        </button>
      </div>
      {url.trim() !== "" && !validUrl && <span className="error">{y.urlInvalid}</span>}
      <ErrorText error={importUrl.error} />

      {job && view && (
        <div className="stack" style={{ gap: 6 }} aria-live="polite">
          {(job.status === "running" || job.status === "queued") && (
            <>
              <div className="row" style={{ justifyContent: "space-between" }}>
                <span>{fmt(y.downloading, { title: view.title ?? url })}</span>
                <span className="row">
                  <span className="mono muted">{view.percent}%</span>
                  <button className="btn small ghost" type="button" onClick={() => cancel.mutate(job.id)}>{y.cancel}</button>
                </span>
              </div>
              <ProgressBar value={job.progress} label={y.url} />
              <span className="muted mono">
                {fmt(y.speed, { v: view.speed })} · {fmt(y.eta, { v: view.eta })} · {fmt(y.size, { v: view.size })}
              </span>
            </>
          )}
          {job.status === "cancelled" && <span className="muted">{y.cancelled}</span>}
          {job.status === "failed" && (
            <div className="row">
              <span className="error" role="alert">
                {view.errorCode ? youtubeErrors[locale][view.errorCode]
                  : coded ? translate(locale, coded.key, coded.vars) : job.error}
              </span>
              <button className="btn small" type="button" onClick={() => setAsking(true)} disabled={!validUrl}>{y.retry}</button>
            </div>
          )}
          {job.status === "done" && (
            <span className="row">
              <span className="muted">{y.done}</span>
              {view.episodeId && <Link to={`/episodes/${view.episodeId}`}>{y.openEpisode}</Link>}
            </span>
          )}
        </div>
      )}

      {asking && <ConsentDialog y={y} onAccept={start} onClose={() => setAsking(false)} />}
    </div>
  );
}

function ConsentDialog({ y, onAccept, onClose }: {
  y: (typeof youtubeDictionaries)["uz"]; onAccept: () => void; onClose: () => void;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  const [c, setC] = useState<ConsentState>({ owner: false, terms: false });
  useEffect(() => {
    const d = ref.current;
    if (d && !d.open) d.showModal();
  }, []);
  return (
    <dialog ref={ref} className="card" onClose={onClose} aria-labelledby="yt-consent-title"
            style={{ width: "min(620px, 92vw)", color: "inherit", padding: 20 }}>
      <div className="stack">
        <h3 id="yt-consent-title" style={{ margin: 0 }}>{y.consentTitle}</h3>
        <p className="muted" style={{ margin: 0 }}>{y.recommend}</p>
        <label className="row" style={{ alignItems: "flex-start" }}>
          <input type="checkbox" checked={c.owner} onChange={(e) => setC({ ...c, owner: e.target.checked })} />
          <span>{y.consentOwner}</span>
        </label>
        <label className="row" style={{ alignItems: "flex-start" }}>
          <input type="checkbox" checked={c.terms} onChange={(e) => setC({ ...c, terms: e.target.checked })} />
          <span>{y.consentTerms}</span>
        </label>
        <span className="muted">{y.consentNetwork}</span>
        <div className="row" style={{ justifyContent: "flex-end" }}>
          <button className="btn" type="button" onClick={() => ref.current?.close()} autoFocus>{y.consentCancel}</button>
          <button className="btn primary" type="button" disabled={!consentGiven(c)} onClick={onAccept}>{y.consentAccept}</button>
        </div>
      </div>
    </dialog>
  );
}
