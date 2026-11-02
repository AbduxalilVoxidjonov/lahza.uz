import { create } from "zustand";

import { DEFAULT_STYLE, type Orthography, type StyleTemplate } from "../api/types";
import type { Locale } from "../i18n";

const KEY = "lahza.settings.v1";

export const DEFAULT_FILENAME_TEMPLATE = "{shou}_{epizod}_{nn}_{sarlavha}";
export const LOCALES: readonly Locale[] = ["uz", "uz-Cyrl", "ru", "en"];

interface SettingsState {
  locale: Locale;
  orthography: Orthography;
  style: StyleTemplate;
  exportDir: string | null;
  filenameTemplate: string;
  /** libass yo'q bo'lganda subtitrsiz eksportga ruxsat. */
  allowNoSubs: boolean;
  setLocale: (l: Locale) => void;
  setOrthography: (o: Orthography) => void;
  setStyle: (s: Partial<StyleTemplate>) => void;
  /** Saqlangan shablonni to'liq yuklash (yetishmagan maydonlar standartdan). */
  replaceStyle: (s: Partial<StyleTemplate>) => void;
  setExportDir: (d: string | null) => void;
  setFilenameTemplate: (t: string) => void;
  setAllowNoSubs: (v: boolean) => void;
}

type Persisted = Pick<SettingsState, "locale" | "orthography" | "style" | "exportDir" | "filenameTemplate" | "allowNoSubs">;

function load(): Persisted {
  const fallback: Persisted = {
    locale: "uz",
    orthography: "official",
    style: DEFAULT_STYLE,
    exportDir: null,
    filenameTemplate: DEFAULT_FILENAME_TEMPLATE,
    allowNoSubs: false,
  };
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return fallback;
    const p = JSON.parse(raw) as Partial<Persisted>;
    return {
      ...fallback,
      ...p,
      locale: p.locale && LOCALES.includes(p.locale) ? p.locale : fallback.locale,
      // Eski versiyada saqlangan uslubda yangi maydonlar yo'q - standart bilan to'ldiramiz.
      style: { ...DEFAULT_STYLE, ...(p.style ?? {}) },
    };
  } catch {
    return fallback;
  }
}

function save(s: Persisted) {
  try {
    localStorage.setItem(KEY, JSON.stringify(s));
  } catch {
    /* saqlab bo'lmasa ham ishlayveradi */
  }
}

export const useSettings = create<SettingsState>((set, get) => {
  const persist = () => {
    const { locale, orthography, style, exportDir, filenameTemplate, allowNoSubs } = get();
    save({ locale, orthography, style, exportDir, filenameTemplate, allowNoSubs });
  };
  return {
    ...load(),
    setLocale: (locale) => (set({ locale }), persist()),
    setOrthography: (orthography) => (set({ orthography }), persist()),
    setStyle: (s) => (set({ style: { ...get().style, ...s } }), persist()),
    replaceStyle: (s) => (set({ style: { ...DEFAULT_STYLE, ...s } }), persist()),
    setExportDir: (exportDir) => (set({ exportDir }), persist()),
    setFilenameTemplate: (filenameTemplate) => (set({ filenameTemplate }), persist()),
    setAllowNoSubs: (allowNoSubs) => (set({ allowNoSubs }), persist()),
  };
});
