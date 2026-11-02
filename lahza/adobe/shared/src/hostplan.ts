// Host-reja (`lahza.hostplan/1`) - engine/src/lahza_engine/hostplan/model.py ning TS nusxasi.
// Ikkalasi bir xil bo'lishi shart: Python modeli o'zgarsa, shu fayl ham yangilanadi.
// Vaqt - soniya. `rec_*` - sekvensiya/kompozitsiya vaqti, `src_*` - manba fayl vaqti.
// `pos_x`/`pos_y` - manba kadri markazi sekvensiyaning qaysi pikseliga tushadi; `scale_pct` - 100 = asl o'lcham.

export const HOSTPLAN_SCHEMA = "lahza.hostplan/1" as const;

export interface HostSequence {
  name: string;
  width: number;
  height: number;
  fps: number;
  audio_hz: number;
  duration_s: number;
}

export interface HostMedia {
  id: string;
  path: string;
  width: number;
  height: number;
  fps: number;
  duration_s: number;
  has_audio: boolean;
}

export interface TransformKey {
  t: number;
  scale_pct: number;
  pos_x: number;
  pos_y: number;
  rotation: number;
  interp: "linear" | "hold" | "ease";
}

export interface HostEffect {
  kind: "gaussian_blur" | "lumetri_preset" | "lut";
  amount: number | null;
  preset: string | null;
  lut_path: string | null;
}

export interface HostLayer {
  role: "main" | "bg" | "top" | "bottom";
  keys: TransformKey[];
  effects: HostEffect[];
  crop_rect: [number, number, number, number] | null;
}

export interface HostTransition {
  kind: "cut" | "cross_dissolve" | "dip_to_black" | "dip_to_white" | "push" | "wipe" | "zoom";
  dur_s: number;
  lahza_plugin: string | null;
}

export interface VideoClipItem {
  id: string;
  media: string;
  src_in: number;
  src_out: number;
  rec_in: number;
  rec_out: number;
  speed: number;
  volume_db: number;
  mute: boolean;
  layers: HostLayer[];
  transition_in: HostTransition | null;
  label: string | null;
}

export interface MusicItem {
  media: string;
  src_in: number;
  rec_in: number;
  rec_out: number;
  volume_db: number;
  duck: boolean;
  fade_in_s: number;
  fade_out_s: number;
}

export interface CaptionWord {
  text: string;
  t0: number;
  t1: number;
}

export interface CaptionLine {
  t0: number;
  t1: number;
  text: string;
  words: CaptionWord[];
  speaker: string | null;
}

export interface Captions {
  srt_path: string | null;
  words_path: string | null;
  lines: CaptionLine[];
  style: Record<string, unknown>;
}

export interface TextOverlay {
  id: string;
  rec_in: number;
  rec_out: number;
  text: string;
  kind: "title" | "hook" | "lower_third" | "cta" | "card";
  background: string | null;
  position: "upper" | "middle" | "lower";
}

export interface Marker {
  t: number;
  name: string;
  comment: string;
  kind: "hook" | "highlight" | "emphasis" | "note";
}

export interface HostPlan {
  schema: typeof HOSTPLAN_SCHEMA;
  source: "clip" | "montage";
  source_id: string;
  sequence: HostSequence;
  media: HostMedia[];
  video: VideoClipItem[];
  music: MusicItem[];
  captions: Captions;
  text: TextOverlay[];
  markers: Marker[];
  not_translated: string[];
}

/** Engine'dan kelgan JSON haqiqatan host-reja ekanini tekshiradi (plagin noto'g'ri versiya bilan ishlamasin). */
export function assertHostPlan(x: unknown): HostPlan {
  const p = x as Partial<HostPlan> | null;
  if (!p || p.schema !== HOSTPLAN_SCHEMA || !p.sequence || !Array.isArray(p.video) || !Array.isArray(p.media)) {
    throw new Error("Engine javobi lahza.hostplan/1 emas — plagin va engine versiyalarini tekshiring");
  }
  return p as HostPlan;
}
