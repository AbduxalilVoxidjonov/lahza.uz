import { useEffect, useState } from "react";

import { useInstallYoutubeComponents, useRefreshYoutubeImport, type YoutubeImportStatus } from "../../api/youtube";
import { fmt, youtubeDictionaries } from "../../i18n/youtube";
import { fmtBytes } from "../../lib/youtube-import";
import { useJobs } from "../../store/jobs";
import { useSettings } from "../../store/settings";
import { ErrorText, ProgressBar } from "../ui";

/** ADR-0010 2-band: yt-dlp, yt-dlp-ejs va Deno ilovaga kirmaydi - shu tugma bilan bir marta yuklanadi. */
export function YoutubeComponentsInstall({ st }: { st: YoutubeImportStatus }) {
  const locale = useSettings((s) => s.locale);
  const y = youtubeDictionaries[locale];
  const install = useInstallYoutubeComponents();
  const refresh = useRefreshYoutubeImport();
  const [jobId, setJobId] = useState<string | null>(st.install_job?.id ?? null);
  const job = useJobs((s) => (jobId ? s.jobs[jobId] : undefined)) ?? (jobId === st.install_job?.id ? st.install_job : undefined);
  const running = install.isPending || job?.status === "queued" || job?.status === "running";

  useEffect(() => {
    if (job?.status === "done" || job?.status === "failed") void refresh();
    // `refresh` har renderda yangi funksiya; faqat holat o'zgarganda qayta so'raladi.
  }, [job?.status]);

  if (st.components_ready && !running) {
    return job?.status === "done" ? <span className="muted">{y.installDone}</span> : null;
  }
  const component = job?.stage ?? "…";
  return (
    <div className="stack" style={{ gap: 6 }} aria-live="polite">
      <span className="muted">{y.installHint}</span>
      {running ? (
        <>
          <span>{fmt(y.installing, { component })}</span>
          <ProgressBar value={job?.progress ?? 0} label={y.setTitle} />
        </>
      ) : (
        <button className="btn primary" type="button" style={{ alignSelf: "flex-start" }}
                onClick={() => install.mutate(undefined, { onSuccess: (res) => setJobId(res.job.id) })}>
          {fmt(y.installComponents, { size: fmtBytes(st.components_download_bytes) })}
        </button>
      )}
      {job?.status === "failed" && <span className="error" role="alert">{fmt(y.installFailed, { error: job.error ?? "" })}</span>}
      <ErrorText error={install.error} />
    </div>
  );
}
