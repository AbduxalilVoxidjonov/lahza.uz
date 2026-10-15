import { useState } from "react";

import { errorText } from "../api/client";
import { useCapabilities, useExportClip } from "../api/hooks";
import { useT } from "../i18n";
import { useSettings } from "../store/settings";
import { hasNativeDialog, pickPath } from "./dialog";

/**
 * Bir yoki bir nechta klipni eksport navbatiga qo'yish. Papka sozlamalardan; Tauri'da yo'q bo'lsa
 * dialog ochiladi, brauzerda esa foydalanuvchi uni "Eksport" sahifasida kiritadi.
 */
export function useExportAction(episodeId: string) {
  const t = useT();
  const exportClip = useExportClip(episodeId);
  const { style, exportDir, setExportDir, filenameTemplate, allowNoSubs } = useSettings();
  const caps = useCapabilities();
  /** libass yo'q va foydalanuvchi subtitrsiz eksportga rozi bo'lmagan - eksport bloklanadi. */
  const blockedNoSubs = caps.data?.libass === false && !allowNoSubs;
  const [error, setError] = useState<string | null>(null);
  const [queued, setQueued] = useState(0);

  const run = async (clipIds: string[]) => {
    setError(null);
    if (!clipIds.length) return;
    if (blockedNoSubs) {
      setError(t("exp.needNoSubs"));
      return;
    }
    let dir = exportDir;
    if (!dir && hasNativeDialog()) {
      dir = await pickPath({ directory: true, title: t("ed.exportDir") });
      if (dir) setExportDir(dir);
    }
    if (!dir) {
      setError(t("exp.noDir"));
      return;
    }
    let n = 0;
    for (const clipId of clipIds) {
      try {
        await exportClip.mutateAsync({ clipId, outDir: dir, style, orthography: style.orthography, filenameTemplate,
          allowNoSubs: caps.data?.libass === false && allowNoSubs });
        n++;
      } catch (e) {
        setError(errorText(e));
      }
    }
    setQueued(n);
  };

  return { run, error, queued, pending: exportClip.isPending, blockedNoSubs };
}
