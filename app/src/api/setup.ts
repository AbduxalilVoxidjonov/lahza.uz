import { useEffect } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api, post } from './client';
import { editingAgentStatusKey } from './editing-agent';
import type { Job } from './types';
import { activeSetupJob, parseSetup, SetupSession } from '../lib/first-run';

const session = new SetupSession();
const key = ['first-run-setup'];
export function useFirstRunSetup() {
  const qc = useQueryClient();
  const status = useQuery({ queryKey: key, queryFn: async ({ signal }) => parseSetup(await api<unknown>('/v1/setup', { signal })), retry: false,
    refetchInterval: q => q.state.status !== 'error' && activeSetupJob(q.state.data?.job ?? null) ? 1000 : false });
  const start = useMutation({ mutationKey: ['first-run-start'], mutationFn: () => session.start(async () => {
    const job = await post<unknown>('/v1/setup:start', { consent: true });
    const checked = parseSetup({ ready: false, components: [], job });
    if (!checked.job) throw new Error('Missing setup job');
    return checked.job;
  }), retry: false,
    onSuccess: job => { qc.setQueryData(key, (old: ReturnType<typeof parseSetup> | undefined) => old ? { ...old, job } : old); },
    onSettled: () => { void qc.invalidateQueries({ queryKey: key }); } });
  // Errors remain in the mutation cache across remounts; the latch prevents automatic retry.
  const attempts = qc.getMutationCache().findAll({ mutationKey: ['first-run-start'] });
  const startError = attempts[attempts.length - 1]?.state.status === 'error';
  const cancel = useMutation({ mutationFn: async () => {
    session.defer();
    const job = status.data?.job;
    if (job && activeSetupJob(job)) await post<Job>(`/v1/jobs/${encodeURIComponent(job.id)}:cancel`);
  }, onSuccess: () => qc.invalidateQueries({ queryKey: key }), retry: false });
  const { mutate } = start;
  useEffect(() => {
    const s = status.data;
    if (!s) return;
    // Claim synchronously before dispatch so StrictMode cannot dispatch twice.
    if (session.claim(s)) mutate();
  }, [status.data, mutate]);
  const terminal = status.data?.job;
  const terminalKey = terminal && !activeSetupJob(terminal) ? `${terminal.id}:${terminal.status}` : null;
  useEffect(() => {
    if (!terminalKey) return;
    for (const queryKey of [key, ['models'], ['capabilities'], editingAgentStatusKey]) void qc.invalidateQueries({ queryKey });
  }, [terminalKey, qc]);
  return { status, start, cancel, startError, defer: () => session.defer() };
}
