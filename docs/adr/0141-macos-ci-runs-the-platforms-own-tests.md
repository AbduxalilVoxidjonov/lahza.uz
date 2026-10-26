---
status: accepted
---

# macOS CI runs the platform's own tests

Date: 2026-10-26

## Context

electron-ci runs the e2e suite on Windows, Linux and macOS. GitHub's
account-wide cap of five concurrent macOS jobs — counted across every
repository of the billing entity — is the binding constraint on the whole
pipeline: the matrix's macOS legs plus `rust-test` filled it, so a second
push run, or any other repository's macOS job, queued behind the first.

With the split packed from measured cost (ADR 0140), macOS's four legs
each carried about 14 minutes, against 10 and 12 on Windows and Linux.
Classifying the 141 spec files showed where that time went: 84 of them
exercise renderer logic that behaves identically under Chromium on every
OS — dock and timeline editing, keyframes, text, the agent and MCP
surfaces, media-pool plumbing — and those 84 cost macOS 23 of its 46
minutes of parallel test time. Linux and Windows run every one of them.

## Decision

- **macOS runs the platform's own specs.** `SKIP_ON["macos-latest"]` in
  `e2e/slices.mjs` lists the specs macOS leaves to the other two OSes; the
  pack simply omits them from macOS's legs. It is a skip list, not an
  allow list: a new spec runs on macOS until someone decides it need not.
- **What macOS keeps** is what only macOS can show: window chrome and the
  traffic lights, the application menu, Keychain-backed storage,
  notifications and shell integration, window geometry and quit semantics,
  the VideoToolbox and Metal lanes, Motif capture on the GPU host, every
  `@serial` spec (the cross-OS determinism PNGs come from there), the
  per-OS ffmpeg build's codec and container matrix, and the export
  conformance gates that only a real GPU holds to the strict SSIM floor —
  Linux and Windows rasterize in software and run those gates at relaxed
  thresholds.
- **Kept although they would qualify:** `smoke` (a per-platform smoke test
  is the point of one), `caption-corpus` (the one end-to-end use of the
  Meta modifier), `timeline-selection-focus` (branches on Display P3), and
  `model-settings`, `popup-overflow`, `role-mixer-audition` (each records a
  failure first seen only on macOS).
- **Not decided here:** the four export-pressure suites
  (`export-resource-admission`, `export-finalization-retry`,
  `resource-recovery`, `resource-single-slot`) keep running on every OS;
  their platform coverage is a separate question. The test refuses to
  list them.
- **macOS runs three legs**, not four, at about 11 minutes each — under
  Linux's five — which returns one macOS slot to the account.

## Consequences

- A regression in platform-agnostic renderer logic is still caught, twice,
  on Linux and Windows; it is no longer caught a third time on macOS.
- The skipped specs never run on macOS in CI, the nightly `@matrix` sweep
  included; a scoped dispatch (`inputs.e2e_args`) is unsliced and runs
  whatever it names on whichever OS it picks.
- `scripts/e2e-split.test.mjs` asserts each listed spec exists, is listed
  once, has no `@serial` test, is not a pressure suite, and that at least
  two OSes run the whole suite. A spec that gains a `@serial` test must
  leave the list.
- Moving a spec between the buckets is one line and a reason.

## Validation

By the 2026-10-26 snapshot macOS packs 66 specs onto three legs of 11.2
minutes each (24.6 minutes of parallel tests, 7.1 of serial project, 1.4
of packaging, 0.5 of decode-bench media), against four legs of 13.7.

First CI runs after the change (40306227783 and 40308714737,
2026-10-26): green, with the e2e matrix done 16 minutes after its first
leg started; the three macOS legs ran 11 to 13 minutes, the Windows legs
9 to 13, the Linux legs 12 to 16 (one of them 22 with a slow apt mirror,
since bounded). The second run's one red was a Windows import flake,
green on rerun. The snapshot was then refreshed from the second run,
which is the first measured with the skip list in force.
