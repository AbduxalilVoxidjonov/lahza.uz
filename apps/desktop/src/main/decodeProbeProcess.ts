import type { EventEmitter } from 'node:events'
import type { HwProbeVerdict } from './decode-capability'

export interface DecodeProbeRequest { path: string; lane: 'videotoolbox'; device: string | null }
export interface DecodeProbeChild extends EventEmitter {
  pid?: number
  postMessage(message: unknown): void
}
interface Dependencies {
  spawn(): DecodeProbeChild
  kill(child: DecodeProbeChild): void
  reserve(): () => void
  timeoutMs?: number
  reapMs?: number
}
const transient = (reason: string): HwProbeVerdict => ({ ok: false, reason, cacheable: false })

/** One disposable native probe at a time. The parent owns the deadline and
 * reservation: a result is usable only after clean exit; a kill request alone
 * never releases admission. A stuck OS process disables further probes for
 * this app session without holding up its callers or poisoning the disk cache.
 *
 * A probe asked for while another runs waits its turn: one probe running is
 * not an answer about another format, and a caller turns any answer but `ok`
 * into software decoding. Each waits for the previous caller's answer, not its
 * child's exit; an answer after a failure has already disabled probing, so a
 * child the OS cannot reap holds up no one. */
export function createDecodeProbeProcess(deps: Dependencies) {
  let unavailableReason: string | null = null
  let active: { stop(reason: string): void } | undefined
  // The answer the next probe waits for; null when none is pending, so an
  // idle probe starts in the caller's turn.
  let last: Promise<void> | null = null
  return {
    get unavailableReason() { return unavailableReason },
    stop() {
      unavailableReason = 'stopped'
      active?.stop('stopped')
    },
    probe(request: DecodeProbeRequest): Promise<HwProbeVerdict> {
      const answer = last ? last.then(() => probeOnce(request)) : probeOnce(request)
      const answered = answer.then(() => {}, () => {})
      last = answered
      void answered.then(() => { if (last === answered) last = null })
      return answer
    },
  }

  async function probeOnce(request: DecodeProbeRequest): Promise<HwProbeVerdict> {
    if (unavailableReason) return transient(unavailableReason)
    let release: () => void
    try { release = deps.reserve() } catch {
      // Import derivatives can occupy the only CPU slot on small machines.
      // Briefly wait for admission without bypassing the resource authority
      // or turning temporary contention into a sticky software selection.
      const admitted = await new Promise<(() => void) | undefined>(resolve => {
        let retry: ReturnType<typeof setTimeout>
        const finish = (reservation?: () => void) => {
          clearTimeout(retry)
          clearTimeout(deadline)
          active = undefined
          resolve(reservation)
        }
        const attempt = () => {
          try { finish(deps.reserve()) } catch { retry = setTimeout(attempt, 50) }
        }
        const deadline = setTimeout(() => finish(), 4_000)
        active = { stop: () => finish() }
        retry = setTimeout(attempt, 50)
      })
      if (!admitted) return transient(unavailableReason ?? 'resource-busy')
      release = admitted
      if (unavailableReason) { release(); return transient(unavailableReason) }
    }
    let child: DecodeProbeChild
    try { child = deps.spawn() } catch {
      release()
      unavailableReason = 'probe-start-failed'
      return transient(unavailableReason)
    }
    return new Promise(resolve => {
      let settled = false
      let exited = false
      let sent = false
      let verdict: HwProbeVerdict | undefined
      let failure: string | undefined
      let reapTimer: ReturnType<typeof setTimeout> | undefined
      const settle = (result: HwProbeVerdict) => {
        if (!settled) { settled = true; resolve(result) }
      }
      const stop = (reason: string) => {
        if (exited || failure) return
        failure = reason
        unavailableReason = reason
        clearTimeout(deadline)
        // Bound caller latency even if the OS cannot reap the child yet.
        // Keep both active and its reservation until the actual exit event.
        reapTimer = setTimeout(() => settle(transient(reason)), deps.reapMs ?? 1_000)
        try { deps.kill(child) } catch { /* exit remains the only proof of cleanup */ }
      }
      const deadline = setTimeout(() => stop('timeout'), deps.timeoutMs ?? 4_000)
      active = { stop }
      child.once('spawn', () => {
        // Startup itself may exceed the deadline before a PID is available.
        if (failure) { try { deps.kill(child) } catch { /* retain ownership */ } }
      })
      child.on('message', (message: unknown) => {
        if (exited || failure || !message || typeof message !== 'object') return
        const m = message as { type?: string; verdict?: HwProbeVerdict }
        if (m.type === 'ready' && !sent) {
          sent = true
          try { child.postMessage(request) } catch { stop('probe-ipc-failed') }
        } else if (m.type === 'result' && !verdict) {
          const v = m.verdict
          if (!v || typeof v.ok !== 'boolean' || !(v.reason === null || typeof v.reason === 'string')) {
            stop('probe-invalid-result')
            return
          }
          verdict = { ok: v.ok, reason: v.reason }
          try { child.postMessage({ type: 'ack' }) } catch { stop('probe-ipc-failed') }
        } else if (m.type === 'failed') stop('probe-failed')
      })
      child.on('error', () => stop('probe-error'))
      child.once('exit', (code: number) => {
        exited = true
        clearTimeout(deadline)
        clearTimeout(reapTimer)
        active = undefined
        release()
        if (failure) settle(transient(failure))
        else if (code === 0 && verdict) settle(verdict)
        else {
          unavailableReason = 'probe-exited'
          settle(transient(unavailableReason))
        }
      })
    })
  }
}
