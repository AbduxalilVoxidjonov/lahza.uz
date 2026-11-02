import { useState } from "react";

import { useDiagnostics, useReveal } from "../../api/hooks";
import { useT } from "../../i18n";
import { PathPicker } from "../PathPicker";
import { ErrorText } from "../ui";

/** Diagnostika paketi (M2-APP-11): versiyalar, apparat, oxirgi loglar - transkript matnisiz. */
export function DiagnosticsPanel() {
  const t = useT();
  const diag = useDiagnostics();
  const reveal = useReveal();
  const [dir, setDir] = useState("");
  return (
    <section className="card stack" aria-labelledby="set-diag">
      <h2 id="set-diag">{t("diag.title")}</h2>
      <p className="muted">{t("diag.hint")}</p>
      <div className="row" style={{ alignItems: "end" }}>
        <div style={{ flex: 1 }}>
          <PathPicker label={t("diag.dir")} value={dir} onChange={setDir} options={{ directory: true }} />
        </div>
        <button type="button" className="btn small" disabled={!dir || diag.isPending} onClick={() => diag.mutate(dir)}>
          {diag.isPending ? t("common.loading") : t("diag.create")}
        </button>
      </div>
      {diag.data && (
        <span className="row" role="status">
          <span className="muted mono">{t("diag.done", { path: diag.data.path })}</span>
          <button type="button" className="btn small" onClick={() => diag.data && reveal.mutate(diag.data.path)}>
            {t("exp.reveal")}
          </button>
        </span>
      )}
      <ErrorText error={diag.error ?? reveal.error} />
    </section>
  );
}
