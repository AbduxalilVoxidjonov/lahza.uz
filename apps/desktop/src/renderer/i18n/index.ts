import i18n from "i18next";
import LanguageDetector from "i18next-browser-languagedetector";
import { initReactI18next } from "react-i18next";

import enUS from "./locales/en-US";
import zhCN from "./locales/zh-CN";
import uzUZ from "./locales/uz-UZ";

// Lahza Studio is made for Uzbek speakers: Uzbek comes first and is the
// default for a first launch on any system.
export const SUPPORTED_LOCALES = ["uz-UZ", "en-US", "zh-CN"] as const;
export type Locale = (typeof SUPPORTED_LOCALES)[number];

/// Autonyms (each language's name in itself). Combined with a globe
/// icon in the locale toggle, this gives the universally-recognized
/// "language picker" affordance (Wikipedia / Google convention) and
/// keeps the label readable across switches — a Chinese-only user
/// sees "中文" on first launch, not the cryptic "中".
export const LOCALE_LABELS: Record<Locale, string> = {
  "uz-UZ": "O'zbekcha",
  "en-US": "English",
  "zh-CN": "中文",
};

// Register the same payload under the bare language code as well as the
// region-tagged code. `LanguageDetector` may surface `"en"` or `"zh"` from
// `navigator.language` depending on the OS / browser; without these aliases
// `t(...)` falls back to the literal key name. Cheap belt + suspenders.
const resources = {
  "uz-UZ": { translation: uzUZ },
  uz: { translation: uzUZ },
  "en-US": { translation: enUS },
  en: { translation: enUS },
  "zh-CN": { translation: zhCN },
  zh: { translation: zhCN },
};

i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    resources,
    // A first launch opens in Uzbek whatever the OS language (Uzbek speakers
    // mostly run Russian or English Windows); the persisted choice from
    // app_settings replaces it as soon as settings load. Tests are written
    // against the en-US source strings, so Vitest keeps OS detection.
    ...(import.meta.env.MODE === "test" ? {} : { lng: "uz-UZ" }),
    fallbackLng: "en-US",
    supportedLngs: ["uz-UZ", "uz", "en-US", "en", "zh-CN", "zh"],
    nonExplicitSupportedLngs: true,
    load: "currentOnly",
    detection: {
      // The detector only DETECTS the OS default for a genuine first launch
      // (navigator → <html lang>); `caches: []` stops it writing anywhere, so it
      // cannot fight the persisted value (see settings/appSettingsStore.ts).
      order: ["navigator", "htmlTag"],
      caches: [],
    },
    interpolation: {
      escapeValue: false, // React already escapes
    },
    react: {
      // We bundle resources synchronously, so suspense isn't needed and only
      // causes flashes-of-blank-UI without an outer <Suspense> boundary.
      useSuspense: false,
    },
    returnNull: false,
    // Flip to true while debugging missing-key issues — i18next then logs each
    // lookup to the browser console, which makes it obvious when a locale or
    // namespace isn't loading.
    debug: false,
  });

// Keep <html lang> on the UI language so spellcheck, hyphenation and screen
// readers treat the text as what it is.
i18n.on("languageChanged", (lng) => {
  if (typeof document !== "undefined") document.documentElement.lang = lng;
});

export default i18n;
