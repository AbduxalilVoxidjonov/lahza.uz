// YouTube havolasidan import (YT-1, ADR-0010): `/v1/settings/youtube-import` va `/v1/media:import-url`.
// Yuklash progressi `download` vazifasining `job` hodisalari orqali keladi (hooks.ts -> useEngineEvents).
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useJobs } from "../store/jobs";
import { get, post, put } from "./client";
import type { Job } from "./types";

export interface YoutubeImportStatus {
  /** Sozlamalarda yoqilgan (standart: false). */
  enabled: boolean;
  /** yt-dlp komponenti topildi. */
  installed: boolean;
  version: string | null;
  /** yt-dlp-ejs topildi. */
  ejs: boolean;
  /** "deno" | "node" | "bun" | null. */
  js_runtime: string | null;
  ffmpeg: boolean;
}

export interface ImportUrlBody {
  project_id: string;
  url: string;
  /** Majburiy: "menga tegishli yoki ruxsatim bor" + YouTube shartlari ogohlantirishi. */
  consent: true;
  title?: string;
  focus?: string;
  num_speakers?: number;
  force_lite?: boolean;
}

const KEY = ["youtube-import"] as const;

export const useYoutubeImportStatus = () =>
  useQuery({ queryKey: KEY, queryFn: () => get<YoutubeImportStatus>("/v1/settings/youtube-import") });

export function useSetYoutubeImport() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (enabled: boolean) => put<YoutubeImportStatus>("/v1/settings/youtube-import", { enabled }),
    onSuccess: (data) => qc.setQueryData(KEY, data),
  });
}

export function useImportUrl() {
  const upsert = useJobs((s) => s.upsert);
  return useMutation({
    mutationFn: (body: ImportUrlBody) => post<{ job: Job }>("/v1/media:import-url", body),
    onSuccess: (res) => upsert(res.job),
  });
}
