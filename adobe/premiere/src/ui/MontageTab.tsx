import { useEffect, useState } from "react";

import type { Job, Template } from "@shared/types";
import { baseName, makeMontage, type FlowDeps } from "../flow";
import type { BuildResult, BuildStep } from "../host/adapter";
import type { Locale } from "../i18n";
import { BuildProgress, BuildResultView, ErrorLine, ProgressBar, Section, errMsg, useT } from "./common";

export function MontageTab({ deps, locale }: { deps: FlowDeps; locale: Locale }) {
  const t = useT();
  const [templates, setTemplates] = useState<Template[] | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [paths, setPaths] = useState<string[]>([]);
  const [job, setJob] = useState<Job | null>(null);
  const [step, setStep] = useState<BuildStep | null>(null);
  const [result, setResult] = useState<BuildResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = async () => {
    try {
      setPaths(await deps.adapter.selectedMediaPaths());
    } catch (e) {
      setError(errMsg(e));
    }
  };

  useEffect(() => {
    deps.client
      .templates()
      .then((ts) => {
        setTemplates(ts);
        setSelected((s) => s ?? ts[0]?.id ?? null);
      })
      .catch((e) => setError(errMsg(e)));
    void refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [deps]);

  const run = async () => {
    const tpl = templates?.find((x) => x.id === selected);
    if (!tpl) return;
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      const r = await makeMontage(deps, tpl, paths, setJob, setStep);
      setResult(r.result);
    } catch (e) {
      setError(errMsg(e));
    } finally {
      setBusy(false);
      setJob(null);
      setStep(null);
    }
  };

  const name = (tp: Template) => (locale === "en" ? (tp.name.en ?? tp.name.uz) : tp.name.uz);

  return (
    <div className="stack">
      <Section title={t("montage.templates")}>
        {templates === null ? (
          <div className="muted small">{t("common.loading")}</div>
        ) : templates.length === 0 ? (
          <div className="muted small">{t("montage.no_templates")}</div>
        ) : (
          <ul className="templates">
            {templates.map((tp) => (
              <li key={tp.id}>
                <label className={`tpl ${selected === tp.id ? "active" : ""}`}>
                  <input type="radio" name="tpl" checked={selected === tp.id} onChange={() => setSelected(tp.id)} />
                  <span className="grow">{name(tp)}</span>
                  <span className="badge">{tp.aspect}</span>
                  <span className="muted small">{Math.round(tp.target_duration_ms / 1000)} s</span>
                </label>
              </li>
            ))}
          </ul>
        )}
      </Section>
      <Section
        title={t("montage.sources", { n: paths.length })}
        aside={
          <button className="btn small ghost" onClick={() => void refresh()} disabled={busy}>
            {t("analyze.refresh")}
          </button>
        }
      >
        {paths.length === 0 ? (
          <div className="small">{t("analyze.none")}</div>
        ) : (
          <ul className="paths">
            {paths.map((p) => (
              <li key={p} className="mono" title={p}>
                {baseName(p)}
              </li>
            ))}
          </ul>
        )}
        <button className="btn primary" onClick={() => void run()} disabled={busy || !paths.length || !selected}>
          {t("montage.run")}
        </button>
        {job && (
          <div className="stack-sm">
            <div className="muted small">{t("montage.running", { stage: job.stage ?? job.status })}</div>
            <ProgressBar value={job.progress} />
          </div>
        )}
        <BuildProgress step={step} />
        <ErrorLine error={error} />
        <BuildResultView result={result} />
      </Section>
    </div>
  );
}
