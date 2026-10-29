import { Link } from "react-router-dom";

import type { EpisodeSource } from "../../api/types";
import { youtubeDictionaries } from "../../i18n/youtube";
import { youtubeAt } from "../../lib/youtube-import";
import { useSettings } from "../../store/settings";
import { fmtTime } from "../ui";

/** YT-1: epizod YouTube'dan import qilingan bo'lsa - manba havolasi va boblar (transkriptda shu vaqtga o'tish). */
export function YoutubeSource({ episodeId, source }: { episodeId: string; source: EpisodeSource }) {
  const locale = useSettings((s) => s.locale);
  const y = youtubeDictionaries[locale];
  return (
    <section className="card stack" style={{ gap: 8 }} aria-labelledby="yt-source-title">
      <div className="row" style={{ justifyContent: "space-between" }}>
        <h2 id="yt-source-title" style={{ margin: 0 }}>{y.sourceTitle}</h2>
        <a className="btn small" href={source.url} target="_blank" rel="noreferrer">{y.openOnYoutube}</a>
      </div>
      <span className="muted">
        {source.title ?? source.video_id}{source.uploader ? ` · ${source.uploader}` : ""}
      </span>
      {source.chapters.length > 0 && (
        <details open={source.chapters.length <= 12}>
          <summary>{y.chapters} ({source.chapters.length})</summary>
          <ol className="plain-list stack" style={{ gap: 2, margin: "6px 0 0" }}>
            {source.chapters.map((c) => (
              <li key={c.start_ms} className="row" style={{ gap: 8 }}>
                <Link className="mono" to={`/episodes/${episodeId}/transcript?t=${c.start_ms}`} title={y.inTranscript}>
                  {fmtTime(c.start_ms)}
                </Link>
                <span style={{ flex: 1 }}>{c.title}</span>
                <a className="muted" href={youtubeAt(source.url, c.start_ms)} target="_blank" rel="noreferrer">↗</a>
              </li>
            ))}
          </ol>
        </details>
      )}
    </section>
  );
}
