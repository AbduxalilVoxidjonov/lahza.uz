import { readFileSync } from 'node:fs'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { configureReleaseUpdater, createMacReleaseUpdates, findMacRelease, GITHUB_UPDATE_FEED } from './releaseUpdates'
import { RELEASE_API_URL, RELEASE_REPOSITORY_URL } from '../shared/release-source'

const release = (version = '0.6.0', arch = 'arm64') => ({
  tag_name: `v${version}`, draft: false, prerelease: false,
  assets: [{ name: `LahzaStudio-mac-${arch}.dmg`, state: 'uploaded', size: 1024,
    browser_download_url: `${RELEASE_REPOSITORY_URL}/releases/download/v${version}/LahzaStudio-mac-${arch}.dmg` }],
})
function setup() {
  const fetchReleases = vi.fn().mockResolvedValue([release()])
  const openDownload = vi.fn().mockResolvedValue(undefined)
  return { fetchReleases, openDownload, updates: createMacReleaseUpdates({ version: '0.5.4', arch: 'arm64', fetchReleases, openDownload }) }
}
afterEach(() => { vi.useRealTimers(); vi.restoreAllMocks() })

describe('Lahza release source', () => {
  it('pins automatic updates to our repository and matches the packaged publisher', () => {
    const updater = { setFeedURL: vi.fn() }
    configureReleaseUpdater(updater)
    expect(updater.setFeedURL).toHaveBeenCalledExactlyOnceWith({ provider: 'github', owner: 'AbduxalilVoxidjonov', repo: 'lahza.uz', releaseType: 'release' })
    const config = readFileSync(new URL('../../electron-builder.yml', import.meta.url), 'utf8')
    expect(config).toContain(`owner: ${GITHUB_UPDATE_FEED.owner}`)
    expect(config).toContain(`repo: ${GITHUB_UPDATE_FEED.repo}`)
  })
  it('selects the highest compatible stable app release rather than a content release', () => {
    expect(findMacRelease([release('0.6.0'), { ...release('9.0.0'), tag_name: 'content-whisper-cli-v1.9.1' }, release('0.7.0'), release('0.5.4')], '0.5.4', 'arm64')?.version).toBe('0.7.0')
  })
  it('ignores drafts, prereleases, old installers, missing assets and another architecture', () => {
    expect(findMacRelease([{ ...release(), draft: true }, { ...release(), prerelease: true }, release('0.2.6'), release('0.7.0', 'x64'), { ...release(), assets: [] }], '0.5.4', 'arm64')).toBeNull()
  })
  it('rejects foreign asset URLs and incomplete uploads', () => {
    const foreign = release()
    foreign.assets[0]!.browser_download_url = 'https://example.com/installer.dmg'
    const incomplete = release()
    incomplete.assets[0]!.state = 'open'
    expect(findMacRelease([foreign, incomplete], '0.5.4', 'arm64')).toBeNull()
    expect(() => findMacRelease({}, '0.5.4', 'arm64')).toThrow()
  })
  it('compares versions numerically and never offers a downgrade', () => {
    expect(findMacRelease([release('0.9.0'), release('0.10.0')], '0.5.4', 'arm64')?.version).toBe('0.10.0')
    expect(findMacRelease([release('0.5.4')], '0.6.0', 'arm64')).toBeNull()
  })
  it('checks metadata without starting a browser download or restarting', async () => {
    const { updates, fetchReleases, openDownload } = setup()
    expect(await updates.download()).toBe('not-ready')
    await updates.check()
    expect(fetchReleases).toHaveBeenCalledExactlyOnceWith(RELEASE_API_URL)
    expect(updates.status()).toEqual({ phase: 'available', version: '0.6.0', installation: 'manual' })
    updates.preferenceChanged()
    updates.installOnQuit(0)
    expect(openDownload).not.toHaveBeenCalled()
    expect(await updates.restart()).toBe('not-ready')
    expect(await updates.download()).toBe('opened')
    expect(openDownload).toHaveBeenCalledExactlyOnceWith(release().assets[0]!.browser_download_url)
  })
  it('surfaces connection failures and recovers on retry', async () => {
    vi.spyOn(console, 'warn').mockImplementation(() => {})
    const { updates, fetchReleases } = setup()
    fetchReleases.mockRejectedValueOnce(new Error('offline'))
    await updates.check()
    expect(updates.status().phase).toBe('error')
    await updates.check()
    expect(updates.status().phase).toBe('available')
  })
  it('reports current when no newer compatible app release is published', async () => {
    const { updates, fetchReleases } = setup()
    fetchReleases.mockResolvedValue([])
    await updates.check()
    expect(updates.status().phase).toBe('current')
  })
  it('coalesces concurrent checks and explicit browser handoffs', async () => {
    const { updates, fetchReleases, openDownload } = setup()
    let finish!: (payload: unknown) => void
    fetchReleases.mockImplementationOnce(() => new Promise(resolve => { finish = resolve }))
    const first = updates.check()
    const second = updates.check()
    expect(fetchReleases).toHaveBeenCalledTimes(1)
    finish([release()])
    await Promise.all([first, second])
    const download = updates.download()
    expect(updates.download()).toBe(download)
    await download
    expect(openDownload).toHaveBeenCalledTimes(1)
  })
  it('lets the user retry a failed browser handoff', async () => {
    vi.spyOn(console, 'warn').mockImplementation(() => {})
    const { updates, openDownload } = setup()
    await updates.check()
    openDownload.mockRejectedValueOnce(new Error('browser unavailable'))
    expect(await updates.download()).toBe('download-failed')
    expect(updates.status().phase).toBe('error')
    expect(await updates.download()).toBe('opened')
  })
  it('checks after startup and every six hours, and stops cleanly', async () => {
    vi.useFakeTimers()
    const { updates, fetchReleases } = setup()
    updates.start()
    updates.start()
    await vi.advanceTimersByTimeAsync(5000)
    expect(fetchReleases).toHaveBeenCalledTimes(1)
    await vi.advanceTimersByTimeAsync(6 * 60 * 60 * 1000 - 5000)
    expect(fetchReleases).toHaveBeenCalledTimes(2)
    updates.stop()
    await vi.advanceTimersByTimeAsync(6 * 60 * 60 * 1000)
    expect(fetchReleases).toHaveBeenCalledTimes(2)
  })
})
