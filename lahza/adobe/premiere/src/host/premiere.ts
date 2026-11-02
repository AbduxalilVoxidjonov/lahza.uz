// Haqiqiy Premiere Pro UXP implementatsiyasi (`require("premierepro")`).
// API nomlari va imzolari: @adobe/premierepro 26.5.1 (rasmiy TS deklaratsiyalar, Apache-2.0),
// developer.adobe.com/premiere-pro/uxp/ppro-reference va github.com/AdobeDocs/uxp-premiere-pro-samples
// (premiere-api: sequenceEditor.ts, keyframe.ts, effects.ts, transition.ts, markers.ts, projectPanel.ts).
//
// Qoidalar (rasmiy changelog 26.3): har bir `create*Action` `project.lockedAccess()` ICHIDA yaratiladi va
// `project.executeTransaction()` bilan bajariladi (bitta undo qadam). Shu tartib 25.6 da ham ishlaydi.
//
// `// ANIQLANSIN:` - hujjatda tasdiqlanmagan xatti-harakat; haqiqiy Premiere'da sinab ko'rilishi kerak.

import type {
  Action,
  AudioClipTrackItem,
  ClipProjectItem,
  Component,
  ComponentParam,
  FrameRate,
  PointF,
  premierepro,
  Project,
  ProjectItem,
  Sequence,
  TickTime,
  VideoClipTrackItem,
} from "@adobe/premierepro";
import type { HostPlan, HostSequence, Marker, TransformKey } from "@shared/hostplan";
import { buildFromPlan } from "./build";
import {
  HostUnsupported,
  type BuildStep,
  type CropPct,
  type HostAdapter,
  type HostOps,
  type HostWarning,
  type ItemRef,
  type PlaceAudioRequest,
  type PlaceVideoRequest,
  type ProjectInfo,
  type TransformContext,
} from "./adapter";
import { hostRequire } from "../uxp-env";

/** Nusxa (bg/top) qatlamlarining keraksiz audiosi tushadigan trek (A3), u yerda o'chirib qo'yiladi. */
const AUDIO_DUP = 2;

/** Motion komponenti matchName (ANIQLANSIN: ExtendScript'dagi nom; UXP namunasi indeks 1 ni ishlatadi). */
const MOTION_MATCH = "AE.ADBE Motion";

/** Kalit kadr vaqti asosi. ANIQLANSIN: ExtendScript'da kalit kadr vaqti klipning MANBA vaqtida edi.
 *  UXP hujjati buni aytmaydi - "source" (src_in + t) tanlandi; agar sinovda element boshidan (0..dur)
 *  ekani chiqsa, "item" ga o'zgartiring. */
const KEY_TIME_BASE: "source" | "item" = "source";

/** Position birligi. ANIQLANSIN: ExtendScript'da Motion.Position kadr o'lchamiga nisbatan [0..1] edi
 *  (PointF qiymat). UXP'da ham shunday deb qabul qilindi. */
const POSITION_NORMALIZED = true;

interface PremiereHandle {
  video: VideoClipTrackItem;
  audio: AudioClipTrackItem | null;
}

interface MediaEntry {
  /** SequenceEditor ProjectItem kutadi; In/Out esa ClipProjectItem'da (rasmiy namunadagi kabi ikkalasi). */
  item: ProjectItem;
  clip: ClipProjectItem;
}

interface AudioHandle {
  audio: AudioClipTrackItem;
}

export function loadPremiere(): premierepro {
  const p = hostRequire<premierepro>("premierepro");
  if (!p) throw new Error("Premiere Pro UXP API topilmadi (panel Premiere ichida ishga tushirilishi kerak)");
  return p;
}

const normPath = (s: string) => s.replace(/\\/g, "/").replace(/\/+$/, "").toLowerCase();

/** Ro'yxatdan nom tanlash: avval aniq nomlar, keyin regex. */
export function pickName(names: string[], exact: string[], re: RegExp[]): string | null {
  for (const e of exact) if (names.includes(e)) return e;
  for (const r of re) {
    const hit = names.find((n) => r.test(n));
    if (hit) return hit;
  }
  return null;
}

export const TRANSITION_PATTERNS: Record<string, { exact: string[]; re: RegExp[] }> = {
  // ANIQLANSIN: aniq matchName'lar hujjatda ro'yxatlanmagan - runtime'da getVideoTransitionMatchNames() dan qidiriladi.
  cross_dissolve: { exact: ["ADBE Cross Dissolve New", "AE.ADBE Cross Dissolve New"], re: [/cross\s*dissolve/i] },
  dip_to_black: { exact: [], re: [/dip\s*to\s*black/i] },
  dip_to_white: { exact: [], re: [/dip\s*to\s*white/i] },
  push: { exact: [], re: [/\bpush\b/i] },
  wipe: { exact: [], re: [/(^|\W)wipe$/i, /\bwipe\b/i] },
  zoom: { exact: [], re: [/cross\s*zoom/i, /\bzoom\b/i] },
};

export class PremiereOps implements HostOps {
  /** Host darajasidagi qo'shimcha eslatmalar (natijaga qo'shiladi). */
  readonly notes: HostWarning[] = [];
  private seq: Sequence | null = null;
  private fr: FrameRate | null = null;
  private clips = new Map<string, MediaEntry>();

  constructor(
    private p: premierepro,
    private project: Project,
  ) {}

  // ---------- yordamchilar ----------

  /** Bitta undo qadam: action'lar lockedAccess ichida yaratiladi va tranzaksiyada bajariladi. */
  private run(label: string, make: () => Action[]): void {
    let ok = false;
    let err: unknown = null;
    this.project.lockedAccess(() => {
      try {
        const actions = make();
        if (!actions.length) {
          ok = true;
          return;
        }
        ok = this.project.executeTransaction((ca) => {
          for (const a of actions) ca.addAction(a);
        }, `Lahza: ${label}`);
      } catch (e) {
        err = e;
      }
    });
    if (err) throw err;
    if (!ok) throw new Error(`Premiere tranzaksiyasi bajarilmadi: ${label}`);
  }

  private sec(t: number): TickTime {
    return this.p.TickTime.createWithSeconds(Math.max(0, t));
  }

  /** Sekvensiya vaqti - kadrga aniq (fps bo'yicha butun kadr). */
  private frame(t: number): TickTime {
    if (!this.fr) return this.sec(t);
    return this.p.TickTime.createWithFrameAndFrameRate(Math.round(Math.max(0, t) * this.fr.value), this.fr);
  }

  private get sequence(): Sequence {
    if (!this.seq) throw new Error("Sekvensiya hali yaratilmagan");
    return this.seq;
  }

  private async findClipByPath(path: string): Promise<MediaEntry | null> {
    const want = normPath(path);
    const cached = this.clips.get(want);
    if (cached) return cached;
    const root = await this.project.getRootItem();
    const queue: ProjectItem[] = [...(await root.getItems())];
    while (queue.length) {
      const it = queue.shift()!;
      const clip = this.p.ClipProjectItem.cast(it) as ClipProjectItem | null;
      if (clip) {
        try {
          const fp = await clip.getMediaFilePath();
          if (fp && normPath(fp) === want) {
            const entry = { item: it, clip };
            this.clips.set(want, entry);
            return entry;
          }
        } catch {
          /* sekvensiya yoki boshqa element - fayl yo'li yo'q */
        }
        continue;
      }
      const folder = this.p.FolderItem.cast(it) as ReturnType<premierepro["FolderItem"]["cast"]> | null;
      if (folder) queue.push(...(await folder.getItems()));
    }
    return null;
  }

  private async clipOrThrow(path: string): Promise<MediaEntry> {
    const c = await this.findClipByPath(path);
    if (!c) throw new Error(`Loyihada topilmadi: ${path}`);
    return c;
  }

  private async findVideoAt(track: number, recIn: number): Promise<VideoClipTrackItem | null> {
    const t = await this.sequence.getVideoTrack(track);
    const items = (await t.getTrackItems(this.p.Constants.TrackItemType.CLIP, false)) as VideoClipTrackItem[];
    return this.closest(items, recIn) as Promise<VideoClipTrackItem | null>;
  }

  private async findAudioAt(track: number, recIn: number): Promise<AudioClipTrackItem | null> {
    const count = await this.sequence.getAudioTrackCount();
    if (track >= count) return null;
    const t = await this.sequence.getAudioTrack(track);
    const items = await t.getTrackItems(this.p.Constants.TrackItemType.CLIP, false);
    return this.closest(items, recIn) as Promise<AudioClipTrackItem | null>;
  }

  private async closest<T extends { getStartTime(): Promise<TickTime> }>(items: T[], recIn: number): Promise<T | null> {
    const tol = this.fr ? 0.5 / this.fr.value : 0.02;
    for (const it of items) {
      const s = await it.getStartTime();
      if (Math.abs(s.seconds - recIn) <= tol) return it;
    }
    return null;
  }

  private async findComponent(chain: { getComponentCount(): number; getComponentAtIndex(i: number): Component }, match: (m: string) => boolean): Promise<Component | null> {
    const n = chain.getComponentCount();
    for (let i = 0; i < n; i++) {
      const c = chain.getComponentAtIndex(i);
      if (match(await c.getMatchName())) return c;
    }
    return null;
  }

  /** Parametrni displayName bo'yicha (inglizcha UI), topilmasa indeks bo'yicha. ANIQLANSIN: lokalizatsiyalangan UI'da displayName boshqacha. */
  private param(c: Component, names: string[], fallbackIndex: number | null): ComponentParam | null {
    const n = c.getParamCount();
    for (let i = 0; i < n; i++) {
      const prm = c.getParam(i);
      if (names.some((x) => prm.displayName.toLowerCase() === x.toLowerCase())) return prm;
    }
    return fallbackIndex !== null && fallbackIndex < n ? c.getParam(fallbackIndex) : null;
  }

  private setStatic(label: string, prm: ComponentParam, value: number | boolean | PointF): void {
    this.run(`${label}: static`, () => [prm.createSetTimeVaryingAction(false)]);
    this.run(`${label}: value`, () => [prm.createSetValueAction(prm.createKeyframe(value), true)]);
  }

  // ---------- HostOps ----------

  async importFiles(paths: string[]): Promise<void> {
    const missing: string[] = [];
    for (const p of paths) if (!(await this.findClipByPath(p))) missing.push(p);
    if (missing.length) {
      // targetBin = null -> loyiha ildizi (rasmiy namuna: import.ts).
      const ok = await this.project.importFiles(missing, true, null as unknown as ProjectItem, false);
      if (!ok) throw new Error("Premiere fayllarni import qilmadi");
    }
    for (const p of paths) await this.clipOrThrow(p);
  }

  async createSequence(s: HostSequence): Promise<{ name: string }> {
    const existing = new Set((await this.project.getSequences()).map((q) => q.name));
    let name = s.name;
    for (let i = 2; existing.has(name); i++) name = `${s.name} (${i})`;
    // createSequence(name) - standart preset (25.6+). O'lcham/fps keyin SequenceSettings bilan (rasmiy namuna: sequence.ts).
    const seq = await this.project.createSequence(name);
    this.seq = seq;
    const settings = await seq.getSettings();
    const rect = new this.p.RectF();
    rect.width = s.width;
    rect.height = s.height;
    await settings.setVideoFrameRect(rect);
    const fr = this.p.FrameRate.createWithValue(s.fps);
    settings.setVideoFrameRate(fr);
    try {
      await settings.setAudioSampleRate(this.p.FrameRate.createWithValue(s.audio_hz));
      await settings.setVideoPixelAspectRatio(this.p.SequenceSettings.PAR_SQUARE);
    } catch {
      this.notes.push({ code: "sequence_settings", detail: "audio_hz/PAR" });
    }
    this.run("sequence settings", () => [seq.createSetSettingsAction(settings)]);
    this.fr = fr;
    const size = await seq.getFrameSize();
    if (Math.round(size.width) !== s.width || Math.round(size.height) !== s.height) {
      this.notes.push({ code: "sequence_settings", detail: `${size.width}x${size.height} != ${s.width}x${s.height}` });
    }
    await this.project.openSequence(seq);
    await this.project.setActiveSequence(seq);
    return { name };
  }

  async placeVideo(req: PlaceVideoRequest): Promise<ItemRef> {
    const { item: pItem, clip } = await this.clipOrThrow(req.mediaPath);
    const editor = this.p.SequenceEditor.getEditor(this.sequence);
    // ANIQLANSIN: insert ProjectItem'ning In/Out nuqtalarini hurmat qiladimi (ExtendScript'da - ha).
    // Shuning uchun keyin trek elementining in/out/end qiymatlari tekshirilib, kerak bo'lsa tuzatiladi.
    this.run("source in/out", () => [clip.createSetInOutPointsAction(this.sec(req.srcIn), this.sec(req.srcOut))]);
    const audioIdx = req.audioTrack ?? AUDIO_DUP;
    // Insert + limitShift=true: boshqa treklar siljimaydi; hujjat bo'yicha mavjud bo'lmagan trek indeksi berilsa
    // yangi trek yaratiladi (createInsertProjectItemAction). Har trekda vaqt o'sish tartibida qo'yilgani uchun
    // insert overwrite bilan bir xil natija beradi.
    this.run("insert", () => [
      editor.createInsertProjectItemAction(pItem, this.frame(req.recIn), req.videoTrack, audioIdx, true),
    ]);
    this.run("clear in/out", () => [clip.createClearInOutPointsAction()]);

    const video = await this.findVideoAt(req.videoTrack, req.recIn);
    if (!video) throw new Error(`V${req.videoTrack + 1} da ${req.recIn}s dagi element topilmadi`);
    const inP = await video.getInPoint();
    const outP = await video.getOutPoint();
    const fix: (() => Action)[] = [];
    const eps = this.fr ? 1 / this.fr.value : 0.04;
    if (Math.abs(inP.seconds - req.srcIn) > eps) fix.push(() => video.createSetInPointAction(this.sec(req.srcIn)));
    if (Math.abs(outP.seconds - req.srcOut) > eps) fix.push(() => video.createSetOutPointAction(this.sec(req.srcOut)));
    const end = await video.getEndTime();
    if (Math.abs(end.seconds - req.recOut) > eps) fix.push(() => video.createSetEndAction(this.frame(req.recOut)));
    if (req.name) fix.push(() => video.createSetNameAction(req.name!));
    if (fix.length) this.run("trim", () => fix.map((f) => f()));

    const audio = await this.findAudioAt(audioIdx, req.recIn);
    if (req.audioTrack === null && audio) {
      // bg/top nusxasining audiosi: A3 da, o'chirilgan (asosiy audio ikki marta eshitilmasin).
      this.run("disable dup audio", () => [audio.createSetDisabledAction(true)]);
    }
    const handle: PremiereHandle = { video, audio: req.audioTrack === null ? null : audio };
    return { handle, videoTrack: req.videoTrack };
  }

  async setClipAudio(item: ItemRef, opts: { volumeDb: number; mute: boolean }): Promise<void> {
    const { audio } = item.handle as PremiereHandle;
    if (!audio) throw new HostUnsupported("audio_level", "audio element topilmadi");
    if (opts.mute) {
      this.run("mute", () => [audio.createSetDisabledAction(true)]);
      return;
    }
    if (opts.volumeDb !== 0) await this.levelOn(audio, opts.volumeDb);
  }

  async setAudioLevel(item: ItemRef, db: number): Promise<void> {
    await this.levelOn((item.handle as AudioHandle).audio, db);
  }

  /**
   * ANIQLANSIN: audio "Volume" komponenti (matchName) va "Level" parametri birligi hujjatda yo'q.
   * ExtendScript'dagi ma'lum formula ishlatiladi: level = 10^((dB - 15) / 20); shuning uchun natija "taxminiy".
   */
  private async levelOn(audio: AudioClipTrackItem, db: number): Promise<void> {
    const chain = await audio.getComponentChain();
    const vol = await this.findComponent(chain, (m) => /volume/i.test(m));
    if (!vol) throw new HostUnsupported("audio_level", "Volume komponenti topilmadi");
    const level = this.param(vol, ["Level"], 1);
    if (!level) throw new HostUnsupported("audio_level", "Level parametri topilmadi");
    this.setStatic("level", level, Math.pow(10, (db - 15) / 20));
    this.notes.push({ code: "audio_level_approx", detail: `${db} dB` });
  }

  async setTransform(item: ItemRef, keys: TransformKey[], ctx: TransformContext): Promise<void> {
    const { video } = item.handle as PremiereHandle;
    const chain = await video.getComponentChain();
    const motion =
      (await this.findComponent(chain, (m) => m === MOTION_MATCH)) ??
      // rasmiy namuna (keyframe.ts) Motion'ni indeks 1 da oladi
      (chain.getComponentCount() > 1 ? chain.getComponentAtIndex(1) : null);
    if (!motion) throw new HostUnsupported("transform_failed", "Motion komponenti topilmadi");
    // ANIQLANSIN: parametr tartibi ExtendScript'dagidek: 0 Position, 1 Scale, 4 Rotation.
    const pos = this.param(motion, ["Position"], 0);
    const scale = this.param(motion, ["Scale"], 1);
    const rot = this.param(motion, ["Rotation"], 4);
    if (!pos || !scale) throw new HostUnsupported("transform_failed", "Position/Scale parametrlari topilmadi");

    const W = ctx.sequence.width;
    const H = ctx.sequence.height;
    const posVal = (k: TransformKey): PointF =>
      POSITION_NORMALIZED ? new this.p.PointF(k.pos_x / W, k.pos_y / H) : new this.p.PointF(k.pos_x, k.pos_y);
    const keyTime = (k: TransformKey) => this.sec(KEY_TIME_BASE === "source" ? ctx.srcIn + k.t : k.t);

    const same = (f: (k: TransformKey) => number) => keys.every((k) => Math.abs(f(k) - f(keys[0])) < 1e-6);
    const streams: { label: string; prm: ComponentParam; val: (k: TransformKey) => number | PointF; constant: boolean }[] = [
      { label: "scale", prm: scale, val: (k) => k.scale_pct, constant: same((k) => k.scale_pct) },
      { label: "position", prm: pos, val: posVal, constant: same((k) => k.pos_x) && same((k) => k.pos_y) },
    ];
    if (rot && keys.some((k) => k.rotation !== 0)) {
      streams.push({ label: "rotation", prm: rot, val: (k) => k.rotation, constant: same((k) => k.rotation) });
    }

    for (const s of streams) {
      if (keys.length === 1 || s.constant) {
        this.setStatic(s.label, s.prm, s.val(keys[0]));
        continue;
      }
      try {
        if (!(await s.prm.areKeyframesSupported())) throw new Error(`${s.label}: kalit kadr qo'llanmaydi`);
        this.run(`${s.label}: time varying`, () => [s.prm.createSetTimeVaryingAction(true)]);
        this.run(`${s.label}: keyframes`, () =>
          keys.map((k) => {
            const kf = s.prm.createKeyframe(s.val(k));
            kf.position = keyTime(k);
            return s.prm.createAddKeyframeAction(kf);
          }),
        );
        const C = this.p.Constants.InterpolationMode;
        this.run(`${s.label}: interpolation`, () =>
          keys.map((k) =>
            s.prm.createSetInterpolationAtKeyframeAction(
              keyTime(k),
              k.interp === "hold" ? C.HOLD : k.interp === "ease" ? C.BEZIER : C.LINEAR,
            ),
          ),
        );
      } catch (e) {
        // build.ts birinchi kadr bilan statik qayta chaqiradi (fallback).
        throw new HostUnsupported("keyframes_static", e instanceof Error ? e.message : String(e));
      }
    }
  }

  private async appendFilter(item: ItemRef, exact: string[], re: RegExp[], code: "blur_missing" | "crop_missing"): Promise<Component> {
    const { video } = item.handle as PremiereHandle;
    const names = await this.p.VideoFilterFactory.getMatchNames();
    const match = pickName(names, exact, re);
    if (!match) throw new HostUnsupported(code, `effekt topilmadi: ${re.map(String).join(", ")}`);
    const comp = await this.p.VideoFilterFactory.createComponent(match);
    const chain = await video.getComponentChain();
    this.run(`effect ${match}`, () => [chain.createAppendComponentAction(comp)]);
    // ANIQLANSIN: qo'shilgan effekt zanjir oxirida bo'ladi deb olinadi.
    let added: Component | null = null;
    this.project.lockedAccess(() => {
      added = chain.getComponentAtIndex(chain.getComponentCount() - 1);
    });
    if (!added) throw new HostUnsupported(code, "qo'shilgan effekt topilmadi");
    return added;
  }

  async addGaussianBlur(item: ItemRef, amount: number): Promise<void> {
    // ANIQLANSIN: matchName "AE.ADBE Gaussian Blur 2" (ExtendScript davridagi nom); runtime ro'yxatdan qidiriladi.
    const fx = await this.appendFilter(item, ["AE.ADBE Gaussian Blur 2", "AE.ADBE Gaussian Blur"], [/gaussian\s*blur/i], "blur_missing");
    const blurriness = this.param(fx, ["Blurriness"], 0);
    if (blurriness) this.setStatic("blurriness", blurriness, amount);
    const repeat = this.param(fx, ["Repeat Edge Pixels"], null);
    if (repeat) this.setStatic("repeat edge", repeat, true);
  }

  async setCrop(item: ItemRef, crop: CropPct): Promise<void> {
    // ANIQLANSIN: "Crop" effekti matchName va parametr tartibi (Left, Top, Right, Bottom - %).
    const fx = await this.appendFilter(item, ["AE.ADBE Crop"], [/\bcrop\b/i], "crop_missing");
    const order: [keyof CropPct, string][] = [["left", "Left"], ["top", "Top"], ["right", "Right"], ["bottom", "Bottom"]];
    order.forEach(([k, label], i) => {
      const prm = this.param(fx, [label], i);
      if (!prm) throw new HostUnsupported("crop_missing", `${label} parametri yo'q`);
      this.setStatic(`crop ${k}`, prm, crop[k]);
    });
  }

  async addTransition(item: ItemRef, kind: keyof typeof TRANSITION_PATTERNS, durS: number): Promise<void> {
    const { video } = item.handle as PremiereHandle;
    const names = await this.p.TransitionFactory.getVideoTransitionMatchNames();
    const pat = TRANSITION_PATTERNS[kind];
    const match = pat ? pickName(names, pat.exact, pat.re) : null;
    if (!match) throw new HostUnsupported("transition_missing", `${kind}: Premiere'da mos o'tish topilmadi`);
    const tr = this.p.TransitionFactory.createVideoTransition(match);
    const opts = this.p.AddTransitionOptions();
    opts.setApplyToStart(true);
    opts.setDuration(this.sec(durS));
    this.run(`transition ${match}`, () => [video.createAddVideoTransitionAction(tr, opts)]);
  }

  async placeAudio(req: PlaceAudioRequest): Promise<ItemRef> {
    const { item: pItem, clip } = await this.clipOrThrow(req.mediaPath);
    const editor = this.p.SequenceEditor.getEditor(this.sequence);
    const dur = req.recOut - req.recIn;
    this.run("music in/out", () => [clip.createSetInOutPointsAction(this.sec(req.srcIn), this.sec(req.srcIn + dur))]);
    // ANIQLANSIN: faqat-audio fayl uchun videoTrackIndex e'tiborsiz qoldirilishi (video qismi yo'q).
    this.run("insert music", () => [
      editor.createInsertProjectItemAction(pItem, this.frame(req.recIn), 0, req.audioTrack, true),
    ]);
    this.run("clear in/out", () => [clip.createClearInOutPointsAction()]);
    const audio = await this.findAudioAt(req.audioTrack, req.recIn);
    if (!audio) throw new Error(`A${req.audioTrack + 1} da musiqa elementi topilmadi`);
    const end = await audio.getEndTime();
    const fix: Action[] = [];
    this.run("music trim", () => {
      if (Math.abs(end.seconds - req.recOut) > 0.05) fix.push(audio.createSetEndAction(this.frame(req.recOut)));
      fix.push(audio.createSetNameAction(req.name));
      return fix;
    });
    const handle: AudioHandle = { audio };
    return { handle, videoTrack: -1 };
  }

  async importCaptions(srtPath: string): Promise<"placed" | "imported"> {
    // Tasdiqlangan: Project.importFiles SRT'ni loyihaga olib keladi (Premiere SRT'ni qo'llaydi).
    // ANIQLANSIN: SRT ProjectItem'ni sekvensiyaning Captions trekiga qo'yish API'si yo'q - CaptionTrack'da faqat
    // o'qish/nom/mute bor, SequenceEditor esa video/audio treklarga qo'yadi. Tasdiqlanmagan insert video trekka
    // tushib, montajni buzishi mumkin, shuning uchun qo'yilmaydi: foydalanuvchi SRT'ni Timeline'ga sudraydi.
    await this.project.importFiles([srtPath], true, null as unknown as ProjectItem, false);
    return "imported";
  }

  async addMarker(m: Marker, durS = 0): Promise<void> {
    const markers = await this.p.Markers.getMarkers(this.sequence);
    this.run(`marker ${m.name}`, () => [
      markers.createAddMarkerAction(m.name, this.p.Marker.MARKER_TYPE_COMMENT, this.sec(m.t), this.sec(durS), m.comment),
    ]);
    const C = this.p.Constants.MarkerColor;
    const color = m.kind === "hook" ? C.RED : m.kind === "highlight" ? C.GREEN : m.kind === "emphasis" ? C.YELLOW : C.BLUE;
    try {
      const added = markers
        .getMarkers()
        .find((x) => x.getName() === m.name && Math.abs(x.getStart().seconds - m.t) < 0.05);
      if (added) this.run("marker color", () => [added.createSetColorByIndexAction(color)]);
    } catch {
      /* rang - ixtiyoriy */
    }
  }
}

export class PremiereAdapter implements HostAdapter {
  constructor(private p: premierepro = loadPremiere()) {}

  private async project(): Promise<Project | null> {
    try {
      return (await this.p.Project.getActiveProject()) ?? null;
    } catch {
      return null;
    }
  }

  async selectedMediaPaths(): Promise<string[]> {
    const project = await this.project();
    if (!project) return [];
    const out: string[] = [];
    const add = async (it: ProjectItem | null) => {
      const clip = it ? (this.p.ClipProjectItem.cast(it) as ClipProjectItem | null) : null;
      if (!clip) return;
      if ((await clip.getContentType()) !== this.p.Constants.ContentType.MEDIA) return;
      const fp = await clip.getMediaFilePath();
      if (fp && !out.includes(fp)) out.push(fp);
    };
    // 1) Project panelidagi tanlov (ProjectUtils.getSelection, 25.6).
    const sel = await this.p.ProjectUtils.getSelection(project);
    for (const it of await sel.getItems()) await add(it);
    // 2) Bo'lmasa - faol sekvensiyada tanlangan kliplarning manbasi.
    if (!out.length) {
      const seq = await project.getActiveSequence();
      if (seq) {
        const ts = await seq.getSelection();
        for (const ti of await ts.getTrackItems()) await add(await ti.getProjectItem());
      }
    }
    return out;
  }

  async projectInfo(): Promise<ProjectInfo | null> {
    const project = await this.project();
    if (!project) return null;
    const seq = await project.getActiveSequence().catch(() => null);
    return { name: project.name, path: project.path, activeSequence: seq?.name ?? null };
  }

  async buildFromPlan(plan: HostPlan, onStep?: (s: BuildStep) => void) {
    const project = await this.project();
    if (!project) throw new Error("Premiere'da ochiq loyiha yo'q");
    const ops = new PremiereOps(this.p, project);
    const res = await buildFromPlan(ops, plan, onStep);
    return { ...res, warnings: [...ops.notes, ...res.warnings] };
  }
}
