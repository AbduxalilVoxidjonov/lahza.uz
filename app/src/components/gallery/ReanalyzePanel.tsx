import { useState } from "react";

import { useReanalyze } from "../../api/hooks";
import { useT } from "../../i18n";
import { ErrorText } from "../ui";

/** "Highlight'larni qayta topish": LLM paydo bo'lgan, epizod esa Lite'da tahlil qilingan bo'lsa ajralib turadi. */
export function ReanalyzePanel({ episodeId, highlight }: { episodeId: string; highlight: boolean }) {
  const t = useT();
  const re = useReanalyze(episodeId);
  const [open, setOpen] = useState(false);
  const [focus, setFocus] = useState("");
  const [lite, setLite] = useState(false);
  const [speakers, setSpeakers] = useState("");
  return (
    <div className="popover-wrap">
      <button type="button" className={`btn small${highlight ? " primary" : ""}`} aria-expanded={open} onClick={() => setOpen((v) => !v)}>
        {t("gal.reanalyze")}
      </button>
      {open && (
        <form
          className="card stack popover"
          onSubmit={(e) => {
            e.preventDefault();
            re.mutate({
              focus: focus.trim() || undefined,
              force_lite: lite,
              num_speakers: speakers ? Number(speakers) : undefined,
            }, { onSuccess: () => setOpen(false) });
          }}
        >
          <label className="field">
            {t("proj.focus")}
            <input className="input" value={focus} onChange={(e) => setFocus(e.target.value)} />
          </label>
          <label className="field">
            {t("gal.numSpeakers")}
            <input className="input" type="number" min={1} max={10} value={speakers} placeholder={t("gal.auto")}
                   onChange={(e) => setSpeakers(e.target.value)} />
          </label>
          <label className="row muted check">
            <input type="checkbox" checked={lite} onChange={(e) => setLite(e.target.checked)} /> {t("proj.lite")}
          </label>
          <p className="muted">{t("gal.reanalyzeHint")}</p>
          <div className="row">
            <button className="btn small primary" disabled={re.isPending}>{t("gal.reanalyzeRun")}</button>
            <button type="button" className="btn small ghost" onClick={() => setOpen(false)}>{t("common.cancel")}</button>
          </div>
          <ErrorText error={re.error} />
        </form>
      )}
    </div>
  );
}
