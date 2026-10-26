// Pro: shaxsiy lug'at (PRO-1) va real natijalardan ball vaznlari (PRO-6) - sof yordamchilar
// (React'siz, node testlari uchun).

export interface DictionaryEntry {
  id: number;
  wrong: string;
  right: string;
  kind: "ism" | "atama" | "soz";
  count: number;
  /** Takrorlangan va ziddiyatsiz: keyingi transkripsiyada qo'llanadi. */
  active: boolean;
  last_episode_id: string | null;
  updated_at: string;
}

export interface DictionaryResponse {
  entries: DictionaryEntry[];
  min_count: number;
  conf_threshold: number;
}

export interface Weights {
  weight_llm: number;
  weight_signals: number;
}

export interface WeightsInfo {
  scope: string;
  weights: Weights;
  defaults: Weights;
  source: "project" | "global" | "default";
  learned: boolean;
  n_samples: number;
  min_samples: number;
}

export interface ClipMetrics {
  clip_id: string;
  views: number;
  likes: number | null;
  recorded_at: string;
}

const MAX = 1e12;

/** "12 500", "12,500", "12.5k", "1.2M", "3 млн" -> butun son; bo'sh -> null; yaroqsiz -> NaN. */
export function parseCount(raw: string): number | null {
  const s = raw.trim().toLowerCase().replace(/\s+/g, "");
  if (!s) return null;
  const m = /^(\d+(?:[.,]\d+)?)(k|m|ming|mln|млн|тыс|минг)?$/.exec(s);
  if (!m) {
    // ming ajratgichlari: 12,500 / 12.500 / 1,250,000
    if (/^\d{1,3}([.,]\d{3})+$/.test(s)) return Number(s.replace(/[.,]/g, ""));
    return Number.NaN;
  }
  const num = m[1] ?? "";
  const suf = m[2];
  let n: number;
  if (!suf && /^\d{1,3}[.,]\d{3}$/.test(num)) n = Number(num.replace(/[.,]/, ""));
  else n = Number(num.replace(",", "."));
  const mult = !suf ? 1 : suf === "k" || suf === "ming" || suf === "тыс" || suf === "минг" ? 1e3 : 1e6;
  const out = Math.round(n * mult);
  return out >= 0 && out <= MAX ? out : Number.NaN;
}

/** Vazn ulushi foizda ("70%"). */
export const pct = (w: number) => `${Math.round(w * 100)}%`;

/** Vaznlar standartdan farq qiladimi (tiklash tugmasi faolligi). */
export function differsFromDefault(info: WeightsInfo | undefined): boolean {
  if (!info) return false;
  return info.learned || info.source !== "default";
}

/** O'rganishgacha qolgan namuna soni (0 - yetarli). */
export const samplesLeft = (info: WeightsInfo) => Math.max(0, info.min_samples - info.n_samples);
