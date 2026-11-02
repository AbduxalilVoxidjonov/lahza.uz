import { useState } from "react";

import { useProjects } from "../../api/hooks";
import {
  useDeleteDictionaryEntry,
  useDictionary,
  useExportDictionary,
  useExportFinetune,
  useHighlightWeights,
  useResetWeights,
} from "../../api/learning";
import { fmt, learningDictionaries } from "../../i18n/learning";
import { differsFromDefault, pct, samplesLeft, type DictionaryEntry, type WeightsInfo } from "../../lib/learning";
import { useSettings } from "../../store/settings";
import { PathPicker } from "../PathPicker";
import { Empty, ErrorText, QueryState } from "../ui";

type M = (typeof learningDictionaries)["uz"];

const kindText = (m: M, k: DictionaryEntry["kind"]) => (k === "ism" ? m.kindIsm : k === "atama" ? m.kindAtama : m.kindSoz);

/** Shaxsiy lug'at jadvali - sof ko'rinish. */
export function DictionaryTable(p: { m: M; entries: DictionaryEntry[]; busy: boolean; onDelete: (id: number) => void }) {
  const { m } = p;
  if (!p.entries.length) return <Empty>{m.dictEmpty}</Empty>;
  return (
    <table className="table">
      <thead>
        <tr>
          <th>{m.wrong}</th>
          <th>{m.right}</th>
          <th>{m.count}</th>
          <th>{m.state}</th>
          <th><span className="sr-only">{m.remove}</span></th>
        </tr>
      </thead>
      <tbody>
        {p.entries.map((e) => (
          <tr key={e.id}>
            <td className="muted">{e.wrong}</td>
            <td>{e.right} <span className="badge">{kindText(m, e.kind)}</span></td>
            <td>{e.count}</td>
            <td><span className={`badge ${e.active ? "good" : ""}`}>{e.active ? m.active : m.pending}</span></td>
            <td>
              <button type="button" className="btn small ghost" disabled={p.busy}
                      aria-label={fmt(m.remove, { w: e.wrong, r: e.right })} onClick={() => p.onDelete(e.id)}>
                ✕
              </button>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

/** Joriy vaznlar va tiklash tugmasi - sof ko'rinish. */
export function WeightsView(p: { m: M; info: WeightsInfo; busy: boolean; onReset: () => void }) {
  const { m, info } = p;
  const src = info.source === "project" ? m.srcProject : info.source === "global" ? m.srcGlobal : m.srcDefault;
  const left = samplesLeft(info);
  return (
    <div className="stack" style={{ gap: 6 }}>
      <div className="row" style={{ gap: 12 }}>
        <span>{m.wLlm}: <b>{pct(info.weights.weight_llm)}</b></span>
        <span>{m.wSignals}: <b>{pct(info.weights.weight_signals)}</b></span>
        <span className={`badge ${info.source === "default" ? "" : "good"}`}>{src}</span>
      </div>
      <span className="muted">
        {fmt(m.samples, { n: info.n_samples })}
        {left > 0 && ` · ${fmt(m.left, { n: left })}`}
      </span>
      <div>
        <button type="button" className="btn small" disabled={p.busy || !differsFromDefault(info)} onClick={p.onReset}>
          {m.reset}
        </button>
      </div>
    </div>
  );
}

/** Sozlamalar: shaxsiy lug'at (PRO-1) va ball vaznlari (PRO-6). */
export function LearningPanel() {
  const m = learningDictionaries[useSettings((s) => s.locale)];
  const dict = useDictionary();
  const delEntry = useDeleteDictionaryEntry();
  const projects = useProjects();
  const [projectId, setProjectId] = useState("");
  const weights = useHighlightWeights(projectId || undefined);
  const reset = useResetWeights();
  const [folder, setFolder] = useState("");
  const exDict = useExportDictionary();
  const exFt = useExportFinetune();
  return (
    <section className="card stack" aria-labelledby="set-learning">
      <h2 id="set-learning" style={{ margin: 0 }}>{m.title}</h2>
      <span className="muted">{m.hint}</span>

      <h3 style={{ margin: 0 }}>{m.dictTitle}</h3>
      <span className="muted">{fmt(m.dictHint, { n: dict.data?.min_count ?? 2 })}</span>
      <QueryState query={dict} />
      <ErrorText error={delEntry.error} />
      {dict.data && <DictionaryTable m={m} entries={dict.data.entries} busy={delEntry.isPending} onDelete={(id) => delEntry.mutate(id)} />}
      <PathPicker label={m.exportFolder} value={folder} onChange={setFolder} options={{ directory: true, title: m.exportFolder }} />
      <div className="row">
        <button type="button" className="btn small" disabled={!folder || exDict.isPending} onClick={() => exDict.mutate(folder)}>
          {m.exportDict}
        </button>
        <button type="button" className="btn small" disabled={!folder || exFt.isPending}
                onClick={() => exFt.mutate({ outPath: folder, projectId: projectId || undefined })}>
          {m.exportFinetune}
        </button>
      </div>
      <span className="muted">{m.finetuneHint}</span>
      {exDict.data && <span role="status">{fmt(m.exported, { path: exDict.data.path, n: exDict.data.entries })}</span>}
      {exFt.data && <span role="status">{fmt(m.exported, { path: exFt.data.path, n: exFt.data.segments })}</span>}
      <ErrorText error={exDict.error ?? exFt.error} />

      <h3 style={{ margin: 0 }}>{m.weightsTitle}</h3>
      <span className="muted">{fmt(m.weightsHint, { n: weights.data?.min_samples ?? 8 })}</span>
      <label className="field" style={{ width: 280 }}>
        {m.scope}
        <select className="select" value={projectId} onChange={(e) => setProjectId(e.target.value)}>
          <option value="">{m.scopeGlobal}</option>
          {projects.data?.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
        </select>
      </label>
      <QueryState query={weights} />
      {weights.data && (
        <WeightsView m={m} info={weights.data} busy={reset.isPending} onReset={() => reset.mutate(projectId || undefined)} />
      )}
      <ErrorText error={reset.error} />
    </section>
  );
}
