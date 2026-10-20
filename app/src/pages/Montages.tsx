import { Link } from "react-router-dom";

import { useDeleteMontage, useMontages, useTemplates } from "../api/hooks";
import type { MontageStatus } from "../api/types";
import { Empty, ErrorText, fmtTime, QueryState } from "../components/ui";
import { useT } from "../i18n";
import { localText } from "../lib/montage";
import { useSettings } from "../store/settings";

export function MontageStatusBadge({ status }: { status: MontageStatus }) {
  const t = useT();
  const cls = status === "ready" ? "good" : status === "failed" ? "bad" : "accent";
  return <span className={`badge ${cls}`}>{t(`mon.status.${status}`)}</span>;
}

function fmtDate(s: string | undefined, locale: string): string {
  if (!s) return "";
  const d = new Date(s);
  if (Number.isNaN(d.getTime())) return s;
  return d.toLocaleString(locale === "uz-Cyrl" ? "uz" : locale, { dateStyle: "medium", timeStyle: "short" });
}

/** Montajlar ro'yxati. */
export function Montages() {
  const t = useT();
  const locale = useSettings((s) => s.locale);
  const montages = useMontages();
  const templates = useTemplates();
  const remove = useDeleteMontage();
  const tplName = (id: string) => {
    const x = templates.data?.find((tp) => tp.id === id);
    return x ? localText(x.name, locale) : id;
  };

  return (
    <div className="stack" style={{ gap: 16 }}>
      <div className="page-head">
        <h1>{t("nav.montages")}</h1>
        <div className="row">
          <Link to="/templates" className="btn" style={{ textDecoration: "none" }}>{t("nav.templates")}</Link>
          <Link to="/montages/new" className="btn primary" style={{ textDecoration: "none" }}>{t("mon.new")}</Link>
        </div>
      </div>
      <QueryState query={montages} />
      <ErrorText error={remove.error} />
      {montages.data?.length === 0 && (
        <Empty>{t("mon.empty")} <Link to="/templates">{t("mon.emptyCta")}</Link></Empty>
      )}
      <ul className="grid plain-list" aria-label={t("nav.montages")}>
        {montages.data?.map((m) => (
          <li key={m.id} className="card stack" style={{ gap: 8 }}>
            <div className="row" style={{ justifyContent: "space-between", alignItems: "flex-start" }}>
              <Link to={`/montages/${m.id}`} className="tpl-title">{m.name || m.id}</Link>
              <MontageStatusBadge status={m.status} />
            </div>
            <span className="muted">{tplName(m.template_id)}</span>
            <span className="muted mono">
              {m.duration_ms ? fmtTime(m.duration_ms) : "—"} · {fmtDate(m.updated_at || m.created_at, locale)}
            </span>
            <div className="row" style={{ marginTop: "auto" }}>
              <Link to={`/montages/${m.id}`} className="btn small primary" style={{ textDecoration: "none" }}>{t("mon.open")}</Link>
              <button type="button" className="btn small ghost bad" disabled={remove.isPending}
                      onClick={() => window.confirm(t("mon.confirmDelete", { name: m.name || m.id })) && remove.mutate(m.id)}>
                {t("common.delete")}
              </button>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
