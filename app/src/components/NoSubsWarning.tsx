import { useCapabilities } from "../api/hooks";
import { useT } from "../i18n";
import { useSettings } from "../store/settings";

/** libass yo'q bo'lsa: ogohlantirish va "subtitrsiz eksport" tanlovi (engine aks holda 422 qaytaradi). */
export function NoSubsWarning() {
  const t = useT();
  const caps = useCapabilities();
  const { allowNoSubs, setAllowNoSubs } = useSettings();
  if (caps.data?.libass !== false) return null;
  return (
    <div className="notice warn stack" role="alert" style={{ gap: 6 }}>
      <span>{t("cap.noLibass")}</span>
      <label className="row check">
        <input type="checkbox" checked={allowNoSubs} onChange={(e) => setAllowNoSubs(e.target.checked)} />
        {t("exp.allowNoSubs")}
      </label>
    </div>
  );
}
