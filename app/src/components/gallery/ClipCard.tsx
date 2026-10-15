import { memo } from "react";
import { Link } from "react-router-dom";

import { useObjectUrl, usePreviewFrame } from "../../api/hooks";
import type { Clip, ClipStatus } from "../../api/types";
import { useT } from "../../i18n";
import { useInView } from "../../lib/useInView";
import { outDuration } from "../../lib/words";
import { useSettings } from "../../store/settings";
import { KindBadge, StatusBadge } from "../ClipBadges";
import { fmtTime } from "../ui";

/** Muqova o'rniga engine preview kadri - karta ko'rinishga kirgandagina so'raladi. */
function Cover({ clip, episodeId }: { clip: Clip; episodeId: string }) {
  const t = useT();
  const style = useSettings((s) => s.style);
  const [ref, seen] = useInView<HTMLDivElement>();
  const frame = usePreviewFrame({
    episodeId,
    clipId: clip.id,
    tMs: Math.min(1000, Math.round(outDuration(clip) / 2)),
    style,
    orthography: style.orthography,
    enabled: seen,
    rev: [clip.start_ms, clip.end_ms, clip.cuts],
  });
  const url = useObjectUrl(frame.data);
  return (
    <div ref={ref} className="cover">
      {url ? (
        <img src={url} alt={t("gal.cover", { title: clip.title || "—" })} loading="lazy" />
      ) : (
        <span className="muted">{frame.isError ? "—" : seen ? t("common.loading") : ""}</span>
      )}
    </div>
  );
}

export const ClipCard = memo(function ClipCard(p: {
  clip: Clip;
  episodeId: string;
  active: boolean;
  checked: boolean;
  onActivate: () => void;
  onCheck: () => void;
  onStatus: (s: ClipStatus) => void;
  onSimilar: () => void;
  similarPending: boolean;
}) {
  const t = useT();
  const { clip } = p;
  const dur = Math.round(outDuration(clip) / 1000);
  return (
    <article
      className={`card clip-card ${clip.status}${p.active ? " active" : ""}`}
      aria-label={clip.title || t("clips.untitled")}
      aria-current={p.active || undefined}
      onFocus={p.onActivate}
      onClick={p.onActivate}
    >
      <Cover clip={clip} episodeId={p.episodeId} />
      <div className="row" style={{ justifyContent: "space-between" }}>
        <label className="row check">
          <input type="checkbox" checked={p.checked} onChange={p.onCheck} aria-label={t("gal.selectForExport")} />
          <span className="score" title={t("clips.score")}>{Math.round(clip.score)}</span>
        </label>
        <span className="row" style={{ gap: 6 }}>
          <KindBadge kind={clip.kind} />
          <span className="badge">{t("common.seconds", { n: dur })}</span>
          <span className="badge mono">{fmtTime(clip.start_ms)}</span>
        </span>
      </div>
      <div className="title">{clip.title || "—"}</div>
      <div className="muted reason">{clip.reason}</div>
      <div className="row">
        <StatusBadge status={clip.status} />
        {clip.source === "qolda" && <span className="badge">{t("source.qolda")}</span>}
      </div>
      <div className="row">
        <button type="button" className="btn small good" aria-pressed={clip.status === "qabul"} onClick={() => p.onStatus("qabul")}>
          {t("clips.accept")}
        </button>
        <button type="button" className="btn small bad" aria-pressed={clip.status === "rad"} onClick={() => p.onStatus("rad")}>
          {t("clips.reject")}
        </button>
        <Link className="btn small" to={`/episodes/${p.episodeId}/clips/${clip.id}`}>{t("clips.open")}</Link>
        <button type="button" className="btn small ghost" disabled={p.similarPending} onClick={p.onSimilar}>
          {t("gal.similar")}
        </button>
      </div>
    </article>
  );
});
