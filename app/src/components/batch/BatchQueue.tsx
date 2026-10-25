import { useState } from "react";
import { Link } from "react-router-dom";

import {
  useAddToQueue,
  useCancelQueueItem,
  useClearQueue,
  useQueue,
  useRemoveQueueItem,
  useReorderQueue,
  useRetryQueueItem,
} from "../../api/queue";
import type { JobStatus, QueueItem } from "../../api/types";
import { useT } from "../../i18n";
import { batchDictionaries, fmt } from "../../i18n/batch";
import { canCancel, canRemove, canRetry, mergePaths, moveQueued, parsePathList, summarize, withLiveJob } from "../../lib/batch-queue";
import { baseName, hasNativeDialog, pickPaths, VIDEO_EXTS } from "../../lib/dialog";
import { useJobs } from "../../store/jobs";
import { useSettings } from "../../store/settings";
import { ErrorText, isMessageKey, ProgressBar, QueryState } from "../ui";

const BADGE: Record<JobStatus, string> = { queued: "", running: "accent", done: "good", failed: "bad", cancelled: "warn" };

/** Partiyaviy tahlil (PRO-5): bir nechta faylni loyiha navbatiga qo'shish va navbatni boshqarish. */
export function BatchQueue({ projectId }: { projectId: string }) {
  const locale = useSettings((s) => s.locale);
  const b = batchDictionaries[locale];
  const queue = useQueue(projectId);
  const live = useJobs((s) => s.jobs);
  const add = useAddToQueue();
  const cancel = useCancelQueueItem();
  const remove = useRemoveQueueItem();
  const retry = useRetryQueueItem();
  const reorder = useReorderQueue();
  const clear = useClearQueue();
  const native = hasNativeDialog();
  const [selected, setSelected] = useState<string[]>([]);
  const [manual, setManual] = useState("");
  const [focus, setFocus] = useState("");
  const [lite, setLite] = useState(false);

  const paths = native ? selected : parsePathList(manual);
  const items = (queue.data ?? []).map((x) => withLiveJob(x, x.job_id ? live[x.job_id] : undefined));
  const sum = summarize(items);
  const finished = sum.done + sum.failed + sum.cancelled;

  const submit = () =>
    add.mutate(
      { project_id: projectId, paths, focus: focus.trim() || undefined, force_lite: lite },
      {
        onSuccess: () => {
          setSelected([]);
          setManual("");
        },
      },
    );

  const move = (id: string, delta: -1 | 1 | "top") => {
    const ids = moveQueued(items, id, delta);
    if (ids) reorder.mutate(ids);
  };

  return (
    <section className="card stack" aria-labelledby="batch-title">
      <h2 id="batch-title">{b.title}</h2>
      <span className="muted">{b.hint}</span>
      {native ? (
        <div className="row">
          <button
            type="button"
            className="btn small"
            onClick={() =>
              void pickPaths({ title: b.pick, extensions: VIDEO_EXTS, filterName: "Video" }).then((p) =>
                setSelected((cur) => mergePaths(cur, p)),
              )
            }
          >
            {b.pick}
          </button>
          {selected.length > 0 && (
            <>
              <span className="muted">{fmt(b.selected, { n: selected.length })}</span>
              <button type="button" className="btn small ghost" onClick={() => setSelected([])}>
                {b.clearSelection}
              </button>
            </>
          )}
        </div>
      ) : (
        <label className="field">
          {b.paths}
          <textarea className="input mono" rows={3} value={manual} placeholder={"/yo'l/1.mp4\n/yo'l/2.mp4"}
                    onChange={(e) => setManual(e.target.value)} />
        </label>
      )}
      {native && selected.length > 0 && (
        <ul className="plain-list muted mono" style={{ margin: 0 }}>
          {selected.map((p) => <li key={p}>{baseName(p)}</li>)}
        </ul>
      )}
      <div className="row">
        <input className="input" style={{ flex: 1, minWidth: 220 }} placeholder={b.focus} aria-label={b.focus}
               value={focus} onChange={(e) => setFocus(e.target.value)} />
        <label className="row muted">
          <input type="checkbox" checked={lite} onChange={(e) => setLite(e.target.checked)} /> {b.lite}
        </label>
        <button type="button" className="btn primary" disabled={!paths.length || add.isPending} onClick={submit}>
          {b.add}
          {paths.length > 1 ? ` (${paths.length})` : ""}
        </button>
      </div>
      <ErrorText error={add.error ?? cancel.error ?? remove.error ?? retry.error ?? reorder.error ?? clear.error} />

      <div className="row" style={{ justifyContent: "space-between" }}>
        <h3 style={{ margin: 0 }}>{b.queue}</h3>
        {items.length > 0 && (
          <span className="row">
            <span className="muted" role="status">
              {fmt(b.summary, { done: sum.done, total: sum.total, failed: sum.failed })}
            </span>
            {finished > 0 && (
              <button type="button" className="btn small ghost" disabled={clear.isPending}
                      onClick={() => clear.mutate(projectId)}>
                {b.clearFinished}
              </button>
            )}
          </span>
        )}
      </div>
      {items.length > 0 && <ProgressBar value={sum.progress} label={b.queue} />}
      <QueryState query={queue} />
      {queue.data && items.length === 0 && <span className="muted">{b.empty}</span>}
      <ol className="stack plain-list" aria-label={b.queue}>
        {items.map((x) => (
          <QueueRow
            key={x.id}
            item={x}
            onMove={(d) => move(x.id, d)}
            onCancel={() => cancel.mutate(x.id)}
            onRemove={() => remove.mutate(x.id)}
            onRetry={() => retry.mutate(x.id)}
            busy={reorder.isPending}
          />
        ))}
      </ol>
    </section>
  );
}

function QueueRow({
  item,
  onMove,
  onCancel,
  onRemove,
  onRetry,
  busy,
}: {
  item: QueueItem;
  onMove: (d: -1 | 1 | "top") => void;
  onCancel: () => void;
  onRemove: () => void;
  onRetry: () => void;
  busy: boolean;
}) {
  const t = useT();
  const locale = useSettings((s) => s.locale);
  const b = batchDictionaries[locale];
  const name = item.title || baseName(item.path);
  const stageKey = `stage.${item.stage ?? ""}`;
  const stage = item.stage ? (isMessageKey(stageKey) ? t(stageKey) : item.stage) : "";
  return (
    <li className="stack" style={{ gap: 6, borderTop: "1px solid var(--line)", paddingTop: 8 }}>
      <div className="row" style={{ justifyContent: "space-between" }}>
        <span className="row" style={{ gap: 8 }}>
          <span className={`badge ${BADGE[item.status]}`}>{b[item.status]}</span>
          {item.episode_id && item.status === "done" ? (
            <Link to={`/episodes/${item.episode_id}`} title={b.open}>{name}</Link>
          ) : (
            <span title={item.path}>{name}</span>
          )}
        </span>
        <span className="row">
          {item.status === "queued" && (
            <>
              <button type="button" className="btn small ghost" disabled={busy} aria-label={`${b.top}: ${name}`}
                      onClick={() => onMove("top")}>⤒</button>
              <button type="button" className="btn small ghost" disabled={busy} aria-label={`${b.up}: ${name}`}
                      onClick={() => onMove(-1)}>↑</button>
              <button type="button" className="btn small ghost" disabled={busy} aria-label={`${b.down}: ${name}`}
                      onClick={() => onMove(1)}>↓</button>
            </>
          )}
          {canCancel(item.status) && (
            <button type="button" className="btn small ghost" onClick={onCancel}>{b.cancel}</button>
          )}
          {canRetry(item.status) && (
            <button type="button" className="btn small" onClick={onRetry}>{b.retry}</button>
          )}
          {canRemove(item.status) && (
            <button type="button" className="btn small ghost" onClick={onRemove}>{b.remove}</button>
          )}
        </span>
      </div>
      {item.status === "running" && (
        <div className="stack" style={{ gap: 4 }}>
          <span className="row muted" style={{ justifyContent: "space-between" }}>
            <span>{stage && fmt(b.stage, { stage })}</span>
            <span className="mono">{Math.round(item.progress * 100)}%</span>
          </span>
          <ProgressBar value={item.progress} label={name} />
        </div>
      )}
      {item.status === "failed" && item.error && (
        <span className="error" role="alert">{t("common.error", { msg: item.error })}</span>
      )}
    </li>
  );
}
