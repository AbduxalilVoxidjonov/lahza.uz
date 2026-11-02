// Host-reja -> host amallari ketma-ketligi. Host-neytral: Premiere (premiere.ts) ham, testlar (fake.ts) ham shu
// mantiqdan o'tadi. Qoidalar:
//  * treklar roli bo'yicha: bg -> bottom -> main -> top (pastdan yuqoriga), faqat rejada bori ajratiladi;
//  * audio: asosiy qatlam -> A1, musiqa -> A2; bg/top nusxalarining audiosi kerak emas (`audioTrack: null`);
//  * kliplar har trekda rec_in o'sish tartibida qo'yiladi (insert + limitShift = overwrite bilan teng, pastga qarang);
//  * API yetmasa - fallback va `HostWarning`; faqat import va sekvensiya xatosi butun qurishni to'xtatadi.

import type { HostLayer, HostMedia, HostPlan, HostSequence, VideoClipItem } from "@shared/hostplan";
import {
  HostUnsupported,
  type BuildResult,
  type BuildStep,
  type CropPct,
  type HostOps,
  type HostWarning,
  type ItemRef,
  type StepKey,
  type WarnCode,
} from "./adapter";

type Role = HostLayer["role"];
const ROLE_ORDER: Role[] = ["bg", "bottom", "main", "top"];

export const AUDIO_MAIN = 0;
export const AUDIO_MUSIC = 1;

/** Rejada uchragan rollar uchun video trek indekslari (0 = V1). */
export function trackLayout(plan: HostPlan): Record<Role, number> {
  const present = new Set<Role>();
  for (const v of plan.video) for (const l of v.layers) present.add(l.role);
  const out = {} as Record<Role, number>;
  let i = 0;
  for (const r of ROLE_ORDER) if (present.has(r)) out[r] = i++;
  for (const r of ROLE_ORDER) if (out[r] === undefined) out[r] = i; // ishlatilmaydi, lekin aniqlangan
  return out;
}

/** Audio qaysi qatlamdan olinadi: main bo'lsa main, aks holda (split) birinchi qatlam. */
function audioLayer(item: VideoClipItem): HostLayer | undefined {
  return item.layers.find((l) => l.role === "main") ?? item.layers[0];
}

/**
 * Sekvensiyadagi ko'rinadigan to'rtburchak (crop_rect, px) -> manba kadrining qirqish foizlari
 * (Premiere "Crop" effekti chap/yuqori/o'ng/past %). Birinchi kalit kadr bo'yicha (statik).
 */
export function cropFromRect(
  rect: [number, number, number, number],
  key: { scale_pct: number; pos_x: number; pos_y: number },
  mediaW: number,
  mediaH: number,
): CropPct {
  const s = key.scale_pct / 100;
  const w = mediaW * s;
  const h = mediaH * s;
  const left = key.pos_x - w / 2;
  const top = key.pos_y - h / 2;
  const [x, y, rw, rh] = rect;
  const pct = (v: number, size: number) => Math.round(Math.min(100, Math.max(0, (v / size) * 100)) * 1000) / 1000;
  return {
    left: pct(x - left, w),
    top: pct(y - top, h),
    right: pct(left + w - (x + rw), w),
    bottom: pct(top + h - (y + rh), h),
  };
}

/**
 * Montajda o'tishli element `rec_in` oldingi element oxiri bilan `dur_s` ga ustma-ust (engine:
 * MontageTimeline.item_starts). Premiere'da bir trekda ustma-ust qo'yib bo'lmaydi (insert oldingisini bo'lib
 * yuboradi), o'tish esa kesim nuqtasida manba "handle"lari bilan quriladi. Shuning uchun: element kesim nuqtasidan
 * (oldingi oxiri) boshlanadi, manba boshi ham shuncha suriladi (kontent vaqtda joyida qoladi), kalit kadrlar
 * mos ravishda suriladi; o'tish shu kesimga qo'yiladi (ustma-ust qism handle bo'lib xizmat qiladi).
 */
export function resolveOverlaps(items: VideoClipItem[]): VideoClipItem[] {
  const sorted = [...items].sort((a, b) => a.rec_in - b.rec_in);
  const out: VideoClipItem[] = [];
  let prevEnd = -Infinity;
  for (const it of sorted) {
    const ov = prevEnd - it.rec_in;
    if (ov > 1e-6 && ov < it.rec_out - it.rec_in) {
      const shiftKeys = (keys: HostLayer["keys"]) => {
        const moved = keys.map((k) => ({ ...k, t: Math.round((k.t - ov) * 1e6) / 1e6 }));
        // manfiy vaqtga tushganlardan faqat oxirgisi (0 ga) qoladi - boshlanish holati saqlanadi
        const firstPos = moved.findIndex((k) => k.t > 0);
        const lastNeg = firstPos === -1 ? moved.length - 1 : firstPos - 1;
        const head = lastNeg >= 0 ? [{ ...moved[lastNeg], t: 0 }] : [];
        return [...head, ...moved.filter((k) => k.t > 0)];
      };
      out.push({
        ...it,
        rec_in: prevEnd,
        src_in: it.src_in + ov * it.speed,
        layers: it.layers.map((l) => ({ ...l, keys: shiftKeys(l.keys) })),
      });
    } else {
      out.push(it);
    }
    prevEnd = Math.max(prevEnd, out[out.length - 1].rec_out);
  }
  return out;
}

export async function buildFromPlan(
  ops: HostOps,
  plan: HostPlan,
  onStep?: (s: BuildStep) => void,
): Promise<BuildResult> {
  const warnings: HostWarning[] = [];
  const warn = (code: WarnCode, detail?: string) => warnings.push(detail === undefined ? { code } : { code, detail });
  const media = new Map<string, HostMedia>(plan.media.map((m) => [m.id, m]));
  const seq: HostSequence = plan.sequence;
  const tracks = trackLayout(plan);

  const steps: StepKey[] = ["import", "sequence", ...plan.video.map(() => "clip" as const)];
  if (plan.music.length) steps.push("music");
  steps.push("captions");
  if (plan.markers.length) steps.push("markers");
  if (plan.text.length) steps.push("text");
  let stepIdx = 0;
  const step = (key: StepKey, detail?: string) =>
    onStep?.({ index: stepIdx++, total: steps.length, key, ...(detail ? { detail } : {}) });

  // 1. Import (barcha media + musiqa) - xato bo'lsa to'xtaymiz.
  step("import");
  const usedIds = new Set<string>([...plan.video.map((v) => v.media), ...plan.music.map((m) => m.media)]);
  const paths: string[] = [];
  for (const id of usedIds) {
    const m = media.get(id);
    if (!m) warn("media_missing", id);
    else paths.push(m.path);
  }
  await ops.importFiles(paths);

  // 2. Sekvensiya.
  step("sequence", seq.name);
  const created = await ops.createSequence(seq);

  // 3. Video elementlar: rec_in bo'yicha tartib (har trekda o'suvchi vaqt).
  let placed = 0;
  const items = resolveOverlaps(plan.video);
  for (const item of items) {
    step("clip", item.label ?? item.id);
    const m = media.get(item.media);
    if (!m) {
      warn("media_missing", item.media);
      continue;
    }
    const recDur = item.rec_out - item.rec_in;
    let srcOut = item.src_out;
    if (Math.abs(item.speed - 1) > 1e-6) {
      // Tezlikni o'rnatuvchi action API'da yo'q (VideoClipTrackItem'da faqat getSpeed) -> 1x, rec davomiyligi saqlanadi.
      warn("speed", `${item.id}: ${item.speed}x`);
      srcOut = item.src_in + recDur;
    }
    const aLayer = audioLayer(item);
    const layers = [...item.layers].sort((a, b) => ROLE_ORDER.indexOf(a.role) - ROLE_ORDER.indexOf(b.role));
    let anyPlaced = false;
    for (const layer of layers) {
      const withAudio = layer === aLayer && m.has_audio;
      let ref: ItemRef;
      try {
        ref = await ops.placeVideo({
          itemId: `${item.id}:${layer.role}`,
          mediaPath: m.path,
          videoTrack: tracks[layer.role],
          audioTrack: withAudio ? AUDIO_MAIN : null,
          recIn: item.rec_in,
          recOut: item.rec_out,
          srcIn: item.src_in,
          srcOut,
          name: item.label ? `${item.label} · ${layer.role}` : null,
        });
      } catch (e) {
        warn("clip_failed", `${item.id}/${layer.role}: ${errText(e)}`);
        continue;
      }
      anyPlaced = true;
      await applyLayer(ops, ref, layer, item, m, seq, warn);
      if (withAudio && (item.mute || item.volume_db !== 0)) {
        await soft(warn, "audio_level", item.id, () => ops.setClipAudio(ref, { volumeDb: item.volume_db, mute: item.mute }));
      }
      if (item.transition_in && item.transition_in.kind !== "cut" && item.transition_in.dur_s > 0) {
        const tr = item.transition_in;
        await soft(warn, "transition_failed", `${item.id}: ${tr.kind}`, () =>
          ops.addTransition(ref, tr.kind as Exclude<typeof tr.kind, "cut">, tr.dur_s),
        );
      }
    }
    if (anyPlaced) placed++;
  }

  // 4. Musiqa.
  if (plan.music.length) {
    step("music");
    for (const mu of plan.music) {
      const m = media.get(mu.media);
      if (!m) {
        warn("media_missing", mu.media);
        continue;
      }
      try {
        const ref = await ops.placeAudio({
          mediaPath: m.path,
          audioTrack: AUDIO_MUSIC,
          recIn: mu.rec_in,
          recOut: mu.rec_out,
          srcIn: mu.src_in,
          name: "Lahza · musiqa",
        });
        if (mu.volume_db !== 0) await soft(warn, "audio_level", "music", () => ops.setAudioLevel(ref, mu.volume_db));
        // Fade va ducking: audio Level kalit kadrlari / Essential Sound API'si tasdiqlanmagan.
        if (mu.fade_in_s > 0 || mu.fade_out_s > 0) warn("music_fades", `${mu.fade_in_s}s / ${mu.fade_out_s}s`);
        if (mu.duck) warn("music_duck");
      } catch (e) {
        warn("clip_failed", `music: ${errText(e)}`);
      }
    }
  }

  // 5. Subtitr (SRT).
  step("captions");
  if (plan.captions.srt_path) {
    try {
      const r = await ops.importCaptions(plan.captions.srt_path, seq);
      if (r === "imported") warn("captions_imported_only", plan.captions.srt_path);
    } catch (e) {
      warn("captions_failed", errText(e));
    }
  } else if (plan.captions.lines.length) {
    warn("captions_none");
  }

  // 6. Markerlar.
  if (plan.markers.length) {
    step("markers");
    for (const mk of plan.markers) await soft(warn, "marker_failed", mk.name, () => ops.addMarker(mk));
  }

  // 7. Matn qatlamlari: Premiere UXP'da matn/grafika yaratish API'si yo'q (faqat MOGRT) -> davomiyli marker.
  if (plan.text.length) {
    step("text");
    for (const t of plan.text) {
      warn("text_as_marker", t.text);
      await soft(warn, "marker_failed", t.text, () =>
        ops.addMarker({ t: t.rec_in, name: `[${t.kind}] ${t.text}`, comment: t.text, kind: "note" }, t.rec_out - t.rec_in),
      );
    }
  }

  for (const n of plan.not_translated) warn("not_translated", n);
  onStep?.({ index: steps.length, total: steps.length, key: "done" });
  return { sequenceName: created.name, warnings, placedClips: placed };
}

async function applyLayer(
  ops: HostOps,
  ref: ItemRef,
  layer: HostLayer,
  item: VideoClipItem,
  m: HostMedia,
  seq: HostSequence,
  warn: (c: WarnCode, d?: string) => void,
): Promise<void> {
  const where = `${item.id}/${layer.role}`;
  if (layer.keys.length) {
    const ctx = { sequence: seq, mediaWidth: m.width, mediaHeight: m.height, srcIn: item.src_in, recIn: item.rec_in };
    try {
      await ops.setTransform(ref, layer.keys, ctx);
    } catch (e) {
      if (layer.keys.length > 1) {
        // Fallback: kalit kadrlar o'tmasa - birinchi kadr statik (scale/position), harakat yo'qoladi.
        warn("keyframes_static", `${where}: ${errText(e)}`);
        try {
          await ops.setTransform(ref, [layer.keys[0]], ctx);
        } catch (e2) {
          warn("transform_failed", `${where}: ${errText(e2)}`);
        }
      } else {
        warn("transform_failed", `${where}: ${errText(e)}`);
      }
    }
  }
  if (layer.crop_rect) {
    const crop = cropFromRect(layer.crop_rect, layer.keys[0] ?? { scale_pct: 100, pos_x: seq.width / 2, pos_y: seq.height / 2 }, m.width, m.height);
    await soft(warn, "crop_missing", where, () => ops.setCrop(ref, crop));
  }
  for (const fx of layer.effects) {
    if (fx.kind === "gaussian_blur") {
      await soft(warn, "blur_missing", where, () => ops.addGaussianBlur(ref, fx.amount ?? 60));
    } else if (fx.kind === "lumetri_preset") {
      warn("lumetri", `${where}: ${fx.preset ?? ""}`);
    } else if (fx.kind === "lut") {
      warn("lut", `${where}: ${fx.lut_path ?? ""}`);
    }
  }
}

/** Ixtiyoriy amal: xato qurishni to'xtatmaydi, ogohlantirishga aylanadi. */
async function soft(
  warn: (c: WarnCode, d?: string) => void,
  code: WarnCode,
  detail: string,
  fn: () => Promise<unknown>,
): Promise<void> {
  try {
    await fn();
  } catch (e) {
    warn(e instanceof HostUnsupported ? e.code : code, `${detail}: ${errText(e)}`);
  }
}

export function errText(e: unknown): string {
  return e instanceof Error ? e.message : String(e);
}
