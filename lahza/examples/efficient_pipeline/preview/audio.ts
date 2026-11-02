import { dbGain, duckEnvelope, envelopeAt, type Clip, type PreviewPlan } from "./model";

/** Caller decodes/caches only the selected short music track, once per revision.
 * No per-frame analyser, audio polling, fetch or dynamic import. */
export type MusicBuffers = ReadonlyMap<string, AudioBuffer>;
export class PreviewAudio {
  private context?: AudioContext;
  private nodes: MediaElementAudioSourceNode[] = [];
  private gains: GainNode[] = [];
  private music?: AudioBufferSourceNode;
  private musicGain?: GainNode;
  private readonly duck;
  private readonly buffers: MusicBuffers;
  constructor(private readonly videos: readonly HTMLVideoElement[], private readonly plan: PreviewPlan, buffers: MusicBuffers) {
    this.buffers = buffers;
    this.duck = duckEnvelope(plan.speech);
    for (const item of plan.timeline.music) {
      const buffer = buffers.get(item.media);
      if (!buffer) throw new Error(`Dekodlangan musiqa kerak: ${item.media}`);
      if (buffer.duration > 120 || buffer.length * buffer.numberOfChannels * 4 > 64 * 1024 * 1024)
        throw new Error("Preview musiqasi chegarasi: 120 s / 64 MiB PCM");
    }
  }
  /** Call synchronously from a user gesture. Each engine owns NEW DOM videos,
   * so StrictMode never calls createMediaElementSource twice on the same element. */
  async unlock(): Promise<void> {
    if (!this.context) {
      const context = new AudioContext();
      this.context = context;
      for (const video of this.videos) {
        const source = context.createMediaElementSource(video), gain = context.createGain();
        gain.gain.value = 0;
        source.connect(gain).connect(context.destination);
        this.nodes.push(source); this.gains.push(gain);
        video.muted = false;
      }
    }
    await this.context.resume();
  }
  stop(): void {
    const context = this.context;
    if (!context) return;
    for (const gain of this.gains) {
      gain.gain.cancelScheduledValues(context.currentTime);
      gain.gain.setValueAtTime(0, context.currentTime);
    }
    this.music?.stop(); this.music?.disconnect(); this.music = undefined;
    this.musicGain?.disconnect(); this.musicGain = undefined;
  }
  start(slot: number, clip: Clip, outputMs: number): void {
    this.stop();
    const context = this.context, gain = this.gains[slot];
    if (!context || !gain) throw new Error("AudioContext ochilmagan");
    const now = context.currentTime;
    const fade = this.plan.timeline.audio.fade_ms;
    const globalFade = (ms: number): number => fade > 0
      ? Math.max(0, Math.min(1, ms / fade, (this.plan.durationMs - ms) / fade)) : 1;
    scheduleCurve(gain.gain, now, outputMs, clip.endMs, ms => clip.gain * globalFade(ms));
    const item = this.plan.timeline.music[0];
    if (!item) return;
    const buffer = this.buffers.get(item.media);
    if (!buffer) throw new Error("Musiqa yo‘q");
    const end = Math.min(item.end_ms ?? this.plan.durationMs, this.plan.durationMs,
      item.start_ms + buffer.duration * 1000 - item.src_in_ms);
    const start = Math.max(outputMs, item.start_ms);
    if (start >= end) return;
    const music = context.createBufferSource(), musicGain = context.createGain();
    this.music = music; this.musicGain = musicGain;
    music.buffer = buffer;
    music.connect(musicGain).connect(context.destination);
    const offset = (item.src_in_ms + start - item.start_ms) / 1000;
    const when = now + (start - outputMs) / 1000;
    const musicFade = (ms: number): number => Math.max(0, Math.min(1,
      item.fade_in_ms > 0 ? (ms - item.start_ms) / item.fade_in_ms : 1,
      item.fade_out_ms > 0 ? (end - ms) / item.fade_out_ms : 1));
    scheduleCurve(musicGain.gain, when, start, end, ms => dbGain(item.gain_db) *
      musicFade(ms) * globalFade(ms) * (item.duck ? envelopeAt(this.duck, ms) : 1));
    music.start(when, offset, (end - start) / 1000);
  }
  async dispose(): Promise<void> {
    this.stop(); this.nodes.forEach(node => node.disconnect()); this.gains.forEach(node => node.disconnect());
    this.nodes = []; this.gains = [];
    await this.context?.close(); this.context = undefined;
  }
}

/** 100 Hz control curve allocated only on start/resume/cut, NOT each frame.
 * WebAudio evaluates interpolation on the audio thread. */
function scheduleCurve(param: AudioParam, when: number, startMs: number, endMs: number,
  value: (ms: number) => number): void {
  const duration = (endMs - startMs) / 1000;
  const count = Math.max(2, Math.ceil(duration * 100) + 1);
  const curve = Float32Array.from({ length: count }, (_, i) => value(startMs + (endMs - startMs) * i / (count - 1)));
  if (duration > 0) param.setValueCurveAtTime(curve, when, duration);
  else param.setValueAtTime(value(startMs), when);
}
