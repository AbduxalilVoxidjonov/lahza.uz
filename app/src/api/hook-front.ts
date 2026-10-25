import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { get, put } from "./client";
import type { Clip, HookCandidate } from "./types";

/** PRO-3 "Hook oldinga": yoqish (avto / gap / oraliq) yoki o'chirish. */
export type HookRequest =
  | { enabled: false }
  | { enabled: true; sentence_id?: number; start_ms?: number; end_ms?: number };

export const useHookCandidates = (episodeId: string, clipId: string, enabled: boolean) =>
  useQuery({
    queryKey: ["hook-candidates", episodeId, clipId],
    queryFn: () => get<HookCandidate[]>(`/v1/episodes/${episodeId}/clips/${clipId}/hook/candidates`),
    enabled,
  });

export function usePutHook(episodeId: string, clipId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: HookRequest) => put<Clip>(`/v1/episodes/${episodeId}/clips/${clipId}/hook`, body),
    onSuccess: (clip) => {
      qc.setQueryData<Clip[]>(["clips", episodeId], (old) => old?.map((c) => (c.id === clip.id ? clip : c)));
      // Chiqish vaqti siljidi: avtomatik kamera kalit kadrlari serverda tashlandi.
      void qc.invalidateQueries({ queryKey: ["keyframes", episodeId, clipId] });
    },
  });
}
