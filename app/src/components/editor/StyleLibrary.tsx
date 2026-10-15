import { useState } from "react";

import { useDeleteStyle, useExportStyle, useImportStyle, useSaveStyle, useStyles } from "../../api/hooks";
import type { StyleTemplate } from "../../api/types";
import { useT } from "../../i18n";
import { joinPath, safeName } from "../../lib/dialog";
import { PathPicker } from "../PathPicker";
import { ErrorText, QueryState } from "../ui";

/** Saqlangan brend shablonlari: yuklash, saqlash, yangilash, o'chirish, fayl orqali import/eksport. */
export function StyleLibrary({ style, onLoad }: { style: StyleTemplate; onLoad: (s: StyleTemplate) => void }) {
  const t = useT();
  const styles = useStyles();
  const saveStyle = useSaveStyle();
  const delStyle = useDeleteStyle();
  const importStyle = useImportStyle();
  const exportStyle = useExportStyle();
  const [selId, setSelId] = useState("");
  const [name, setName] = useState(style.name);
  const [filePath, setFilePath] = useState("");
  const [dirPath, setDirPath] = useState("");
  const [io, setIo] = useState(false);
  const current = styles.data?.find((s) => s.id === selId);
  const err = saveStyle.error ?? delStyle.error ?? importStyle.error ?? exportStyle.error;

  return (
    <fieldset className="fieldset stack">
      <legend>{t("style.library")}</legend>
      <QueryState query={styles} />
      <div className="row">
        <select className="select" style={{ flex: 1 }} aria-label={t("style.saved")} value={selId}
                onChange={(e) => {
                  setSelId(e.target.value);
                  const rec = styles.data?.find((s) => s.id === e.target.value);
                  if (rec) setName(rec.name);
                }}>
          <option value="">{styles.data?.length ? t("style.pick") : t("style.noSaved")}</option>
          {styles.data?.map((s) => (
            <option key={s.id} value={s.id}>{s.name}</option>
          ))}
        </select>
        <button type="button" className="btn small" disabled={!current} onClick={() => current && onLoad({ ...current.template, name: current.name })}>
          {t("style.load")}
        </button>
        <button type="button" className="btn small ghost" disabled={!current || delStyle.isPending}
                onClick={() => current && window.confirm(t("style.confirmDelete", { name: current.name })) &&
                  delStyle.mutate(current.id, { onSuccess: () => setSelId("") })}>
          {t("common.delete")}
        </button>
      </div>
      <div className="row">
        <input className="input" style={{ flex: 1 }} aria-label={t("style.name")} placeholder={t("style.name")}
               value={name} onChange={(e) => setName(e.target.value)} />
        <button type="button" className="btn small" disabled={!name.trim() || saveStyle.isPending}
                onClick={() => saveStyle.mutate({ name: name.trim(), template: { ...style, name: name.trim() } },
                  { onSuccess: (r) => setSelId(r.id) })}>
          {t("style.saveNew")}
        </button>
        <button type="button" className="btn small" disabled={!current || saveStyle.isPending}
                onClick={() => current && saveStyle.mutate({ id: current.id, name: name.trim() || current.name, template: { ...style, name: name.trim() || current.name } })}>
          {t("style.update")}
        </button>
        <button type="button" className="btn small ghost" aria-expanded={io} onClick={() => setIo((v) => !v)}>
          {t("style.importExport")}
        </button>
      </div>
      {io && (
        <div className="stack">
          <div className="row" style={{ alignItems: "end" }}>
            <div style={{ flex: 1 }}>
              <PathPicker label={t("style.importFile")} value={filePath} onChange={setFilePath}
                          options={{ extensions: ["json"], filterName: "JSON" }} />
            </div>
            <button type="button" className="btn small" disabled={!filePath || importStyle.isPending}
                    onClick={() => importStyle.mutate(filePath, { onSuccess: (r) => { setSelId(r.id); onLoad({ ...r.template, name: r.name }); } })}>
              {t("style.import")}
            </button>
          </div>
          <div className="row" style={{ alignItems: "end" }}>
            <div style={{ flex: 1 }}>
              <PathPicker label={t("style.exportDir")} value={dirPath} onChange={setDirPath} options={{ directory: true }} />
            </div>
            <button type="button" className="btn small" disabled={!current || !dirPath || exportStyle.isPending}
                    onClick={() => current && exportStyle.mutate({ id: current.id, path: joinPath(dirPath, `${safeName(current.name)}.json`) })}>
              {t("style.export")}
            </button>
          </div>
          {exportStyle.isSuccess && <span className="muted" role="status">{t("common.saved")}</span>}
        </div>
      )}
      <ErrorText error={err} />
    </fieldset>
  );
}
