import { useState } from "react";

import { useDeleteLexicon, useLexicon, useProjects } from "../../api/hooks";
import { useT } from "../../i18n";
import { LexiconForm } from "../transcript/LexiconForm";
import { Empty, ErrorText, QueryState } from "../ui";

/** Lug'at (ismlar, brendlar, atamalar): ASR va imlo normalizatsiyasi uchun. */
export function LexiconManager() {
  const t = useT();
  const projects = useProjects();
  const [projectId, setProjectId] = useState("");
  const lex = useLexicon(projectId || undefined);
  const del = useDeleteLexicon();
  return (
    <section className="card stack" aria-labelledby="set-lex">
      <div className="row" style={{ justifyContent: "space-between" }}>
        <h2 id="set-lex" style={{ margin: 0 }}>{t("lex.title")}</h2>
        <select className="select" style={{ width: 240 }} aria-label={t("lex.scope")} value={projectId}
                onChange={(e) => setProjectId(e.target.value)}>
          <option value="">{t("lex.global")}</option>
          {projects.data?.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
        </select>
      </div>
      <LexiconForm key={projectId} showId={projectId || undefined} />
      <QueryState query={lex} />
      <ErrorText error={del.error} />
      {lex.data?.length === 0 && <Empty>{t("lex.empty")}</Empty>}
      {!!lex.data?.length && (
        <table className="table">
          <thead>
            <tr>
              <th>{t("lex.term")}</th>
              <th>{t("lex.variants")}</th>
              <th>{t("lex.kind")}</th>
              <th><span className="sr-only">{t("common.actions")}</span></th>
            </tr>
          </thead>
          <tbody>
            {lex.data.map((e) => (
              <tr key={e.id}>
                <td>{e.term}</td>
                <td className="muted">{e.variants.join(", ") || "—"}</td>
                <td>
                  {t(`lex.kind.${e.kind}`)}
                  {!e.show_id && <span className="badge" style={{ marginLeft: 6 }}>{t("lex.globalBadge")}</span>}
                </td>
                <td>
                  <button type="button" className="btn small ghost" disabled={del.isPending}
                          aria-label={t("lex.delete", { term: e.term })} onClick={() => del.mutate(e.id)}>
                    ✕
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
