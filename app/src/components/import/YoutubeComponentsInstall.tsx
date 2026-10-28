import { useEffect, useState } from "react";

import {
  useCheckYoutubeUpdates, useInstallYoutubeComponents, useRefreshYoutubeImport, type YoutubeImportStatus,
} from "../../api/youtube";
import { fmt, youtubeDictionaries } from "../../i18n/youtube";
import { fmtBytes } from "../../lib/youtube-import";
import { useJobs } from "../../store/jobs";
import { useSettings } from "../../store/settings";
import { ErrorText, ProgressBar } from "../ui";

const versionList = (v: Record<string, string>) =>
  Object.entries(v).map(([name, ver]) => `${name} ${ver}`).join(", ");

/**
 * ADR-0010 2-band: yt-dlp, yt-dlp-ejs va Deno ilovaga kirmaydi - shu tugma bilan bir marta yuklanadi.
 * Yangilanish ilova relizisiz: PyPI/GitHub'dagi oxirgi versiya (`check` faqat tugma bosilganda).
 */
export function YoutubeComponentsInstall({ st, updates = false }: { st: YoutubeImportStatus; updates?: boolean }) {
  const locale = useSettings((s) => s.locale);
  const y = youtubeDictionaries[locale];
  const install = useInstallYoutubeComponents();
  const check = useCheckYoutubeUpdates();
  const refresh = useRefreshYoutubeImport();
  const [jobId, setJobId] = useState<string | null>(st.install_job?.id ?? null);
  const job = useJobs((s) => (jobId ? s.jobs[jobId] : undefined)) ?? (jobId === st.install_job?.id ? st.install_job : undefined);
  const running = install.isPending || job?.status === "queued" || job?.status === "running";

  useEffect(() => {
    if (job?.status === "done" || job?.status === "failed") {
      void refresh();
      check.reset();
    }
    // `refresh`/`check` har renderda yangi obyekt; faqat vazifa holati o'zgarganda.
  }, [job?.status]);

  const start = (update: boolean) => install.mutate(update, { onSuccess: (res) => setJobId(res.job.id) });
  const progress = running && (
    <>
      <span>{fmt(y.installing, { component: job?.stage ?? "…" })}</span>
      <ProgressBar value={job?.progress ?? 0} label={y.setTitle} />
    </>
  );
  const failed = job?.status === "failed" && (
    <span className="error" role="alert">{fmt(y.installFailed, { error: job.error ?? "" })}</span>
  );

  if (st.components_ready && !running) {
    if (!updates) return job?.status === "done" ? <span className="muted">{y.installDone}</span> : null;
    const u = check.data;
    return (
      <div className="stack" style={{ gap: 6 }} aria-live="polite">
        <span className="muted mono">{fmt(y.versions, { list: versionList(st.component_versions) })}</span>
        <div className="row">
          <button className="btn small" type="button" disabled={check.isPending} onClick={() => check.mutate()}>
            {check.isPending ? y.checking : y.checkUpdates}
          </button>
          {u && !u.update_available && <span className="muted">{y.upToDate}</span>}
          {u?.update_available && (
            <>
              <span>{fmt(y.updateAvailable, { list: versionList(u.latest) })}</span>
              <button className="btn small primary" type="button" onClick={() => start(true)}>
                {fmt(y.updateNow, { size: fmtBytes(u.download_bytes) })}
              </button>
            </>
          )}
        </div>
        {failed}
        <ErrorText error={check.error ?? install.error} />
      </div>
    );
  }
  return (
    <div className="stack" style={{ gap: 6 }} aria-live="polite">
      <span className="muted">{y.installHint}</span>
      {progress || (
        <button className="btn primary" type="button" style={{ alignSelf: "flex-start" }} onClick={() => start(false)}>
          {fmt(y.installComponents, { size: fmtBytes(st.components_download_bytes) })}
        </button>
      )}
      {failed}
      <ErrorText error={install.error} />
    </div>
  );
}
