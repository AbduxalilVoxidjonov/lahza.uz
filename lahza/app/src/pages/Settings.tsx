import { EditingSkillsPanel } from "../components/settings/EditingSkillsPanel";
import { ExternalAssetsPanel } from "../components/settings/ExternalAssetsPanel";
import { CapabilitiesPanel } from "../components/settings/CapabilitiesPanel";
import { DiagnosticsPanel } from "../components/settings/DiagnosticsPanel";
import { LearningPanel } from "../components/settings/LearningPanel";
import { LexiconManager } from "../components/settings/LexiconManager";
import { LicensePanel } from "../components/settings/LicensePanel";
import { LicensesPanel } from "../components/settings/LicensesPanel";
import { ModelManager } from "../components/settings/ModelManager";
import { ShortcutsTable } from "../components/settings/ShortcutsTable";
import { YoutubeImportPanel } from "../components/settings/YoutubeImportPanel";
import { LOCALE_NAMES, useT, type Locale } from "../i18n";
import type { Orthography, Script } from "../api/types";
import { LOCALES, useSettings } from "../store/settings";

export function Settings() {
  const t = useT();
  const { locale, setLocale, style, setStyle } = useSettings();
  return (
    <div className="stack" style={{ gap: 20, maxWidth: 980 }}>
      <h1>{t("set.title")}</h1>
      <section className="card row" aria-label={t("set.general")}>
        <label className="field" style={{ width: 260 }}>
          {t("set.language")}
          <select className="select" value={locale} onChange={(e) => setLocale(e.target.value as Locale)}>
            {LOCALES.map((l) => (
              <option key={l} value={l} lang={l}>{LOCALE_NAMES[l]}</option>
            ))}
          </select>
        </label>
        <label className="field" style={{ width: 260 }}>
          {t("style.orthography")}
          <select className="select" value={style.orthography} onChange={(e) => setStyle({ orthography: e.target.value as Orthography })}>
            <option value="official">{t("orth.official")}</option>
            <option value="ascii">{t("orth.ascii")}</option>
            <option value="new">{t("orth.new")}</option>
          </select>
        </label>
        <label className="field" style={{ width: 260 }}>
          {t("style.script")}
          <select className="select" value={style.script ?? "latin"} onChange={(e) => setStyle({ script: e.target.value as Script })}>
            <option value="latin">{t("script.latin")}</option>
            <option value="cyrillic" lang="uz-Cyrl">{t("script.cyrillic")}</option>
          </select>
        </label>
      </section>
      <ModelManager />
      <CapabilitiesPanel />
      <ExternalAssetsPanel />
      <YoutubeImportPanel />
      <EditingSkillsPanel />
      <LexiconManager />
      <LearningPanel />
      <DiagnosticsPanel />
      <ShortcutsTable />
      <LicensePanel />
      <LicensesPanel />
      <p className="muted">{t("set.privacy")}</p>
    </div>
  );
}
