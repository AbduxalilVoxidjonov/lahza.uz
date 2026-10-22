// Namunaviy host-reja: 9:16 klip — 3 element (fit_blur, split + cross_dissolve, main + dip_to_black + speed),
// musiqa (duck), 2 matn (hook, card), 2 marker, captions 3 qator.
import type { HostPlan } from "../../shared/src/hostplan";

export const SRC = "/Users/test/Movies/intervyu.mp4";
export const MUSIC = "/Users/test/Music/fon.mp3";

export function samplePlan(): HostPlan {
  return {
    schema: "lahza.hostplan/1",
    source: "clip",
    source_id: "ep1/c1",
    sequence: { name: "Lahza — Hook", width: 1080, height: 1920, fps: 30, audio_hz: 48000, duration_s: 12 },
    media: [
      { id: "m1", path: SRC, width: 1920, height: 1080, fps: 30, duration_s: 120, has_audio: true },
      { id: "mu", path: MUSIC, width: 0, height: 0, fps: 0, duration_s: 90, has_audio: true },
    ],
    video: [
      {
        id: "v1",
        media: "m1",
        src_in: 10,
        src_out: 14,
        rec_in: 0,
        rec_out: 4,
        speed: 1,
        volume_db: 0,
        mute: false,
        transition_in: null,
        label: "hook",
        layers: [
          {
            role: "bg",
            keys: [{ t: 0, scale_pct: 177.78, pos_x: 540, pos_y: 960, rotation: 0, interp: "linear" }],
            effects: [{ kind: "gaussian_blur", amount: 60, preset: null, lut_path: null }],
            crop_rect: null,
          },
          {
            role: "main",
            keys: [
              { t: 0, scale_pct: 56.25, pos_x: 540, pos_y: 960, rotation: 0, interp: "ease" },
              { t: 3.5, scale_pct: 62, pos_x: 520, pos_y: 960, rotation: 0, interp: "ease" },
            ],
            effects: [],
            crop_rect: null,
          },
        ],
      },
      {
        id: "v2",
        media: "m1",
        src_in: 20,
        src_out: 24,
        rec_in: 4,
        rec_out: 8,
        speed: 1,
        volume_db: -3,
        mute: false,
        transition_in: { kind: "cross_dissolve", dur_s: 0.5, lahza_plugin: null },
        label: null,
        layers: [
          {
            role: "top",
            keys: [{ t: 0, scale_pct: 177.78, pos_x: 300, pos_y: 480, rotation: 0, interp: "linear" }],
            effects: [],
            crop_rect: [0, 0, 1080, 960],
          },
          {
            role: "bottom",
            keys: [{ t: 0, scale_pct: 177.78, pos_x: 780, pos_y: 1440, rotation: 0, interp: "linear" }],
            effects: [],
            crop_rect: [0, 960, 1080, 960],
          },
        ],
      },
      {
        id: "v3",
        media: "m1",
        src_in: 40,
        src_out: 46,
        rec_in: 8,
        rec_out: 12,
        speed: 1.5,
        volume_db: 0,
        mute: false,
        transition_in: { kind: "dip_to_black", dur_s: 0.4, lahza_plugin: null },
        label: null,
        layers: [
          {
            role: "main",
            keys: [
              { t: 0, scale_pct: 100, pos_x: 540, pos_y: 960, rotation: 0, interp: "hold" },
              { t: 2, scale_pct: 120, pos_x: 540, pos_y: 900, rotation: 0, interp: "hold" },
            ],
            effects: [{ kind: "lumetri_preset", amount: null, preset: "warm", lut_path: null }],
            crop_rect: null,
          },
        ],
      },
    ],
    music: [
      { media: "mu", src_in: 0, rec_in: 0, rec_out: 12, volume_db: -14, duck: true, fade_in_s: 0.5, fade_out_s: 1.5 },
    ],
    captions: {
      srt_path: "/tmp/out/hook.srt",
      words_path: "/tmp/out/hook_words.json",
      lines: [
        {
          t0: 0.5,
          t1: 2.0,
          text: "Bugun sizga",
          speaker: null,
          words: [
            { text: "Bugun", t0: 0.5, t1: 0.9 },
            { text: "sizga", t0: 1.0, t1: 1.6 },
          ],
        },
        {
          t0: 2.1,
          t1: 3.8,
          text: "muhim sirni aytaman",
          speaker: null,
          words: [
            { text: "muhim", t0: 2.1, t1: 2.5 },
            { text: "sirni", t0: 2.5, t1: 3.0 },
            { text: "aytaman", t0: 3.0, t1: 3.8 },
          ],
        },
        {
          t0: 6.0,
          t1: 7.5,
          text: "oʻzbek tilida",
          speaker: "S1",
          words: [
            { text: "oʻzbek", t0: 6.0, t1: 6.6 },
            { text: "tilida", t0: 6.7, t1: 7.5 },
          ],
        },
      ],
      style: {
        font_family: "Inter",
        font_size: 72,
        bold: true,
        primary_color: "#FFFFFF",
        highlight_color: "#FFD400",
        outline_color: "#000000",
        outline_width: 5,
        position: "lower",
        uppercase: false,
        animation: "karaoke",
        box: false,
      },
    },
    text: [
      { id: "t1", rec_in: 0, rec_out: 2.5, text: "Buni bilmasangiz...", kind: "hook", background: null, position: "upper" },
      { id: "t2", rec_in: 10, rec_out: 12, text: "Obuna bo'ling!", kind: "card", background: "#1E40AF", position: "middle" },
    ],
    markers: [
      { t: 0, name: "Hook", comment: "kirish gapi", kind: "hook" },
      { t: 5.2, name: "Urg'u", comment: "", kind: "emphasis" },
    ],
    not_translated: ["shake fx (v3)"],
  };
}
