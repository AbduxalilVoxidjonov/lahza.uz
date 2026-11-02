import type { AppUpdater } from 'electron-updater'
import type { UpdateDownloadResult, UpdateRestartResult, UpdateStatus } from '../shared/updates'
import { RELEASE_API_URL, RELEASE_OWNER, RELEASE_REPO, RELEASE_REPOSITORY_URL } from '../shared/release-source'

export const GITHUB_UPDATE_FEED = {
  provider: 'github' as const, owner: RELEASE_OWNER, repo: RELEASE_REPO, releaseType: 'release' as const,
}

/** Pin the runtime as well as the packaged app-update.yml to our repository. */
export function configureReleaseUpdater(updater: Pick<AppUpdater, 'setFeedURL'>) {
  updater.setFeedURL(GITHUB_UPDATE_FEED)
}

const STABLE_VERSION = /^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$/
function newer(left: string, right: string): boolean {
  const a = left.split('.').map(BigInt)
  const b = right.split('.').map(BigInt)
  for (let i = 0; i < 3; i++) {
    if (a[i] !== b[i]) return a[i]! > b[i]!
  }
  return false
}
function record(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === 'object'
}

/** Ignore legacy, content-only, prerelease and incomplete releases. */
export function findMacRelease(payload: unknown, currentVersion: string, arch: string): { version: string; url: string } | null {
  if (!Array.isArray(payload) || !STABLE_VERSION.test(currentVersion)) throw new Error('Invalid release metadata or application version')
  let found: { version: string; url: string } | null = null
  const filename = `LahzaStudio-mac-${arch}.dmg`
  for (const release of payload) {
    if (!record(release) || release.draft !== false || release.prerelease !== false || typeof release.tag_name !== 'string') continue
    const version = release.tag_name.startsWith('v') ? release.tag_name.slice(1) : ''
    if (!STABLE_VERSION.test(version) || !newer(version, currentVersion) || found && !newer(version, found.version)) continue
    const url = `${RELEASE_REPOSITORY_URL}/releases/download/${release.tag_name}/${filename}`
    if (!Array.isArray(release.assets) || !release.assets.some(asset =>
      record(asset) && asset.name === filename && asset.state === 'uploaded' &&
      typeof asset.size === 'number' && asset.size > 0 && asset.browser_download_url === url,
    )) continue
    found = { version, url }
  }
  return found
}

/** Ad-hoc signed Mac builds can check releases and offer their DMG for manual installation. */
export function createMacReleaseUpdates(deps: {
  version: string
  arch: string
  fetchReleases: (url: string) => Promise<unknown>
  openDownload: (url: string) => Promise<void>
}) {
  let status: UpdateStatus = { phase: 'idle', installation: 'manual' }
  let release: ReturnType<typeof findMacRelease> = null
  let pending: Promise<void> | null = null
  let opening: Promise<UpdateDownloadResult> | null = null
  let startup: ReturnType<typeof setTimeout> | undefined
  let interval: ReturnType<typeof setInterval> | undefined
  async function check() {
    if (pending) return pending
    status = { phase: 'checking', installation: 'manual' }
    pending = (async () => {
      try {
        release = findMacRelease(await deps.fetchReleases(RELEASE_API_URL), deps.version, deps.arch)
        status = release ? { phase: 'available', installation: 'manual', version: release.version } : { phase: 'current', installation: 'manual' }
      } catch (error) {
        console.warn('[updates]', error)
        release = null
        status = { phase: 'error', installation: 'manual' }
      }
    })().finally(() => { pending = null })
    return pending
  }
  return {
    status: (): UpdateStatus => ({ ...status }),
    check,
    preferenceChanged() { /* Mac installation remains an explicit action. */ },
    download(): Promise<UpdateDownloadResult> {
      if (opening) return opening
      if (!release) return Promise.resolve('not-ready')
      const offered = release
      opening = deps.openDownload(offered.url).then((): UpdateDownloadResult => 'opened').catch((error): UpdateDownloadResult => {
        console.warn('[updates]', error)
        status = { phase: 'error', installation: 'manual', version: offered.version }
        return 'download-failed'
      }).finally(() => { opening = null })
      return opening
    },
    restart: async (): Promise<UpdateRestartResult> => 'not-ready',
    installOnQuit(_exitCode: number) { /* DMGs are installed by the user. */ },
    start() {
      if (startup || interval) return
      startup = setTimeout(() => { void check() }, 5_000)
      interval = setInterval(() => { void check() }, 6 * 60 * 60 * 1000)
      startup.unref()
      interval.unref()
    },
    stop() {
      clearTimeout(startup)
      clearInterval(interval)
      startup = undefined
      interval = undefined
    },
  }
}
