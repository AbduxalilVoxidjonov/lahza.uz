/** Structural subset of JASSUB 2.5.23's public canvas-only API.
 * Pass a REAL JASSUB instance; no fabricated ASS renderer or source-video clock. */
export interface JassubPort {
  readonly ready: Promise<void>;
  manualRender(data: Pick<VideoFrameCallbackMetadata, "expectedDisplayTime" | "width" | "height" | "mediaTime">,
    repaint?: boolean): Promise<void>;
  destroy(): Promise<void>;
}
export interface AssRenderer {
  readonly ready: Promise<void>;
  setCurrentTime(outputMs: number): void;
  setIsPaused(paused: boolean): void;
  destroy(): Promise<void>;
}
export type AssFactory = (canvas: HTMLCanvasElement, onError: (error: unknown) => void) => AssRenderer;

/** Latest-frame backpressure: at most one worker render in flight and one pending time. */
export function timelineAss(port: JassubPort, width: number, height: number,
  onError: (error: unknown) => void): AssRenderer {
  if (![width, height].every(n => Number.isFinite(n) && n > 0)) throw new Error("ASS o‘lchami noto‘g‘ri");
  const scale = Math.min(1, 1280 / width, 720 / height);
  const renderWidth = Math.max(1, Math.round(width * scale));
  const renderHeight = Math.max(1, Math.round(height * scale));
  let dead = false, paused = true, pending: number | undefined, flight: Promise<void> | undefined;
  let failed = false;
  const fail = (error: unknown): void => { if (!dead && !failed) { failed = true; onError(error); } };
  const pump = (): void => {
    if (dead || failed || flight || pending === undefined) return;
    flight = (async () => {
      await port.ready;
      while (!dead && pending !== undefined) {
        const ms = pending; pending = undefined;
        await port.manualRender({ expectedDisplayTime: performance.now(), width: renderWidth,
          height: renderHeight, mediaTime: ms / 1000 }, paused);
      }
    })().catch(fail).finally(() => { flight = undefined; pump(); });
  };
  return {
    ready: port.ready,
    setCurrentTime(ms) {
      if (!Number.isFinite(ms) || ms < 0) throw new Error("ASS vaqti noto‘g‘ri");
      pending = ms; pump();
    },
    setIsPaused(value) { paused = value; },
    async destroy() { dead = true; pending = undefined; await flight; await port.destroy(); },
  };
}
