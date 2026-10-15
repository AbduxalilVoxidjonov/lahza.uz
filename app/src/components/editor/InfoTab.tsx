import { useState } from "react";

import { usePatchClip } from "../../api/hooks";
import type { Clip } from "../../api/types";
import { useT } from "../../i18n";
import { ErrorText } from "../ui";
import { KindBadge } from "../ClipBadges";

/** Ma'lumot: sarlavha/izoh/heshteglar, ball va tanlanish sababi. */
export function InfoTab({ clip, episodeId }: { clip: Clip; episodeId: string }) {
  const t = useT();
  const patch = usePatchClip(episodeId);
  const [title, setTitle] = useState(clip.title);
  const [caption, setCaption] = useState(clip.caption);
  const [tags, setTags] = useState(clip.hashtags.join(" "));
  return (
    <div className="stack">
      <form
        className="stack"
        onSubmit={(e) => {
          e.preventDefault();
          patch.mutate({ id: clip.id, title, caption, hashtags: tags.split(/\s+/).filter(Boolean) });
        }}
      >
        <label className="field">
          {t("ed.titleField")}
          <input className="input" value={title} onChange={(e) => setTitle(e.target.value)} />
        </label>
        <label className="field">
          {t("ed.caption")}
          <textarea className="textarea" value={caption} onChange={(e) => setCaption(e.target.value)} />
        </label>
        <label className="field">
          {t("ed.hashtags")}
          <input className="input" value={tags} onChange={(e) => setTags(e.target.value)} />
        </label>
        <div className="row">
          <button className="btn primary" disabled={patch.isPending}>{t("common.save")}</button>
          {patch.isSuccess && <span className="muted" role="status">{t("common.saved")}</span>}
          <ErrorText error={patch.error} />
        </div>
      </form>
      <div>
        <h2>{t("ed.reason")}</h2>
        <p>{clip.reason || "—"}</p>
      </div>
      <table className="table">
        <tbody>
          <tr><th>{t("clips.score")}</th><td className="mono">{Math.round(clip.score)}</td></tr>
          <tr><th>{t("clips.kind")}</th><td><KindBadge kind={clip.kind} /></td></tr>
          {Object.entries(clip.scores).map(([k, v]) => (
            <tr key={k}><th>{k}</th><td className="mono">{Math.round(v * 100) / 100}</td></tr>
          ))}
          <tr><th>{t("ed.source")}</th><td>{t(`source.${clip.source}`)}</td></tr>
        </tbody>
      </table>
    </div>
  );
}
