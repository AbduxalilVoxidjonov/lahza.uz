import { useEffect, useRef } from "react";

/** Matn kiritish elementida fokus bo'lsa yorliqlar ishlamaydi (TZ 11, M3-A11Y-1). */
export function isTypingTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  if (target.isContentEditable) return true;
  return !!target.closest("input, textarea, select");
}

/**
 * Kalitlar: "space", "j", "mod+e" (mod = Cmd yoki Ctrl). Ishlov beruvchi true qaytarmasa
 * standart xatti-harakat bekor qilinadi.
 */
export type HotkeyMap = Record<string, (e: KeyboardEvent) => void>;

function keyName(e: KeyboardEvent): string {
  const base = e.code === "Space" ? "space" : e.key.toLowerCase();
  return (e.metaKey || e.ctrlKey ? "mod+" : "") + (e.shiftKey && base.length > 1 ? "shift+" : "") + base;
}

export function useHotkeys(map: HotkeyMap, enabled = true) {
  const ref = useRef(map);
  ref.current = map;
  useEffect(() => {
    if (!enabled) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.repeat && e.code !== "KeyJ" && e.code !== "KeyL") return;
      if (isTypingTarget(e.target)) return;
      // Fokusdagi tugma Space'ni o'zi bosadi - ijro bilan to'qnashmasin.
      if (e.code === "Space" && e.target instanceof HTMLButtonElement) return;
      if (e.altKey) return;
      const fn = ref.current[keyName(e)];
      if (!fn) return;
      e.preventDefault();
      fn(e);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [enabled]);
}
