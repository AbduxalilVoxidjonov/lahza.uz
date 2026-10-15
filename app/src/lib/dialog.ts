// Fayl/papka tanlash: Tauri'da tizim dialogi; brauzerda (dasturlash rejimi) foydalanuvchi yo'lni
// matn maydoniga yozadi (components/PathPicker.tsx).
import { isTauri } from "@tauri-apps/api/core";
import { open } from "@tauri-apps/plugin-dialog";

export const hasNativeDialog = () => isTauri();

export interface PickOptions {
  directory?: boolean;
  title?: string;
  defaultPath?: string;
  extensions?: string[];
  filterName?: string;
}

/** Tauri dialogi; brauzerda yoki bekor qilinganda null. */
export async function pickPath(o: PickOptions): Promise<string | null> {
  if (!isTauri()) return null;
  const res = await open({
    directory: !!o.directory,
    multiple: false,
    title: o.title,
    defaultPath: o.defaultPath,
    filters: o.extensions ? [{ name: o.filterName ?? o.extensions.join(", "), extensions: o.extensions }] : undefined,
  });
  return typeof res === "string" ? res : null;
}

/** Papka + fayl nomi (saqlash dialogi ruxsati so'ralmasligi uchun papka tanlanadi). */
export function joinPath(dir: string, name: string): string {
  const sep = dir.includes("\\") && !dir.includes("/") ? "\\" : "/";
  return dir.endsWith(sep) ? dir + name : dir + sep + name;
}

/** Fayl nomi uchun xavfsiz qism. */
export const safeName = (s: string) => s.trim().replace(/[\\/:*?"<>|]+/g, "_").slice(0, 60) || "lahza";
