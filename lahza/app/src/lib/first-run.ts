import type { Job } from '../api/types';
export interface SetupStatus {
  ready: boolean;
  components: { id: string; ready: boolean; required: boolean; download_bytes: number | null; detail: string | null }[];
  job: Job | null;
}
export const activeSetupJob = (job: Job | null) => !!job && (job.status === 'queued' || job.status === 'running');
export const repairNeeded = (status: SetupStatus) => status.components.some(c => !c.ready && c.required && ['render', 'llm_runtime'].includes(c.id));
export function parseSetup(value: unknown): SetupStatus {
  if (!value || typeof value !== 'object') throw new Error('Invalid setup response');
  const s = value as SetupStatus;
  if (typeof s.ready !== 'boolean' || !Array.isArray(s.components) || !s.components.every(c => c && typeof c.id === 'string' && typeof c.ready === 'boolean' && typeof c.required === 'boolean' && (c.download_bytes === null || (typeof c.download_bytes === 'number' && Number.isFinite(c.download_bytes) && c.download_bytes >= 0)) && (c.detail === null || typeof c.detail === 'string'))) throw new Error('Invalid setup components');
  if (s.job !== null && (!s.job || typeof s.job.id !== 'string' || s.job.kind !== 'install' || !['queued', 'running', 'done', 'failed', 'cancelled'].includes(s.job.status) || typeof s.job.progress !== 'number' || !Number.isFinite(s.job.progress))) throw new Error('Invalid setup job');
  return s;
}
/** Session-owned latch survives component remounts and StrictMode effect replay. */
export class SetupSession {
  attempted = false;
  private pending: Promise<Job> | null = null;
  claim(status: SetupStatus): boolean {
    if (status.job) this.attempted = true;
    if (this.attempted || status.ready || repairNeeded(status)) return false;
    this.attempted = true;
    return true;
  }
  defer() { this.attempted = true; }
  start(start: () => Promise<Job>): Promise<Job> {
    if (this.pending) return this.pending;
    this.attempted = true;
    this.pending = Promise.resolve().then(start).finally(() => { this.pending = null; });
    return this.pending;
  }
}

/** Decimal units match the advertised download bytes, including small VAD files. */
export function formatDownloadSize(bytes: number): string {
  const [unit, divisor] = bytes >= 1e9 ? ['GB', 1e9] as const
    : bytes >= 1e6 ? ['MB', 1e6] as const
    : bytes >= 1e3 ? ['KB', 1e3] as const : ['B', 1] as const;
  return `${Number((bytes / divisor).toFixed(1))} ${unit}`;
}
