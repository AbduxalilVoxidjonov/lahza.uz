import { useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { useCancelJob, useCapabilities, useClips, useEpisode, usePatchClip, useSimilar } from "../api/hooks";
import type { Clip, ClipKind, ClipStatus } from "../api/types";
import { CLIP_KINDS, CLIP_STATUSES } from "../components/ClipBadges";
import { ClipCard } from "../components/gallery/ClipCard";
import { ReanalyzePanel } from "../components/gallery/ReanalyzePanel";
import { NoSubsWarning } from "../components/NoSubsWarning";
import { Empty, ErrorText, JobLine, QueryState } from "../components/ui";
import { useT } from "../i18n";
import { useHotkeys } from "../lib/hotkeys";
import { useExportAction } from "../lib/useExportAction";
import { useJobs } from "../store/jobs";

type Sort = "score" | "time" | "duration";

/** Kliplar galereyasi (TZ 11): saralash/filtr, qabul/rad, o'xshashini top, ko'p klipni eksport. */
export function Episode() {
  const t = useT();
  const { episodeId = "" } = useParams();
  const clips = useClips(episodeId);
  const episode = useEpisode(episodeId);
  const caps = useCapabilities();
  const patch = usePatchClip(episodeId);
  const similar = useSimilar(episodeId);
  const cancel = useCancelJob();
  const exporter = useExportAction(episodeId);

  const [sort, setSort] = useState<Sort>("score");
  const [kind, setKind] = useState<ClipKind | "all">("all");
  const [status, setStatus] = useState<ClipStatus | "all">("all");
  const [minScore, setMinScore] = useState(0);
  const [checked, setChecked] = useState<Set<string>>(new Set());
  const [active, setActive] = useState<string | null>(null);
  const [similarMsg, setSimilarMsg] = useState<string | null>(null);

  const job = useJobs((s) =>
    Object.values(s.jobs).find((j) => j.kind === "analyze" && j.meta["episode_id"] === episodeId && j.status !== "done"),
  );

  const visible = useMemo(() => {
    const list = (clips.data ?? []).filter(
      (c) => (kind === "all" || c.kind === kind) && (status === "all" || c.status === status) && c.score >= minScore,
    );
    const dur = (c: Clip) => c.end_ms - c.start_ms;
    if (sort === "score") return list.sort((a, b) => b.score - a.score);
    if (sort === "time") return list.sort((a, b) => a.start_ms - b.start_ms);
    return list.sort((a, b) => dur(a) - dur(b));
  }, [clips.data, sort, kind, status, minScore]);

  const setStatusFor = (id: string, s: ClipStatus) => patch.mutate({ id, status: s });
  const toggleCheck = (id: string) =>
    setChecked((prev) => {
      const n = new Set(prev);
      if (n.has(id)) n.delete(id);
      else n.add(id);
      return n;
    });

  const exportIds = checked.size ? [...checked] : active ? [active] : [];
  useHotkeys({
    a: () => active && setStatusFor(active, "qabul"),
    r: () => active && setStatusFor(active, "rad"),
    "mod+e": () => void exporter.run(exportIds),
  });

  const findSimilar = (id: string) =>
    similar.mutate(id, { onSuccess: (found) => setSimilarMsg(t("gal.similarFound", { n: found.length })) });

  const accepted = (clips.data ?? []).filter((c) => c.status === "qabul").map((c) => c.id);
  const llmUpgrade = !!caps.data?.llm && episode.data?.highlight_mode === "lite";

  return (
    <div className="stack" style={{ gap: 20 }}>
      <div className="page-head">
        <div>
          <Link to="/projects" className="muted">← {t("nav.projects")}</Link>
          <h1>{episode.data?.title ?? t("clips.title")}</h1>
        </div>
        <div className="row">
          <Link className="btn small" to={`/episodes/${episodeId}/transcript`}>{t("tr.open")}</Link>
          <ReanalyzePanel episodeId={episodeId} highlight={llmUpgrade} />
        </div>
      </div>

      {llmUpgrade && <div className="card notice" role="note">{t("gal.llmAvailable")}</div>}

      {job && (
        <div className="card">
          <JobLine job={job} onCancel={() => cancel.mutate(job.id)} />
        </div>
      )}

      <div className="row filters" role="group" aria-label={t("gal.filters")}>
        <label className="field">
          {t("gal.sort")}
          <select className="select" value={sort} onChange={(e) => setSort(e.target.value as Sort)}>
            <option value="score">{t("clips.sortScore")}</option>
            <option value="time">{t("clips.sortTime")}</option>
            <option value="duration">{t("gal.sortDuration")}</option>
          </select>
        </label>
        <label className="field">
          {t("clips.kind")}
          <select className="select" value={kind} onChange={(e) => setKind(e.target.value as ClipKind | "all")}>
            <option value="all">{t("common.all")}</option>
            {CLIP_KINDS.map((k) => <option key={k} value={k}>{t(`kind.${k}`)}</option>)}
          </select>
        </label>
        <label className="field">
          {t("gal.status")}
          <select className="select" value={status} onChange={(e) => setStatus(e.target.value as ClipStatus | "all")}>
            <option value="all">{t("common.all")}</option>
            {CLIP_STATUSES.map((s) => <option key={s} value={s}>{t(`status.${s}`)}</option>)}
          </select>
        </label>
        <label className="field" style={{ minWidth: 160 }}>
          {t("gal.minScore", { n: minScore })}
          <input type="range" min={0} max={100} step={5} value={minScore} onChange={(e) => setMinScore(Number(e.target.value))} />
        </label>
        <div className="row" style={{ marginLeft: "auto", alignSelf: "end" }}>
          <button type="button" className="btn small" disabled={!accepted.length} onClick={() => setChecked(new Set(accepted))}>
            {t("gal.selectAccepted")}
          </button>
          <button type="button" className="btn small primary" disabled={!exportIds.length || exporter.pending}
                  onClick={() => void exporter.run(exportIds)}>
            {t("gal.exportSelected", { n: exportIds.length })} <kbd>⌘E</kbd>
          </button>
        </div>
      </div>

      <NoSubsWarning />
      {exporter.error && (
        <span className="error" role="alert">{exporter.error} <Link to="/exports">{t("nav.exports")}</Link></span>
      )}
      {exporter.queued > 0 && !exporter.error && (
        <span className="muted" role="status">{t("exp.queued", { n: exporter.queued })} <Link to="/exports">{t("nav.exports")}</Link></span>
      )}
      {similarMsg && <span className="muted" role="status">{similarMsg}</span>}
      <ErrorText error={patch.error ?? similar.error} />
      <QueryState query={clips} />
      {clips.data?.length === 0 && <Empty>{t("clips.empty")}</Empty>}
      {clips.data && clips.data.length > 0 && visible.length === 0 && <Empty>{t("gal.noMatch")}</Empty>}
      <p className="muted sr-only">{t("gal.kbdHint")}</p>

      <div className="grid">
        {visible.map((c) => (
          <ClipCard
            key={c.id}
            clip={c}
            episodeId={episodeId}
            active={active === c.id}
            checked={checked.has(c.id)}
            onActivate={() => setActive(c.id)}
            onCheck={() => toggleCheck(c.id)}
            onStatus={(s) => setStatusFor(c.id, s)}
            onSimilar={() => findSimilar(c.id)}
            similarPending={similar.isPending && similar.variables === c.id}
          />
        ))}
      </div>
    </div>
  );
}
