import { useCallback, useEffect, useRef, useState, type RefObject } from "react";

import type { Clip } from "../api/types";
import { skipCuts } from "./words";

const RATES = [1, 1.5, 2] as const;

/**
 * Klip oralig'ida proksi videoni boshqarish: kesimlar ustidan sakraydi, klip oxirida to'xtaydi.
 * Playhead silliq bo'lishi uchun ijro paytida requestAnimationFrame ishlatiladi.
 */
export function usePlayer(video: RefObject<HTMLVideoElement | null>, clip: Pick<Clip, "start_ms" | "end_ms" | "cuts">) {
  const [now, setNow] = useState(clip.start_ms);
  const [playing, setPlaying] = useState(false);
  const rateIdx = useRef(0);
  const clipRef = useRef(clip);
  clipRef.current = clip;

  useEffect(() => {
    if (!playing) return;
    let raf = 0;
    const tick = () => {
      const v = video.current;
      if (v) {
        const c = clipRef.current;
        let ms = Math.round(v.currentTime * 1000);
        const skipped = skipCuts(c.cuts, ms);
        if (skipped !== ms) {
          v.currentTime = skipped / 1000;
          ms = skipped;
        }
        if (ms >= c.end_ms) {
          v.pause();
          ms = c.end_ms;
        }
        setNow(ms);
      }
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [playing, video]);

  const seek = useCallback(
    (ms: number) => {
      const clamped = Math.max(0, ms);
      if (video.current) video.current.currentTime = clamped / 1000;
      setNow(clamped);
    },
    [video],
  );

  const play = useCallback(() => {
    const v = video.current;
    if (!v) return;
    const c = clipRef.current;
    const cur = v.currentTime * 1000;
    if (cur < c.start_ms || cur >= c.end_ms - 50) v.currentTime = c.start_ms / 1000;
    void v.play();
  }, [video]);

  const pause = useCallback(() => {
    video.current?.pause();
    rateIdx.current = 0;
    if (video.current) video.current.playbackRate = 1;
  }, [video]);

  const toggle = useCallback(() => {
    if (video.current?.paused) play();
    else pause();
  }, [play, pause]);

  /** L: ijro; qayta bosilsa tezlik 1.5x, 2x. */
  const forward = useCallback(() => {
    const v = video.current;
    if (!v) return;
    if (!v.paused) rateIdx.current = Math.min(RATES.length - 1, rateIdx.current + 1);
    v.playbackRate = RATES[rateIdx.current] ?? 1;
    if (v.paused) play();
  }, [play, video]);

  /** J: 5 soniya orqaga (HTML video teskari ijroni qo'llamaydi). */
  const back = useCallback(() => {
    const v = video.current;
    if (!v) return;
    seek(Math.max(clipRef.current.start_ms, v.currentTime * 1000 - 5000));
  }, [seek, video]);

  const bind = {
    onPlay: () => setPlaying(true),
    onPause: () => setPlaying(false),
    onSeeked: (e: { currentTarget: HTMLVideoElement }) => setNow(Math.round(e.currentTarget.currentTime * 1000)),
    onLoadedMetadata: (e: { currentTarget: HTMLVideoElement }) => {
      e.currentTarget.currentTime = clipRef.current.start_ms / 1000;
    },
  };

  return { now, playing, seek, play, pause, toggle, forward, back, bind };
}
