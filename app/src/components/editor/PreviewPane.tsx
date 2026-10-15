import { useMemo, type RefObject } from "react";

import { useObjectUrl, usePreviewFrame } from "../../api/hooks";
import type { Clip, StyleTemplate, Word } from "../../api/types";
import { useT } from "../../i18n";
import { orth } from "../../lib/orth";
import { useDebounced } from "../../lib/useDebounced";
import { srcToOut } from "../../lib/words";
import { SAFE, SafeZoneOverlay } from "../SafeZone";

interface Props {
  episodeId: string;
  clip: Clip;
  src: string | undefined;
  video: RefObject<HTMLVideoElement | null>;
  videoProps: Record<string, unknown>;
  now: number;
  playing: boolean;
  style: StyleTemplate;
  words: Word[];
  showSafe: boolean;
  engineFrame: boolean;
}

/**
 * 9:16 preview (M2-APP-7): ijro paytida proksi video + taxminiy CSS subtitr; to'xtaganda
 * engine'ning haqiqiy kadri (ekrandagi = eksportdagi), uslub/vaqt o'zgarishida debounce bilan.
 */
export function PreviewPane(p: Props) {
  const t = useT();
  const tOut = srcToOut(p.clip, p.now);
  // Qiymatlar alohida debounce qilinadi (obyekt har renderda yangi bo'lib, taymerni qayta boshlamasin).
  const dT = useDebounced(tOut, 350);
  const dStyle = useDebounced(p.style, 350);
  const frame = usePreviewFrame({
    episodeId: p.episodeId,
    clipId: p.clip.id,
    tMs: dT,
    style: dStyle,
    orthography: dStyle.orthography,
    enabled: p.engineFrame && !p.playing,
    rev: [p.clip.start_ms, p.clip.end_ms, p.clip.cuts],
  });
  const url = useObjectUrl(frame.data);
  const showFrame = p.engineFrame && !p.playing && !!url && !frame.isError;

  const caption = useMemo(() => {
    const i = p.words.findIndex((w) => w.start_ms <= p.now && p.now < w.end_ms + 300);
    if (i < 0) return null;
    const n = Math.max(1, p.style.max_words);
    const start = Math.floor(i / n) * n;
    return { chunk: p.words.slice(start, start + n), active: p.words[i] };
  }, [p.words, p.now, p.style.max_words]);

  const s = p.style;
  const posTop = s.position === "upper" ? `${SAFE.top * 100}%` : s.position === "middle" ? "45%" : undefined;
  const posBottom = s.position === "lower" ? `${SAFE.bottom * 100}%` : undefined;

  return (
    <div className="phone" aria-label={t("ed.preview")}>
      {p.src && (
        <video
          ref={p.video}
          src={`${p.src}#t=${p.clip.start_ms / 1000},${p.clip.end_ms / 1000}`}
          playsInline
          preload="auto"
          aria-label={t("ed.video")}
          {...p.videoProps}
        />
      )}
      {showFrame && <img className="engine-frame" src={url} alt={t("ed.engineFrame")} />}
      {!showFrame && caption && (
        <div
          className="caption-preview"
          aria-hidden
          style={{
            top: posTop,
            bottom: posBottom,
            fontSize: `${(s.font_size / 1920) * 100}cqh`,
            fontFamily: s.font_family,
            fontWeight: s.bold ? 800 : 500,
            color: s.primary_color,
            textTransform: s.uppercase ? "uppercase" : "none",
            background: s.box ? `color-mix(in srgb, ${s.box_color} ${Math.round(s.box_opacity * 100)}%, transparent)` : undefined,
          }}
        >
          {caption.chunk.map((w, k) => (
            <span key={k} style={{ color: w === caption.active ? s.highlight_color : undefined }}>
              {orth(w.text, s.orthography)}{" "}
            </span>
          ))}
        </div>
      )}
      <SafeZoneOverlay visible={p.showSafe} />
      {p.engineFrame && !p.playing && frame.isFetching && <span className="frame-status" role="status">{t("ed.frameLoading")}</span>}
      {p.engineFrame && frame.isError && <span className="frame-status error" role="alert">{t("ed.frameError")}</span>}
    </div>
  );
}
