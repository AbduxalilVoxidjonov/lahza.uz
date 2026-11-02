// Test uchun host-rejalar (engine `plan_from_clip` / `plan_from_montage` chiqishiga o'xshash).
import type { HostPlan, VideoClipItem } from "@shared/hostplan";

const W = 1080;
const H = 1920;

export function clipPlan(): HostPlan {
  return {
    schema: "lahza.hostplan/1",
    source: "clip",
    source_id: "c1",
    sequence: { name: "Lahza — Mehmon gapi", width: W, height: H, fps: 30, audio_hz: 48000, duration_s: 9 },
    media: [
      { id: "m1", path: "/media/podcast.mp4", width: 1920, height: 1080, fps: 30, duration_s: 3600, has_audio: true },
      { id: "mus", path: "/media/music.mp3", width: 0, height: 0, fps: 0, duration_s: 120, has_audio: true },
    ],
    video: [
      // ikkinchi bo'lak oldin turibdi - build rec_in bo'yicha saralashi kerak
      {
        id: "v2",
        media: "m1",
        src_in: 104,
        src_out: 109,
        rec_in: 4,
        rec_out: 9,
        speed: 1,
        volume_db: 0,
        mute: false,
        layers: [
          {
            role: "main",
            keys: [
              { t: 0, scale_pct: 177.7778, pos_x: 700, pos_y: 960, rotation: 0, interp: "linear" },
              { t: 2, scale_pct: 177.7778, pos_x: 540, pos_y: 960, rotation: 0, interp: "hold" },
              { t: 4.5, scale_pct: 177.7778, pos_x: 380, pos_y: 960, rotation: 0, interp: "linear" },
            ],
            effects: [],
            crop_rect: null,
          },
        ],
        transition_in: { kind: "cut", dur_s: 0, lahza_plugin: null },
        label: "asosiy",
      },
      {
        id: "v1",
        media: "m1",
        src_in: 100,
        src_out: 104,
        rec_in: 0,
        rec_out: 4,
        speed: 1,
        volume_db: -3,
        mute: false,
        layers: [
          {
            role: "bg",
            keys: [{ t: 0, scale_pct: 177.7778, pos_x: 540, pos_y: 960, rotation: 0, interp: "linear" }],
            effects: [{ kind: "gaussian_blur", amount: 60, preset: null, lut_path: null }],
            crop_rect: null,
          },
          {
            role: "main",
            keys: [{ t: 0, scale_pct: 56.25, pos_x: 540, pos_y: 960, rotation: 0, interp: "linear" }],
            effects: [],
            crop_rect: null,
          },
        ],
        transition_in: null,
        label: "hook",
      },
    ],
    music: [{ media: "mus", src_in: 0, rec_in: 0, rec_out: 9, volume_db: -14, duck: true, fade_in_s: 0.5, fade_out_s: 1.5 }],
    captions: {
      srt_path: "/out/mehmon.srt",
      words_path: "/out/mehmon_words.json",
      lines: [{ t0: 0.2, t1: 1.8, text: "Salom do'stlar", words: [], speaker: null }],
      style: { uppercase: true },
    },
    text: [{ id: "t1", rec_in: 0, rec_out: 2, text: "Eng muhim gap", kind: "hook", background: null, position: "upper" }],
    markers: [
      { t: 0, name: "Hook", comment: "Salom do'stlar", kind: "hook" },
      { t: 5.5, name: "Urg'u", comment: "", kind: "emphasis" },
    ],
    not_translated: ["shake (asosiy)"],
  };
}

export function splitPlan(): HostPlan {
  const p = clipPlan();
  const item: VideoClipItem = {
    id: "s1",
    media: "m1",
    src_in: 10,
    src_out: 14,
    rec_in: 0,
    rec_out: 4,
    speed: 1,
    volume_db: 0,
    mute: false,
    layers: [
      { role: "top", keys: [{ t: 0, scale_pct: 100, pos_x: 540, pos_y: 480, rotation: 0, interp: "linear" }], effects: [], crop_rect: [0, 0, 1080, 960] },
      { role: "bottom", keys: [{ t: 0, scale_pct: 100, pos_x: 540, pos_y: 1440, rotation: 0, interp: "linear" }], effects: [], crop_rect: [0, 960, 1080, 960] },
    ],
    transition_in: null,
    label: null,
  };
  return { ...p, video: [item], music: [], text: [], markers: [], not_translated: [] };
}

/** Montaj: 2-element 0.5 s cross_dissolve bilan oldingisiga ustma-ust (engine item_starts). */
export function montagePlan(): HostPlan {
  const p = clipPlan();
  const mk = (id: string, recIn: number, recOut: number, srcIn: number, tr: VideoClipItem["transition_in"]): VideoClipItem => ({
    id,
    media: "m1",
    src_in: srcIn,
    src_out: srcIn + (recOut - recIn),
    rec_in: recIn,
    rec_out: recOut,
    speed: 1,
    volume_db: 0,
    mute: false,
    layers: [
      {
        role: "main",
        keys: [
          { t: 0, scale_pct: 100, pos_x: 540, pos_y: 960, rotation: 0, interp: "ease" },
          { t: 0.25, scale_pct: 105, pos_x: 540, pos_y: 960, rotation: 0, interp: "ease" },
          { t: 2, scale_pct: 120, pos_x: 540, pos_y: 960, rotation: 0, interp: "ease" },
        ],
        effects: [{ kind: "lumetri_preset", amount: null, preset: "warm", lut_path: null }],
        crop_rect: null,
      },
    ],
    transition_in: tr,
    label: null,
  });
  return {
    ...p,
    source: "montage",
    source_id: "mon1",
    video: [
      mk("a", 0, 3, 20, null),
      mk("b", 2.5, 6, 50, { kind: "cross_dissolve", dur_s: 0.5, lahza_plugin: "dissolve" }),
      mk("c", 6, 8, 80, { kind: "zoom", dur_s: 0.4, lahza_plugin: "zoomin" }),
    ],
    music: [],
    text: [],
    markers: [],
    not_translated: [],
  };
}
