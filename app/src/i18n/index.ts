// Oddiy i18n: kalit -> matn. Asosiy lug'at - o'zbek (lotin); qolgan lug'atlar `Messages` turini
// `satisfies` bilan bajaradi, ya'ni kalit yetishmasa yoki ortiqcha bo'lsa TS xato beradi (M2-APP-10).
import { useEffect } from "react";

import { useSettings } from "../store/settings";
import { en } from "./en";
import { ru } from "./ru";
import { uz } from "./uz";
import { uzCyrl } from "./uz-Cyrl";

export type Locale = "uz" | "uz-Cyrl" | "ru" | "en";
export type MessageKey = keyof typeof uz;
/** Har bir lug'at aynan shu turga mos bo'lishi shart. */
export type Messages = { readonly [K in MessageKey]: string };

const dicts: Record<Locale, Messages> = { uz, "uz-Cyrl": uzCyrl, ru, en };

/** Interfeys tilining o'z nomi (tanlov ro'yxati uchun - tarjima qilinmaydi). */
export const LOCALE_NAMES: Record<Locale, string> = {
  uz: "Oʻzbekcha",
  "uz-Cyrl": "Ўзбекча",
  ru: "Русский",
  en: "English",
};

export type TFunc = (key: MessageKey, vars?: Record<string, string | number>) => string;

export function translate(locale: Locale, key: MessageKey, vars?: Record<string, string | number>): string {
  let s: string = dicts[locale][key] ?? uz[key] ?? key;
  if (vars) for (const [k, v] of Object.entries(vars)) s = s.replaceAll(`{${k}}`, String(v));
  return s;
}

export function useT(): TFunc {
  const locale = useSettings((s) => s.locale);
  return (key, vars) => translate(locale, key, vars);
}

/** Raqamlar lokal formatda (TZ 11). */
export function useFmtNumber() {
  const locale = useSettings((s) => s.locale);
  return (n: number, digits = 0) =>
    new Intl.NumberFormat(locale === "en" ? "en" : locale === "ru" ? "ru" : "uz", {
      maximumFractionDigits: digits,
    }).format(n);
}

/** <html lang> joriy tilga mos (ekran o'quvchilari uchun). */
export function useDocumentLang() {
  const locale = useSettings((s) => s.locale);
  useEffect(() => {
    document.documentElement.lang = locale;
  }, [locale]);
}
