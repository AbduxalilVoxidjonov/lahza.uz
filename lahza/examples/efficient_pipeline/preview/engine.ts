import { PreviewAudio, type MusicBuffers } from "./audio";
import type { AssFactory, AssRenderer } from "./ass";
import { cropRect, locate, outputToSource, sourceToOutput, type Clip, type PreviewPlan, type SimpleColor } from "./model";

export type PreviewState = "seeking" | "paused" | "playing" | "error";
export interface PreviewOptions {
  plan: PreviewPlan;
  musicBuffers: MusicBuffers;
  createAss?: AssFactory;
  /** Preview-only CSS/Canvas adjustment, NOT an FFmpeg preset or LUT translation. */
  color?: SimpleColor;
  onTime(ms: number): void;
  onState(state: PreviewState, message?: string): void;
}
interface Slot {
  video: HTMLVideoElement; layer: HTMLDivElement;
  key?: string; task?: Promise<number>; controller?: AbortController;
}
const aborted = (): DOMException => new DOMException("Preview bekor qilindi", "AbortError");
const isAbort = (error: unknown): boolean => error instanceof DOMException && error.name === "AbortError";

export class PreviewEngine {
  private readonly slots: [Slot, Slot];
  private readonly audio: PreviewAudio;
  private readonly lifetime = new AbortController();
  private readonly frameCanvas: HTMLCanvasElement;
  private readonly context: CanvasRenderingContext2D | null;
  private readonly subtitles?: AssRenderer;
  private readonly observer: ResizeObserver;
  private readonly filter: string;
  private active = 0;
  private index = -1;
  private timeMs = 0;
  private targetMs = 0;
  private wanted = false;
  private running = false;
  private moving = false;
  private generation = 0;
  private raf = 0;
  private rvfc = 0;
  private dead = false;

  constructor(private readonly host: HTMLElement, private readonly options: PreviewOptions) {
    if (!("requestVideoFrameCallback" in HTMLVideoElement.prototype))
      throw new Error("requestVideoFrameCallback kerak; render preview fallback ishlating");
    if (typeof ResizeObserver === "undefined") throw new Error("ResizeObserver kerak");
    if (options.plan.timeline.captions.enabled && !options.createAss)
      throw new Error("Subtitr yoqilgan: haqiqiy ASS renderer kerak");
    const color = options.color;
    if (color && (![color.brightness, color.contrast, color.saturation].every(Number.isFinite) ||
      [color.brightness, color.contrast, color.saturation].some(x => x < 0 || x > 2)))
      throw new Error("SimpleColor oralig‘i 0..2");
    this.filter = color ? `brightness(${color.brightness}) contrast(${color.contrast}) saturate(${color.saturation})` : "none";
    this.slots = [this.newSlot(), this.newSlot()];
    this.audio = new PreviewAudio(this.slots.map(slot => slot.video), options.plan, options.musicBuffers);
    this.frameCanvas = document.createElement("canvas");
    this.frameCanvas.style.cssText = "position:absolute;inset:0;width:100%;height:100%;pointer-events:none;z-index:3";
    this.frameCanvas.hidden = !color;
    this.context = color ? this.frameCanvas.getContext("2d", { alpha: false }) : null;
    this.observer = new ResizeObserver(() => this.resize());
    let assCanvas: HTMLCanvasElement | undefined;
    try {
      if (color && (!this.context || !("filter" in this.context)))
        throw new Error("Canvas filter qo‘llanmaydi; rangni o‘chiring yoki render preview ishlating");
      host.append(this.frameCanvas);
      if (options.plan.timeline.captions.enabled && options.createAss) {
        // Fresh node EACH mount: OffscreenCanvas transfer cannot be undone or repeated.
        assCanvas = document.createElement("canvas");
        assCanvas.style.cssText = "position:absolute;inset:0;width:100%;height:100%;pointer-events:none;z-index:4";
        host.append(assCanvas);
        this.subtitles = options.createAss(assCanvas, error => this.fail(error));
        void this.subtitles.ready.catch(error => this.fail(error));
      }
      this.observer.observe(host);
      this.resize();
      const signal = this.lifetime.signal;
      document.addEventListener("visibilitychange", () => { if (document.hidden) this.pause(); }, { signal });
      this.slots.forEach((slot, i) => {
        slot.video.addEventListener("waiting", () => {
          if (i !== this.active || this.moving) return;
          this.running = false; this.audio.stop(); this.subtitles?.setIsPaused(true);
          if (this.wanted) this.options.onState("seeking");
        }, { signal });
        slot.video.addEventListener("playing", () => { if (i === this.active) this.started(); }, { signal });
        slot.video.addEventListener("ended", () => {
          if (i === this.active && this.wanted && !this.moving) this.advance();
        }, { signal });
        slot.video.addEventListener("error", () => {
          if (i === this.active && !this.moving) this.fail(new Error("Native kodek/URL o‘qilmadi; transcode fallback ishlating"));
        }, { signal });
      });
    } catch (error) {
      this.dead = true; this.lifetime.abort(); this.observer.disconnect();
      this.slots.forEach(slot => { slot.video.pause(); slot.video.removeAttribute("src"); slot.video.load(); slot.layer.remove(); });
      this.frameCanvas.remove(); assCanvas?.remove();
      void this.audio.dispose().catch(cleanupError => console.error("Preview init cleanup:", cleanupError));
      void this.subtitles?.destroy().catch(cleanupError => console.error("ASS init cleanup:", cleanupError));
      throw error;
    }
  }
  private newSlot(): Slot {
    const layer = document.createElement("div"), video = document.createElement("video");
    // Keep standby attached/compositable; display:none/visibility:hidden can suppress rVFC.
    layer.style.cssText = "position:absolute;inset:0;overflow:hidden;z-index:0";
    video.style.cssText = "position:absolute;max-width:none";
    video.playsInline = true; video.preload = "auto"; video.crossOrigin = "anonymous";
    video.muted = true; video.preservesPitch = true;
    layer.append(video); this.host.append(layer);
    return { video, layer };
  }
  private get slot(): Slot {
    const slot = this.slots[this.active];
    if (!slot) throw new Error("Video buferi yo‘q");
    return slot;
  }
  private get clip(): Clip {
    const clip = this.options.plan.clips[this.index];
    if (!clip) throw new Error("Klip yo‘q");
    return clip;
  }
  private cancelFrame(): void {
    if (this.rvfc) this.slot.video.cancelVideoFrameCallback(this.rvfc);
    this.rvfc = 0;
  }
  /** No performance.now timeline integrator. A seek assignment is NOT a decoded frame. */
  async seek(outputMs: number): Promise<void> {
    if (this.dead) return;
    const point = locate(this.options.plan, outputMs);
    this.targetMs = point.ms;
    const generation = ++this.generation;
    this.moving = true; this.running = false;
    this.cancelFrame(); this.audio.stop(); this.subtitles?.setIsPaused(true);
    this.slots.forEach(slot => slot.video.pause());
    this.options.onState("seeking");
    // Never seek the visible element: it retains its last decoded frame.
    const next = 1 - this.active, slot = this.slots[next];
    if (!slot) return;
    const target = Math.min(outputToSource(point.clip, point.ms),
      Math.max(point.clip.inMs / 1000, (point.clip.outMs - 1) / 1000));
    try {
      await this.prepare(slot, point.index, target);
      if (this.dead || generation !== this.generation) return;
      this.active = next; this.index = point.index; this.timeMs = point.ms; this.moving = false;
      this.applyCrop(slot, point.clip);
      this.draw();
      this.slots.forEach((item, i) => { item.layer.style.zIndex = i === next ? "2" : "1"; });
      this.subtitles?.setCurrentTime(this.timeMs);
      this.options.onTime(this.timeMs);
      this.watchFrames();
      this.preloadNext();
      this.options.onState("paused");
      if (this.wanted) await this.start(generation);
    } catch (error) { if (!isAbort(error) && generation === this.generation) this.fail(error); }
  }
  async play(): Promise<void> {
    if (this.dead || document.hidden) return;
    this.wanted = true;
    try {
      // Creation/resume begins in the button gesture, before any seek awaits.
      await this.audio.unlock();
      if (this.dead || !this.wanted) return;
      if (this.moving || this.index < 0 || this.timeMs >= this.options.plan.durationMs)
        await this.seek(this.timeMs >= this.options.plan.durationMs ? 0 : this.targetMs);
      else await this.start(this.generation);
    } catch (error) { this.fail(error); }
  }
  pause(): void {
    if (this.dead) return;
    if (this.running && !this.moving) this.timeMs = sourceToOutput(this.clip, this.slot.video.currentTime);
    ++this.generation; this.wanted = false; this.running = false; this.moving = false;
    cancelAnimationFrame(this.raf); this.raf = 0;
    this.cancelFrame();
    this.slots.forEach(slot => { slot.controller?.abort(); slot.key = undefined; slot.video.pause(); });
    this.audio.stop(); this.subtitles?.setIsPaused(true);
    this.options.onTime(this.timeMs); this.options.onState("paused");
  }
  private async start(generation: number): Promise<void> {
    if (this.dead || generation !== this.generation || !this.wanted) return;
    this.slot.video.playbackRate = this.clip.speed;
    await this.slot.video.play();
    if (this.dead || generation !== this.generation || !this.wanted) return;
    this.started(); this.watchFrames();
    if (!this.raf) this.raf = requestAnimationFrame(this.tick);
  }
  private started(): void {
    if (this.dead || !this.wanted || this.moving || this.running || this.index < 0) return;
    this.running = true;
    this.audio.start(this.active, this.clip, sourceToOutput(this.clip, this.slot.video.currentTime));
    this.subtitles?.setIsPaused(false); this.options.onState("playing");
  }
  private readonly tick = (): void => {
    this.raf = 0;
    if (this.dead || !this.wanted) return;
    if (this.running && !this.moving && !this.slot.video.seeking && !this.slot.video.paused && this.slot.video.readyState >= 3) {
      if (this.slot.video.currentTime * 1000 >= this.clip.outMs) this.advance();
      else {
        this.timeMs = sourceToOutput(this.clip, this.slot.video.currentTime);
        this.options.onTime(this.timeMs); // DOM playhead only; no React setState.
      }
    }
    this.raf = requestAnimationFrame(this.tick);
  };
  private advance(): void {
    const next = this.options.plan.clips[this.index + 1];
    if (next) void this.seek(next.startMs);
    else { this.pause(); this.timeMs = this.options.plan.durationMs; this.options.onTime(this.timeMs); }
  }
  private watchFrames(): void {
    if (this.rvfc || this.dead || this.moving || this.index < 0) return;
    const video = this.slot.video;
    this.rvfc = video.requestVideoFrameCallback((_now, metadata) => {
      this.rvfc = 0;
      if (this.dead || this.moving || video !== this.slot.video) return;
      if (!video.seeking && metadata.mediaTime * 1000 < this.clip.outMs) {
        this.draw();
        this.subtitles?.setCurrentTime(sourceToOutput(this.clip, metadata.mediaTime));
      }
      this.watchFrames();
    });
  }
  private prepare(slot: Slot, index: number, target: number): Promise<number> {
    const key = `${index}:${target}`;
    if (slot.key === key && slot.task) return slot.task;
    slot.controller?.abort();
    const controller = new AbortController(); slot.controller = controller; slot.key = key;
    const clip = this.options.plan.clips[index];
    if (!clip) return Promise.reject(new Error("Klip topilmadi"));
    const video = slot.video;
    slot.task = (async () => {
      video.pause();
      if (video.getAttribute("src") !== clip.url) {
        video.src = clip.url; video.load();
      }
      if (video.readyState < 1) await mediaMetadata(video, controller.signal);
      if (video.videoWidth !== clip.width || video.videoHeight !== clip.height)
        throw new Error("Media o‘lchami metadata bilan mos emas (rotation/SAR fallback kerak)");
      if (controller.signal.aborted) throw aborted();
      return await seekDecoded(video, target, Math.max(0.05, 1.5 / clip.fps), controller.signal);
    })();
    return slot.task;
  }
  private preloadNext(): void {
    const nextIndex = this.index + 1, clip = this.options.plan.clips[nextIndex];
    const slot = this.slots[1 - this.active];
    if (!slot) return;
    if (!clip) { slot.controller?.abort(); slot.key = undefined; slot.video.removeAttribute("src"); slot.video.load(); return; }
    // Only the standby slot; no third video or hidden proxy decoder.
    void this.prepare(slot, nextIndex, clip.inMs / 1000).catch(error => {
      if (!isAbort(error)) slot.key = undefined; // Retry when the user reaches this cut; surface failure then.
    });
  }
  private applyCrop(slot: Slot, clip: Clip): void {
    const rect = cropRect(clip, this.options.plan.width / this.options.plan.height);
    Object.assign(slot.video.style, { width: `${100 * clip.width / rect.w}%`, height: `${100 * clip.height / rect.h}%`,
      left: `${-100 * rect.x / rect.w}%`, top: `${-100 * rect.y / rect.h}%` });
  }
  private resize(): void {
    const dpr = 1; // Eco default: CSS pixels only, even on Retina displays.
    const scale = Math.min(this.host.clientWidth * dpr / this.options.plan.width,
      this.host.clientHeight * dpr / this.options.plan.height, 1280 / this.options.plan.width, 720 / this.options.plan.height);
    this.frameCanvas.width = Math.max(1, Math.round(this.options.plan.width * scale));
    this.frameCanvas.height = Math.max(1, Math.round(this.options.plan.height * scale));
    if (!this.moving && this.index >= 0) this.draw(); // Resize replay is the sole non-new-frame redraw.
  }
  private draw(): void {
    const context = this.context;
    if (!context || this.index < 0) return;
    const rect = cropRect(this.clip, this.options.plan.width / this.options.plan.height);
    context.filter = this.filter;
    context.drawImage(this.slot.video, rect.x, rect.y, rect.w, rect.h, 0, 0, this.frameCanvas.width, this.frameCanvas.height);
  }
  private fail(error: unknown): void {
    if (this.dead || isAbort(error)) return;
    this.pause();
    this.options.onState("error", error instanceof Error ? error.message : String(error));
  }
  async dispose(): Promise<void> {
    if (this.dead) return;
    this.pause(); this.dead = true; this.lifetime.abort(); this.observer.disconnect();
    this.slots.forEach(slot => { slot.video.removeAttribute("src"); slot.video.load(); slot.layer.remove(); });
    this.frameCanvas.remove();
    await Promise.all([this.audio.dispose(), this.subtitles?.destroy()]);
  }
}

function mediaMetadata(video: HTMLVideoElement, signal: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    const cleanup = (): void => {
      clearTimeout(timer); video.removeEventListener("loadedmetadata", ready);
      video.removeEventListener("error", failed); signal.removeEventListener("abort", cancel);
    };
    const ready = (): void => { cleanup(); resolve(); };
    const failed = (): void => { cleanup(); reject(new Error("Video ochilmadi; URL, Range/CORS va kodekni tekshiring")); };
    const cancel = (): void => { cleanup(); reject(aborted()); };
    const timer = setTimeout(failed, 15_000);
    video.addEventListener("loadedmetadata", ready); video.addEventListener("error", failed);
    signal.addEventListener("abort", cancel, { once: true });
    if (signal.aborted) cancel(); else if (video.readyState >= 1) ready();
  });
}
function seekDecoded(video: HTMLVideoElement, target: number, tolerance: number, signal: AbortSignal): Promise<number> {
  return new Promise((resolve, reject) => {
    let id = 0;
    const cleanup = (): void => {
      clearTimeout(timer); video.cancelVideoFrameCallback(id);
      video.removeEventListener("error", failed); signal.removeEventListener("abort", cancel);
    };
    const failed = (): void => { cleanup(); reject(new Error("Seek kadri kelmadi; native kodek/proxy fallback kerak")); };
    const cancel = (): void => { cleanup(); reject(aborted()); };
    const frame = (): void => {
      id = video.requestVideoFrameCallback((_now, metadata) => {
        if (!video.seeking && video.readyState >= 2 && Math.abs(metadata.mediaTime - target) <= tolerance) {
          cleanup(); resolve(metadata.mediaTime);
        } else frame();
      });
    };
    const timer = setTimeout(failed, 15_000);
    video.addEventListener("error", failed); signal.addEventListener("abort", cancel, { once: true });
    if (signal.aborted) { cancel(); return; }
    frame(); // Arm BEFORE seek; currentTime alone cannot prove that the frame was decoded.
    try { video.currentTime = target; } catch (error) { cleanup(); reject(error); }
  });
}
