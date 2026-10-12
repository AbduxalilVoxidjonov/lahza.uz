// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import '../i18n'
import { UpdateNotification } from './UpdateNotification'
import { UpdateDialog } from './UpdateDialog'
import { UpdateButton } from './UpdateButton'
import { useAppSettingsStore } from '../settings/appSettingsStore'

afterEach(() => { cleanup(); vi.unstubAllEnvs() })

function setup(autoInstall = true) {
  useAppSettingsStore.setState(state => ({ settings: { ...state.settings, auto_install_updates_on_quit: autoInstall } }))
  const ready = { phase: 'ready', version: '1.2.0' }
  const restart = vi.fn().mockResolvedValue('restarting')
  const download = vi.fn().mockResolvedValue('ready')
  const api = { updates: { status: vi.fn().mockResolvedValue(ready), check: vi.fn().mockResolvedValue(ready), restart, download } }
  Object.assign(window, { api })
  return api.updates
}

describe('update actions', () => {
  it('announces a ready update without a modal and dismisses without changing the exit preference', async () => {
    const { restart } = setup()
    render(<UpdateNotification />)
    await screen.findByRole('complementary', { name: 'A new version is available' })
    expect(screen.queryByRole('dialog')).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'Later' }))
    expect(screen.queryByRole('complementary')).toBeNull()
    expect(restart).not.toHaveBeenCalled()
    expect(useAppSettingsStore.getState().settings.auto_install_updates_on_quit).toBe(true)
  })

  it('restarts once with a blocking saving state, leaving an opt-out unchanged', async () => {
    const { restart } = setup(false)
    render(<UpdateNotification />)
    fireEvent.click(await screen.findByRole('button', { name: 'Update and restart app' }))
    await screen.findByRole('dialog', { name: 'Saving and restarting…' })
    expect(restart).toHaveBeenCalledOnce()
    expect(useAppSettingsStore.getState().settings.auto_install_updates_on_quit).toBe(false)
    expect(screen.queryByRole('button', { name: 'Close' })).toBeNull()
  })

  it('keeps the update available for retry if saving fails', async () => {
    const { restart } = setup()
    restart.mockResolvedValue('save-failed')
    render(<UpdateNotification />)
    fireEvent.click(await screen.findByRole('button', { name: 'Update and restart app' }))
    await screen.findByRole('alert')
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
    expect((screen.getByRole('button', { name: 'Update and restart app' }) as HTMLButtonElement).disabled).toBe(false)
    expect(useAppSettingsStore.getState().settings.auto_install_updates_on_quit).toBe(true)
  })

  it('offers the same actions from Help after dismissing the notification', async () => {
    setup(false)
    const onClose = vi.fn()
    render(<UpdateDialog onClose={onClose} />)
    await screen.findByRole('button', { name: 'Update and restart app' })
    expect(screen.getByText(/You can return to the update from the Help menu or the start screen’s update button/)).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Later' }))
    expect(onClose).toHaveBeenCalledOnce()
  })

  it('offers an explicit download in manual mode and opening the dialog does not download', async () => {
    const api = setup(false)
    api.check.mockResolvedValue({ phase: 'available', version: '1.2.0' })
    render(<UpdateDialog onClose={vi.fn()} />)
    const download = await screen.findByRole('button', { name: 'Download and install' })
    expect(screen.getByText(/It will only download when you choose/)).toBeTruthy()
    expect(api.download).not.toHaveBeenCalled()
    fireEvent.click(download)
    await waitFor(() => expect(api.download).toHaveBeenCalledOnce())
    expect(api.restart).toHaveBeenCalledOnce()
    await screen.findByRole('dialog', { name: 'Saving and restarting…' })
    expect(useAppSettingsStore.getState().settings.auto_install_updates_on_quit).toBe(false)
  })

  it('allows retry after a manual download fails', async () => {
    const api = setup(false)
    api.check.mockResolvedValue({ phase: 'available', version: '1.2.0' })
    api.download.mockResolvedValue('download-failed')
    render(<UpdateDialog onClose={vi.fn()} />)
    fireEvent.click(await screen.findByRole('button', { name: 'Download and install' }))
    expect((await screen.findByRole('alert')).textContent).toContain('Could not download the update')
    expect((screen.getByRole('button', { name: 'Download and install' }) as HTMLButtonElement).disabled).toBe(false)
  })

  it('keeps the start screen entry after dismissing the notification and reuses the update dialog', async () => {
    const api = setup(false)
    api.status.mockResolvedValue({ phase: 'available', version: '1.2.0' })
    api.check.mockResolvedValue({ phase: 'available', version: '1.2.0' })
    render(<><UpdateNotification /><UpdateButton /></>)
    fireEvent.click(await screen.findByRole('button', { name: 'Later' }))
    expect(screen.queryByRole('complementary')).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'A new version is available' }))
    await screen.findByRole('dialog', { name: 'A new version is available' })
    expect(screen.getByRole('button', { name: 'Download and install' })).toBeTruthy()
    expect(api.download).not.toHaveBeenCalled()
  })

  it.each(['idle', 'checking', 'current', 'disabled', 'error'])('keeps the dev check icon visible in the %s state', async phase => {
    vi.stubEnv('DEV', true)
    const api = setup()
    api.status.mockResolvedValue({ phase })
    render(<UpdateButton />)
    await waitFor(() => expect(api.status).toHaveBeenCalled())
    const button = screen.getByRole('button', { name: 'Check for Updates…' })
    expect(button.textContent).toBe('')
    expect(button.querySelector('svg')).toBeTruthy()
    expect(api.check).not.toHaveBeenCalled()
    expect(api.download).not.toHaveBeenCalled()
    expect(screen.queryByRole('button', { name: 'A new version is available' })).toBeNull()
  })

  it.each(['idle', 'checking', 'current', 'disabled', 'error'])('hides the release check icon without a known update in the %s state', async phase => {
    vi.stubEnv('DEV', false)
    const api = setup()
    api.status.mockResolvedValue({ phase })
    render(<UpdateButton />)
    await waitFor(() => expect(api.status).toHaveBeenCalled())
    expect(screen.queryByRole('button')).toBeNull()
  })

  it('shows the release icon when a new version is available', async () => {
    vi.stubEnv('DEV', false)
    const api = setup(false)
    api.status.mockResolvedValue({ phase: 'available', version: '1.2.0' })
    render(<UpdateButton />)
    const button = await screen.findByRole('button', { name: 'A new version is available' })
    expect(button.textContent).toBe('')
    expect(button.querySelector('svg')).toBeTruthy()
    expect(api.check).not.toHaveBeenCalled()
    expect(api.download).not.toHaveBeenCalled()
  })

  it('keeps a manual notification download mounted through progress and failure', async () => {
    const api = setup(false)
    api.status.mockResolvedValue({ phase: 'available', version: '1.2.0' })
    let fail!: (result: string) => void
    api.download.mockImplementation(() => new Promise(resolve => { fail = resolve }))
    render(<UpdateNotification />)
    fireEvent.click(await screen.findByRole('button', { name: 'Download and install' }))
    api.status.mockResolvedValue({ phase: 'downloading', version: '1.2.0', percent: 25 })
    await screen.findByText('Downloading 1.2.0… 25%', {}, { timeout: 2000 })
    expect(screen.queryByRole('dialog')).toBeNull()
    api.status.mockResolvedValue({ phase: 'error', version: '1.2.0' })
    fail('download-failed')
    await screen.findByRole('alert')
    expect(screen.getByRole('complementary')).toBeTruthy()
    await screen.findByRole('button', { name: 'Download and install' }, { timeout: 2000 })
    expect(api.download).toHaveBeenCalledOnce()
  })
})
