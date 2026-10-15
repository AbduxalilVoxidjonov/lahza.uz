import { create } from "zustand";

import type { Job } from "../api/types";

interface JobsState {
  jobs: Record<string, Job>;
  upsert: (job: Job) => void;
}

export const useJobs = create<JobsState>((set) => ({
  jobs: {},
  upsert: (job) => set((s) => ({ jobs: { ...s.jobs, [job.id]: job } })),
}));
