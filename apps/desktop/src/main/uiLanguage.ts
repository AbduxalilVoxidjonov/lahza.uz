// The language main's own native dialogs speak. The UI language lives in
// app_settings (`language`); main mirrors it here so a dialog raised outside
// the renderer (data folder, quit prompt, elevation notice) matches the window.
// Unset means a first launch, which the renderer opens in Uzbek.

let current: string | null = null

export function setUiLanguage(language: string | null | undefined): void {
  current = language ?? null
}

/** Pick the variant for the current UI language. */
export function tr<T>(t: { uz: T; en: T; zh: T }): T {
  const l = (current ?? 'uz-UZ').toLowerCase()
  return l.startsWith('zh') ? t.zh : l.startsWith('en') ? t.en : t.uz
}
