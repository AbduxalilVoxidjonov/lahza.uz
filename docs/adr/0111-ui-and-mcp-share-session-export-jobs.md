# 0111 — UI and MCP share application-session export jobs

Status: Accepted

## Context

PR [#50](https://github.com/WeftCut/WeftCut/pull/50) proposed asynchronous MCP
export using the renderer. Since its base, export gained resource reservations,
retryable finalization and time remapping. Porting its old pipeline would remove
those behaviors. Its review also required a no-overwrite rename fallback and
preflight on portable filesystems such as exFAT.

## Decision

`ExportJobs` in main owns admission, request idempotency, application-session
records and the project edit gate. UI and MCP submit to this authority; both
control the same task. One task, including one awaiting finalization retry, is
admitted at a time. Actor writes, history changes, project replacement and Motif
authoring reject while admitted. Derivative cache writebacks remain allowed.

The renderer adapter subscribes before announcing readiness for a workspace
generation. Main can admit a preparing job while the editor initializes, with a
bounded readiness wait. `exportRunner` contains the existing media preparation,
resource admission and renderer pipeline. The existing resource authority owns
all permits and finalization reservations.

Native code probes the destination directory before rendering, allocates one
same-directory staging file, and publishes only a complete file. No-overwrite
publication uses a hard link, falling back to the platform's atomic no-replace
rename. There is no copy fallback. UI replacement requires explicit consent and
atomically replaces the old file only after completion. MCP defaults to numbered
names or can require a strict name; neither policy overwrites.

Completed encoding is immutable. Mux or publication failure retains it and its
reservation as `awaiting_retry`. Retrying a publication failure reuses the muxed
file; retrying a mux failure consumes the encoded streams. A new basename must
stay in the same directory and retain the extension. Changing a UI filename
removes earlier overwrite consent.

Cancellation is latched through gaps between native stages. Native children,
mixing tasks and renderer work drain before admission is released. Cancellation
of export preparation does not cancel unrelated shared proxy/conform/bake work.
Publication is the commit point: if it wins a cancellation race, the job reports
completion and the actual destination. Confirmed application exit cancels or
discards, drains the job, and only then closes the editor and resource services.

MCP disconnect does not cancel export. A repeated `request_id` with the same
explicit arguments returns the same job before defaults or busy state are read;
different arguments conflict. Records survive reconnects, but not app restart.
MCP settings are per-job overrides, not saved defaults. MCP never prompts or
automatically falls back from native encoding to WebCodecs. Existing native
hardware-to-software candidate selection remains part of the native engine.

## Consequences

Five tools expose options, start, status, retry and cancel. Wire settings use
snake_case; one mapping feeds the shared settings validator. The ExportPanel
shows the same progress, actual settings and result for either entry point.
Agents must poll and report the completed `output_path`, rather than assuming
that their candidate filename was used.

Editing is frozen while export is active or awaiting retry. This intentionally
avoids editable snapshot exports, queuing, restart recovery and multiple export
workers in this change.

Inspired by PR #50 and its contributor theo_russell.
