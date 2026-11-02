// UXP muhiti: host modullari faqat `require()` orqali (rasmiy namunadagi kabi). Node testlarida ular yo'q,
// shuning uchun har biri lazy va xavfsiz o'raladi. Turlar - faqat bizga kerakli qism
// (manba: developer.adobe.com/premiere-pro/uxp/uxp-api/reference-js/modules/{os,fs}).

export interface UxpOs {
  platform(): string;
  homedir(): string;
}

export interface UxpFs {
  readFile(path: string, options: { encoding: "utf-8" }): Promise<string>;
  writeFile(path: string, data: string, options: { encoding: "utf-8" }): Promise<number>;
  rename(oldPath: string, newPath: string): Promise<number>;
  unlink(path: string): Promise<number>;
  mkdir(path: string, options?: { recursive?: boolean }): Promise<number>;
}

/** UXP/CJS `require` bormi (Premiere ichida - ha; vitest/Node ESM'da - yo'q). */
export function hostRequire<T>(id: string): T | null {
  try {
    if (typeof require !== "function") return null;
    return require(id) as T;
  } catch {
    return null;
  }
}

/** Premiere UXP ichida ishlayaptimizmi: `premierepro` moduli faqat u yerda bor. */
export function isInPremiere(): boolean {
  return hostRequire<object>("premierepro") !== null;
}
