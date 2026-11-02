// Engine API turlarining plaginlarga kerakli qismi (to'liq ro'yxat: app/src/api/types.ts, docs/04-engine-api.md).

/** Subtitr imlosi (docs/08-ozbek-imlosi.md): rasmiy (oʻ), ASCII (o'), yangi alifbo (ö). */
export type Orthography = "official" | "ascii" | "new";

export type JobStatus = "queued" | "running" | "done" | "failed" | "cancelled";

export interface Job {
  id: string;
  kind: "analyze" | "export" | "install" | "pack" | "montage";
  status: JobStatus;
  progress: number;
  stage: string | null;
  error: string | null;
  result: Record<string, unknown> | null;
  meta: Record<string, unknown>;
}

export type ClipStatus = "nomzod" | "qabul" | "rad" | "eksport_qilingan";

export interface Clip {
  id: string;
  media_id: string;
  start_ms: number;
  end_ms: number;
  title: string;
  caption: string;
  hashtags: string[];
  kind: string | null;
  score: number;
  reason: string;
  status: ClipStatus;
  source: "ai_llm" | "ai_lite" | "qolda";
  cuts: [number, number][];
}

export interface TranscriptWord {
  text: string;
  start_ms: number;
  end_ms: number;
  conf: number | null;
  speaker: string | null;
}

export interface TranscriptSentence {
  id: number;
  start_ms: number;
  end_ms: number;
  speaker: string | null;
  text: string;
  words: TranscriptWord[];
}

export interface LocalText {
  uz: string;
  "uz-Cyrl"?: string;
  ru?: string;
  en?: string;
}

export interface Template {
  id: string;
  name: LocalText;
  description?: LocalText;
  category: string;
  builtin: boolean;
  aspect: "9:16" | "1:1" | "16:9";
  target_duration_ms: number;
}

export type MontageSource =
  | { kind: "file"; path: string }
  | { kind: "clip"; episode_id: string; clip_id: string }
  | { kind: "episode"; episode_id: string };
