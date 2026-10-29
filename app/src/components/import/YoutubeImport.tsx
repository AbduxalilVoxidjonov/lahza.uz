import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";

import { useCancelJob } from "../../api/hooks";
import { useImportUrl, useResolveUrl, useYoutubeImportStatus } from "../../api/youtube";
import { translate } from "../../i18n";
import { fmt, youtubeDictionaries, youtubeErrors } from "../../i18n/youtube";
import { jobCodedError } from "../../lib/error-codes";
import {
  canStart, consentGiven, downloadView, importedVideo, isYtErrorCode, outdatedRuntimes, parseYoutubeSource,
  youtubeFieldState, youtubeInputEnabled, type ConsentState, type ImportedVideo,
} from "../../lib/youtube-import";
import { useJobs } from "../../store/jobs";
import { useSettings } from "../../store/settings";
import { ErrorText, ProgressBar, QueryState } from "../ui";
import { YoutubeComponentsInstall } from "./YoutubeComponentsInstall";
import { YoutubePlaylistPicker } from "./YoutubePlaylistPicker";

export interface YoutubeImportProps {
  /** Loyiha id'si yoki uni rozilikdan keyin oladigan funksiya (Boshlash sahifasi: "YouTube" loyihasi). */
  projectId: string | (() => Promise<string>);
  focus?: string;
  lite?: boolean;
  /** Ixcham ko'rinish (Boshlash sahifasi): uzun tavsiya matni faqat rozilik oynasida. */
  compact?: boolean;
  /** Bitta video tugmasi matni (standart: "Yuklab olish va tahlil qilish"). */
  startLabel?: string;
  /** Bitta video yuklab bo'lingach (bir marta) - masalan, montaj manbasiga qo'shish. */
  onImported?: (video: ImportedVideo, projectId: string) => void;
}

/** YT-1 (ADR-0010): havola -> rozilik oynasi -> alohida jarayonda yuklash -> oddiy tahlil oqimi.
 * Playlist/kanal havolasi: rozilik -> ro'yxat (`/v1/media:resolve-url`) -> tanlanganlar navbatga.
 * Loyihalar sahifasida va Boshlash sahifasining 1-qadamida (SourcePicker) ishlatiladi. */
export function YoutubeImport({
  projectId, focus = "", lite = false, compact = false, startLabel, onImported,
}: YoutubeImportProps) {
  const locale = useSettings((s) => s.locale);
  const y = youtubeDictionaries[locale];
  const status = useYoutubeImportStatus();
  const importUrl = useImportUrl();
  const cancel = useCancelJob();
  const resolve = useResolveUrl();
  const [url, setUrl] = useState("");
  const [added, setAdded] = useState<number | null>(null);
  const [asking, setAsking] = useState(false);
  const [jobId, setJobId] = useState<string | null>(null);
  // Rozilikdan keyin aniqlangan loyiha (funksiya berilgan bo'lsa) va uni olishdagi xato.
  const [pid, setPid] = useState<string | null>(typeof projectId === "string" ? projectId : null);
  const [ensuring, setEnsuring] = useState(false);
  const [projectError, setProjectError] = useState<unknown>(null);
  const job = useJobs((s) => (jobId ? s.jobs[jobId] : undefined));
  const st = status.data;
  const busy = ensuring || importUrl.isPending || job?.status === "queued" || job?.status === "running";
  const source = parseYoutubeSource(url);
  const validUrl = source !== null;
  const isList = source !== null && source.kind !== "video";
  const resolveCode = (resolve.error as { code?: unknown } | null)?.code;

  // Tugagan import natijasi har vazifa uchun bir marta uzatiladi.
  const reported = useRef<string | null>(null);
  const imported = importedVideo(job);
  useEffect(() => {
    if (!job || !imported || !pid || reported.current === job.id) return;
    reported.current = job.id;
    onImported?.(imported, pid);
  }, [job?.id, imported?.path, pid]);

  const start = async () => {
    setAsking(false);
    setProjectError(null);
    let project = typeof projectId === "string" ? projectId : null;
    if (project === null) {
      setEnsuring(true);
      try {
        project = await (projectId as () => Promise<string>)();
      } catch (cause) {
        setProjectError(cause);
        return;
      } finally {
        setEnsuring(false);
      }
    }
    setPid(project);
    if (isList && source) {
      setAdded(null);
      resolve.mutate(source.url);
      return;
    }
    importUrl.mutate(
      { project_id: project, url: url.trim(), consent: true, focus: focus || undefined, force_lite: lite },
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
      {!compact && field !== "disabled" && field !== "loading" && <div className="notice">{y.recommend}</div>}
      {field === "notInstalled" && <div className="notice bad" role="alert">{y.notInstalled}</div>}
      {field === "noJs" && <div className="notice warn">{y.noJs}</div>}
      {st?.js_runtime_outdated?.length ? (
        <div className="notice warn" role="status">{fmt(y.jsOutdated, { list: outdatedRuntimes(st) })}</div>
      ) : null}
      {st && field !== "disabled" && <YoutubeComponentsInstall st={st} />}
      <div className="row">
        <label className="field" style={{ flex: 1, minWidth: compact ? 200 : 260 }}>
          <span className={compact ? "sr-only" : undefined}>{y.url}</span>
          <input className="input" type="url" inputMode="url" placeholder={y.urlPlaceholder} value={url}
                 aria-invalid={url.trim() !== "" && !validUrl} disabled={!youtubeInputEnabled(field)}
                 aria-describedby={field === "disabled" ? "yt-disabled-note" : undefined}
                 onChange={(e) => {
                   setUrl(e.target.value);
                   resolve.reset();
                 }} />
        </label>
        {isList ? (
          <button className="btn primary" type="button" onClick={() => setAsking(true)}
                  disabled={!st?.enabled || !st?.installed || resolve.isPending || ensuring}>
            {resolve.isPending ? y.resolving : y.openList}
          </button>
        ) : (
          <button className="btn primary" type="button" onClick={() => setAsking(true)}
                  disabled={!canStart({ enabled: !!st?.enabled, installed: !!st?.installed, url, busy })}>
            {ensuring ? y.preparing : startLabel ?? y.start}
          </button>
        )}
      </div>
      {url.trim() !== "" && !validUrl && <span className="error">{y.urlInvalid}</span>}
      {source?.kind === "playlist" && <span className="muted">{y.urlPlaylist}</span>}
      {source?.kind === "channel" && <span className="muted">{y.urlChannel}</span>}
      <ErrorText error={projectError ?? importUrl.error} />
      {isYtErrorCode(resolveCode)
        ? <span className="error" role="alert">{youtubeErrors[locale][resolveCode]}</span>
        : <ErrorText error={resolve.error} />}
      {resolve.data && resolve.data.kind !== "video" && added === null && (
        resolve.data.entries.length
          ? (pid && <YoutubePlaylistPicker data={resolve.data} projectId={pid} focus={focus} lite={lite} onDone={setAdded} />)
          : <span className="muted">{youtubeErrors[locale].empty}</span>
      )}
      {added !== null && (
        <span className="row" role="status">
          <span className="muted">{fmt(y.addedToQueue, { n: added })}</span>
          {/* Navbat (BatchQueue) loyiha sahifasida - Boshlash sahifasidan u yerga havola. */}
          {compact && pid && <Link to={`/projects/${pid}`}>{y.openQueue}</Link>}
        </span>
      )}

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
              {/* YouTube o'zgarsa yt-dlp eskiradi - yangilanish ilova relizisiz, Sozlamalarda. */}
              {view.errorCode !== "network" && <Link className="btn small ghost" to="/settings#set-youtube">{y.checkUpdates}</Link>}
            </div>
          )}
          {job.status === "done" && (
            <span className="row">
              <span className="muted">{onImported && imported ? y.doneSource : y.done}</span>
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
