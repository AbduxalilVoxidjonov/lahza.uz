// Oflayn litsenziya kaliti (V1-3, ADR-0016): `/v1/license` javob turi va sof yordamchilar.
// Bayroq o'chiq bo'lsa (standart) engine `{enabled: false, state: "disabled"}` qaytaradi -
// panel umuman ko'rsatilmaydi va hech narsa bloklanmaydi.

export type LicenseState =
  | "disabled" | "not_configured" | "unlicensed" | "valid" | "expired" | "not_yet_valid"
  | "wrong_version" | "wrong_device" | "clock_rollback" | "invalid";

export interface LicenseInfo {
  id: string;
  licensee: string;
  edition: string;
  issued: string;
  expires: string | null;
  perpetual: boolean;
  max_devices: number | null;
  device_locked: boolean;
  min_version: string | null;
  max_version: string | null;
}

export interface LicenseStatus {
  enabled: boolean;
  state: LicenseState;
  device_id: string | null;
  license: LicenseInfo | null;
  reason: string | null;
  app_version: string;
  activated_at?: string | null;
}

/** Xato kodlari (engine `detail` = "kod: xabar"). */
export const LICENSE_ERROR_CODES = [
  "malformed", "unsupported", "bad_signature", "not_configured", "disabled",
  "expired", "not_yet_valid", "wrong_version", "wrong_device", "clock_rollback",
] as const;
export type LicenseErrorCode = (typeof LICENSE_ERROR_CODES)[number];

/** Panel faqat bayroq yoqilganda ko'rinadi. */
export function licensePanelVisible(status: LicenseStatus | undefined | null): boolean {
  return !!status && status.enabled === true && status.state !== "disabled";
}

/** "bad_signature: imzo noto'g'ri" -> "bad_signature"; noma'lum bo'lsa null. */
export function licenseErrorCode(message: string): LicenseErrorCode | null {
  const code = (message.split(":")[0] ?? "").trim();
  return (LICENSE_ERROR_CODES as readonly string[]).includes(code) ? (code as LicenseErrorCode) : null;
}

export function stateTone(state: LicenseState): "good" | "warn" | "bad" {
  if (state === "valid") return "good";
  if (state === "unlicensed" || state === "not_configured") return "warn";
  return "bad";
}

/** Kiritilgan kalit bo'sh emasmi (bo'shliq/qator ko'chishi e'tiborsiz). */
export function keyInputReady(text: string): boolean {
  return text.replace(/[\s-]/g, "").length >= 16;
}
