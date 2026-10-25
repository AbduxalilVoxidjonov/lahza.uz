import { useMutation, useQuery } from "@tanstack/react-query";
import { api } from "./client";
import type { MontageTimeline } from "./types";
import { parsePlan, parsePreview, parseStatus } from "../lib/editing-agent";
export const editingAgentStatusKey = ["editing-agent", "status"] as const;
export const useEditingAgentStatus = () => useQuery({
  queryKey: editingAgentStatusKey,
  queryFn: async ({ signal }) => parseStatus(await api<unknown>("/v1/editing-agent/status", { signal })),
  staleTime: 0, retry: false,
});
type PreviewRequest = { timeline: MontageTimeline; plan: unknown; selected_video_id: string | null; signal: AbortSignal };
export const useEditingAgentPlan = () => useMutation({
  mutationFn: async ({ signal, ...body }: Omit<PreviewRequest, "plan"> & { prompt: string }) => parsePlan(await api<unknown>("/v1/editing-agent:plan", { method: "POST", body: JSON.stringify(body), signal })), retry: false,
});
export const useEditingAgentPreview = () => useMutation({
  mutationFn: async ({ signal, ...body }: PreviewRequest) => parsePreview(await api<unknown>("/v1/editing-agent:preview", { method: "POST", body: JSON.stringify(body), signal })), retry: false,
});
