// Transkripsiya sifati (Sozlamalar): sof mantiq (React'siz - node testlari uchun).
// Engine: GET/POST /v1/asr-quality (engine/src/lahza_engine/models/asr_quality.py).
// "Tez" = NavAI base (standart, birinchi sozlash o'rnatadi), "Aniq" = NavAI small (ixtiyoriy).

export type QualityMode = "fast" | "accurate";

export interface QualityStatusLike {
  mode: QualityMode | "custom" | "none";
  current_model_id: string | null;
  fast: { installed: boolean };
  accurate: { installed: boolean; download_bytes: number; download_available: boolean };
}

export interface JobLike {
  id: string;
  status: string;
  meta: Record<string, unknown>;
}

/** Tanlangan radio qiymati: boshqa ASR (custom) yoki ASR yo'q bo'lsa - hech biri. */
export function selectedMode(s: QualityStatusLike): QualityMode | null {
  return s.mode === "fast" || s.mode === "accurate" ? s.mode : null;
}

/**
 * Foydalanuvchi rejimni tanlaganda nima qilinadi:
 * `none` - allaqachon tanlangan; `switch` - o'rnatilgan, darhol almashtiriladi;
 * `offer` - "Aniq" o'rnatilmagan: yuklash/fayldan o'rnatish taklif qilinadi;
 * `missing` - "Tez" modeli yo'q (birinchi sozlash tugamagan).
 */
export function chooseAction(s: QualityStatusLike, mode: QualityMode): "none" | "switch" | "offer" | "missing" {
  if (s.mode === mode) return "none";
  if (mode === "fast") return s.fast.installed ? "switch" : "missing";
  return s.accurate.installed ? "switch" : "offer";
}

/** Yuklash hajmi foydalanuvchiga: "~240 MB" (MiB, 10 ga yaxlitlangan). */
export function approxMb(bytes: number): string {
  const mb = bytes / 1024 / 1024;
  return `~${Math.max(10, Math.round(mb / 10) * 10)} MB`;
}

export const isActive = (job: JobLike | undefined): boolean =>
  !!job && (job.status === "running" || job.status === "queued");

/** Sahifa qayta ochilganda ham davom etayotgan "Aniq" o'rnatish vazifasi topiladi. */
export function activeQualityJob<J extends JobLike>(jobs: Record<string, J>): J | undefined {
  return Object.values(jobs).find((j) => j.meta["op"] === "asr-quality" && isActive(j));
}
