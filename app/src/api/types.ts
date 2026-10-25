// Engine API turlari (engine/src/lahza_engine/api/app.py va types.py bilan mos).

export type Tier = "unsupported" | "lite" | "standard" | "pro";
export type Task = "asr" | "align" | "vad" | "diarization" | "vision" | "llm";
export type Compat = "recommended" | "slow" | "incompatible";
export type Orthography = "official" | "ascii" | "new";
/** Subtitr yozuvi (PRO-4): "cyrillic" - lug'atli transliteratsiya engine'da. */
export type Script = "latin" | "cyrillic";
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
  /** Montaj render vazifalarida bo'sh bo'lishi mumkin (meta.montage_id ishlatiladi). */
  episode_id?: string | null;
  clip_id?: string | null;
  title?: string | null;
  /** Montaj renderi uchun (klip maydonlari bunda null). */
  montage_id?: string | null;
}

/** `download` - YouTube havolasidan yuklash (YT-1); `meta.download`: {downloaded_bytes, total_bytes, speed, eta}. */
export type JobKind = "analyze" | "export" | "install" | "pack" | "montage" | "download";

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
  /** PRO-3 "Hook oldinga": null/yo'q - o'chiq; aks holda shu bo'lak (manba vaqti) klip boshiga nusxalanadi. */
  hook?: ClipHook | null;
}

export interface ClipHook {
  start_ms: number;
  end_ms: number;
}

export interface HookCandidate extends ClipHook {
  sentence_ids: number[];
  text: string;
  score: number;
  reasons: string[];
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
  /** Yozuv; yo'q bo'lsa "latin" (eski shablonlar). */
  script?: Script;
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
  script: "latin",
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

export type EngineEvent =
  | { type: "job"; ts: number; job: Job }
  /** Partiyaviy navbat o'zgardi; `item: null` - bir nechta element yoki o'chirish. */
  | { type: "queue"; ts: number; item: QueueItem | null };

/** Partiyaviy tahlil navbati elementi (PRO-5, `/v1/queue`). */
export interface QueueItem {
  id: string;
  project_id: string;
  /** Element ishga tushganda yaratiladi. */
  episode_id: string | null;
  path: string;
  title: string | null;
  options: { focus?: string | null; num_speakers?: number | null; force_lite?: boolean };
  position: number;
  status: JobStatus;
  progress: number;
  stage: string | null;
  error: string | null;
  job_id: string | null;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
}

// ================================================================ Lahza Montaj (docs/11, ADR-0011/0012)

/** Lokalizatsiyalangan matn (`uz` majburiy). */
export interface LocalText {
  uz: string;
  "uz-Cyrl"?: string | null;
  ru?: string | null;
  en?: string | null;
}

export type FxKind = "transition" | "motion" | "color" | "text" | "overlay" | "audio" | "speed";
export type FxParamType = "float" | "int" | "enum" | "bool" | "color" | "string" | "path";

export interface FxParamSpec {
  id: string;
  type: FxParamType;
  min?: number | null;
  max?: number | null;
  values?: string[] | null;
  default?: unknown;
  /** Ixtiyoriy lokal nom (manifestda bo'lsa). */
  name?: Record<string, string> | null;
}

/** GET /v1/fx - plagin manifesti (`lahza.fx/1`). */
export interface FxManifest {
  schema?: string;
  id: string;
  version: string;
  kind: FxKind;
  name: Record<string, string>;
  description?: Record<string, string> | null;
  backend: string;
  params: FxParamSpec[];
  default_trigger?: string | null;
  license?: string | null;
}

export type Aspect = "9:16" | "1:1" | "16:9";
export const ASPECTS: Aspect[] = ["9:16", "1:1", "16:9"];
export type TemplateCategory = "podkast" | "elon" | "tadbir" | "mahsulot" | "intervyu" | "talim" | "boshqa";
export type FxTrigger = "on_start" | "on_end" | "on_cut" | "on_emphasis" | "on_speaker_change" | "every_n";
export type TextKind = "card" | "title" | "hook" | "cta" | "lower_third";
export type TextPosition = "upper" | "middle" | "lower";
export type TextAnimation = "none" | "fade" | "pop" | "slide_up";
export type Selection = "highlight" | "scenes" | "full";
export type ShotOrder = "berilgan" | "xronologik" | "ball";

export interface TransitionRef {
  plugin: string;
  dur_ms: number;
  params?: Record<string, unknown>;
}

export interface TextCard {
  text: string;
  dur_ms: number;
  kind: TextKind;
  background?: string | null;
  position: TextPosition;
  animation: TextAnimation;
}

export interface FxRule {
  plugin: string;
  trigger: FxTrigger;
  params?: Record<string, unknown>;
  every_n?: number | null;
  max_count?: number | null;
  min_gap_ms: number;
}

export interface MusicSpec {
  required: boolean;
  gain_db: number;
  duck: boolean;
  fade_in_ms: number;
  fade_out_ms: number;
}

/** Video shablon (`lahza.template/1`). Javobda `None` maydonlar tushirib qoldiriladi. */
export interface Template {
  schema?: "lahza.template/1";
  id: string;
  version: string;
  name: LocalText;
  description?: LocalText | null;
  category: TemplateCategory;
  builtin: boolean;
  aspect: Aspect;
  fps: number;
  target_duration_ms: number;
  min_shot_ms: number;
  max_shot_ms: number;
  selection: Selection;
  order: ShotOrder;
  max_per_source?: number | null;
  respect_sentences: boolean;
  reframe: "auto" | "fit_blur" | "center";
  transition?: TransitionRef | null;
  fx: FxRule[];
  color?: string | null;
  captions: boolean;
  caption_style?: StyleTemplate | null;
  intro?: TextCard | null;
  hook_text?: TextCard | null;
  outro?: TextCard | null;
  music?: MusicSpec | null;
  source_gain_db: number;
  mute_sources: boolean;
  loudnorm_lufs?: number | null;
  logo: boolean;
}

export interface MontageFormat {
  aspect: Aspect;
  w: number;
  h: number;
  fps: number;
  audio_hz: number;
}

export interface MediaRef {
  id: string;
  path: string;
  hash?: string | null;
  duration_ms: number;
  width: number;
  height: number;
  fps: number;
  has_audio: boolean;
  origin: string;
}

export interface FxRef {
  plugin: string;
  at_ms: number;
  dur_ms?: number | null;
  params: Record<string, unknown>;
  source: "shablon" | "qolda";
}

export interface Crop {
  cx: number;
  cy: number;
  zoom: number;
}

export type ItemReframe = "auto" | "focus" | "fit_blur" | "center";

export interface VideoItem {
  id: string;
  media: string;
  src_in_ms: number;
  src_out_ms: number;
  reframe: ItemReframe;
  crop?: Crop | null;
  speed: number;
  volume_db: number;
  mute: boolean;
  transition_in?: TransitionRef | null;
  fx: FxRef[];
  role?: string | null;
  reason: string;
  user_edited: boolean;
}

export interface TextItem {
  id: string;
  start_ms: number;
  end_ms: number;
  text: string;
  kind: TextKind;
  background?: string | null;
  position: TextPosition;
  animation: TextAnimation;
  font_size?: number | null;
}

export interface MusicItem {
  media: string;
  src_in_ms: number;
  start_ms: number;
  end_ms?: number | null;
  gain_db: number;
  duck: boolean;
  fade_in_ms: number;
  fade_out_ms: number;
}

export interface Captions {
  enabled: boolean;
  style: StyleTemplate;
  words: Word[];
}

export interface Brand {
  logo_path?: string | null;
  logo_position: LogoPosition;
  logo_opacity: number;
}

export interface AudioMix {
  source_gain_db: number;
  loudnorm_lufs?: number | null;
  fade_ms: number;
}

export interface Provenance {
  template_id?: string | null;
  template_version?: string | null;
  engine?: string | null;
  created_at?: string | null;
  planner?: string | null;
  notes: string[];
}

/** Lahza Timeline (`lahza.timeline/1`) - JSON'da kalit `schema`. */
export interface StickerItem {
  id: string;
  path: string;
  start_ms: number;
  end_ms: number;
  x: number;
  y: number;
  width: number;
  height: number;
  rotation: number;
  opacity: number;
  layer: number;
  animation: "none" | "fade" | "pop";
}

export interface MontageTimeline {
  target_platform?: TargetPlatform;
  schema: "lahza.timeline/1";
  format: MontageFormat;
  media: Record<string, MediaRef>;
  video: VideoItem[];
  text: TextItem[];
  music: MusicItem[];
  stickers?: StickerItem[];
  captions: Captions;
  brand: Brand;
  audio: AudioMix;
  color?: FxRef | null;
  provenance: Provenance;
}

export type MontageSource =
  | { kind: "file"; path: string }
  | { kind: "clip"; episode_id: string; clip_id: string }
  | { kind: "episode"; episode_id: string };

export interface MontageOverrides {
  target_platform?: TargetPlatform;
  target_duration_ms?: number | null;
  aspect?: Aspect | null;
  music_path?: string | null;
  title?: string | null;
  cta?: string | null;
  shou?: string | null;
  captions?: boolean | null;
  caption_style?: StyleTemplate | null;
  logo_path?: string | null;
  transition?: string | null;
  color?: string | null;
}

export type MontageStatus = "planning" | "ready" | "failed";

/** GET /v1/montages ro'yxati elementi. */
export interface MontageSummary {
  id: string;
  name: string;
  template_id: string;
  status: MontageStatus;
  duration_ms: number | null;
  created_at: string;
  updated_at: string;
  project_id: string | null;
}

/** GET /v1/montages/{id} `exports[]` elementi. */
export interface MontageExport {
  id: string;
  job_id: string | null;
  path: string | null;
  status: JobStatus;
  error: string | null;
  created_at: string | null;
  finished_at: string | null;
}

/** Yechilgan manba: `media_id` (src1, src2, ...) = timeline `MediaRef.id`; epizod/klip uchun `title`. */
export type MontageSourceResolved = MontageSource & { media_id?: string; path?: string; title?: string | null };

/** GET /v1/montages/{id}. */
export interface MontageDetail {
  id: string;
  name: string;
  template_id: string;
  project_id?: string | null;
  status: MontageStatus;
  duration_ms?: number | null;
  created_at?: string;
  updated_at?: string;
  sources: MontageSourceResolved[];
  overrides: MontageOverrides | null;
  timeline: MontageTimeline | null;
  /** Reja xatosi; qayta reja muvaffaqiyatsiz bo'lsa status=ready bo'lib qoladi va bu to'ldiriladi. */
  error: string | null;
  user_edited?: boolean;
  /** Joriy/oxirgi reja vazifasi. */
  job_id?: string | null;
  exports: MontageExport[];
}

export interface MontageRenderResult {
  video: string;
  edl: string;
  srt: string | null;
  warnings: string[];
  encoder?: string;
}

export type TargetPlatform = "instagram_reels" | "youtube_shorts" | "youtube_video" | "custom";
export interface ExportProfile {
  id: TargetPlatform;
  name: string;
  recommended_format: { aspect: "9:16" | "16:9"; w: number; h: number; fps: number } | null;
  safe_zone: { top_pct: number; bottom_pct: number; side_pct: number };
  safe_zone_note: string;
  restrictions: { max_duration_s: number | null; square_or_vertical: boolean };
  recommendations: { max_duration_s: number | null; encoding: string | null; fps_note: string };
  sources: { url: string; verification_status: "verified" | "unavailable"; note: string }[];
  verified_at: string;
}

export interface ProfileEvaluation { errors: string[]; warnings: string[] }
