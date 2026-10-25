import { useState } from 'react';
import { useFirstRunSetup } from '../api/setup';
import { activeSetupJob, formatDownloadSize, repairNeeded, type SetupStatus } from '../lib/first-run';
import { useSetupMessages } from '../i18n/setup';

export function SetupPanel({ status, loading, error, startError, busy, cancelError, onRetry, onCheck, onCancel, onDefer }: {
  status?: SetupStatus; loading: boolean; error: boolean; startError: boolean; busy: boolean; cancelError: boolean;
  onRetry: () => void; onCheck: () => void; onCancel: () => void; onDefer: () => void;
}) {
  const m = useSetupMessages();
  if (status?.ready && !error) return null;
  const job = status?.job ?? null;
  const active = activeSetupJob(job) || busy;
  const repair = status ? repairNeeded(status) : false;
  const failed = startError || job?.status === 'failed' || (job?.status === 'done' && !status?.ready);
  const missing = status?.components.filter(c => !c.ready) ?? [];
  const known = missing.every(c => c.download_bytes !== null);
  const bytes = missing.reduce((sum, c) => sum + (c.download_bytes ?? 0), 0);
  const size = known ? formatDownloadSize(bytes) : m.estimate;
  const progress = job ? Math.round(Math.max(0, Math.min(1, job.progress)) * 100) : 0;
  return <section className="card stack" aria-label={m.title} style={{ marginBottom: 20 }}>
    <h2>{m.title}</h2>
    <p role={error || failed || repair ? 'alert' : 'status'}>{error ? m.connection : loading ? m.checking : status?.ready ? m.ready : repair ? m.repair : failed ? m.error : job?.status === 'cancelled' ? m.cancelled : m.download}</p>
    {status && !status.ready && !repair && <p>{m.size}: {size}</p>}
    {active && !error && <div><label htmlFor="setup-progress">{m.progress} — {progress}%</label><progress id="setup-progress" max={100} value={progress} style={{ width: '100%' }} /></div>}
    {cancelError && <p role="alert">{m.cancelError}</p>}
    <div className="row">
      {error || repair ? <button onClick={onCheck}>{m.check}</button> : status && !loading && !active && <button onClick={onRetry}>{m.retry}</button>}
      {active && <button disabled={busy} onClick={onCancel}>{m.cancel}</button>}
      {!status?.ready && <button onClick={onDefer}>{active ? m.basic : m.later}</button>}
    </div>
    {!status?.ready && <p className="muted">{m.basicHint}</p>}
    {job?.error && <details><summary>{m.details}</summary><p>{job.error}</p></details>}
  </section>;
}
export function FirstRunSetup() {
  const s = useFirstRunSetup();
  const [deferred, setDeferred] = useState(false);
  const m = useSetupMessages();
  if (s.status.data?.ready && !s.status.isError) return null;
  if (deferred) return <div className="row" style={{ marginBottom: 12 }}><span>{m.basicHint}</span><button onClick={() => setDeferred(false)}>{m.details}</button></div>;
  return <SetupPanel status={s.status.data} loading={s.status.isPending} error={s.status.isError}
    startError={s.startError} busy={s.start.isPending} cancelError={s.cancel.isError}
    onRetry={() => s.start.mutate()} onCheck={() => { void s.status.refetch(); }}
    onCancel={() => s.cancel.mutate()} onDefer={() => { s.defer(); setDeferred(true); }} />;
}
