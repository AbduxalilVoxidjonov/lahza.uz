import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useAutoInstallUpdatesOnQuit } from '../settings/appSettingsStore'
import { useUpdateStatus } from './updateStatus'
import { UpdateActions } from './UpdateActions'

// A non-modal notice: never steal focus from editing or an export dialog.
// Dismissal is session-local and never changes the installation preference.
export function UpdateNotification() {
  const { t } = useTranslation()
  const status = useUpdateStatus()
  const autoInstall = useAutoInstallUpdatesOnQuit()
  const [dismissed, setDismissed] = useState<string | undefined>()
  if (!status.version || dismissed === status.version || !['available', 'downloading', 'ready', 'restarting', 'error'].includes(status.phase)) return null
  return <aside className="update-notification" aria-label={t('updates.available')}>
    <div role="status">
      <strong>{t('updates.available')}</strong>
      {['available', 'downloading', 'error'].includes(status.phase)
        ? <p>{t(status.phase === 'available' ? 'updates.available_manual' : `updates.${status.phase}`, { version: status.version, percent: status.percent ?? 0 })}</p>
        : <><p>{t('updates.version', { version: status.version })}</p>
          <p>{t(autoInstall ? 'updates.ready_auto' : 'updates.ready_manual')}</p></>}
    </div>
    <UpdateActions status={status} onLater={() => setDismissed(status.version)} />
  </aside>
}
