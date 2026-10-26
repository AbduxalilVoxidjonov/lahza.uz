// "Claude montaj" bo'limi: `/v1/claude/*` javoblarini tekshirish, holatdan UI holatini chiqarish
// va `claude_*` xato kodlarini ajratish. Sof modul (React'siz) - node testlari to'g'ridan-to'g'ri ishlatadi.

export type ClaudeTarget = "claude_code" | "claude_desktop";
export const CLAUDE_TARGETS: readonly ClaudeTarget[] = ["claude_code", "claude_desktop"];
export type ClaudeAuthState = "unknown" | "ok" | "not_logged_in" | "error";
export type Planner = "local" | "claude";

export interface ClaudeStatus {
  enabled: boolean;
  cli: { installed: boolean; path: string | null; version: string | null };
  desktop: { installed: boolean; path: string | null };
  auth: { state: ClaudeAuthState; detail: string | null; checked_at: string | null };
  mcp: { claude_code: boolean; claude_desktop: boolean };
  mcp_command: string[];
}

export interface ClaudeConnectResult {
  actions: string[];
  status: ClaudeStatus;
}

const obj = (v: unknown): v is Record<string, unknown> => !!v && typeof v === "object" && !Array.isArray(v);
const strOrNull = (v: unknown): v is string | null => v === null || typeof v === "string";
const strList = (v: unknown): v is string[] => Array.isArray(v) && v.length <= 200 && v.every((x) => typeof x === "string");
const AUTH_STATES: readonly ClaudeAuthState[] = ["unknown", "ok", "not_logged_in", "error"];

/** `GET /v1/claude/status` (va unga teng javoblar). Noto'g'ri shakl - xato. */
export function parseClaudeStatus(v: unknown): ClaudeStatus {
  const bad = () => new Error("Invalid claude status response");
  if (!obj(v) || typeof v.enabled !== "boolean") throw bad();
  const { cli, desktop, auth, mcp } = v;
  if (!obj(cli) || typeof cli.installed !== "boolean" || !strOrNull(cli.path ?? null) || !strOrNull(cli.version ?? null)) throw bad();
  if (!obj(desktop) || typeof desktop.installed !== "boolean" || !strOrNull(desktop.path ?? null)) throw bad();
  if (!obj(auth) || !AUTH_STATES.includes(auth.state as ClaudeAuthState) || !strOrNull(auth.detail ?? null) || !strOrNull(auth.checked_at ?? null)) throw bad();
  if (!obj(mcp) || typeof mcp.claude_code !== "boolean" || typeof mcp.claude_desktop !== "boolean") throw bad();
  const command = v.mcp_command ?? [];
  if (!strList(command)) throw bad();
  return {
    enabled: v.enabled,
    cli: { installed: cli.installed, path: (cli.path as string | null) ?? null, version: (cli.version as string | null) ?? null },
    desktop: { installed: desktop.installed, path: (desktop.path as string | null) ?? null },
    auth: { state: auth.state as ClaudeAuthState, detail: (auth.detail as string | null) ?? null, checked_at: (auth.checked_at as string | null) ?? null },
    mcp: { claude_code: mcp.claude_code, claude_desktop: mcp.claude_desktop },
    mcp_command: command,
  };
}

/** `POST /v1/claude/connect|disconnect` javobi. */
export function parseConnectResult(v: unknown): ClaudeConnectResult {
  if (!obj(v) || !strList(v.actions)) throw new Error("Invalid claude connect response");
  return { actions: v.actions, status: parseClaudeStatus(v.status) };
}

/** Reja javobidagi ixtiyoriy `planner` maydoni; yo'q yoki noma'lum bo'lsa - "local". */
export function parsePlanner(v: unknown): Planner {
  return obj(v) && v.planner === "claude" ? "claude" : "local";
}

/** Claude rejalovchisi nima uchun ishlatib bo'lmaydi (UI matn kaliti bilan bir xil nom). */
export type ClaudeBlock = "unavailable" | "not_installed" | "disabled" | "not_logged_in";

export interface ClaudeTargetView {
  target: ClaudeTarget;
  installed: boolean;
  connected: boolean;
  /** Ulash mumkin: dastur o'rnatilgan va hali ulanmagan. */
  canConnect: boolean;
  canDisconnect: boolean;
}

export interface ClaudeView {
  /** CLI yoki Desktop'dan kamida bittasi topildi. */
  anyInstalled: boolean;
  /** O'rnatish yo'riqnomasini ko'rsatish kerak (CLI yoki Desktop yo'q). */
  showInstallGuide: boolean;
  auth: ClaudeAuthState;
  /** Login holatini tekshirish faqat CLI bor bo'lganda ma'noli. */
  canCheckAuth: boolean;
  targets: ClaudeTargetView[];
  /** Montaj panelidagi "Claude" rejalovchisi tanlanishi mumkinmi va bo'lmasa - sababi. */
  plannerReady: boolean;
  plannerBlock: ClaudeBlock | null;
}

/**
 * Holatdan UI holati. Rejalovchi Claude Code CLI orqali ishlaydi: CLI kerak, bo'lim yoqilgan,
 * login "not_logged_in" bo'lmasligi kerak ("unknown" - ruxsat, engine o'zi `claude_not_logged_in` qaytaradi).
 */
export function claudeView(s: ClaudeStatus | null | undefined): ClaudeView {
  if (!s) {
    return { anyInstalled: false, showInstallGuide: false, auth: "unknown", canCheckAuth: false, targets: [], plannerReady: false, plannerBlock: "unavailable" };
  }
  const installed: Record<ClaudeTarget, boolean> = { claude_code: s.cli.installed, claude_desktop: s.desktop.installed };
  const targets = CLAUDE_TARGETS.map((target) => {
    const connected = s.mcp[target];
    return { target, installed: installed[target], connected, canConnect: installed[target] && !connected, canDisconnect: connected };
  });
  const plannerBlock: ClaudeBlock | null = !s.cli.installed ? "not_installed"
    : !s.enabled ? "disabled"
    : s.auth.state === "not_logged_in" ? "not_logged_in"
    : null;
  return {
    anyInstalled: s.cli.installed || s.desktop.installed,
    showInstallGuide: !s.cli.installed || !s.desktop.installed,
    auth: s.auth.state,
    canCheckAuth: s.cli.installed,
    targets,
    plannerReady: plannerBlock === null,
    plannerBlock,
  };
}

/** Foydalanuvchi tanlovi; Claude tayyor bo'lmasa har doim mahalliy rejalovchi. */
export function resolvePlanner(choice: Planner | null, claudeReady: boolean): Planner {
  return choice === "claude" && claudeReady ? "claude" : "local";
}

export const CLAUDE_ERROR_CODES = [
  "claude_disabled", "claude_not_installed", "claude_not_logged_in", "claude_timeout", "claude_bad_plan",
] as const;
export type ClaudeErrorCode = (typeof CLAUDE_ERROR_CODES)[number];

const isClaudeCode = (c: unknown): c is ClaudeErrorCode =>
  typeof c === "string" && (CLAUDE_ERROR_CODES as readonly string[]).includes(c);

/**
 * Engine xatosi `detail = "kod: xabar"` (ApiError.message) yoki tuzilgan `{code, message}`
 * (ApiError.code). Tanilgan `claude_*` kod bo'lsa - {code, message}, aks holda null.
 */
export function parseClaudeError(e: unknown): { code: ClaudeErrorCode; message: string } | null {
  if (e && typeof e === "object" && isClaudeCode((e as { code?: unknown }).code)) {
    const message = (e as { message?: unknown }).message;
    return { code: (e as { code: ClaudeErrorCode }).code, message: typeof message === "string" ? message : "" };
  }
  const text = typeof e === "string" ? e : e instanceof Error ? e.message : null;
  if (!text) return null;
  const m = /^\s*([a-z_]+)\s*:\s*([\s\S]*)$/.exec(text);
  if (!m || !isClaudeCode(m[1])) return isClaudeCode(text.trim()) ? { code: text.trim() as ClaudeErrorCode, message: "" } : null;
  return { code: m[1], message: (m[2] ?? "").trim() };
}

/** Tasdiqlash oynasi uchun: bo'sh `actions` - o'zgartiradigan narsa yo'q. */
export function confirmableActions(actions: string[]): { actions: string[]; empty: boolean } {
  const clean = actions.map((a) => a.trim()).filter(Boolean);
  return { actions: clean, empty: clean.length === 0 };
}

/** O'rnatish yo'riqnomasi uchun rasmiy sahifalar (matn sifatida ko'rsatiladi). */
export const CLAUDE_INSTALL_LINKS: Record<ClaudeTarget, string> = {
  claude_code: "https://docs.claude.com/en/docs/claude-code/setup",
  claude_desktop: "https://claude.ai/download",
};
