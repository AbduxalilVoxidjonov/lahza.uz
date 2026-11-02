import { useMutation, useQuery } from "@tanstack/react-query";
import { api } from "./client";
import type { MontageTimeline } from "./types";
import { parsePlan, parsePreview, parseStatus } from "../lib/editing-agent";
import { parsePlanner, type Planner } from "../lib/claude";
export const editingAgentStatusKey = ["editing-agent", "status"] as const;
export const useEditingAgentStatus = () => useQuery({
  queryKey: editingAgentStatusKey,
  queryFn: async ({ signal }) => parseStatus(await api<unknown>("/v1/editing-agent/status", { signal })),
  staleTime: 0, retry: false,
});
type PreviewRequest = { timeline: MontageTimeline; plan: unknown; selected_video_id: string | null; signal: AbortSignal };
/** `planner` ixtiyoriy (yo'q = mahalliy); javobga ixtiyoriy `planner` maydoni qo'shiladi. */
export const useEditingAgentPlan = () => useMutation({
  mutationFn: async ({ signal, ...body }: Omit<PreviewRequest, "plan"> & { prompt: string; planner?: Planner }) => {
    const raw = await api<unknown>("/v1/editing-agent:plan", { method: "POST", body: JSON.stringify(body), signal });
    return { ...parsePlan(raw), planner: parsePlanner(raw) };
  }, retry: false,
});
export const useEditingAgentPreview = () => useMutation({
  mutationFn: async ({ signal, ...body }: PreviewRequest) => parsePreview(await api<unknown>("/v1/editing-agent:preview", { method: "POST", body: JSON.stringify(body), signal })), retry: false,
});
