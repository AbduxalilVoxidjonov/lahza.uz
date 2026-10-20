import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { errorText } from "../api/client";
import {
  useDeleteTemplate,
  useDuplicateTemplate,
  useExportTemplate,
  useImportTemplate,
  useTemplates,
} from "../api/hooks";
import type { Template } from "../api/types";
import { CategoryTabs, filterTemplates, type CategoryFilter } from "../components/templates/CategoryTabs";
import { TemplateCard } from "../components/templates/TemplateCard";
import { Empty, ErrorText, QueryState } from "../components/ui";
import { useT } from "../i18n";
import { hasNativeDialog, joinPath, pickPath, safeName } from "../lib/dialog";
import { localText } from "../lib/montage";
import { useSettings } from "../store/settings";

/** Shablonlar galereyasi (docs/11 8.1): toifalar, preset kartalari, "Qo'llash". */
export function Templates() {
  const t = useT();
  const navigate = useNavigate();
  const locale = useSettings((s) => s.locale);
  const templates = useTemplates();
  const dup = useDuplicateTemplate();
  const remove = useDeleteTemplate();
  const imp = useImportTemplate();
  const exp = useExportTemplate();
  const [cat, setCat] = useState<CategoryFilter>("all");
  const [msg, setMsg] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const list = templates.data ?? [];
  const shown = filterTemplates(list, cat);

  const onImport = async () => {
    setError(null);
    setMsg(null);
    const path = hasNativeDialog()
      ? await pickPath({ title: t("tpl.import"), extensions: ["json"], filterName: "Lahza template" })
      : window.prompt(t("tpl.importPrompt"));
    if (!path) return;
    imp.mutate(path.trim(), {
      onSuccess: (tpl) => setMsg(t("tpl.imported", { name: localText(tpl.name, locale) })),
      onError: (e) => setError(errorText(e)),
    });
  };

  const onExport = async (tpl: Template) => {
    setError(null);
    setMsg(null);
    const file = `${safeName(localText(tpl.name, locale) || tpl.id)}.json`;
    let path: string | null = null;
    if (hasNativeDialog()) {
      const dir = await pickPath({ directory: true, title: t("tpl.exportDir") });
      path = dir ? joinPath(dir, file) : null;
    } else {
      path = window.prompt(t("tpl.exportPrompt"), file);
    }
    if (!path) return;
    exp.mutate({ id: tpl.id, path: path.trim() }, {
      onSuccess: () => setMsg(t("tpl.exported", { path: path ?? "" })),
      onError: (e) => setError(errorText(e)),
    });
  };

  const onDuplicate = (tpl: Template, edit: boolean) =>
    dup.mutate({ id: tpl.id }, {
      onSuccess: (copy) => (edit ? navigate(`/templates/${encodeURIComponent(copy.id)}`) : setMsg(t("tpl.duplicated"))),
    });

  const onDelete = (tpl: Template) => {
    if (window.confirm(t("tpl.confirmDelete", { name: localText(tpl.name, locale) }))) remove.mutate(tpl.id);
  };

  return (
    <div className="stack" style={{ gap: 16 }}>
      <div className="page-head">
        <div>
          <h1>{t("tpl.title")}</h1>
          <p className="lead">{t("tpl.lead")}</p>
        </div>
        <div className="row">
          <button type="button" className="btn" onClick={() => void onImport()} disabled={imp.isPending}>
            {t("tpl.import")}
          </button>
          <Link to="/templates/new" className="btn primary" style={{ textDecoration: "none" }}>{t("tpl.new")}</Link>
        </div>
      </div>

      <QueryState query={templates} />
      {msg && <span className="muted" role="status">{msg}</span>}
      {error && <span className="error" role="alert">{t("common.error", { msg: error })}</span>}
      <ErrorText error={dup.error ?? remove.error} />

      {templates.data && (
        <>
          <CategoryTabs value={cat} onChange={setCat} templates={list} />
          {shown.length === 0 && <Empty>{cat === "mine" ? t("tpl.emptyMine") : t("tpl.empty")}</Empty>}
          <div className="grid" role="list" aria-label={t("tpl.title")}>
            {shown.map((tpl) => (
              <div role="listitem" key={tpl.id} style={{ display: "flex" }}>
                <TemplateCard
                  tpl={tpl}
                  actions={
                    <>
                      <button type="button" className="btn small primary"
                              onClick={() => navigate(`/montages/new?template=${encodeURIComponent(tpl.id)}`)}>
                        {t("tpl.apply")}
                      </button>
                      <button type="button" className="btn small" disabled={dup.isPending} onClick={() => onDuplicate(tpl, false)}>
                        {t("tpl.duplicate")}
                      </button>
                      <Link to={`/templates/${encodeURIComponent(tpl.id)}`} className="btn small ghost" style={{ textDecoration: "none" }}>
                        {tpl.builtin ? t("tpl.view") : t("tpl.edit")}
                      </Link>
                      <button type="button" className="btn small ghost" onClick={() => void onExport(tpl)}>
                        {t("tpl.export")}
                      </button>
                      {!tpl.builtin && (
                        <button type="button" className="btn small ghost bad" onClick={() => onDelete(tpl)}>
                          {t("common.delete")}
                        </button>
                      )}
                    </>
                  }
                />
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
