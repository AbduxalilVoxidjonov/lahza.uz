import { app, ipcMain } from 'electron'
import path from 'node:path'
import { LahzaEngine, resolveLahzaPaths } from './engine'
import { LahzaService } from './service'
import { setLahzaService } from './registry'
import type { TsActorHost } from '../state/ts-actor-host'

/** Wire the Lahza engine into the app: one lazily started sidecar, its IPC
 *  channels for the Lahza dock panel, and the service the `lahza_*` MCP tools
 *  read through `lahzaService()`. The sidecar is stopped on quit. */
export function installLahza(host: () => TsActorHost | null): LahzaService {
  const paths = resolveLahzaPaths({ packaged: app.isPackaged, resourcesPath: process.resourcesPath,
    devRoot: path.resolve(import.meta.dirname, '../..') })
  const service = new LahzaService(new LahzaEngine({ paths }), host)
  setLahzaService(service)
  const handle = (channel: string, fn: (args: Record<string, unknown>) => unknown) =>
    ipcMain.handle(`lahza:${channel}`, async (_e, args: Record<string, unknown> = {}) => {
      // Errors cross IPC as plain records: Electron flattens a thrown Error to
      // its message, and the panel wants the code too.
      try { return { ok: true, value: await fn(args) } }
      catch (e) {
        const err = e as { code?: string; message?: string }
        return { ok: false, error: { code: err.code ?? 'lahza_error', message: err.message ?? String(e) } }
      }
    })
  handle('status', () => service.status())
  handle('start', () => service.start())
  handle('analyze', (a) => service.analyze({ path: String(a.path ?? ''), force_lite: a.force_lite === true }))
  handle('job', (a) => service.job(String(a.id)))
  handle('cancelJob', (a) => service.cancelJob(String(a.id)))
  handle('episodes', () => service.episodes())
  handle('highlights', (a) => service.highlights(String(a.episode_id)))
  handle('place', (a) => service.place({ episode_id: String(a.episode_id), clip_id: String(a.clip_id) }))
  handle('exportClip', (a) => service.exportClip({ episode_id: String(a.episode_id), clip_id: String(a.clip_id), out_dir: String(a.out_dir ?? '') }))
  app.on('before-quit', () => { service.stop() })
  return service
}
