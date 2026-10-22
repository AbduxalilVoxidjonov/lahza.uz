// Host qatlami: UI va engine oqimi faqat `HostAdapter` bilan gaplashadi.
// `HostOps` - past darajadagi host amallari (Premiere: premiere.ts, testlar: fake.ts).
// Rejani amallarga aylantirish (`buildFromPlan`, build.ts) host-neytral va soxta ops bilan to'liq testlanadi.

import type { HostPlan, HostSequence, HostTransition, Marker, TransformKey } from "@shared/hostplan";

export interface ProjectInfo {
  name: string;
  path: string;
  activeSequence: string | null;
}

export interface BuildStep {
  index: number;
  total: number;
  key: StepKey;
  detail?: string;
}

export type StepKey = "import" | "sequence" | "clip" | "music" | "captions" | "markers" | "text" | "done";

/** Host'ga o'tmagan yoki taxminiy o'tgan narsa. `code` - i18n kaliti (`warn.<code>`), `detail` - aniq joy. */
export interface HostWarning {
  code: WarnCode;
  detail?: string;
}

export type WarnCode =
  | "keyframes_static" // kalit kadrlar o'tmadi -> statik scale/position
  | "transform_failed"
  | "speed" // tezlikni o'zgartirish API'da yo'q
  | "blur_missing"
  | "crop_missing"
  | "lumetri" // Lumetri preset API'da yo'q
  | "lut"
  | "transition_missing"
  | "transition_failed"
  | "audio_level"
  | "music_fades"
  | "music_duck"
  | "captions_imported_only" // SRT loyihaga import qilindi, trekka qo'lda
  | "captions_failed"
  | "captions_none"
  | "text_as_marker" // matn qatlami -> marker
  | "marker_failed"
  | "clip_failed"
  | "media_missing"
  | "sequence_settings" // sekvensiya o'lchami/fps talab qilinganidan farq qiladi
  | "audio_level_approx" // audio daraja dB -> Premiere "Level" qiymati taxminiy formulada
  | "not_translated"; // engine'ning o'z ro'yxati (plan.not_translated)

export interface BuildResult {
  sequenceName: string;
  warnings: HostWarning[];
  placedClips: number;
}

export interface HostAdapter {
  /** Loyiha panelida (yoki faol sekvensiyada) tanlangan media fayllarining absolyut yo'llari. */
  selectedMediaPaths(): Promise<string[]>;
  projectInfo(): Promise<ProjectInfo | null>;
  buildFromPlan(plan: HostPlan, onStep?: (s: BuildStep) => void): Promise<BuildResult>;
}

/** Host buni qila olmaydi (API yo'q yoki tasdiqlanmagan). build.ts fallback qiladi va ogohlantiradi. */
export class HostUnsupported extends Error {
  constructor(
    public code: WarnCode,
    message: string,
  ) {
    super(message);
    this.name = "HostUnsupported";
  }
}

export interface ItemRef {
  /** Host'dagi element (Premiere: VideoClipTrackItem); fake'da - satr id. */
  handle: unknown;
  videoTrack: number;
}

export interface PlaceVideoRequest {
  itemId: string;
  mediaPath: string;
  videoTrack: number;
  /** `null` - audio kerak emas (bg/top qatlam nusxasi): host uni o'chirib qo'yadi. */
  audioTrack: number | null;
  recIn: number;
  recOut: number;
  srcIn: number;
  srcOut: number;
  name: string | null;
}

export interface PlaceAudioRequest {
  mediaPath: string;
  audioTrack: number;
  recIn: number;
  recOut: number;
  srcIn: number;
  name: string;
}

export interface TransformContext {
  sequence: HostSequence;
  mediaWidth: number;
  mediaHeight: number;
  /** element boshidagi manba vaqti (kalit kadr vaqti manba vaqtida bo'lsa kerak). */
  srcIn: number;
  recIn: number;
}

export interface CropPct {
  left: number;
  top: number;
  right: number;
  bottom: number;
}

export interface HostOps {
  importFiles(paths: string[]): Promise<void>;
  createSequence(seq: HostSequence): Promise<{ name: string }>;
  placeVideo(req: PlaceVideoRequest): Promise<ItemRef>;
  /** Asosiy qatlam audiosi: daraja (dB) va o'chirish. */
  setClipAudio(item: ItemRef, opts: { volumeDb: number; mute: boolean }): Promise<void>;
  setTransform(item: ItemRef, keys: TransformKey[], ctx: TransformContext): Promise<void>;
  addGaussianBlur(item: ItemRef, amount: number): Promise<void>;
  setCrop(item: ItemRef, crop: CropPct): Promise<void>;
  addTransition(item: ItemRef, kind: Exclude<HostTransition["kind"], "cut">, durS: number): Promise<void>;
  placeAudio(req: PlaceAudioRequest): Promise<ItemRef>;
  setAudioLevel(item: ItemRef, db: number): Promise<void>;
  /** SRT: "placed" - captions trekiga qo'yildi; "imported" - faqat loyihaga import qilindi. */
  importCaptions(srtPath: string, sequence: HostSequence): Promise<"placed" | "imported">;
  addMarker(m: Marker, durS?: number): Promise<void>;
}
