// Soxta host: har bir amalni yozib oladi (testlar va brauzerda UI ko'rish uchun).
// `unsupported` - qaysi amallar `HostUnsupported` tashlashini belgilaydi (fallback yo'llarini sinash).

import type { HostPlan } from "@shared/hostplan";
import { buildFromPlan } from "./build";
import {
  HostUnsupported,
  type BuildStep,
  type HostAdapter,
  type HostOps,
  type ItemRef,
  type ProjectInfo,
  type WarnCode,
} from "./adapter";

export interface FakeCall {
  op: keyof HostOps;
  args: unknown[];
}

type OpName = keyof HostOps;

export interface FakeOptions {
  /** Amal -> qaysi kod bilan "qo'llanmaydi". `setTransform:multi` - faqat >1 kalit kadrda. */
  unsupported?: Partial<Record<OpName | "setTransform:multi", WarnCode>>;
  captions?: "placed" | "imported";
  selected?: string[];
  project?: ProjectInfo | null;
}

export class FakeOps implements HostOps {
  readonly calls: FakeCall[] = [];
  private n = 0;

  constructor(private opts: FakeOptions = {}) {}

  private rec(op: OpName, ...args: unknown[]) {
    const code = this.opts.unsupported?.[op];
    if (code) throw new HostUnsupported(code, `${op} qo'llanmaydi (fake)`);
    this.calls.push({ op, args });
  }

  /** Faqat berilgan amal chaqiruvlari. */
  of<K extends OpName>(op: K): FakeCall[] {
    return this.calls.filter((c) => c.op === op);
  }

  async importFiles(paths: string[]) {
    this.rec("importFiles", paths);
  }
  async createSequence(seq: HostPlan["sequence"]) {
    this.rec("createSequence", seq);
    return { name: seq.name };
  }
  async placeVideo(req: Parameters<HostOps["placeVideo"]>[0]): Promise<ItemRef> {
    this.rec("placeVideo", req);
    return { handle: `v${this.n++}:${req.itemId}`, videoTrack: req.videoTrack };
  }
  async setClipAudio(item: ItemRef, opts: { volumeDb: number; mute: boolean }) {
    this.rec("setClipAudio", item.handle, opts);
  }
  async setTransform(item: ItemRef, keys: Parameters<HostOps["setTransform"]>[1], ctx: Parameters<HostOps["setTransform"]>[2]) {
    const multi = this.opts.unsupported?.["setTransform:multi"];
    if (multi && keys.length > 1) throw new HostUnsupported(multi, "kalit kadrlar qo'llanmaydi (fake)");
    this.rec("setTransform", item.handle, keys, ctx);
  }
  async addGaussianBlur(item: ItemRef, amount: number) {
    this.rec("addGaussianBlur", item.handle, amount);
  }
  async setCrop(item: ItemRef, crop: Parameters<HostOps["setCrop"]>[1]) {
    this.rec("setCrop", item.handle, crop);
  }
  async addTransition(item: ItemRef, kind: Parameters<HostOps["addTransition"]>[1], durS: number) {
    this.rec("addTransition", item.handle, kind, durS);
  }
  async placeAudio(req: Parameters<HostOps["placeAudio"]>[0]): Promise<ItemRef> {
    this.rec("placeAudio", req);
    return { handle: `a${this.n++}`, videoTrack: -1 };
  }
  async setAudioLevel(item: ItemRef, db: number) {
    this.rec("setAudioLevel", item.handle, db);
  }
  async importCaptions(srtPath: string, seq: HostPlan["sequence"]) {
    this.rec("importCaptions", srtPath, seq.name);
    return this.opts.captions ?? "placed";
  }
  async addMarker(m: HostPlan["markers"][number], durS?: number) {
    this.rec("addMarker", m, durS ?? 0);
  }
}

export class FakeAdapter implements HostAdapter {
  readonly ops: FakeOps;
  readonly steps: BuildStep[] = [];

  constructor(private opts: FakeOptions = {}) {
    this.ops = new FakeOps(opts);
  }

  async selectedMediaPaths() {
    return this.opts.selected ?? [];
  }

  async projectInfo() {
    return this.opts.project === undefined ? { name: "Demo.prproj", path: "/tmp/Demo.prproj", activeSequence: null } : this.opts.project;
  }

  buildFromPlan(plan: HostPlan, onStep?: (s: BuildStep) => void) {
    return buildFromPlan(this.ops, plan, (s) => {
      this.steps.push(s);
      onStep?.(s);
    });
  }
}
