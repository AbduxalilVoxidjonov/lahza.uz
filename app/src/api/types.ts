// Engine API turlari (engine/src/lahza_engine/api/app.py va types.py bilan mos).

export type Tier = "unsupported" | "lite" | "standard" | "pro";
export type Task = "asr" | "align" | "vad" | "diarization" | "vision" | "llm";
export type Compat = "recommended" | "slow" | "incompatible";
export type Orthography = "official" | "ascii" | "new";
export type ClipStatus = "nomzod" | "qabul" | "rad" | "eksport_qilingan";
export type ClipSource = "ai_llm" | "ai_lite" | "qolda";
export type ClipKind = "maslahat" | "hikoya" | "kulgili" | "bahsli_fikr" | "fakt" | "savol_javob";
export type JobStatus = "queued" | "running" | "done" | "failed" | "cancelled";

export interface Gpu {
  vendor: string;
  name: string;
  vram_gb: number | null;
}

export interface HardwareInfo {
  profile: {
    os: string;
    os_version: string;
    arch: string;
    cpu: string;
    ram_gb: number;
    free_disk_gb: number;
    gpus: Gpu[];
  };
  tier: Tier;
  reasons: string[];
}

export interface CatalogEntry {
  id: string;
  task: Task;
  name: string;
  version: string;
  license: string;
  source_url: string;
  status: "candidate" | "approved" | "deprecated";
  files: { path: string; size_bytes: number | null }[];
}

export interface BundleItem {
  task: Task;
  entry: CatalogEntry | null;
  compat: Compat | null;
  reason: string;
  mandatory: boolean;
}

export interface Bundle {
  tier: Tier;
  items: BundleItem[];
}

export interface InstalledModel {
  id: string;
  task: Task;
  version: string;
  path: string;
  source: "catalog" | "custom";
  verified: boolean;
  installed_at?: string;
  /** `:test` natijasi (null - hali sinalmagan). */
  self_test_ok?: boolean | null;
}

export interface Registry {
  models: InstalledModel[];
  defaults: Record<string, string>;
}

export interface Project {
  id: string;
  name: string;
  created_at?: string;
}

export interface Episode {
  id: string;
  show_id: string;
  title: string;
  project_dir: string;
  status: EpisodeStatus;
  highlight_mode?: HighlightMode | null;
  created_at: string;
}

export type EpisodeStatus = "new" | "analyzing" | "ready" | "failed";
export type HighlightMode = "llm" | "lite";

export interface MediaInfo {
  duration_ms: number;
  fps: number;
  width: number;
  height: number;
  path: string;
}

/** GET /v1/episodes/{eid} */
export interface EpisodeDetail {
  id: string;
  show_id: string;
  title: string;
  status: EpisodeStatus;
  project_dir: string;
  media: MediaInfo | null;
  highlight_mode: HighlightMode | null;
}

export interface Waveform {
  duration_ms: number;
  /** 0..1 oralig'idagi cho'qqilar. */
  peaks: number[];
}

export interface Speaker {
  label: string;
  display_name: string | null;
}

export type Layout = "focus" | "split" | "fit_blur" | "manual";
export type Lane = "a" | "b";

export interface Keyframe {
  /** Chiqish (klip ichidagi, kesimlardan keyingi) vaqti. */
  t_ms: number;
  layout: Layout;
  /** 0..1; engine `null` qaytarishi mumkin (markaz aniqlanmagan, masalan fit_blur). */
  cx: number | null;
  cy: number | null;
  /** 0.5..4 */
  zoom: number;
  lane: Lane;
  source: string;
}

export type LexiconKind = "ism" | "brend" | "atama";

export interface LexiconEntry {
  /** library.db -> lexicon.id (INTEGER). */
  id: number;
  show_id: string | null;
  term: string;
  variants: string[];
  kind: LexiconKind;
}

export interface FontInfo {
  family: string;
  path: string;
  ok: boolean;
  missing: string[];
}

export interface Capabilities {
  ffmpeg: boolean;
  libass: boolean;
  encoders: string[];
  vad: "silero" | "energy";
  aligner: boolean;
  diarizer: boolean;
  face_detector: boolean;
  llm: boolean;
}

export interface ExportItem {
  job: Job;
  episode_id: string;
  clip_id: string;
  title: string;
}

export type JobKind = "analyze" | "export" | "install" | "pack";

export interface Job {
  id: string;
  kind: JobKind;
  status: JobStatus;
  progress: number;
  stage: string | null;
  error: string | null;
  result: Record<string, unknown> | null;
  /** retry_of, export_id, title, episode_id, clip_id; pack uchun op: "export" | "import". */
  meta: Record<string, unknown>;
  /** Unix vaqt (s). */
  created_at?: number;
}

export interface Word {
  text: string;
  start_ms: number;
  end_ms: number;
  conf: number | null;
  speaker: string | null;
  edited: boolean;
  /** Tahrirdan oldingi ASR matni (faqat edited=true bo'lsa). */
  original_text?: string | null;
}

export interface Sentence {
  id: number;
  start_ms: number;
  end_ms: number;
  speaker: string | null;
  words: Word[];
  text: string;
}

export interface Clip {
  id: string;
  media_id: string;
  start_ms: number;
  end_ms: number;
  start_sentence_id: number;
  end_sentence_id: number;
  hook_sentence_id: number | null;
  title: string;
  caption: string;
  hashtags: string[];
  kind: ClipKind | null;
  score: number;
  scores: Record<string, number>;
  reason: string;
  status: ClipStatus;
  source: ClipSource;
  llm_model_id?: string | null;
  cuts: [number, number][];
}

export interface StyleTemplate {
  name: string;
  font_family: string;
  font_size: number;
  bold: boolean;
  primary_color: string;
  highlight_color: string;
  outline_color: string;
  outline_width: number;
  shadow: number;
  box: boolean;
  box_color: string;
  box_opacity: number;
  position: "lower" | "middle" | "upper";
  uppercase: boolean;
  animation: "karaoke" | "pop" | "none";
  max_words: number;
  max_lines: number;
  orthography: Orthography;
  /** Pop animatsiyasi kattalashuvi, % (100..160). */
  pop_scale: number;
  keywords: string[];
  remove_fillers: boolean;
  filler_words: string[];
  mask_profanity: boolean;
  profanity_words: string[];
  logo_path: string | null;
  logo_position: LogoPosition;
  logo_opacity: number;
}

export type LogoPosition = "top_left" | "top_right" | "bottom_left" | "bottom_right";

export interface StyleRecord {
  id: string;
  name: string;
  template: StyleTemplate;
}

export const DEFAULT_STYLE: StyleTemplate = {
  name: "Standart",
  font_family: "Inter",
  font_size: 72,
  bold: true,
  primary_color: "#FFFFFF",
  highlight_color: "#FFD400",
  outline_color: "#000000",
  outline_width: 5,
  shadow: 0,
  box: false,
  box_color: "#000000",
  box_opacity: 0.6,
  position: "lower",
  uppercase: false,
  animation: "karaoke",
  max_words: 3,
  max_lines: 2,
  orthography: "official",
  pop_scale: 115,
  keywords: [],
  remove_fillers: false,
  filler_words: ["ee", "eee", "mmm", "hmm", "aa", "ı"],
  mask_profanity: false,
  profanity_words: [],
  logo_path: null,
  logo_position: "top_right",
  logo_opacity: 0.8,
};

export interface EngineEvent {
  type: "job";
  ts: number;
  job: Job;
}
