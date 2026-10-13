# Post-drag performance diagnostics

These opt-in probes establish a measurement loop for stalls after releasing a
marker or clip. They are retained for repeatable local diagnosis; disabled by
default, bounded, and independent of commit/history/saving policy.

## Automated Electron / CDP capture

Build with `npm run build:e2e`, then run from the repository root:

```powershell
node apps/desktop/e2e/scripts/profile-marker-drag.mjs `
  --project 'C:\path\to\project' `
  --user-data "$env:APPDATA\WeftCut" `
  --work-dir 'tmp/marker-drag-diagnostics' `
  --label baseline --samples 6 --cpu-profile --chrome-trace
```

For the current development renderer, add `--renderer-url http://localhost:1420`
with `npm run dev` running. Compare the same build mode, window layout, project,
zoom, playback state, cache warmth and profiler options. CPU profiling adds
overhead; repeat without `--cpu-profile`/`--chrome-trace` for interaction latency.
Do not run other test workloads concurrently with performance measurements.

The script copies the project, media/cache and Motif library into the work
directory on the first run. Later runs reuse that copy. It uses a separate
Electron user profile and actual pointer gestures on one marker. Linked Motif
authoring directories and external media can still be read from their original
locations; all editor mutations and autosaves target the copy. Keep the window
visible and do not interact with it during capture. Cache copies can be large.

After a 12-second warmup it alternates 40-pixel drags with a 2.8-second interval,
writes `<label>.timings.json` and `<label>.summary.json`, and optionally writes
renderer/main `.cpuprofile` files and a Chromium `.chrome-trace.json`. Load those
in DevTools Performance / a compatible trace viewer. Logs unrelated to timings
(including MCP connection credentials) are not copied into the report. Profiles
can contain local source paths: keep the work directory out of version control.

The gate requires one accepted edit and complete visible-window measurement per
gesture, checks autosaved marker positions against the live summary **without
forcing a save**, requires refresh below 100 ms (configurable with
`--max-refresh-ms`), and requires autosave timer lateness below 100 ms. Missing
edits, hidden windows or missing phases invalidate the run rather than passing
with empty results. A failure still leaves diagnostic artifacts and closes only
the test-owned Electron process tree.

## Capture

Start the updated development app from PowerShell:

```powershell
$env:WEFTCUT_EDIT_TRACE = '1'
npm run dev
```

The variable is consumed when Vite starts/builds the renderer, not by an already
built executable. Alternatively, in the updated development app press F12 and
run `localStorage.setItem('weftcut.debug.editTrace', '1')`; this takes effect on
the next edit without reloading. Close DevTools before measuring.

Drag and release a marker or clip 3–5 times, leaving at least three seconds
between gestures. Include a visibly slow release and a smooth release. Keep the
window visible and use the same zoom and playback state for comparisons.

Filter the development terminal for `[DEBUG-edit-latency]`. Each JSON line has
a generated `traceId`; join lines with the same ID. Renderer lines are also in
DevTools, but main command/save lines are in the terminal. All lines use the
existing bounded diagnostic log and are included in Help's diagnostic export
(`current/events.jsonl`, possibly `events.previous.jsonl`). Allow three seconds
after the last gesture before exporting. No project contents, marker text,
paths or entity IDs are emitted by these probes.

Disable immediately with
`localStorage.setItem('weftcut.debug.editTrace', '0')`. To return to the default,
remove that storage key and `Remove-Item Env:WEFTCUT_EDIT_TRACE`, then restart
the dev command. No new observers are started while disabled; an already
started two-second observation finishes normally.

## Interpret

| Phase / stage | What it measures |
| --- | --- |
| `renderer.invoke.*` | From the edit's IPC invocation to response/rejection; begins just after pointer release, not at OS input arrival |
| `main.command.*` | Synchronous actor work, with `commandAccepted` for domain refusals |
| `recipe`, `reconcile_markers`, `reconcile_transitions` | Mutation and relationship maintenance |
| `produce_including_finalize` | Includes those three stages plus Immer finalization/freezing; **do not sum nested durations** |
| `locked_layer_check`, `stamp`, `validate`, `history_record`, `notify_subscribers` | Remaining commit costs |
| `main.summary` | Building the project summary requested by the correlated refresh |
| `renderer.refresh / summary_ipc` | Waiting for the summary, including IPC and main-process queuing |
| `renderer.refresh / store_apply` | Synchronous store/index/selection work; excludes subsequent React rendering |
| `store_apply_to_two_raf` | Two animation-frame opportunities after applying state; includes scheduling/render work but **does not prove pixels were presented** |
| `main.autosave / serialize`, `write_file`, `backup_and_gc` | Actual synchronous save costs, separately from debounce delay |
| `main.autosave / timerLateMs` | How late the 500ms debounce callback ran; event-loop contention evidence, not write duration |
| `renderer.frames` | Two-second window from edit invocation: maximum rAF gap, its offset, >50ms gaps, long-task count/duration, and visibility |

`startedAt` is a wall-clock timestamp for approximate cross-process alignment.
Durations and offsets use each process's monotonic clock; do not subtract raw
`performance.now()` values from different processes. A long task can start
before the probe in the same pointer handler: its full duration is retained if
it overlaps the window. Frame observations include any other work in that
window and are not proof that the traced edit caused every stall.

Large invoke/summary waits with short main stages call for inspecting IPC
queuing and other main-process work. Large store/next-frame times or long tasks
point to renderer work. Large save stages around 500ms after release point to
persistence. `hiddenDuringWindow: true` makes frame-gap comparisons unreliable.

No-op edits can have no refresh/save. Failed or superseded refreshes have
`applied: false`; a timeout has `frameOpportunityObserved: false`. Autosave
coalesces edits: only the **latest** edit's trace is attributed to that write;
an untraced later edit clears attribution. Missing save lines alone do not
prove that saving failed. Observations are bounded to four concurrent windows.

## Validation

Targeted unit tests cover trace scope cleanup, disabled behavior, exceptions,
command-to-event correlation, and debounce attribution with separately injected
serialization/write delays. The Electron `edit-latency.spec.ts` gate drives a
real drag through all phases with synthetic dense markers; its timings are a
control sample, not a reproduction of a particular media project's stall.

## 2026-10-13 diagnosis and fix

Warm project copy: 287 markers, 62 layers including 61 Motifs, same development
renderer and workspace layout. Four real drags per differential capture:

| Measurement | Before | After all fixes |
| --- | --- | --- |
| Refresh through two rAF opportunities, CPU profiling enabled | 280–301 ms | 68–72 ms |
| Largest rAF gap | 183–200 ms | about 50 ms |
| Autosave timer lateness beyond its 500 ms debounce | 1157–1181 ms | 0.1–6.1 ms |
| Actual serialize + file write | 1.7–2.2 ms | 1.5–1.7 ms |

A separate six-drag run without CPU profiling measured 61–72 ms refresh,
33–50 ms maximum rAF gaps, 1.4–1.9 ms saves, and 2.3–14.8 ms timer lateness.
Every final marker position matched the autosaved project. Development React
still recorded 53–64 ms long tasks; this is an improvement, not a claim of
perfect 60 fps or a production-build result.

The production-mode E2E build, using the same project/profile copy without CPU
sampling, measured 24–28 ms refresh, 16.8–16.9 ms maximum rAF gaps and no >50 ms
long tasks over four drags. Treat that as an additional result, not the baseline
for the development-mode before/after comparison.

The CPU profile attributed 5.72 seconds across four edits to
`MotifWorkspace.list`, including synchronous directory reads and content hashes.
`MotifFrameService.handleProjectChanged` unnecessarily requested that catalog on
every project edit. Catalog hydration now belongs to startup and actual Motif
change events; the preparation service subscribes to the hydrated catalog.
Removing that request alone fixed main-loop starvation but left renderer stalls.

Renderer fixes address distinct invalidations: App and preview now share the
project-store refresh publisher; unchanged IPC snapshot branches and indices
retain identity; the timeline subscribes to its resolved clock rather than the
whole project; unchanged Marker panel rows and lane glyphs skip rendering.
Finally, `useImportReadiness` keyed its sweep to every summary and called
`setSweepTick`, scheduling a second workspace render even for marker edits.
Its dependencies now follow media changes. Chromium tracing confirmed the
remaining long calls were React work, with short layout/style stages.

The 500 ms autosave debounce, undo history, backups, explicit save and shutdown
flush remain unchanged. Slowing saves further would not address either measured
bottleneck.
