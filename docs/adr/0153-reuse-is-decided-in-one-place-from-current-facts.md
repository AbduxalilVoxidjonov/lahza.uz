---
status: accepted
---

# Reuse is decided in one place, from current facts

Date: 2026-10-29

## Context

An audit of the changes since v0.5.4 found three defects of one kind. Each
answered a request with something that already existed — a pooled item, a
running probe, a running job — without that thing answering the request:

- **Import.** A pooled file overwritten outside the app, then its backup
  imported: the backup's hash matched the hash the item recorded at import,
  the item's file was still there, so the item was answered, playing the
  other bytes. The import decision had been patched six times since ADR
  0151, each patch adding one branch for one way a recorded fact goes stale
  (another spelling, a copy's new path, a vanished file, a rolled-back row,
  a closed project). Each branch chose for itself how much checking was
  enough; the last one checked only that the file existed.
- **Hardware probe.** A VideoToolbox probe asked for while another ran was
  refused as `probe-busy`, and the caller turned the refusal into software
  decoding. Coalescing probes of one format class hid the case for one format;
  an H.264 and an HEVC source opened together still got hardware and software.
- **Clip jobs.** The singleflight key named the answer-changing args in a hand
  list. `describe_clip` gained `refresh` and the list did not, so a refresh
  joined a plain run already going and was never performed.

## Decision

Joining, reusing or caching is a claim that an existing thing answers this
request. Every such claim is made in one place that names everything it
depends on.

- **One decision, re-asked after every await.** An import's match is
  `importSource.nextImportStep`, a pure function of the pool and the facts
  read so far. The importer reads what it asks for, then asks again over the
  pool as it is then, so the final decision runs in the turn of its write.
- **A recorded fact is verified before it is answered.** A pool item's hash
  says what its file held at import. An item is reused only if its own file
  holds those bytes now: the source itself, just read, or its file read
  again. Size, modification time and file number are not enough (ADR 0151).
  An item recording the bytes that no longer holds them is relinked to the
  source (ADR 0151).
- **Contention is not an answer.** A resource that runs one at a time queues
  later callers instead of refusing them. The decode probe process runs one
  probe after another; a caller waits for the previous caller's answer, not
  its child's exit, so a host the OS cannot reap holds no one up.
- **Every input is classified, by a test.** `clipJob.ARG_ROLES` gives each arg
  a clip-compute call may carry a role: `answer` and `fresh` are in the key,
  `span` is read through the source. A test holds the roles to the MCP catalog
  snapshot, so an unclassified arg fails CI before it can join a job.
- **Contracts are tested as properties.** A decision with this many inputs is
  tested against a model of its world, not only against the cases found so
  far: `mediaImport.model.test.ts` drives imports, overwrites, deletions and
  queued workspace copies over a model file system and checks that every
  answered item's own file holds the source's bytes, and that no item's
  settled hash ever changes.

## Pool files changed outside the app

A live reproduction showed what a stale hash costs. A source renamed over
right after `import_media` returned, while its copy waited in the queue, was
copied as it then stood; the write-back adopted the copy's hash, so the item
silently changed bytes, and a thumbnail job that ran late cached the new
picture under the old hash.

- **`Media/` is the app's own, and a file there is never rewritten.** Every
  import copies its source into `Media/` (ADR 0151), so after the copy the
  only file an item reads is one the app wrote. A source outside the project
  is read only until its copy lands. An agent working in the project folder
  already changes its files only through tools (ADR 0152).
- **A copy is the item's file only if it holds the recorded bytes.** The
  workspace-copy write-back compares the copy's hash with the item's; a copy
  of other bytes is deleted and the item keeps its source path.
- **One stat screens every pool file** (`sourceFiles.ts`). Missing: as before.
  A different size: `changed`. A different mtime alone, as a project folder
  copied without its times has: the bytes are read once, in the background
  and one file at a time; a match records the new mtime, a mismatch is
  `changed`. No field is added to `project.json`; the item's `file_size` and
  `file_mtime` are the screen. The summary rebuilds on every publication and
  when the window regains focus.
- **`changed` is unavailable, like missing.** The summary carries
  `available: false, changed: true`; the pool shows a Changed badge that says
  how to restore it. Nothing is deleted. Importing the original again relinks
  the item by its bytes (ADR 0151); importing the new file makes a new item.
  Deliberately swapping the media behind placed clips is a separate command
  (issue #88).
- **Every reader of a source's bytes checks first.** MCP tools that read a
  source (clip compute, `analyze_audio`, `compare_frames`) refuse a changed or
  missing one. The open-time derivative re-fan-out and import recovery leave
  such an item out and enqueue its current record. Each native derivative
  job that reads the source (`jobs::run_derivative`) stats it first, reads its
  bytes when the stat differs from the record, and stats it again after
  generating; a source that changed meanwhile has its derivative deleted and
  nothing committed.

The residual risk is accepted: a file replaced by one of the same size within
the same second of modification time passes the stat. Only a tool that
deliberately keeps times can do that, and importing such a file still reads
its bytes.

## Consequences

Importing the same bytes as a pooled item now reads that item's file too,
unless it is the same file: a second read of a file of the same size, only
when the hashes already match. A hardware probe queued behind another can
wait for that one's deadline before it starts. A refresh runs as its own job
beside a plain run of the same window; ADR 0147's per-file lock keeps their
writes apart.

New reuse points follow the same rules: write down what makes a reused
answer valid, check it in one function, and test that function's contract.
