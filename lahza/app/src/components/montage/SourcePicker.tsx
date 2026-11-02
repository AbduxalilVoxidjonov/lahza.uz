// Montaj uchun videolarni tanlash: fayllar, loyiha kliplari yoki butun epizod.
import { memo, useState } from "react";

import { useClips, useEpisodes, useObjectUrl, usePreviewFrame, useProjects } from "../../api/hooks";
import type { Clip, MontageSource } from "../../api/types";
import { useT } from "../../i18n";
import { baseName, hasNativeDialog, pickPaths, VIDEO_EXTS } from "../../lib/dialog";
import { useInView } from "../../lib/useInView";
import { outDuration } from "../../lib/words";
import { useSettings } from "../../store/settings";
import { Empty, fmtTime, QueryState } from "../ui";

export interface PickedSource {
  key: string;
  source: MontageSource;
  label: string;
  detail?: string;
  projectId?: string;
}

export const sourceKey = (s: MontageSource) =>
  s.kind === "file" ? `file:${s.path}` : s.kind === "clip" ? `clip:${s.episode_id}/${s.clip_id}` : `episode:${s.episode_id}`;

type Mode = "files" | "clips" | "episode";

export function SourcePicker({ picked, onAdd, onRemoveKey }: {
  picked: PickedSource[];
  onAdd: (items: PickedSource[]) => void;
  onRemoveKey: (key: string) => void;
}) {
  const t = useT();
  const [mode, setMode] = useState<Mode>("files");
  const modes: Mode[] = ["files", "clips", "episode"];
  return (
    <div className="stack">
      <details className="quick-details"><summary>{t("quick.library")}</summary>
      <div className="tabs" role="tablist" aria-label={t("mon.srcKinds")}>
        {modes.map((m) => (
          <button key={m} type="button" role="tab" aria-selected={mode === m} className={`tab${mode === m ? " active" : ""}`}
                  onClick={() => setMode(m)}>
            {t(`mon.src.${m}`)}
          </button>
        ))}
      </div>
      </details>
      {mode === "files" && <FilesPicker onAdd={onAdd} />}
      {mode !== "files" && <ProjectPicker mode={mode} picked={picked} onAdd={onAdd} onRemoveKey={onRemoveKey} />}
    </div>
  );
}

function FilesPicker({ onAdd }: { onAdd: (items: PickedSource[]) => void }) {
  const t = useT();
  const [path, setPath] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [picking, setPicking] = useState(false);
  const add = (paths: string[]) =>
    onAdd(paths.filter(Boolean).map((p) => {
      const source: MontageSource = { kind: "file", path: p };
      return { key: sourceKey(source), source, label: baseName(p), detail: p };
    }));
  if (hasNativeDialog()) {
    return (
      <div className="upload-start stack">
        <span className="upload-symbol" aria-hidden="true">↑</span>
        <button type="button" className="btn primary" disabled={picking}
                onClick={async () => {
                  setPicking(true); setError(null);
                  try { add(await pickPaths({ title: t("mon.pickFiles"), extensions: VIDEO_EXTS, filterName: "Video" })); }
                  catch (cause) { setError(cause instanceof Error ? cause.message : String(cause)); }
                  finally { setPicking(false); }
                }}>
          {t("mon.pickFiles")}
        </button>
        <span className="muted">{t("mon.pickFilesHint")}</span>
        {error && <span className="error" role="alert">{error}</span>}
      </div>
    );
  }
  return (
    <div className="upload-start stack">
    <p className="muted">{t("quick.browser")}</p>
    <form className="row"
          onSubmit={(e) => {
            e.preventDefault();
            if (path.trim()) {
              add([path.trim()]);
              setPath("");
            }
          }}>
      <label className="sr-only" htmlFor="mon-path">{t("mon.filePath")}</label>
      <input id="mon-path" className="input mono" value={path} placeholder={t("mon.filePathPh")} onChange={(e) => setPath(e.target.value)} />
      <button className="btn" disabled={!path.trim()}>{t("mon.add")}</button>
    </form>
    </div>
  );
}

function ProjectPicker({ mode, picked, onAdd, onRemoveKey }: {
  mode: "clips" | "episode";
  picked: PickedSource[];
  onAdd: (items: PickedSource[]) => void;
  onRemoveKey: (key: string) => void;
}) {
  const t = useT();
  const projects = useProjects();
  const [projectId, setProjectId] = useState("");
  const [episodeId, setEpisodeId] = useState("");
  const episodes = useEpisodes(projectId || undefined);
  const has = (key: string) => picked.some((p) => p.key === key);

  return (
    <div className="stack">
      <div className="row" style={{ alignItems: "flex-end" }}>
        <label className="field" style={{ minWidth: 200 }}>
          {t("mon.project")}
          <select className="select" value={projectId} onChange={(e) => { setProjectId(e.target.value); setEpisodeId(""); }}>
            <option value="">—</option>
            {projects.data?.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
          </select>
        </label>
        {mode === "clips" && (
          <label className="field" style={{ minWidth: 240 }}>
            {t("mon.episode")}
            <select className="select" value={episodeId} disabled={!projectId} onChange={(e) => setEpisodeId(e.target.value)}>
              <option value="">—</option>
              {episodes.data?.filter((e) => e.status === "ready").map((e) => <option key={e.id} value={e.id}>{e.title}</option>)}
            </select>
          </label>
        )}
      </div>
      <QueryState query={projects} />
      {projects.data?.length === 0 && <Empty>{t("proj.empty")}</Empty>}

      {mode === "episode" && projectId && (
        <>
          <QueryState query={episodes} />
          {episodes.data?.length === 0 && <Empty>{t("mon.noEpisodes")}</Empty>}
          <ul className="stack plain-list" style={{ gap: 6 }}>
            {episodes.data?.map((e) => {
              const source: MontageSource = { kind: "episode", episode_id: e.id };
              const key = sourceKey(source);
              const ready = e.status === "ready";
              return (
                <li key={e.id} className="row" style={{ justifyContent: "space-between" }}>
                  <label className="row check">
                    <input type="checkbox" checked={has(key)} disabled={!ready}
                           onChange={(ev) => ev.target.checked
                             ? onAdd([{ key, source, label: e.title, detail: t("mon.wholeEpisode"), projectId }])
                             : onRemoveKey(key)} />
                    {e.title}
                  </label>
                  {!ready && <span className="badge">{t(`ep.status.${e.status}`)}</span>}
                </li>
              );
            })}
          </ul>
        </>
      )}

      {mode === "clips" && episodeId && (
        <ClipList episodeId={episodeId} projectId={projectId} has={has} onAdd={onAdd} onRemoveKey={onRemoveKey}
                  episodeTitle={episodes.data?.find((e) => e.id === episodeId)?.title ?? ""} />
      )}
    </div>
  );
}

function ClipList({ episodeId, projectId, episodeTitle, has, onAdd, onRemoveKey }: {
  episodeId: string;
  projectId: string;
  episodeTitle: string;
  has: (key: string) => boolean;
  onAdd: (items: PickedSource[]) => void;
  onRemoveKey: (key: string) => void;
}) {
  const t = useT();
  const clips = useClips(episodeId);
  const list = (clips.data ?? []).filter((c) => c.status !== "rad");
  const item = (c: Clip): PickedSource => {
    const source: MontageSource = { kind: "clip", episode_id: episodeId, clip_id: c.id };
    return { key: sourceKey(source), source, label: c.title || c.id, detail: `${episodeTitle} · ${fmtTime(outDuration(c))}`, projectId };
  };
  const notPicked = list.filter((c) => !has(item(c).key));
  return (
    <div className="stack">
      <QueryState query={clips} />
      {clips.data && list.length === 0 && <Empty>{t("clips.empty")}</Empty>}
      {notPicked.length > 0 && (
        <div>
          <button type="button" className="btn small" onClick={() => onAdd(notPicked.map(item))}>
            {t("mon.addAllClips", { n: notPicked.length })}
          </button>
        </div>
      )}
      <div className="grid src-clip-grid">
        {list.map((c) => {
          const it = item(c);
          return <ClipPick key={c.id} clip={c} episodeId={episodeId} checked={has(it.key)}
                           onToggle={(on) => (on ? onAdd([it]) : onRemoveKey(it.key))} />;
        })}
      </div>
    </div>
  );
}

const ClipPick = memo(function ClipPick({ clip, episodeId, checked, onToggle }: {
  clip: Clip; episodeId: string; checked: boolean; onToggle: (on: boolean) => void;
}) {
  const t = useT();
  const style = useSettings((s) => s.style);
  const [ref, seen] = useInView<HTMLDivElement>();
  const frame = usePreviewFrame({
    episodeId,
    clipId: clip.id,
    tMs: Math.min(1000, Math.round(outDuration(clip) / 2)),
    style,
    orthography: style.orthography,
    enabled: seen,
    rev: [clip.start_ms, clip.end_ms, clip.cuts],
  });
  const url = useObjectUrl(frame.data);
  return (
    <label className={`card src-clip${checked ? " active" : ""}`}>
      <div ref={ref} className="src-thumb">
        {url ? <img src={url} alt="" loading="lazy" /> : <span className="muted">{frame.isError ? "—" : ""}</span>}
      </div>
      <span className="row check" style={{ flexWrap: "nowrap", alignItems: "flex-start" }}>
        <input type="checkbox" checked={checked} onChange={(e) => onToggle(e.target.checked)} />
        <span>
          <span style={{ fontWeight: 600 }}>{clip.title || clip.id}</span>
          <br />
          <span className="muted mono">{fmtTime(outDuration(clip))} · {t("clips.score")} {Math.round(clip.score)}</span>
        </span>
      </span>
    </label>
  );
});
