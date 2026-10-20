import { keepPreviousData, useMutation, useQuery, useQueryClient, type QueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { useJobs } from "../store/jobs";
import { del, eventsUrl, get, getBlob, patch, post, postBlob, put } from "./client";
import type {
  Bundle,
  Capabilities,
  Clip,
  EngineEvent,
  Episode,
  EpisodeDetail,
  ExportItem,
  FontInfo,
  FxKind,
  FxManifest,
  HardwareInfo,
  InstalledModel,
  Job,
  Keyframe,
  LexiconEntry,
  LexiconKind,
  MediaRef,
  MontageDetail,
  MontageOverrides,
  MontageSource,
  MontageSummary,
  MontageTimeline,
  Orthography,
  Project,
  Registry,
  Sentence,
  Speaker,
  StyleRecord,
  StyleTemplate,
  Template,
  Waveform,
} from "./types";

type Ok = { ok: boolean };

// ---------------------------------------------------------------- tizim va modellar

export const useHardware = () =>
  useQuery({ queryKey: ["hardware"], queryFn: () => get<HardwareInfo>("/v1/hardware"), staleTime: Infinity });

export const useBundle = () =>
  useQuery({ queryKey: ["bundle"], queryFn: () => get<Bundle>("/v1/catalog/bundle"), staleTime: 60_000 });

export const useModels = () => useQuery({ queryKey: ["models"], queryFn: () => get<Registry>("/v1/models") });

export const useCapabilities = () =>
  useQuery({ queryKey: ["capabilities"], queryFn: () => get<Capabilities>("/v1/capabilities"), staleTime: 60_000 });

export const useFonts = () =>
  useQuery({ queryKey: ["fonts"], queryFn: () => get<FontInfo[]>("/v1/fonts"), staleTime: 5 * 60_000 });

export function useInstallBundle() {
  const upsert = useJobs((s) => s.upsert);
  return useMutation({
    mutationFn: () => post<Job>("/v1/models:install", { consent: true }),
    onSuccess: (job) => upsert(job),
  });
}

function useModelAction<V>(fn: (v: V) => Promise<unknown>) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: fn,
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["models"] });
      void qc.invalidateQueries({ queryKey: ["capabilities"] });
    },
  });
}

export const useDeleteModel = () => useModelAction((id: string) => del<Ok>(`/v1/models/${id}`));
export const useSetDefaultModel = () => useModelAction((id: string) => post<Ok>(`/v1/models/${id}:default`));
export const useScanModels = () => useModelAction(() => post<{ added: InstalledModel[] }>("/v1/models:scan"));

export const useTestModel = () =>
  useMutation({ mutationFn: (id: string) => post<{ ok: boolean; detail: string }>(`/v1/models/${id}:test`) });

/** .lzpack eksport/import - uzoq vazifa (Job kind `pack`). */
export function usePack() {
  const upsert = useJobs((s) => s.upsert);
  return useMutation({
    mutationFn: (v: { mode: "export" | "import"; path: string }) =>
      post<Job>(v.mode === "export" ? "/v1/models:export-pack" : "/v1/models:import-pack", { path: v.path }),
    onSuccess: (job) => upsert(job),
  });
}

export const useDiagnostics = () =>
  useMutation({ mutationFn: (outDir: string) => post<{ path: string }>("/v1/diagnostics", { out_dir: outDir }) });

export const useReveal = () =>
  useMutation({ mutationFn: (path: string) => post<Ok>("/v1/system:reveal", { path }) });

// ---------------------------------------------------------------- loyihalar va epizodlar

export const useProjects = () => useQuery({ queryKey: ["projects"], queryFn: () => get<Project[]>("/v1/projects") });

export const useEpisodes = (projectId: string | undefined) =>
  useQuery({
    queryKey: ["episodes", projectId],
    queryFn: () => get<Episode[]>(`/v1/projects/${projectId}/episodes`),
    enabled: !!projectId,
  });

export const useEpisode = (episodeId: string | undefined) =>
  useQuery({
    queryKey: ["episode", episodeId],
    queryFn: () => get<EpisodeDetail>(`/v1/episodes/${episodeId}`),
    enabled: !!episodeId,
  });

export function useCreateProject() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (name: string) => post<Project>("/v1/projects", { name }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["projects"] }),
  });
}

export function useImportMedia() {
  const qc = useQueryClient();
  const upsert = useJobs((s) => s.upsert);
  return useMutation({
    mutationFn: (body: { project_id: string; path: string; focus?: string; force_lite?: boolean }) =>
      post<{ episode_id: string; job: Job }>("/v1/media:import", body),
    onSuccess: (res, vars) => {
      upsert(res.job);
      void qc.invalidateQueries({ queryKey: ["episodes", vars.project_id] });
    },
  });
}

export function useReanalyze(episodeId: string) {
  const upsert = useJobs((s) => s.upsert);
  return useMutation({
    mutationFn: (body: { force_lite?: boolean; focus?: string; num_speakers?: number }) =>
      post<Job>(`/v1/episodes/${episodeId}:reanalyze`, body),
    onSuccess: (job) => upsert(job),
  });
}

// ---------------------------------------------------------------- transkript, spikerlar, to'lqin

export const useTranscript = (episodeId: string | undefined) =>
  useQuery({
    queryKey: ["transcript", episodeId],
    queryFn: () => get<{ sentences: Sentence[] }>(`/v1/episodes/${episodeId}/transcript`),
    enabled: !!episodeId,
  });

export const useSpeakers = (episodeId: string | undefined) =>
  useQuery({
    queryKey: ["speakers", episodeId],
    queryFn: () => get<Speaker[]>(`/v1/episodes/${episodeId}/speakers`),
    enabled: !!episodeId,
  });

/** Bucket soni davomiylikka qarab: taxminan 100 ms aniqlik, 2000..20000 (engine chegarasi). */
export function waveformBuckets(durationMs: number): number {
  return Math.max(2000, Math.min(20_000, Math.round(durationMs / 100)));
}

export const useWaveform = (episodeId: string | undefined, durationMs: number | undefined) => {
  const buckets = durationMs ? waveformBuckets(durationMs) : 2000;
  return useQuery({
    queryKey: ["waveform", episodeId, buckets],
    queryFn: () => get<Waveform>(`/v1/episodes/${episodeId}/waveform?buckets=${buckets}`),
    enabled: !!episodeId && durationMs !== undefined,
    staleTime: Infinity,
  });
};

/** So'zni tahrirlash: engine faqat shu gapni qayta tekislaydi; kesh javobdagi gap bilan yangilanadi. */
export function useEditWord(episodeId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (v: { sentence_id: number; ord: number; text: string }) =>
      patch<{ ok: boolean; sentence: Sentence }>(`/v1/episodes/${episodeId}/words`, v),
    onSuccess: (res) => {
      qc.setQueryData<{ sentences: Sentence[] }>(["transcript", episodeId], (old) =>
        old
          ? { sentences: old.sentences.map((s) => (s.id === res.sentence.id ? res.sentence : s)) }
          : old,
      );
    },
  });
}

export function useRenameSpeaker(episodeId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (v: { label: string; display_name: string | null }) =>
      patch<Ok>(`/v1/episodes/${episodeId}/speakers/${encodeURIComponent(v.label)}`, {
        display_name: v.display_name,
      }),
    onSuccess: (_r, v) => {
      qc.setQueryData<Speaker[]>(["speakers", episodeId], (old) =>
        old?.map((s) => (s.label === v.label ? { ...s, display_name: v.display_name } : s)),
      );
    },
  });
}

// ---------------------------------------------------------------- kliplar

export const useClips = (episodeId: string | undefined) =>
  useQuery({
    queryKey: ["clips", episodeId],
    queryFn: () => get<Clip[]>(`/v1/episodes/${episodeId}/clips`),
    enabled: !!episodeId,
  });

function replaceClip(qc: QueryClient, episodeId: string, clip: Clip) {
  qc.setQueryData<Clip[]>(["clips", episodeId], (old) => {
    if (!old) return old;
    return old.some((c) => c.id === clip.id) ? old.map((c) => (c.id === clip.id ? clip : c)) : [...old, clip];
  });
}

/** Optimistik yangilanish: trim tutqichlari va A/R tugmalari kechikmasin. */
export function usePatchClip(episodeId: string) {
  const qc = useQueryClient();
  const key = ["clips", episodeId];
  return useMutation({
    mutationFn: ({ id, ...body }: Partial<Clip> & { id: string }) =>
      patch<Ok>(`/v1/episodes/${episodeId}/clips/${id}`, body),
    onMutate: async (v) => {
      await qc.cancelQueries({ queryKey: key });
      const prev = qc.getQueryData<Clip[]>(key);
      qc.setQueryData<Clip[]>(key, (old) => old?.map((c) => (c.id === v.id ? { ...c, ...v } : c)));
      return { prev };
    },
    onError: (_e, _v, ctx) => {
      if (ctx?.prev) qc.setQueryData(key, ctx.prev);
    },
    onSettled: () => qc.invalidateQueries({ queryKey: key }),
  });
}

export function useCreateClip(episodeId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (v: { start_sentence_id: number; end_sentence_id: number; title?: string }) =>
      post<Clip>(`/v1/episodes/${episodeId}/clips`, v),
    onSuccess: (clip) => replaceClip(qc, episodeId, clip),
  });
}

export function usePutCuts(episodeId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (v: { clipId: string; cuts: [number, number][] }) =>
      put<Clip>(`/v1/episodes/${episodeId}/clips/${v.clipId}/cuts`, { cuts: v.cuts }),
    onSuccess: (clip) => replaceClip(qc, episodeId, clip),
  });
}

export function useSimilar(episodeId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (clipId: string) => post<Clip[]>(`/v1/episodes/${episodeId}/clips/${clipId}:similar`),
    onSuccess: (found) => {
      for (const c of found) replaceClip(qc, episodeId, c);
    },
  });
}

export const useKeyframes = (episodeId: string, clipId: string) =>
  useQuery({
    queryKey: ["keyframes", episodeId, clipId],
    queryFn: () => get<Keyframe[]>(`/v1/episodes/${episodeId}/clips/${clipId}/keyframes`),
  });

export function useSaveKeyframes(episodeId: string, clipId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (keyframes: Keyframe[]) =>
      put<Ok>(`/v1/episodes/${episodeId}/clips/${clipId}/keyframes`, { keyframes }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["keyframes", episodeId, clipId] }),
  });
}

export interface ExportVars {
  clipId: string;
  outDir: string;
  style: StyleTemplate;
  orthography?: Orthography;
  filenameTemplate?: string;
  /** libass yo'q bo'lsa subtitrsiz eksportga rozilik (aks holda engine 422 qaytaradi). */
  allowNoSubs?: boolean;
}

export function useExportClip(episodeId: string) {
  const upsert = useJobs((s) => s.upsert);
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (v: ExportVars) =>
      post<Job>(`/v1/episodes/${episodeId}/clips/${v.clipId}:export`, {
        out_dir: v.outDir,
        style: v.style,
        orthography: v.orthography,
        filename_template: v.filenameTemplate || undefined,
        allow_no_subs: v.allowNoSubs ?? false,
      }),
    onSuccess: (job) => {
      upsert(job);
      void qc.invalidateQueries({ queryKey: ["exports"] });
    },
  });
}

/**
 * Engine preview kadri (1080x1920 JPEG). Blob TanStack keshida, object URL esa
 * `useObjectUrl` orqali yaratiladi va eskisi bekor qilinadi (revoke).
 */
export function usePreviewFrame(p: {
  episodeId: string;
  clipId: string;
  tMs: number;
  style: StyleTemplate;
  orthography?: Orthography;
  enabled?: boolean;
  /** Klip o'zgarganini bildiruvchi qiymat (chegaralar, kesimlar) - kesh kalitiga qo'shiladi. */
  rev?: unknown;
}) {
  return useQuery({
    queryKey: ["preview", p.episodeId, p.clipId, p.tMs, p.style, p.orthography, p.rev ?? null],
    queryFn: ({ signal }) =>
      postBlob(
        `/v1/episodes/${p.episodeId}/clips/${p.clipId}:preview`,
        { t_ms: p.tMs, style: p.style, orthography: p.orthography },
        signal,
      ),
    enabled: p.enabled ?? true,
    staleTime: Infinity,
    gcTime: 30_000,
    placeholderData: keepPreviousData,
    retry: false,
  });
}

export function useObjectUrl(blob: Blob | undefined): string | undefined {
  const [url, setUrl] = useState<string>();
  useEffect(() => {
    if (!blob) {
      setUrl(undefined);
      return;
    }
    const u = URL.createObjectURL(blob);
    setUrl(u);
    return () => URL.revokeObjectURL(u);
  }, [blob]);
  return url;
}

// ---------------------------------------------------------------- eksport navbati va vazifalar

export const useExports = () =>
  useQuery({ queryKey: ["exports"], queryFn: () => get<ExportItem[]>("/v1/exports") });

export function useRetryJob() {
  const upsert = useJobs((s) => s.upsert);
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (jobId: string) => post<Job>(`/v1/jobs/${jobId}:retry`),
    onSuccess: (job) => {
      upsert(job);
      void qc.invalidateQueries({ queryKey: ["exports"] });
    },
  });
}

export function useCancelJob() {
  const upsert = useJobs((s) => s.upsert);
  return useMutation({
    mutationFn: (jobId: string) => post<Job>(`/v1/jobs/${jobId}:cancel`),
    onSuccess: (job) => upsert(job),
  });
}

// ---------------------------------------------------------------- lug'at

export const useLexicon = (projectId?: string) =>
  useQuery({
    queryKey: ["lexicon", projectId ?? null],
    queryFn: () =>
      get<LexiconEntry[]>(projectId ? `/v1/lexicon?project_id=${encodeURIComponent(projectId)}` : "/v1/lexicon"),
  });

export function useAddLexicon() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (v: { show_id?: string; term: string; variants: string[]; kind: LexiconKind }) =>
      post<LexiconEntry>("/v1/lexicon", v),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["lexicon"] }),
  });
}

export function useDeleteLexicon() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => del<Ok>(`/v1/lexicon/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["lexicon"] }),
  });
}

// ---------------------------------------------------------------- uslub shablonlari

export const useStyles = () => useQuery({ queryKey: ["styles"], queryFn: () => get<StyleRecord[]>("/v1/styles") });

export function useSaveStyle() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (v: { id?: string; name: string; template: StyleTemplate }) =>
      v.id
        ? put<StyleRecord>(`/v1/styles/${v.id}`, { name: v.name, template: v.template })
        : post<StyleRecord>("/v1/styles", { name: v.name, template: v.template }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["styles"] }),
  });
}

export function useDeleteStyle() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => del<Ok>(`/v1/styles/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["styles"] }),
  });
}

export function useImportStyle() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (path: string) => post<StyleRecord>("/v1/styles:import", { path }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["styles"] }),
  });
}

export const useExportStyle = () =>
  useMutation({ mutationFn: (v: { id: string; path: string }) => post<Ok>(`/v1/styles/${v.id}:export`, { path: v.path }) });

// ---------------------------------------------------------------- montaj: plaginlar va shablonlar

/** Barcha plaginlar bir marta olinadi; tur bo'yicha filtr mijozda (`useFxOf`). */
export const useFx = () =>
  useQuery({ queryKey: ["fx"], queryFn: () => get<FxManifest[]>("/v1/fx"), staleTime: 5 * 60_000 });

export function useFxOf(kinds: FxKind | FxKind[]): FxManifest[] {
  const fx = useFx();
  const list = Array.isArray(kinds) ? kinds : [kinds];
  return (fx.data ?? []).filter((m) => list.includes(m.kind));
}

export const useTemplates = () =>
  useQuery({ queryKey: ["templates"], queryFn: () => get<Template[]>("/v1/templates") });

export const useTemplate = (id: string | undefined) =>
  useQuery({
    queryKey: ["template", id],
    queryFn: () => get<Template>(`/v1/templates/${encodeURIComponent(id ?? "")}`),
    enabled: !!id,
  });

function useTemplateMutation<V, R>(fn: (v: V) => Promise<R>) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: fn,
    onSuccess: (res) => {
      if (res && typeof res === "object" && "id" in res && "name" in res) {
        const tpl = res as unknown as Template;
        qc.setQueryData(["template", tpl.id], tpl);
      }
      void qc.invalidateQueries({ queryKey: ["templates"] });
    },
  });
}

/** Yangi (`isNew`) - POST, aks holda PUT. Builtin - 409 (UI bunga yo'l qo'ymaydi). */
export const useSaveTemplate = () =>
  useTemplateMutation((v: { template: Template; isNew: boolean }) =>
    v.isNew
      ? post<Template>("/v1/templates", v.template)
      : put<Template>(`/v1/templates/${encodeURIComponent(v.template.id)}`, v.template),
  );

export const useDeleteTemplate = () =>
  useTemplateMutation((id: string) => del<Ok>(`/v1/templates/${encodeURIComponent(id)}`));

export const useDuplicateTemplate = () =>
  useTemplateMutation((v: { id: string; name?: string }) =>
    post<Template>(`/v1/templates/${encodeURIComponent(v.id)}:duplicate`, v.name ? { name: v.name } : {}),
  );

export const useImportTemplate = () =>
  useTemplateMutation((path: string) => post<Template>("/v1/templates:import", { path }));

export const useExportTemplate = () =>
  useMutation({
    mutationFn: (v: { id: string; path: string }) =>
      post<Ok>(`/v1/templates/${encodeURIComponent(v.id)}:export`, { path: v.path }),
  });

// ---------------------------------------------------------------- montajlar

export const useMontages = (projectId?: string) =>
  useQuery({
    queryKey: ["montages", projectId ?? null],
    queryFn: () =>
      get<MontageSummary[]>(projectId ? `/v1/montages?project_id=${encodeURIComponent(projectId)}` : "/v1/montages"),
  });

/** Reja tuzilayotganda (WS uzilgan bo'lsa ham) holat vaqti-vaqti bilan qayta so'raladi. */
export const useMontage = (id: string | undefined) =>
  useQuery({
    queryKey: ["montage", id],
    queryFn: () => get<MontageDetail>(`/v1/montages/${id}`),
    enabled: !!id,
    refetchInterval: (q) => (q.state.data?.status === "planning" ? 3000 : false),
  });

export interface CreateMontageVars {
  name?: string;
  project_id?: string;
  template_id: string;
  sources: MontageSource[];
  overrides?: MontageOverrides;
}

export function useCreateMontage() {
  const qc = useQueryClient();
  const upsert = useJobs((s) => s.upsert);
  return useMutation({
    mutationFn: (v: CreateMontageVars) => post<{ montage_id: string; job: Job }>("/v1/montages", v),
    onSuccess: (res) => {
      upsert(res.job);
      void qc.invalidateQueries({ queryKey: ["montages"] });
    },
  });
}

export function useSaveTimeline(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (tl: MontageTimeline) =>
      put<{ ok: boolean; timeline: MontageTimeline }>(`/v1/montages/${id}/timeline`, tl),
    onSuccess: (res) => {
      qc.setQueryData<MontageDetail>(["montage", id], (old) => (old ? { ...old, timeline: res.timeline } : old));
      void qc.invalidateQueries({ queryKey: ["montages"] });
    },
  });
}

/** Qayta reja: qo'lda tahrirlangan elementlar bo'lsa engine 409 qaytaradi - `force` bilan qayta yuboriladi. */
export function useReplanMontage(id: string) {
  const qc = useQueryClient();
  const upsert = useJobs((s) => s.upsert);
  return useMutation({
    mutationFn: (v: { template_id?: string; overrides?: MontageOverrides; force?: boolean }) =>
      post<Job>(`/v1/montages/${id}:replan`, v),
    onSuccess: (job) => {
      upsert(job);
      qc.setQueryData<MontageDetail>(["montage", id], (old) =>
        old ? { ...old, status: "planning", error: null } : old,
      );
      void qc.invalidateQueries({ queryKey: ["montage", id] });
    },
  });
}

export function useRenderMontage(id: string) {
  const qc = useQueryClient();
  const upsert = useJobs((s) => s.upsert);
  return useMutation({
    mutationFn: (v: { out_dir: string; filename?: string; allow_no_subs?: boolean }) =>
      post<Job>(`/v1/montages/${id}:render`, v),
    onSuccess: (job) => {
      upsert(job);
      void qc.invalidateQueries({ queryKey: ["exports"] });
    },
  });
}

export function useDeleteMontage() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => del<Ok>(`/v1/montages/${id}`),
    onSuccess: (_r, id) => {
      qc.removeQueries({ queryKey: ["montage", id] });
      void qc.invalidateQueries({ queryKey: ["montages"] });
    },
  });
}

/**
 * Montaj preview kadri. `timeline` berilsa (saqlanmagan draft) engine shu bo'yicha chizadi,
 * aks holda saqlangan timeline. `rev` - ko'rsatilayotgan holat (draft yoki saqlangan) xeshi.
 */
export function useMontagePreview(p: { id: string; tMs: number; rev: unknown; timeline?: MontageTimeline | null; enabled?: boolean }) {
  return useQuery({
    queryKey: ["montagePreview", p.id, p.tMs, p.rev],
    queryFn: ({ signal }) =>
      postBlob(`/v1/montages/${p.id}:preview`, p.timeline ? { t_ms: p.tMs, timeline: p.timeline } : { t_ms: p.tMs }, signal),
    enabled: p.enabled ?? true,
    staleTime: Infinity,
    gcTime: 30_000,
    placeholderData: keepPreviousData,
    retry: false,
  });
}

/** Muharrirdan musiqa qo'shish: engine faylni tekshiradi va saqlangan timeline `media` lug'atiga qo'shadi. */
export function useAddMontageMedia(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (v: { path: string; role: "music" }) => post<{ media: MediaRef }>(`/v1/montages/${id}/media`, v),
    onSuccess: (res) => {
      qc.setQueryData<MontageDetail>(["montage", id], (old) =>
        old?.timeline ? { ...old, timeline: { ...old.timeline, media: { ...old.timeline.media, [res.media.id]: res.media } } } : old);
    },
  });
}

/** Timeline kartasi uchun manbadan kichik kadr. */
export function useSourceThumb(p: { montageId: string; mediaId: string; tMs: number; enabled?: boolean }) {
  return useQuery({
    queryKey: ["montageThumb", p.montageId, p.mediaId, p.tMs],
    queryFn: ({ signal }) =>
      getBlob(`/v1/montages/${p.montageId}/sources/${encodeURIComponent(p.mediaId)}/thumb?t_ms=${p.tMs}`, signal),
    enabled: p.enabled ?? true,
    staleTime: Infinity,
    gcTime: 5 * 60_000,
    retry: false,
  });
}

// ---------------------------------------------------------------- WebSocket hodisalari

/** Montaj vazifasi (reja yoki render) tugaganda - muvaffaqiyatli yoki xato bilan. */
function onMontageJobSettled(qc: QueryClient, job: Job) {
  const mid = job.meta["montage_id"];
  if (typeof mid === "string") void qc.invalidateQueries({ queryKey: ["montage", mid] });
  void qc.invalidateQueries({ queryKey: ["montages"] });
}

function onJobDone(qc: QueryClient, job: Job) {
  const eid = job.meta["episode_id"] as string | undefined;
  switch (job.kind) {
    case "analyze":
      if (eid) {
        for (const k of ["clips", "transcript", "speakers", "episode"]) void qc.invalidateQueries({ queryKey: [k, eid] });
      }
      void qc.invalidateQueries({ queryKey: ["episodes"] });
      break;
    case "export":
      if (eid) void qc.invalidateQueries({ queryKey: ["clips", eid] });
      break;
    case "install":
    case "pack":
      void qc.invalidateQueries({ queryKey: ["models"] });
      void qc.invalidateQueries({ queryKey: ["capabilities"] });
      break;
  }
}

/** WebSocket hodisalari -> jobs do'koni va kesh yangilanishi. Ilova bo'ylab bir marta ulanadi. */
export function useEngineEvents() {
  const upsert = useJobs((s) => s.upsert);
  const qc = useQueryClient();
  useEffect(() => {
    let ws: WebSocket | null = null;
    let closed = false;
    let retry: ReturnType<typeof setTimeout> | undefined;
    const connect = async () => {
      try {
        ws = new WebSocket(await eventsUrl());
      } catch {
        retry = setTimeout(connect, 2000);
        return;
      }
      ws.onmessage = (m) => {
        let ev: EngineEvent;
        try {
          ev = JSON.parse(m.data as string) as EngineEvent;
        } catch {
          return;
        }
        if (ev.type !== "job") return;
        upsert(ev.job);
        if (ev.job.kind === "export") {
          // Navbat ro'yxati faqat yangi vazifa paydo bo'lganda qayta so'raladi; progress jobs do'konidan.
          const known = qc.getQueryData<ExportItem[]>(["exports"])?.some((x) => x.job.id === ev.job.id);
          if (!known) void qc.invalidateQueries({ queryKey: ["exports"] });
        }
        if (ev.job.status === "done") onJobDone(qc, ev.job);
        const settled = ev.job.status === "done" || ev.job.status === "failed" || ev.job.status === "cancelled";
        if (settled && (ev.job.kind === "montage" || typeof ev.job.meta["montage_id"] === "string")) {
          onMontageJobSettled(qc, ev.job);
        }
      };
      ws.onclose = () => {
        if (!closed) retry = setTimeout(connect, 2000);
      };
    };
    void connect();
    return () => {
      closed = true;
      if (retry) clearTimeout(retry);
      ws?.close();
    };
  }, [upsert, qc]);
}
