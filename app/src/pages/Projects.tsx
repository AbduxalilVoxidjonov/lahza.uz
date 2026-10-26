import { isTauri } from "@tauri-apps/api/core";
import { open } from "@tauri-apps/plugin-dialog";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";

import { useCreateProject, useEpisodes, useImportMedia, useProjects } from "../api/hooks";
import { useYoutubeImportStatus } from "../api/youtube";
import { BatchQueue } from "../components/batch/BatchQueue";
import { YoutubeImport } from "../components/import/YoutubeImport";
import { Empty, ErrorText } from "../components/ui";
import { useT, type MessageKey } from "../i18n";
import { youtubeDictionaries } from "../i18n/youtube";
import { useSettings } from "../store/settings";

export function Projects() {
  const t = useT();
  const { projectId } = useParams();
  const projects = useProjects();
  const create = useCreateProject();
  const [name, setName] = useState("");

  return (
    <div className="stack" style={{ gap: 20 }}>
      <div className="page-head">
        <h1>{t("proj.title")}</h1>
        <form
          className="row"
          onSubmit={(e) => {
            e.preventDefault();
            if (name.trim()) create.mutate(name.trim(), { onSuccess: () => setName("") });
          }}
        >
          <input className="input" style={{ width: 240 }} placeholder={t("proj.name")} value={name}
                 onChange={(e) => setName(e.target.value)} />
          <button className="btn primary" disabled={!name.trim() || create.isPending}>
            {t("proj.create")}
          </button>
        </form>
      </div>

      {projects.data?.length === 0 && <Empty>{t("proj.empty")}</Empty>}
      <div className="row" style={{ alignItems: "stretch" }}>
        {projects.data?.map((p) => (
          <Link key={p.id} to={`/projects/${p.id}`} className={`card nav-link${p.id === projectId ? " active" : ""}`}
                style={{ minWidth: 200 }}>
            {p.name}
          </Link>
        ))}
      </div>

      {projectId && <Episodes projectId={projectId} />}
    </div>
  );
}

function Episodes({ projectId }: { projectId: string }) {
  const t = useT();
  const episodes = useEpisodes(projectId);
  const importMedia = useImportMedia();
  const [focus, setFocus] = useState("");
  const [lite, setLite] = useState(false);
  const [manualPath, setManualPath] = useState("");
  // YT-1: "YouTube havolasi" tanlovi faqat Sozlamalarda yoqilgan bo'lsa ko'rinadi (standart o'chiq).
  const locale = useSettings((s) => s.locale);
  const y = youtubeDictionaries[locale];
  const ytEnabled = !!useYoutubeImportStatus().data?.enabled;
  const [sourceSel, setSource] = useState<"file" | "url">("file");
  const source = ytEnabled ? sourceSel : "file";

  const pick = async () => {
    let path: string | null = manualPath || null;
    if (isTauri()) {
      const res = await open({ multiple: false, filters: [{ name: "Video", extensions: ["mp4", "mov", "mkv"] }] });
      path = typeof res === "string" ? res : null;
    }
    if (path) importMedia.mutate({ project_id: projectId, path, focus: focus || undefined, force_lite: lite });
  };

  return (
    <section className="stack">
      <div className="card stack">
        <h2>{t("proj.import")}</h2>
        {ytEnabled && (
          <div className="tabs" role="tablist" aria-label={y.sourceLabel}>
            {(["file", "url"] as const).map((m) => (
              <button key={m} type="button" role="tab" aria-selected={source === m}
                      className={`tab${source === m ? " active" : ""}`} onClick={() => setSource(m)}>
                {m === "file" ? y.sourceFile : y.sourceUrl}
              </button>
            ))}
          </div>
        )}
        <div className="row">
          <input className="input" style={{ flex: 1, minWidth: 220 }} placeholder={t("proj.focus")} value={focus}
                 onChange={(e) => setFocus(e.target.value)} />
          {source === "file" && !isTauri() && (
            <input className="input" style={{ flex: 1, minWidth: 220 }} placeholder="/yo'l/video.mp4" value={manualPath}
                   onChange={(e) => setManualPath(e.target.value)} />
          )}
          <label className="row muted">
            <input type="checkbox" checked={lite} onChange={(e) => setLite(e.target.checked)} /> {t("proj.lite")}
          </label>
          {source === "file" && (
            <button className="btn primary" onClick={() => void pick()} disabled={importMedia.isPending}>
              {t("proj.import")}
            </button>
          )}
        </div>
        {source === "url" ? (
          <YoutubeImport projectId={projectId} focus={focus} lite={lite} />
        ) : (
          <>
            <span className="muted">{t("proj.importHint")}</span>
            <ErrorText error={importMedia.error} />
          </>
        )}
      </div>

      <BatchQueue projectId={projectId} />

      <h2>{t("proj.episodes")}</h2>
      <table className="table">
        <tbody>
          {episodes.data?.map((e) => (
            <tr key={e.id}>
              <td>
                <Link to={`/episodes/${e.id}`}>{e.title}</Link>
              </td>
              <td className="muted">{t(`ep.status.${e.status}` as MessageKey)}</td>
              <td className="muted mono">{e.created_at}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
