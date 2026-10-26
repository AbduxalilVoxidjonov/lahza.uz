---
status: accepted
---

# The e2e split is packed from measured cost

Date: 2026-10-26

## Context

electron-ci runs the Playwright suite as several legs per OS, because the
GPU-less legs cannot use a second worker. Until now the split was a
hand-kept table in `e2e/slices.mjs`: four slices named after the heavy
export files they owned, and one catch-all that took everything else. The
table was measured when the catch-all held about ten minutes of specs.

It rotted the way the README predicted. The named files shrank to two to
eight minutes each as the `@matrix` tier and the prebuilt analyzer took
their cost away, while the catch-all absorbed every new spec — the
export-pressure suites among them — and grew to 32 minutes on Windows and
38 on Linux. Every run's wall clock was that one leg; the other four legs
sat idle for most of it. The timing artifacts that could have shown this
were published on every run and read by nobody, because reading them was
a manual recipe.

The practice elsewhere is to split by historical timing data and let the
tool read it: CircleCI's `--split-by=timings`, Depot's test splitting,
Knapsack Pro. Playwright's own `--shard` was considered and rejected: it
splits whole files by count in path order, blind to cost and to the three
once-per-OS extras (the serial project, the decode-bench media, packaging)
that have to ride particular legs.

## Decision

- **Legs are positional, per OS.** `e2e-1` … `e2e-N`, with `LEGS` in
  `slices.mjs` giving the count per OS (five on Windows and Linux, four on
  macOS, set by the account's 20-job and 5-macOS concurrency caps). The
  workflow's `part:` matrix declares the maximum and `exclude:` drops the
  rest.
- **The pack is computed, not written.** Every spec file on disk is costed
  from a committed snapshot, `e2e/timings.json` — summed test time per OS
  from a green run — and placed heaviest-first onto the lightest leg
  (longest-processing-time). Every leg of a commit packs the same listing
  against the same snapshot, so the result is identical on every runner.
- **Carriers are fixed.** `CARRIERS` pins the serial project and the
  decode-bench media to `e2e-1` and packaging to `e2e-2`, so the
  workflow's `if:` conditions can name them. Their measured wall clock is
  counted toward the leg before any spec is placed.
- **An unmeasured spec packs at a default cost.** It still lands on exactly
  one leg; its real cost enters at the next refresh.
- **Refresh is one command.** `npm run e2e:timings -- <green run id>`
  (`scripts/e2e-timings-snapshot.mjs`) folds the `e2e-timings-<os>-<part>`
  artifacts and the carrier steps' timings into the snapshot, and refuses
  a red run or one missing an OS.
- **The invariants are tested.** `scripts/e2e-split.test.mjs` asserts every
  spec on exactly one leg of every OS, the carriers where the workflow
  expects them, matrix and `LEGS` in agreement, balance (heaviest leg at
  most 1.5× the lightest by the snapshot) and bounded drift (at most ten
  specs unmeasured or stale). When balance or drift fires, the fix is the
  refresh command.
- **`WEFTCUT_E2E_IGNORE` is removed.** Every leg is an explicit
  `WEFTCUT_E2E_ONLY` set; there is no catch-all.

## Consequences

- Adding, removing or renaming a spec needs no edit anywhere in the split.
- A snapshot refresh is the only maintenance, and the test says when it is
  due; nothing about the pack is described in prose that can go stale.
- The leg count is the floor. With the pack balanced a leg costs its OS's
  total over `LEGS[os]`, so a shorter run means fewer specs, cheaper
  specs, or legs bought back from the concurrency budget.
- A snapshot measured on one commit is approximate for another, so legs
  will not be exactly even; coverage is unaffected, since the pack covers
  every spec exactly once regardless of the costs it assumes.
- The pack treats summed test time as wall clock. That matched every
  measured leg, including macOS with `workers: 2`, where no two tests
  overlapped (run 40287526652: 38.0 min of tests in a 38.7 min leg). A
  test pins the workers line in `playwright.config.ts` as a reminder to
  re-measure if it changes. Why two macOS workers never overlap is open.

## Validation

`scripts/e2e-split.test.mjs`, `scripts/run-e2e.test.mjs` and
`scripts/e2e-timings-snapshot.test.mjs` under `npm run test:scripts`.

By the 2026-10-26 snapshot (run 40287526652) every leg is 10.1 min on
Windows, 12.2 on Linux and 13.7 on macOS, against 34, 38 and 40 for the
old catch-all leg; suite totals are 42.8 / 53.0 / 45.7 min of parallel
test time, 5.1 / 4.7 / 7.1 min of serial project, 2.0 / 2.9 / 1.4 min of
packaging.

First CI run after the change (40302096925, 2026-10-26): green, 25 minutes
end to end against 65 (42 of them jobs) for the run before it. Legs ran 7 to
18 minutes; the parallel project's summed test time matched its wall clock
on every single-worker leg, and Windows matched the snapshot within a
minute. Linux ran one leg 4.5 minutes over its prediction (runner
variance, seen before the change too), and one Linux leg lost 12 minutes
to a slow apt mirror, which is not the split's. One macOS leg of UI specs
did run its two workers concurrently (9.8 min of tests in 5.0), so the
no-overlap observation holds for the export-heavy legs, not universally;
the pack still treats sums as wall clock, which over-estimates such a leg
and only costs balance, never coverage.
