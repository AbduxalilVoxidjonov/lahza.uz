import { useObjectUrl, useMontagePreview, useExportProfiles } from "../../api/hooks";
import type { MontageTimeline, StickerItem } from "../../api/types";
import { useT } from "../../i18n";
import { useRef } from "react";
import { useEditorT } from "../../i18n/editor-extra";
import { clamp, timelineRev } from "../../lib/montage";
import { useDebounced } from "../../lib/useDebounced";
import { SafeZoneOverlay } from "../SafeZone";
import { fmtTimePrecise } from "../ui";

/**
 * Montaj preview: engine'ning haqiqiy kadri. Saqlanmagan draft bo'lsa u engine'ga yuboriladi
 * (saqlamasdan ko'rinadi); vaqt va draft o'zgarishlari debounce qilinadi.
 */
export function MontagePreview({ montageId, tMs, tl, dirty, showSafe, selectedSticker, onStickerChange }: {
  montageId: string;
  tMs: number;
  /** Ko'rsatiladigan holat: draft (bo'lsa) yoki saqlangan timeline. */
  tl: MontageTimeline;
  dirty: boolean;
  showSafe: boolean;
  selectedSticker?: StickerItem;
  onStickerChange: (item: StickerItem) => void;
}) {
  const t = useT();
  const et = useEditorT();
  const drag = useRef<{ x: number; y: number; item: StickerItem } | null>(null);
  const dT = useDebounced(Math.round(tMs), 300);
  const dTl = useDebounced(tl, 400);
  const dDirty = useDebounced(dirty, 400);
  const profiles = useExportProfiles();
  // Both frame cache and guide follow the current server safe-zone settings.
  const profile = profiles.data?.profiles.find(p => p.id === (dTl.target_platform ?? "custom"));
  const frame = useMontagePreview({ id: montageId, tMs: dT, rev: [timelineRev(dTl), profile?.safe_zone], timeline: dDirty ? dTl : null });
  const url = useObjectUrl(frame.isPlaceholderData ? undefined : frame.data);
  const format = dTl.format;
  const ratio = `${format.w} / ${format.h}`;
  const tall = format.h >= format.w;
  return (
    <div className="stack" style={{ gap: 6, alignItems: "center" }}>
      <div className="phone montage-frame" style={{ aspectRatio: ratio, maxWidth: tall ? 340 : "100%" }}
           aria-label={t("mon.preview", { aspect: format.aspect })}>
        {url && <img className="engine-frame" src={url} alt={t("mon.previewAlt", { t: fmtTimePrecise(dT) })} />}
        {!url && !frame.isError && <span className="frame-status" role="status">{t("ed.frameLoading")}</span>}
        {profile && <SafeZoneOverlay visible={showSafe} margins={{ top: profile.safe_zone.top_pct, bottom: profile.safe_zone.bottom_pct, side: profile.safe_zone.side_pct }} />}
        {selectedSticker && tMs >= selectedSticker.start_ms && tMs < selectedSticker.end_ms && (
          <button type="button" aria-label={et("position")} title={et("position")}
            style={{ position: "absolute", left: `${selectedSticker.x * 100}%`, top: `${selectedSticker.y * 100}%`,
              width: `${selectedSticker.width * 100}%`, height: `${selectedSticker.height * 100}%`,
              transform: `translate(-50%, -50%) rotate(${selectedSticker.rotation}deg)`, background: "transparent",
              border: "2px dashed #70d7ff", cursor: "move", touchAction: "none", zIndex: 5 }}
            onPointerDown={e => { e.currentTarget.setPointerCapture(e.pointerId); drag.current = { x: e.clientX, y: e.clientY, item: selectedSticker }; }}
            onPointerMove={e => {
              const origin = drag.current; const rect = e.currentTarget.parentElement?.getBoundingClientRect();
              if (!origin || !rect) return;
              onStickerChange({ ...origin.item, x: clamp(origin.item.x + (e.clientX - origin.x) / rect.width, 0, 1), y: clamp(origin.item.y + (e.clientY - origin.y) / rect.height, 0, 1) });
            }}
            onPointerUp={() => { drag.current = null; }} onPointerCancel={() => { drag.current = null; }}
            onLostPointerCapture={() => { drag.current = null; }}
            onKeyDown={e => {
              const step = e.shiftKey ? 0.05 : 0.005;
              const dx = e.key === "ArrowLeft" ? -step : e.key === "ArrowRight" ? step : 0;
              const dy = e.key === "ArrowUp" ? -step : e.key === "ArrowDown" ? step : 0;
              if (!dx && !dy) return;
              e.preventDefault(); e.stopPropagation();
              onStickerChange({ ...selectedSticker, x: clamp(selectedSticker.x + dx, 0, 1), y: clamp(selectedSticker.y + dy, 0, 1) });
            }} />
        )}
        {frame.isFetching && url && <span className="frame-status" role="status">{t("ed.frameLoading")}</span>}
        {frame.isError && <span className="frame-status error" role="alert">{t("ed.frameError")}</span>}
      </div>
    </div>
  );
}
