import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'

import {
  CARRIERS,
  LEGS,
  OS_SLICES,
  DEFAULT_SECONDS,
  SKIP_ON,
  osLabelFor,
  pack,
  readSnapshot,
  sliceEnv,
  sliceNames,
  slicesFor,
  snapshotDrift,
  specFiles,
  specFilesFor,
} from '../e2e/slices.mjs'
import { EXTRA_STEPS } from './e2e-timings-snapshot.mjs'

/// electron-ci splits one e2e run across runners by giving each leg an explicit
/// set of spec files, packed by e2e/slices.mjs from the measured cost in
/// e2e/timings.json. The split is only correct if every spec lands on exactly
/// one leg of every OS — and the way it breaks is silent: a spec on no leg runs
/// NOWHERE, on no runner, reported as green by all of them; a spec on two legs
/// runs twice and pays for it. Nothing else can catch the first.
///
/// Everything below is asserted PER OS, because the pack is per OS: macOS runs
/// fewer legs, each owning more files, and costs differ per OS, so the
/// assignment differs too.
///
/// The pack is a pure function of the directory listing and the snapshot, so
/// the one-leg property holds by construction; what is asserted here is that
/// construction, the pack's balance (the reason the split exists), and the
/// facts the workflow still owns and no module can hold — the parts and the
/// (os, part) exclusions it declares, which invocation the restriction reaches,
/// and which leg each once-per-OS extra is gated to.

const HERE = path.dirname(fileURLToPath(import.meta.url))
const DESKTOP = path.resolve(HERE, '..')
const WORKFLOW = path.resolve(DESKTOP, '..', '..', '.github', 'workflows', 'electron-ci.yml')
const PLAYWRIGHT_CONFIG = path.resolve(DESKTOP, 'playwright.config.ts')

const yml = readFileSync(WORKFLOW, 'utf8')

const OSES = Object.keys(LEGS)
const FLAGS = Object.keys(CARRIERS)

const names = (list) =>
  list
    .split(',')
    .map((n) => n.trim())
    .filter(Boolean)

/** The `if:` condition of a named workflow step, as its raw line. */
const stepIf = (step) => {
  const lines = yml.split('\n')
  const at = lines.findIndex((line) => line.trim() === `- name: ${step}`)
  assert.notEqual(at, -1, `no workflow step is named "${step}"`)
  const next = lines.findIndex((line, i) => i > at && /^\s*- (name|uses):/.test(line))
  const condition = lines
    .slice(at + 1, next === -1 ? undefined : next)
    .find((line) => /^\s*if:/.test(line))
  assert.ok(condition, `the "${step}" step has no if: condition, so every slice runs it`)
  return condition
}

// ── the pack ───────────────────────────────────────────────────────────────

test('every spec file an OS runs is owned by exactly one of its legs', () => {
  assert.ok(specFiles().length > 0, 'no spec files found — the split would run nothing')
  for (const os of OSES) {
    const specs = specFilesFor(os)
    const legs = slicesFor(os)
    assert.equal(legs.length, LEGS[os], `${os} packs ${legs.length} legs, LEGS says ${LEGS[os]}`)
    const own = legs.flatMap((leg) => leg.own)
    const counts = new Map()
    for (const n of own) counts.set(n, (counts.get(n) ?? 0) + 1)
    const twice = [...counts].filter(([, c]) => c > 1).map(([n]) => n)
    assert.deepEqual(twice, [], `these spec files are owned by two legs of ${os}, so they run twice`)
    assert.deepEqual([...own].sort(), specs, `on ${os} the legs together do not cover the suite exactly`)
    for (const leg of legs)
      assert.ok(leg.own.length > 0, `${os} ${leg.name} owns no spec: an empty restriction runs the whole suite`)
  }
})

test('every OS runs exactly one carrier of each once-per-OS extra, the fixed one', () => {
  // Single-occupancy per OS, each for its own reason: the determinism artifact
  // name is unsliced, so a second uploader is a hard conflict; packaging twice
  // per OS is waste; and the decode-bench media is 1.8 GB that only the serial
  // project's reader needs, so it rides the serial carrier. ZERO carriers is the
  // quiet half of the same failure — an OS that runs none of them never
  // packages, never captures determinism PNGs, and self-skips the software-lane
  // family gates, all while reporting green. That is why the carriers are legs
  // EVERY OS runs: within the smallest LEGS count.
  const fewest = Math.min(...Object.values(LEGS))
  for (const flag of FLAGS)
    assert.ok(
      sliceNames().slice(0, fewest).includes(CARRIERS[flag]),
      `the \`${flag}\` carrier ${CARRIERS[flag]} must be a leg every OS runs (the first ${fewest})`,
    )
  assert.equal(CARRIERS.decodeBench, CARRIERS.serial, 'the decode-bench media is read only by a @serial spec')
  for (const os of OSES) {
    for (const flag of FLAGS) {
      const found = slicesFor(os).filter((leg) => leg[flag])
      assert.deepEqual(
        found.map((leg) => leg.name),
        [CARRIERS[flag]],
        `${os} must run exactly the one leg carrying \`${flag}\``,
      )
    }
  }
})

test('a leg restricts to its own files', () => {
  // An empty ONLY makes `testMatch` undefined — the whole suite, on that leg.
  for (const os of OSES) {
    for (const leg of slicesFor(os)) {
      const env = sliceEnv(leg.name, os)
      assert.deepEqual(names(env.WEFTCUT_E2E_ONLY), leg.own)
      assert.deepEqual(Object.keys(env), ['WEFTCUT_E2E_ONLY'], 'the pack speaks through one variable')
    }
  }
})

test('the pack is deterministic', () => {
  // Every leg of a commit packs on its own runner; they agree only because the
  // pack is a pure function of the listing and the snapshot.
  for (const os of OSES) assert.deepEqual(pack(os), pack(os))
})

// ── balance: the reason the split exists ──────────────────────────────────

/// How far the heaviest leg may exceed the lightest, by the snapshot's own
/// numbers. The packing lands within a few percent of even; what this catches
/// is DRIFT — specs that grew or arrived since the snapshot — so the fix when it
/// fires is `npm run e2e:timings -- <green run id>`, not a hand-edit.
const BALANCE = 1.5

test('every OS packs within balance by the snapshot', () => {
  for (const os of OSES) {
    const seconds = slicesFor(os).map((leg) => leg.seconds)
    const [min, max] = [Math.min(...seconds), Math.max(...seconds)]
    assert.ok(
      max <= min * BALANCE,
      `${os}: the heaviest leg (${(max / 60).toFixed(1)} min) exceeds ${BALANCE}× the lightest (${(min / 60).toFixed(1)} min) — refresh e2e/timings.json from a green run`,
    )
  }
})

test('the snapshot has not drifted far from the directory', () => {
  // An unmeasured spec packs at the default cost, a stale entry is ignored —
  // neither breaks the split, but past a handful the pack is no longer the
  // measured one. The refresh is one command.
  const { unmeasured, stale } = snapshotDrift()
  const LIMIT = 10
  assert.ok(
    unmeasured.length + stale.length <= LIMIT,
    `${unmeasured.length} unmeasured spec(s) and ${stale.length} stale entr(ies) — run \`npm run e2e:timings -- <green run id>\`: ${[...unmeasured, ...stale].join(', ')}`,
  )
})

test('the snapshot costs every spec and every extra on every OS', () => {
  const snapshot = readSnapshot()
  for (const [file, byOs] of Object.entries(snapshot.seconds.parallel))
    for (const os of OSES) {
      const v = byOs[os]
      // A spec the OS skips may be unmeasured there (slices.mjs packs it at the
      // default cost if the skip is ever lifted); everything else is a number.
      if (v === undefined && SKIP_ON[os]?.includes(file)) continue
      assert.ok(Number.isInteger(v) && v >= 0, `${file} on ${os}: ${v}`)
    }
  for (const extra of FLAGS)
    for (const os of OSES) {
      const v = snapshot.seconds[extra]?.[os]
      assert.ok(Number.isInteger(v) && v > 0, `extra \`${extra}\` on ${os}: ${v}`)
    }
  assert.ok(DEFAULT_SECONDS > 0)
})

// ── SKIP_ON: what an OS deliberately does not run ──────────────────────────

const SPEC_DIR = path.join(DESKTOP, 'e2e', 'electron')
const PRESSURE = [
  'export-resource-admission.spec.ts',
  'export-finalization-retry.spec.ts',
  'resource-recovery.spec.ts',
  'resource-single-slot.spec.ts',
]
/** Source with comments removed, so a prose mention of `@serial` does not count. */
const code = (file) =>
  readFileSync(path.join(SPEC_DIR, file), 'utf8')
    .replace(/\/\*[\s\S]*?\*\//g, '')
    .replace(/\/\/.*$/gm, '')

test('a skipped spec exists, is listed once, has no @serial test, and is not a pressure suite', () => {
  const onDisk = new Set(specFiles())
  for (const [os, skipped] of Object.entries(SKIP_ON)) {
    assert.ok(LEGS[os], `SKIP_ON names ${os}, which is not an OS the matrix runs`)
    assert.deepEqual([...new Set(skipped)].length, skipped.length, `${os}: a spec is listed twice`)
    for (const file of skipped) {
      assert.ok(onDisk.has(file), `${os} skips ${file}, which does not exist — a rename left it behind`)
      assert.ok(
        !/@serial/.test(code(file)),
        `${os} skips ${file}, but it has a @serial test: the serial project runs the whole suite regardless, so listing it misdescribes what the OS runs`,
      )
      assert.ok(!PRESSURE.includes(file), `${os} skips ${file}: the pressure suites' platform coverage is a separate, open decision`)
    }
    assert.ok(skipped.length < onDisk.size / 2 + 20, `${os} skips most of the suite — that is a different design, not a skip list`)
  }
  // Every OS still runs the suite's platform surface: the serial carrier's
  // determinism capture, window chrome, and the smoke test.
  for (const os of OSES)
    for (const kept of ['smoke.spec.ts', 'window-chrome.spec.ts', 'determinism.spec.ts'])
      assert.ok(specFilesFor(os).includes(kept), `${os} must run ${kept}`)
})

test('an OS without a skip list runs every spec', () => {
  const full = OSES.filter((os) => !SKIP_ON[os])
  assert.ok(full.length >= 2, 'at least two OSes must run the whole suite, so a skipped spec still runs twice')
  for (const os of full) assert.deepEqual(specFilesFor(os), specFiles())
})

test('an unmeasured spec still lands on exactly one leg', () => {
  for (const os of OSES) {
    const files = [...specFilesFor(os), 'zz-brand-new.spec.ts']
    const own = pack(os, { files }).flatMap((leg) => leg.own)
    assert.equal(own.filter((f) => f === 'zz-brand-new.spec.ts').length, 1, os)
  }
})

// ── the workflow's half ────────────────────────────────────────────────────

test('every runner platform resolves to an OS the table knows', () => {
  // scripts/run-e2e.mjs's `--slice=<name>` derives the OS from process.platform,
  // so a local replay restricts exactly as the leg it reproduces.
  for (const platform of ['win32', 'linux', 'darwin'])
    assert.ok(OS_SLICES[osLabelFor(platform)], `${platform} maps outside the table`)
  assert.throws(() => osLabelFor('freebsd'), /no e2e slice set for platform/)
  assert.throws(() => sliceEnv(sliceNames()[0]), /unknown OS/)
})

test('an unknown slice name is loud rather than an empty restriction', () => {
  // The failure mode this guards: a typo in the `part:` matrix resolving to no
  // restriction, under which that runner silently repeats the entire suite.
  assert.throws(() => sliceEnv('e2e-0', OSES[0]), /unknown e2e slice/)
  assert.throws(() => sliceEnv('rest', OSES[0]), /unknown e2e slice/)
})

test('a slice its OS does not run is loud rather than a silent skip', () => {
  // Both halves of the (os, part) space that the matrix must not produce. An
  // unknown OS label would pack for the wrong OS; a part the named OS does not
  // run is one the matrix should have excluded, and letting the leg quietly do
  // nothing is how a whole OS loses coverage.
  assert.throws(() => sliceEnv(sliceNames()[0], 'freebsd-latest'), /unknown OS/)
  const skipped = OSES.flatMap((os) =>
    sliceNames()
      .filter((name) => !OS_SLICES[os].includes(name))
      .map((name) => [os, name]),
  )
  assert.ok(skipped.length > 0, 'no OS runs a subset of the table — this guard is untested')
  for (const [os, name] of skipped)
    assert.throws(() => sliceEnv(name, os), /is not one .* runs/, `${os} / ${name}`)
})

test('the slice restriction reaches the parallel project and nothing else', () => {
  // The serial project is NOT sliced — it greps @serial across the whole suite
  // and captures the determinism PNGs. Set anywhere the serial run inherits it,
  // the restriction narrows that project to the leg's files too; most @serial
  // tests live elsewhere, so Playwright kills the whole leg with "No tests
  // found" before a single spec runs.
  const applied = yml.split('\n').filter((l) => /WEFTCUT_E2E_ONLY=/.test(l))
  assert.ok(applied.length > 0, 'nothing applies a slice restriction — the split is not in effect')
  for (const line of applied)
    assert.match(
      line,
      /--project=parallel/,
      `a slice restriction must be set on the parallel invocation itself, never where the serial run inherits it: ${line.trim()}`,
    )
  assert.ok(!/WEFTCUT_E2E_IGNORE/.test(yml), 'the catch-all variable is gone; every leg is an explicit set')
})

test('the E2E step passes both matrix dimensions to the pack', () => {
  // The pack is per OS. Pass the part alone and there is nothing to pack for.
  const invocation = yml.split('\n').find((line) => line.includes('slices.mjs --shell'))
  assert.ok(invocation, 'no leg reads the pack — the split is not in effect')
  const passed = [...invocation.matchAll(/"\$(\w+)"/g)].map(([, name]) => name)
  assert.equal(passed.length, 2, `--shell needs the part AND the OS: ${invocation.trim()}`)
  for (const variable of passed)
    assert.match(
      yml,
      new RegExp(`^\\s+${variable}: \\$\\{\\{ matrix\\.\\w+ \\}\\}$`, 'm'),
      `$${variable} reaches the pack but comes from somewhere other than the matrix`,
    )
})

test('the matrix declares the pack’s parts, and excludes exactly what no OS runs', () => {
  const m = yml.match(/part:\s*\$\{\{[^}]*?'(\["[^\]]+\])'\s*\)\s*\}\}/)
  assert.ok(m, 'no part: matrix dimension found')
  // `all` is the scoped-dispatch slice: handled by its own branch, not the pack.
  const declared = JSON.parse(m[1]).filter((part) => part !== 'all')
  assert.deepEqual(declared, sliceNames(), 'the matrix and LEGS disagree')
  const excluded = [...yml.matchAll(/-\s*os:\s*(\S+)\s*\n\s*part:\s*(\S+)/g)].map(
    ([, os, part]) => `${os} ${part}`,
  )
  const unrun = OSES.flatMap((os) =>
    declared.filter((part) => !OS_SLICES[os].includes(part)).map((part) => `${os} ${part}`),
  )
  assert.deepEqual(
    [...excluded].sort(),
    [...unrun].sort(),
    'the matrix `exclude:` and LEGS disagree: an unexcluded leg reddens on a slice its OS does not run, and an excluded slice still counted for that OS packs files onto a leg that never runs',
  )
})

test('the steps that ride one leg name the carrier their flag fixes', () => {
  // The coupling no module can hold: a workflow `if:` cannot call into the
  // pack, which is why CARRIERS is fixed rather than packed.
  const gated = [
    ['Upload determinism artifacts', 'serial'],
    [EXTRA_STEPS.package, 'package'],
    ['Upload installer', 'package'],
    [EXTRA_STEPS.decodeBench, 'decodeBench'],
  ]
  for (const [step, flag] of gated) {
    const condition = stepIf(step)
    for (const name of sliceNames())
      assert.equal(
        condition.includes(`'${name}'`),
        name === CARRIERS[flag],
        `the "${step}" step must name '${CARRIERS[flag]}' — the \`${flag}\` carrier — and no other: ${condition.trim()}`,
      )
  }
  // The serial PROJECT's own branch, inside the E2E step's script: the same
  // leg as the determinism upload above, or the PNGs are captured on a leg
  // that never uploads them.
  const serial = yml.split('\n').find((line) => line.includes('--project=serial'))
  assert.ok(serial, 'no leg runs the serial project')
  assert.match(
    serial,
    new RegExp(`"\\$PART" = "${CARRIERS.serial}"`),
    `the serial project must run on the \`serial\` carrier: ${serial.trim()}`,
  )
})

test('the snapshot script measures the extras by the steps the workflow actually has', () => {
  // e2e-timings-snapshot.mjs reads each extra's cost from a step's wall clock
  // by name; a renamed step would silently drop that extra from the pack.
  for (const step of Object.values(EXTRA_STEPS))
    assert.ok(yml.includes(`- name: ${step}`), `no workflow step is named "${step}"`)
})

test('the parallel project runs one test at a time where the pack assumes it', () => {
  // The pack treats summed test time as leg wall clock (slices.mjs
  // §specSeconds). That held on every measured leg, but it is only guaranteed
  // where the config says one worker; macOS declares two and measured no
  // overlap anyway. If that line changes, re-measure before trusting the pack.
  const config = readFileSync(PLAYWRIGHT_CONFIG, 'utf8')
  assert.match(config, /workers: process\.env\.CI \? \(process\.platform === 'darwin' \? 2 : 1\) : '50%'/)
})
