import type { Orthography } from "../api/types";

/** Preview uchun imlo o'girish (render paytida engine aynan shu qoidani qo'llaydi). */
export function orth(text: string, mode: Orthography): string {
  if (mode === "ascii") return text.replace(/[ʻʼ]/g, "'");
  if (mode === "new")
    return text
      .replace(/oʻ/g, "ö")
      .replace(/Oʻ/g, "Ö")
      .replace(/gʻ/g, "ğ")
      .replace(/Gʻ/g, "Ğ")
      .replace(/([sScC])([hH])/g, (_m, a: string) => (a === "s" ? "ş" : a === "S" ? "Ş" : a === "c" ? "ç" : "Ç"));
  return text;
}
