// Partiyaviy tahlil navbati (PRO-5): `/v1/queue` hook'lari. Holat o'zgarishlari WebSocket
// `queue` hodisasi orqali keladi (hooks.ts -> useEngineEvents), progress - `job` hodisalaridan.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { del, get, post } from "./client";
import type { QueueItem } from "./types";

export const queueKey = (projectId?: string) => ["queue", projectId ?? "all"] as const;

export const useQueue = (projectId?: string) =>
  useQuery({
    queryKey: queueKey(projectId),
    queryFn: () => get<QueueItem[]>(projectId ? `/v1/queue?project_id=${encodeURIComponent(projectId)}` : "/v1/queue"),
  });

function useQueueAction<V, R>(fn: (v: V) => Promise<R>) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: fn,
    onSettled: () => {
      void qc.invalidateQueries({ queryKey: ["queue"] });
      void qc.invalidateQueries({ queryKey: ["episodes"] });
    },
  });
}

export const useAddToQueue = () =>
  useQueueAction((body: {
    project_id: string;
    paths?: string[];
    /** YouTube havolalari (YT-1): `consent: true` bilan. */
    urls?: { url: string; title?: string }[];
    consent?: boolean;
    focus?: string;
    force_lite?: boolean;
  }) =>
    post<QueueItem[]>("/v1/queue", body),
  );

const item = (id: string) => `/v1/queue/${encodeURIComponent(id)}`;

export const useCancelQueueItem = () => useQueueAction((id: string) => post<QueueItem>(`${item(id)}:cancel`));
export const useRetryQueueItem = () => useQueueAction((id: string) => post<QueueItem>(`${item(id)}:retry`));
export const useRemoveQueueItem = () => useQueueAction((id: string) => del<{ ok: boolean }>(item(id)));
export const useReorderQueue = () => useQueueAction((ids: string[]) => post<QueueItem[]>("/v1/queue:reorder", { ids }));
export const useClearQueue = () =>
  useQueueAction((projectId?: string) => post<{ removed: number }>("/v1/queue:clear", { project_id: projectId ?? null }));
