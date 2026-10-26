import assert from 'node:assert/strict'
import test from 'node:test'

import { extrasFromJobs, fileCostsFromReport, foldReports, parseArtifactName } from './e2e-timings-snapshot.mjs'

const report = (file, tests) => ({
  suites: [
    {
      file,
      specs: tests.map(([title, status, durations]) => ({
        title,
        tests: [{ status, results: durations.map((duration) => ({ duration })) }],
      })),
    },
  ],
  stats: { duration: 1234 },
})

test('a spec file costs the sum of every result, retries included', () => {
  const { costs, unexpected } = fileCostsFromReport({
    suites: [
      {
        file: 'a.spec.ts',
        specs: [{ title: 't1', tests: [{ status: 'flaky', results: [{ duration: 1000 }, { duration: 500 }] }] }],
        suites: [{ specs: [{ title: 't2', tests: [{ status: 'expected', results: [{ duration: 250 }] }] }] }],
      },
    ],
  })
  assert.equal(costs.get('a.spec.ts'), 1750)
  assert.equal(unexpected, 0)
})

test('artifact names resolve to an OS and a part, and nothing else does', () => {
  assert.deepEqual(parseArtifactName('e2e-timings-macos-latest-e2e-3'), { os: 'macos-latest', part: 'e2e-3' })
  assert.equal(parseArtifactName('test-results-macos-latest-e2e-3'), null)
  assert.equal(parseArtifactName('e2e-timings-freebsd-latest-e2e-3'), null)
})

test('folding records a serial-only spec at zero and refuses a stopped leg', () => {
  const specs = ['a.spec.ts', 'serial-only.spec.ts']
  const dirs = {}
  for (const os of ['windows-latest', 'ubuntu-latest', 'macos-latest']) {
    dirs[`e2e-timings-${os}-e2e-1`] = { parallel: report('a.spec.ts', [['t', 'expected', [60_400]]]), serial: { stats: { duration: 300_000 } } }
    dirs[`e2e-timings-${os}-e2e-2`] = { parallel: report('a.spec.ts', [['u', 'expected', [1_000]]]) }
  }
  const folded = foldReports(dirs, specs)
  assert.deepEqual(folded.parallel['a.spec.ts'], { 'windows-latest': 61, 'ubuntu-latest': 61, 'macos-latest': 61 })
  assert.deepEqual(folded.parallel['serial-only.spec.ts'], { 'windows-latest': 0, 'ubuntu-latest': 0, 'macos-latest': 0 })
  assert.deepEqual(folded.serial, { 'windows-latest': 300, 'ubuntu-latest': 300, 'macos-latest': 300 })

  const green = dirs['e2e-timings-ubuntu-latest-e2e-2']
  dirs['e2e-timings-ubuntu-latest-e2e-2'] = { parallel: report('a.spec.ts', [['u', 'unexpected', [1_000, 1_000]]]) }
  assert.throws(() => foldReports(dirs, specs), /not a measurement/)
  dirs['e2e-timings-ubuntu-latest-e2e-2'] = green
  delete dirs['e2e-timings-macos-latest-e2e-1']
  delete dirs['e2e-timings-macos-latest-e2e-2']
  assert.throws(() => foldReports(dirs, specs), /needs all three OSes/)
})

test('an extra is the wall clock of its step on the one leg that ran it', () => {
  const step = (name, seconds) => ({
    name,
    conclusion: 'success',
    started_at: '2026-10-26T08:00:00Z',
    completed_at: new Date(Date.parse('2026-10-26T08:00:00Z') + seconds * 1000).toISOString(),
  })
  const jobs = []
  for (const os of ['windows-latest', 'ubuntu-latest', 'macos-latest']) {
    jobs.push({ name: `e2e (${os}, e2e-1)`, steps: [step('Generate software-lane family fixtures (e2e)', 30), step('Package (unsigned)', 0)] })
    jobs.push({ name: `e2e (${os}, e2e-2)`, steps: [step('Generate software-lane family fixtures (e2e)', 0), step('Package (unsigned)', 120)] })
  }
  jobs.push({ name: 'checks', steps: [step('Package (unsigned)', 999)] })
  const extras = extrasFromJobs(jobs)
  assert.deepEqual(extras.package, { 'windows-latest': 120, 'ubuntu-latest': 120, 'macos-latest': 120 })
  assert.deepEqual(extras.decodeBench, { 'windows-latest': 30, 'ubuntu-latest': 30, 'macos-latest': 30 })
  jobs.push({ name: 'e2e (macos-latest, e2e-3)', steps: [step('Package (unsigned)', 5)] })
  assert.throws(() => extrasFromJobs(jobs), /ran on two legs/)
})
