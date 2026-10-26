import { useState } from "react";

import { ApiError } from "../../api/client";
import { useAsrQuality, useCancelJob, useSetAsrQuality } from "../../api/hooks";
import { useT } from "../../i18n";
import { activeQualityJob, approxMb, chooseAction, selectedMode, type QualityMode } from "../../lib/asr-quality";
import { describeError } from "../../lib/error-codes";
import { useJobs } from "../../store/jobs";
import { PathPicker } from "../PathPicker";
import { CodedErrorText, JobLine, QueryState } from "../ui";

/** Transkripsiya sifati: Tez (NavAI base, standart) / Aniq (NavAI small, ixtiyoriy yuklanadi). */
export function AsrQualityPanel() {
  const t = useT();
  const status = useAsrQuality();
  const choose = useSetAsrQuality();
  const cancel = useCancelJob();
  const [offer, setOffer] = useState(false);
  const [packFile, setPackFile] = useState("");
  const [jobId, setJobId] = useState<string | null>(null);
  const job = useJobs((s) => (jobId ? s.jobs[jobId] : activeQualityJob(s.jobs)));
  const running = job?.status === "running" || job?.status === "queued";
  const busy = choose.isPending || running;
  const data = status.data;
  const size = approxMb(data?.accurate.download_bytes || 251_966_951);

  const submit = (v: { mode: QualityMode; consent?: boolean; pack_path?: string }) =>
    choose.mutate(v, {
      onSuccess: (res) => {
        setJobId(res.job?.id ?? null);
        if (!res.job) setOffer(false);
      },
    });

  const pick = (mode: QualityMode) => {
    if (!data) return;
    const action = chooseAction(data, mode);
    if (action === "none") return setOffer(false);
    if (action === "offer") return setOffer(true);
    setJobId(null);
    submit({ mode });
  };

  const err = choose.error;
  const selected = data ? selectedMode(data) : null;
  const shown: QualityMode | null = offer || running ? "accurate" : selected;

  return (
    <fieldset className="fieldset stack" aria-describedby="asrq-old">
      <legend>{t("asrq.title")}</legend>
      <QueryState query={status} />
      {data && (
        <>
          <label className="row" style={{ alignItems: "start", gap: 8 }}>
            <input type="radio" name="asr-quality" value="fast" checked={shown === "fast"}
                   disabled={busy} onChange={() => pick("fast")} />
            <span className="stack" style={{ gap: 2 }}>
              <span>{t("asrq.fast")}</span>
              <span className="muted">{t("asrq.fastHint")}</span>
            </span>
          </label>
          <label className="row" style={{ alignItems: "start", gap: 8 }}>
            <input type="radio" name="asr-quality" value="accurate" checked={shown === "accurate"}
                   disabled={busy} onChange={() => pick("accurate")} />
            <span className="stack" style={{ gap: 2 }}>
              <span>{t("asrq.accurate")}</span>
              <span className="muted">
                {data.accurate.installed ? t("asrq.accurateInstalledHint") : t("asrq.accurateHint", { size })}
              </span>
            </span>
          </label>
          {data.mode === "custom" && data.current_model_id && (
            <span className="muted" role="status">{t("asrq.custom", { id: data.current_model_id })}</span>
          )}
          {offer && !running && !data.accurate.installed && (
            <div className="card stack" role="group" aria-label={t("asrq.accurate")}>
              <span>{t("asrq.offer", { size })}</span>
              {data.accurate.download_available ? (
                <span className="row">
                  <button type="button" className="btn small primary" disabled={busy}
                          onClick={() => submit({ mode: "accurate", consent: true })}>
                    {t("asrq.download")}
                  </button>
                </span>
              ) : (
                <span className="muted">{t("asrq.noDownload")}</span>
              )}
              <div className="row" style={{ alignItems: "end" }}>
                <div style={{ flex: 1 }}>
                  <PathPicker label={t("asrq.packFile")} value={packFile} onChange={setPackFile}
                              options={{ extensions: ["lzpack"], filterName: "Lahza pack" }} />
                </div>
                <button type="button" className="btn small" disabled={!packFile || busy}
                        onClick={() => submit({ mode: "accurate", pack_path: packFile })}>
                  {t("asrq.importPack")}
                </button>
              </div>
              <span className="row">
                <button type="button" className="btn small ghost" disabled={busy} onClick={() => setOffer(false)}>
                  {t("asrq.dismiss")}
                </button>
              </span>
            </div>
          )}
          {job && job.status !== "done" && (
            <JobLine job={job} onCancel={cancel.isPending ? undefined : () => cancel.mutate(job.id)} />
          )}
          {job?.status === "done" && <span className="muted" role="status">{t("asrq.done")}</span>}
          {!job && choose.isSuccess && <span className="muted" role="status">{t("asrq.switched")}</span>}
          {err && (
            <CodedErrorText view={err instanceof ApiError
              ? describeError(err.code, err.params, err.message)
              : describeError(null, null, err instanceof Error ? err.message : String(err))} />
          )}
          {cancel.error && <CodedErrorText view={describeError(null, null, String(cancel.error))} />}
          <span id="asrq-old" className="muted">{t("asrq.oldProjects")}</span>
        </>
      )}
    </fieldset>
  );
}
