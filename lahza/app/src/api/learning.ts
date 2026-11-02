// Pro: shaxsiy lug'at (PRO-1) va real natijalardan ball vaznlari (PRO-6) - engine API.
// Endpointlar: docs/04-engine-api.md "Pro: shaxsiy lug'at va ball vaznlari".
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { del, get, post, put } from "./client";
import type { ClipMetrics, DictionaryResponse, WeightsInfo } from "../lib/learning";

const dictKey = ["personal-dictionary"];
const weightsKey = (projectId?: string) => ["highlight-weights", projectId ?? null];
const metricsKey = (episodeId: string) => ["clip-metrics", episodeId];

export const useDictionary = () =>
  useQuery({ queryKey: dictKey, queryFn: () => get<DictionaryResponse>("/v1/dictionary") });

export function useDeleteDictionaryEntry() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => del<{ ok: boolean }>(`/v1/dictionary/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: dictKey }),
  });
}

export const useExportDictionary = () =>
  useMutation({
    mutationFn: (outPath: string) => post<{ path: string; entries: number }>("/v1/dictionary:export", { out_path: outPath }),
  });

export const useExportFinetune = () =>
  useMutation({
    mutationFn: (v: { outPath: string; projectId?: string }) =>
      post<{ path: string; segments: number }>("/v1/dictionary/finetune-manifest:export", {
        out_path: v.outPath,
        project_id: v.projectId || null,
      }),
  });

export const useHighlightWeights = (projectId?: string) =>
  useQuery({
    queryKey: weightsKey(projectId),
    queryFn: () =>
      get<WeightsInfo>(projectId ? `/v1/highlight/weights?project_id=${encodeURIComponent(projectId)}` : "/v1/highlight/weights"),
  });

export function useResetWeights() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (projectId?: string) => post<WeightsInfo>("/v1/highlight/weights:reset", { project_id: projectId || null }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["highlight-weights"] }),
  });
}

export const useClipMetrics = (episodeId: string) =>
  useQuery({
    queryKey: metricsKey(episodeId),
    queryFn: () => get<Record<string, ClipMetrics>>(`/v1/episodes/${episodeId}/clip-metrics`),
    staleTime: 60_000,
  });

export function useSaveClipMetrics(episodeId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (v: { clipId: string; views: number; likes: number | null }) =>
      put<{ metrics: ClipMetrics; weights: WeightsInfo }>(`/v1/episodes/${episodeId}/clips/${v.clipId}/metrics`, {
        views: v.views,
        likes: v.likes,
      }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: metricsKey(episodeId) });
      void qc.invalidateQueries({ queryKey: ["highlight-weights"] });
    },
  });
}
