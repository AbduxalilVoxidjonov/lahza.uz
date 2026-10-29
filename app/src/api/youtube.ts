// YouTube havolasidan import (YT-1, ADR-0010): `/v1/settings/youtube-import` va `/v1/media:import-url`.
// Yuklash progressi `download` vazifasining `job` hodisalari orqali keladi (hooks.ts -> useEngineEvents).
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useJobs } from "../store/jobs";
import { get, post, put } from "./client";
import { findYoutubeProject, YOUTUBE_PROJECT_NAME, type ResolvedUrl } from "../lib/youtube-import";
import type { Job, Project } from "./types";

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
  /** yt-dlp, yt-dlp-ejs va Deno mahkamlangan versiyada `Components/` da o'rnatilgan. */
  components_ready: boolean;
  /** O'rnatish uchun yuklanadigan hajm (bayt); tayyor bo'lsa 0. */
  components_download_bytes: number;
  /** Ketayotgan komponent o'rnatish vazifasi (sahifa qayta ochilsa ham kuzatiladi). */
  install_job: Job | null;
  /** `Components/` dagi versiyalar: {"yt-dlp", "yt-dlp-ejs", "deno"}. */
  component_versions: Record<string, string>;
  /** Ishlatilayotgan yt-dlp qayerdan: ilovaning `Components/` papkasi yoki tizim (venv/PATH). */
  ytdlp_source?: "components" | "system" | null;
  /** Ishlatilayotgan JS runtime versiyasi va manbasi (yt-dlp talabiga mos birinchisi). */
  js_runtime_version?: string | null;
  js_runtime_source?: "components" | "system" | null;
  /** Topilgan, lekin yt-dlp uchun eski runtime'lar (Deno < 2.3, Node < 22, ...). */
  js_runtime_outdated?: { name: string; version: string | null }[];
}

/** PyPI/GitHub'dagi oxirgi versiyalar bilan solishtirish (`:check-updates`). */
export interface ComponentUpdates {
  installed: Record<string, string>;
  latest: Record<string, string>;
  update_available: boolean;
  download_bytes: number;
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

// `refetchOnMount: "always"`: kesh eskirgan bo'lsa ham (masalan, o'rnatish import sahifasidan boshlangan,
// keyin Sozlamalar ochilgan) ketayotgan `install_job` yashirin qolmasin.
export const useYoutubeImportStatus = () =>
  useQuery({
    queryKey: KEY,
    queryFn: () => get<YoutubeImportStatus>("/v1/settings/youtube-import"),
    refetchOnMount: "always",
  });

export function useSetYoutubeImport() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (enabled: boolean) => put<YoutubeImportStatus>("/v1/settings/youtube-import", { enabled }),
    onSuccess: (data) => qc.setQueryData(KEY, data),
  });
}

/** Komponentlarni (yt-dlp, yt-dlp-ejs, Deno) foydalanuvchi roziligi bilan bir marta yuklash. */
export function useInstallYoutubeComponents() {
  const upsert = useJobs((s) => s.upsert);
  return useMutation({
    mutationFn: (update: boolean = false) =>
      post<{ job: Job }>("/v1/settings/youtube-import:install-components", { consent: true, update }),
    onSuccess: (res) => upsert(res.job),
  });
}

/** Tarmoq faqat shu tugma bosilganda: PyPI va GitHub'dan oxirgi versiyalar. */
export function useCheckYoutubeUpdates() {
  return useMutation({
    mutationFn: () => post<ComponentUpdates>("/v1/settings/youtube-import:check-updates", {}),
  });
}

/** Holatni qayta so'rash (o'rnatish vazifasi tugaganda). */
export function useRefreshYoutubeImport() {
  const qc = useQueryClient();
  return () => qc.invalidateQueries({ queryKey: KEY });
}

/** Havola turi va playlist/kanal videolari ro'yxati (tarmoq - engine'da, alohida jarayonda). */
export function useResolveUrl() {
  return useMutation({
    mutationFn: (url: string) => post<ResolvedUrl>("/v1/media:resolve-url", { url, consent: true }),
  });
}

export function useImportUrl() {
  const upsert = useJobs((s) => s.upsert);
  return useMutation({
    mutationFn: (body: ImportUrlBody) => post<{ job: Job }>("/v1/media:import-url", body),
    onSuccess: (res) => upsert(res.job),
  });
}

/**
 * Boshlash sahifasi: loyiha so'ralmaydi - "YouTube" loyihasi (bo'lsa o'sha, bo'lmasa yaratiladi) id'si.
 * Loyihalar ro'yxati har safar yangidan olinadi (boshqa oynada yaratilgan bo'lsa ham dublikat bo'lmasin).
 */
export function useEnsureYoutubeProject() {
  const qc = useQueryClient();
  return async (): Promise<string> => {
    const list = await qc.fetchQuery({ queryKey: ["projects"], queryFn: () => get<Project[]>("/v1/projects"), staleTime: 0 });
    const found = findYoutubeProject(list);
    if (found) return found;
    const created = await post<Project>("/v1/projects", { name: YOUTUBE_PROJECT_NAME });
    void qc.invalidateQueries({ queryKey: ["projects"] });
    return created.id;
  };
}
