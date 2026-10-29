import { defineConfig } from '@playwright/test'

/// `@matrix` marks the nightly-only tier — combinatorial cells and low-churn
/// specialty targets excluded from the per-PR run (what earns the tag, and what
/// must not: e2e/README.md §Tiers). `WEFTCUT_E2E_FULL=1` puts them back;
/// electron-ci sets it on its scheduled sweep, and `npm run e2e -- --full` is
/// the local equivalent.
///
/// This is a project-level grepInvert rather than a CLI `--grep-invert` so the
/// command line stays free for a developer to filter with, and so it composes
/// with the serial/parallel split below instead of overwriting it.
const MATRIX_EXCLUDED = process.env.WEFTCUT_E2E_FULL ? [] : [/@matrix/]

/// How electron-ci splits one e2e run across runners: each leg OWNS the spec
/// files `WEFTCUT_E2E_ONLY` names, and `e2e/slices.mjs` packs every file onto
/// exactly one leg per OS from the measured cost in `e2e/timings.json`. Unset,
/// the whole suite runs — a local `npm run e2e`, or CI's single `all` slice.
///
/// Deliberately not Playwright's `--shard`: it splits whole files by COUNT, in
/// path order, blind to cost. This suite's files range from seconds to four
/// minutes, and the once-per-OS extras (the serial project, packaging) ride
/// particular legs; the pack has to see both, so it is computed here from the
/// measurements, not left to a count.
///
/// LANDMINE — globs, never Playwright's positional file filter. That filter is a
/// REGEX over the path, so `audio.spec.ts` also selects
/// `export-range-audio.spec.ts` and the two legs silently run it twice. A
/// `**/name` glob matches the one file it names.
const globs = (names: string | undefined) =>
  (names ?? '')
    .split(',')
    .filter(Boolean)
    .map((name) => `**/${name}`)
const OWNED = globs(process.env.WEFTCUT_E2E_ONLY)

export default defineConfig({
  testDir: 'e2e/electron',
  testMatch: OWNED.length ? OWNED : undefined,
  timeout: 60_000,
  retries: process.env.CI ? 1 : 0,
  /// Stop a broadly broken leg early. Counted in failed ATTEMPTS, retries
  /// included, so with `retries: 1` this is five tests failing twice — a broken
  /// build, not a flake. Without it the two export regressions of 2026-10-24/26
  /// ran every remaining spec and every retry on macOS: 77 and 84 minutes to
  /// report what the first ten failures already said. The matrix's own
  /// `fail-fast: false` is the other half — the other legs still finish and
  /// report, only the broken one stops. Local runs keep going so a developer
  /// sees the whole picture.
  maxFailures: process.env.CI ? 10 : 0,
  /// A JSON report rides alongside the console reporter: `stats` carries the invocation's
  /// wall clock, every test result its own `duration`, `workerIndex`, and
  /// `startTime`. Nothing else here does — CI's default `dot` prints no
  /// per-test time at all, and Playwright's built-in slow-test warning cannot
  /// fire on a single test, its 5-minute default threshold sitting well above
  /// the 60 s `timeout` above.
  ///
  /// The path must stay OUT of `outputDir` (test-results/): Playwright clears
  /// that at the start of every run, and an unscoped `npm run e2e` invokes
  /// Playwright twice (serial, then parallel) — the serial report would not
  /// survive. For the same reason scripts/run-e2e.mjs gives each invocation its
  /// own file via `PLAYWRIGHT_JSON_OUTPUT_FILE`, which outranks this value;
  /// what is written here is what a bare `npx playwright test` produces.
  /// The live reporter flushes test starts/results separately, preserving the
  /// last started test even if cancellation prevents the final JSON report.
  reporter: [[process.env.CI ? 'dot' : 'list'], ['json', { outputFile: 'e2e-report/e2e.json' }], ['./e2e/live-reporter.mjs']],
  /// Generate any missing fixture media before workers boot (see
  /// e2e/global-setup.ts). Idempotent — a warm checkout is a fast no-op.
  globalSetup: './e2e/global-setup.ts',
  /// Project split: `serial` holds the specs that must own the machine
  /// (GPU/HW-lane, perf-measurement, determinism capture — tagged `@serial`
  /// in the test title). `scripts/run-e2e.mjs` runs this project to completion
  /// before starting `parallel`; Playwright otherwise schedules independent
  /// projects concurrently even when one declares `workers: 1`.
  /// Fresh throwaway userData per launchApp() (auto-removed on app.close()) is
  /// what makes the parallel project safe.
  projects: [
    { name: 'serial', grep: /@serial/, grepInvert: MATRIX_EXCLUDED, workers: 1 },
    {
      name: 'parallel',
      grepInvert: [/@serial/, ...MATRIX_EXCLUDED],
      // CI runners fit one export pipeline. The 7 GiB macOS GPU runner also
      // exhausts host memory with two Electron apps, causing resource-busy
      // export failures and shutdown timeouts. Keep CI serial within each leg;
      // the workflow already distributes files across independent runners.
      workers: process.env.CI ? 1 : '50%',
    },
  ],
})
