import { useState } from "react";

import { usePack } from "../../api/hooks";
import { useT } from "../../i18n";
import { joinPath } from "../../lib/dialog";
import { useJobs } from "../../store/jobs";
import { PathPicker } from "../PathPicker";
import { ErrorText, JobLine } from "../ui";

/** .lzpack: internetsiz kompyuterga modellarni ko'chirish (M2-APP-9, onboarding R0 yo'li). */
export function PackPanel({ importOnly = false }: { importOnly?: boolean }) {
  const t = useT();
  const pack = usePack();
  const job = useJobs((s) => (pack.data ? s.jobs[pack.data.id] : undefined));
  const [outDir, setOutDir] = useState("");
  const [inFile, setInFile] = useState("");
  const busy = pack.isPending || job?.status === "running" || job?.status === "queued";
  const stamp = new Date().toISOString().slice(0, 10);

  return (
    <fieldset className="fieldset stack">
      <legend>{t("pack.title")}</legend>
      <p className="muted">{t("pack.hint")}</p>
      <div className="row" style={{ alignItems: "end" }}>
        <div style={{ flex: 1 }}>
          <PathPicker label={t("pack.importFile")} value={inFile} onChange={setInFile}
                      options={{ extensions: ["lzpack"], filterName: "Lahza pack" }} />
        </div>
        <button type="button" className="btn small" disabled={!inFile || busy}
                onClick={() => pack.mutate({ mode: "import", path: inFile })}>
          {t("pack.import")}
        </button>
      </div>
      {!importOnly && (
        <div className="row" style={{ alignItems: "end" }}>
          <div style={{ flex: 1 }}>
            <PathPicker label={t("pack.exportDir")} value={outDir} onChange={setOutDir} options={{ directory: true }} />
          </div>
          <button type="button" className="btn small" disabled={!outDir || busy}
                  onClick={() => pack.mutate({ mode: "export", path: joinPath(outDir, `lahza-models-${stamp}.lzpack`) })}>
            {t("pack.export")}
          </button>
        </div>
      )}
      {job && <JobLine job={job} />}
      {job?.status === "done" && <span className="muted" role="status">{t("pack.done")}</span>}
      <ErrorText error={pack.error} />
    </fieldset>
  );
}
