import type { LahzaService } from './service'

/** The app's one Lahza service, set by `installLahza` at startup. Kept apart
 *  from `install.ts` so the MCP server (and its tests) can read it without
 *  loading `electron`. Null until installed — and in tests that never do. */
let service: LahzaService | null = null

export function setLahzaService(s: LahzaService | null): void { service = s }
export function lahzaService(): LahzaService | null { return service }
