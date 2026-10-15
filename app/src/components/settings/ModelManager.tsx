import { useState } from "react";

import {
  useDeleteModel,
  useInstallBundle,
  useModels,
  useScanModels,
  useSetDefaultModel,
  useTestModel,
} from "../../api/hooks";
import type { InstalledModel } from "../../api/types";
import { useT } from "../../i18n";
import { useJobs } from "../../store/jobs";
import { Empty, ErrorText, JobLine, QueryState } from "../ui";
import { PackPanel } from "./PackPanel";

/** Model menejeri (M2-APP-9): o'rnatilganlar, vazifa bo'yicha standart, o'chirish, sinov, katalogdan o'rnatish. */
export function ModelManager() {
  const t = useT();
  const models = useModels();
  const scan = useScanModels();
  const setDefault = useSetDefaultModel();
  const remove = useDeleteModel();
  const install = useInstallBundle();
  const installJob = useJobs((s) => (install.data ? s.jobs[install.data.id] : undefined));
  const err = scan.error ?? setDefault.error ?? remove.error ?? install.error;

  return (
    <section className="card stack" aria-labelledby="set-models">
      <div className="row" style={{ justifyContent: "space-between" }}>
        <h2 id="set-models" style={{ margin: 0 }}>{t("set.models")}</h2>
        <span className="row">
          <button type="button" className="btn small" disabled={scan.isPending} onClick={() => scan.mutate()}>
            {t("set.scan")}
          </button>
          <button type="button" className="btn small primary"
                  disabled={install.isPending || installJob?.status === "running"}
                  onClick={() => install.mutate()}>
            {t("set.installCatalog")}
          </button>
        </span>
      </div>
      {installJob && installJob.status !== "done" && <JobLine job={installJob} />}
      {installJob?.status === "done" && <span className="muted" role="status">{t("set.installDone")}</span>}
      <ErrorText error={err} />
      <QueryState query={models} />
      {models.data?.models.length === 0 && <Empty>{t("set.noModels")}</Empty>}
      {!!models.data?.models.length && (
        <table className="table">
          <thead>
            <tr>
              <th>{t("set.task")}</th>
              <th>{t("set.model")}</th>
              <th>{t("set.status")}</th>
              <th><span className="sr-only">{t("common.actions")}</span></th>
            </tr>
          </thead>
          <tbody>
            {models.data.models.map((m) => (
              <ModelRow
                key={m.id}
                model={m}
                isDefault={models.data?.defaults[m.task] === m.id}
                onDefault={() => setDefault.mutate(m.id)}
                onDelete={() => window.confirm(t("set.confirmDelete", { id: m.id })) && remove.mutate(m.id)}
                busy={setDefault.isPending || remove.isPending}
              />
            ))}
          </tbody>
        </table>
      )}
      <PackPanel />
    </section>
  );
}

function ModelRow({
  model: m,
  isDefault,
  onDefault,
  onDelete,
  busy,
}: {
  model: InstalledModel;
  isDefault: boolean;
  onDefault: () => void;
  onDelete: () => void;
  busy: boolean;
}) {
  const t = useT();
  const test = useTestModel();
  const [shown, setShown] = useState(false);
  return (
    <tr>
      <td>{t(`task.${m.task}`)}</td>
      <td>
        <span className="mono">{m.id}</span> <span className="muted mono">v{m.version}</span>
        {shown && test.data && (
          <div className={test.data.ok ? "good-text" : "error"} role="status">
            {test.data.ok ? t("set.testOk") : t("set.testFail")}: {test.data.detail}
          </div>
        )}
        {shown && <ErrorText error={test.error} />}
      </td>
      <td>
        <span className="row" style={{ gap: 6 }}>
          {isDefault && <span className="badge good">{t("set.default")}</span>}
          {!m.verified && <span className="badge warn">{t("set.custom")}</span>}
        </span>
      </td>
      <td>
        <span className="row" style={{ gap: 6, justifyContent: "end" }}>
          {!isDefault && (
            <button type="button" className="btn small" disabled={busy} onClick={onDefault}>{t("set.makeDefault")}</button>
          )}
          <button type="button" className="btn small" disabled={test.isPending}
                  onClick={() => {
                    setShown(true);
                    test.mutate(m.id);
                  }}>
            {test.isPending ? t("set.testing") : t("set.test")}
          </button>
          <button type="button" className="btn small bad" disabled={busy} onClick={onDelete}
                  aria-label={t("set.deleteModel", { id: m.id })}>
            {t("common.delete")}
          </button>
        </span>
      </td>
    </tr>
  );
}
