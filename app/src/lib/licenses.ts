// Uchinchi tomon litsenziyalari ro'yxati (V1-5). Ma'lumot `scripts/gen_licenses.py` generatsiya qilgan
// `src/generated/licenses.json` dan olinadi: bundle ichida, engine'siz va tarmoqsiz ishlaydi.

export const UNKNOWN = "ANIQLANSIN";

export type LicenseCategory = "python" | "python-native" | "npm" | "rust" | "runtime" | "native" | "font" | "model";

export const CATEGORY_ORDER: readonly LicenseCategory[] = [
  "runtime", "native", "python", "python-native", "npm", "rust", "font", "model",
];

export type LicenseComponent = {
  id: string;
  group: string;
  category: LicenseCategory;
  name: string;
  version: string;
  license: string;
  basis: string;
  via: string;
  url: string;
  notes: string;
  attribution: string;
  risk: string;
  texts: string[];
};

export type LicenseText = { title: string; body: string };

export type LicenseData = {
  schema_version: number;
  generator: string;
  components: LicenseComponent[];
  texts: Record<string, LicenseText>;
};

export type CategoryFilter = LicenseCategory | "all" | "unresolved";

export function isUnresolved(c: Pick<LicenseComponent, "license" | "version">): boolean {
  return c.license.includes(UNKNOWN) || c.version.includes(UNKNOWN);
}

/** Qidiruv: nom, litsenziya, versiya, manba va izohlar bo'yicha; bo'shliq bilan ajratilgan barcha so'zlar mos kelishi shart. */
export function filterComponents(list: readonly LicenseComponent[], query: string, category: CategoryFilter = "all"): LicenseComponent[] {
  const words = query.toLocaleLowerCase().split(/\s+/).filter(Boolean);
  return list.filter((c) => {
    if (category === "unresolved" ? !isUnresolved(c) : category !== "all" && c.category !== category) return false;
    if (!words.length) return true;
    const hay = [c.name, c.version, c.license, c.via, c.notes, c.attribution, c.category].join(" ").toLocaleLowerCase();
    return words.every((w) => hay.includes(w));
  });
}

export function sortComponents(list: readonly LicenseComponent[]): LicenseComponent[] {
  const rank = (c: LicenseComponent) => {
    const i = CATEGORY_ORDER.indexOf(c.category);
    return i < 0 ? CATEGORY_ORDER.length : i;
  };
  return [...list].sort((a, b) => rank(a) - rank(b) || a.name.localeCompare(b.name, "en", { sensitivity: "base" })
    || a.version.localeCompare(b.version));
}

export function categoryCounts(list: readonly LicenseComponent[]): Record<CategoryFilter, number> {
  const out = { all: list.length, unresolved: 0 } as Record<CategoryFilter, number>;
  for (const cat of CATEGORY_ORDER) out[cat] = 0;
  for (const c of list) {
    out[c.category] = (out[c.category] ?? 0) + 1;
    if (isUnresolved(c)) out.unresolved += 1;
  }
  return out;
}

/** Komponentning to'liq litsenziya matnlari (pulda yo'q id'lar tashlab yuboriladi). */
export function componentTexts(data: Pick<LicenseData, "texts">, c: Pick<LicenseComponent, "texts">): LicenseText[] {
  return c.texts.map((id) => data.texts[id]).filter((t): t is LicenseText => !!t);
}

/** Litsenziyalar bo'yicha qisqa statistika (eng ko'p uchraydiganlari birinchi). */
export function licenseSummary(list: readonly LicenseComponent[], limit = 6): [string, number][] {
  const m = new Map<string, number>();
  for (const c of list) m.set(c.license, (m.get(c.license) ?? 0) + 1);
  return [...m.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0])).slice(0, limit);
}

/** UI'da ko'rsatiladigan FFmpeg versiyasi (LGPL manba taklifi matni uchun). */
export function ffmpegComponent(list: readonly LicenseComponent[]): LicenseComponent | undefined {
  return list.find((c) => c.category === "runtime" && c.name === "FFmpeg");
}
