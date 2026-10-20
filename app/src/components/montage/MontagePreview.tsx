import { useObjectUrl, useMontagePreview } from "../../api/hooks";
import type { MontageTimeline } from "../../api/types";
import { useT } from "../../i18n";
import { timelineRev } from "../../lib/montage";
import { useDebounced } from "../../lib/useDebounced";
import { SafeZoneOverlay } from "../SafeZone";
import { fmtTimePrecise } from "../ui";

/**
 * Montaj preview: engine'ning haqiqiy kadri. Saqlanmagan draft bo'lsa u engine'ga yuboriladi
 * (saqlamasdan ko'rinadi); vaqt va draft o'zgarishlari debounce qilinadi.
 */
export function MontagePreview({ montageId, tMs, tl, dirty, showSafe }: {
  montageId: string;
  tMs: number;
  /** Ko'rsatiladigan holat: draft (bo'lsa) yoki saqlangan timeline. */
  tl: MontageTimeline;
  dirty: boolean;
  showSafe: boolean;
}) {
  const t = useT();
  const dT = useDebounced(Math.round(tMs), 300);
  const dTl = useDebounced(tl, 400);
  const dDirty = useDebounced(dirty, 400);
  const frame = useMontagePreview({ id: montageId, tMs: dT, rev: timelineRev(dTl), timeline: dDirty ? dTl : null });
  const url = useObjectUrl(frame.data);
  const format = tl.format;
  const ratio = `${format.w} / ${format.h}`;
  const tall = format.h >= format.w;
  return (
    <div className="stack" style={{ gap: 6, alignItems: "center" }}>
      <div className="phone montage-frame" style={{ aspectRatio: ratio, maxWidth: tall ? 340 : "100%" }}
           aria-label={t("mon.preview", { aspect: format.aspect })} role="img">
        {url && <img className="engine-frame" src={url} alt={t("mon.previewAlt", { t: fmtTimePrecise(dT) })} />}
        {!url && !frame.isError && <span className="frame-status" role="status">{t("ed.frameLoading")}</span>}
        <SafeZoneOverlay visible={showSafe && format.aspect === "9:16"} />
        {frame.isFetching && url && <span className="frame-status" role="status">{t("ed.frameLoading")}</span>}
        {frame.isError && <span className="frame-status error" role="alert">{t("ed.frameError")}</span>}
      </div>
    </div>
  );
}
