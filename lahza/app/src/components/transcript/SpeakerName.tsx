import { useState } from "react";

import { useRenameSpeaker } from "../../api/hooks";
import type { Speaker } from "../../api/types";
import { useT } from "../../i18n";
import { ErrorText } from "../ui";

/** Spiker yorlig'i; bosilsa ism beriladi (bo'sh qoldirilsa - asl yorliq). */
export function SpeakerName({ episodeId, label, speakers }: { episodeId: string; label: string; speakers: Speaker[] }) {
  const t = useT();
  const rename = useRenameSpeaker(episodeId);
  const sp = speakers.find((s) => s.label === label);
  const shown = sp?.display_name || label;
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState(shown);

  if (!editing) {
    return (
      <button
        type="button"
        className="speaker-tag"
        data-speaker={label}
        title={t("tr.renameSpeaker")}
        aria-label={`${shown}. ${t("tr.renameSpeaker")}`}
        onClick={() => {
          setName(sp?.display_name ?? "");
          setEditing(true);
        }}
      >
        {shown}
      </button>
    );
  }
  return (
    <form
      className="row"
      style={{ gap: 4 }}
      onSubmit={(e) => {
        e.preventDefault();
        rename.mutate({ label, display_name: name.trim() || null }, { onSuccess: () => setEditing(false) });
      }}
    >
      <input
        className="input"
        style={{ width: 140 }}
        autoFocus
        placeholder={label}
        aria-label={t("tr.speakerName")}
        value={name}
        onChange={(e) => setName(e.target.value)}
        onKeyDown={(e) => e.key === "Escape" && setEditing(false)}
      />
      <button className="btn small" disabled={rename.isPending}>{t("common.save")}</button>
      <ErrorText error={rename.error} />
    </form>
  );
}
