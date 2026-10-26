---
status: accepted
---

# A capture timeout is probation, not a verdict

Date: 2026-10-26

## Context

The capture host latches a **lane** (`motifId` + `contentHash`) when the
Motif's own script fails: same content, same failure, so later requests
fast-reject until an edit changes the hash or the user retries explicitly.
This stopped the per-sprite retry storm against known-bad content.

A hung `__motifSetup` or `__motifRender` was classed the same way. The
deadline cannot tell an infinite loop in the Motif (content) from a host
wedged by load (transport): a heavy 1080p page normally renders in about a
second, and five seconds under contention is ordinary. One slow frame
therefore lost every frame of a user Motif for the session, with the baker
reporting a terminal error and preview sprites fast-rejecting forever.

The capture service compounded this on the shared-texture path. It falls
back to PNG for the session on any texture-path error it cannot classify as
content, superseded or capacity. A timeout on a latched lane was recognised
by identity; a timeout on a built-in (no hash, never latched) was not, and a
single slow built-in frame downgraded the whole Windows session to PNG.

## Decision

- **A timeout is typed.** `MotifCaptureTimeoutError` is the class every
  bounded CDP step throws, so classification is by type, not message text.
- **The host is rebuilt either way; the lane is not latched on the first
  timeout.** A timed-out lane is on probation: it gets exactly one more
  attempt on the rebuilt host. A second consecutive timeout is the verdict
  and latches the lane like a thrown exception. A success clears probation.
- **A timeout never switches the session to PNG.** The capture service keeps
  the shared-texture path and rethrows: a PNG retry fixes nothing a hung
  renderer caused, and the downgrade would cost every later frame its GPU
  path. The same holds for disk writes, capacity refusals, superseded
  requests and content failures, as before.

## Consequences

- A truly hung Motif costs at most two deadlines plus two host rebuilds
  before it is latched, instead of one. The retry storm stays closed.
- A healthy Motif survives a load spike: the baker's bounded retries and the
  preview's backoff now reach a real second attempt instead of a cached
  rejection.
- Explicit retry (`retryKeys`) lifts a timeout verdict exactly as it lifts a
  content latch.
- Other mid-render transport rejections (a detached debugger, a crashed
  renderer) still latch the lane immediately. Whether they should is open;
  they are rarer than a timeout and were not changed here.

## Validation

Unit tests drive the host fake through strike, retry, verdict and explicit
retry, and the service through a timeout that must not disable the texture
path. `e2e/electron/motif-capture-load.spec.ts` repeats the first on the real
host with the platform's default backend (a Motif that hangs on demand: 5.0 s
strike, a sub-second retry on the rebuilt host, two more strikes, a 1-2 ms
verdict, another lane still rendering), and with `WEFTCUT_E2E_LOAD=1` measures
load on the running machine.

- 2-core Linux, PNG host: retry 0.4 s. A 1080p authored page went from a
  1.5 s median idle to 2.1 s with both cores burned, 16/16 frames in both
  sweeps; a calibrated 3.5 s frame timed out under four burners per core and
  the same lane rendered in 4.8 s once the load lifted. Before this ADR that
  second request was a cached rejection for the rest of the session.
- 16-thread Windows 11 (i5-13400, RTX 3050), shared-texture host: retry
  0.19 s; the three timeouts cost three host rebuilds and every capture
  stayed on the texture path (6 texture, 0 PNG), so a hung renderer no longer
  downgrades the session. The authored page captured in 29 ms median idle and
  50 ms with all threads burned, 16/16 both; a 2.7 s frame reached 3.7 s under
  four burners per thread and never crossed the deadline, so the recovery
  branch did not trigger there. The spec says so instead of failing.
