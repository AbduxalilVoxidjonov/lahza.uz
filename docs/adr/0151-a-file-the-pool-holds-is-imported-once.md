---
status: accepted
---

# A file the pool holds is imported once

Date: 2026-10-28

## Context

Every import copies its source into the project's `Media/` folder. The copy
never asked whether the pool already held the file: importing
`<project>/Media/take.mp4` again added a second pool item and wrote
`Media/<prefix>-take.mp4` beside the first, and importing the same outside
file twice did the same. Nothing at the UI or MCP surface said so.

The project folder is becoming an agent's working directory. There an agent
turns a file the user mentions into an `import_media` call, so repeated
imports of files already in the project become the normal path, not a slip.

## Decision

- **The pool is checked in the turn that inserts.** After the probe and
  before the insert, `import_media` looks for a pool item whose file is the
  source. Two paths name one file when a stat gives them the same volume and
  file number, so the volume decides which spellings are one file: NTFS holds
  an NFC and an NFD `café.mp4` side by side, and no folding of the path could
  know that. A file system that reports no file number is compared by real
  path, as spelled. Joining an import in flight also requires the probe's byte
  size and modification time to match its stored fingerprint. A settled item
  is matched by content instead: an overwrite can keep the same file number,
  size and second-resolution modification time. Changed bytes are a new item
  with fresh metadata and derivatives, without rewriting the old item's layer
  references. A match ends the import with nothing written and answers the held
  item's id. The check runs in the same synchronous turn as the
  insert, so two imports of one file racing through their probes still land
  one row; the later one waits for the earlier to settle and shares its
  result, so it never answers a row whose failed hash read rolls it back. The
  import diagnostic ends as `already_in_pool`, not as a failure.
- **A source already under `Media/` is recorded in place.** It is where the
  copy would put it, so its pool item gets its `Media/`-relative `path_rel`
  and no copy is queued. Subfolders of `Media/` count.
- **Anything else is copied into `Media/`, inside the project folder or not.**
  Every pooled file of a project lives under `Media/`, so one place lists the
  project's media and `path_rel` has one shape.
- **The same bytes are matched by their hash, before the insert.** The copy
  into `Media/` gives its item the copy's path, so the outside file it came
  from no longer matches by path. When a pool item with a real hash has the
  source's byte size, the source is hashed before the insert (including a
  repeated import of the same path), and the item
  holding those bytes answers. The import reuses that hash, so a file of a
  new size is read no more than before. An item whose hash is still pending
  cannot be matched: two imports of the same bytes racing from two paths land
  two rows, and the MCP record names the other in `same_content_as`.
- **Found bytes relink an item whose file is gone.** When the item holding
  the bytes has lost its own file (its `Media/` copy deleted, its drive
  offline), the import points that item at the source, copies it into
  `Media/` as any import's source is, and regenerates its derivatives. The
  item keeps its id and its layers play again. After awaiting derivative enqueue,
  the import checks its project generation before queuing the copy, including
  when the same project has been closed and reopened.
- **The MCP record says what happened.** An answer for an item the pool held
  before the call carries `existing: true`. The UI and MCP share the import
  arm, so both get the check; only MCP reports these fields.

## Consequences

An agent can call `import_media` for any file it is shown and get the id the
app already uses for it, which is how a mentioned file is tied to the pool.
Bytes the pool holds under any path answer the item that holds them, so a
deliberate second copy of a file is not a second item. A source whose size
matches a pooled item appears on the timeline only after it is hashed. Removing a pool item still never
deletes its file, so a file recorded in place is as safe as a copy.

## Implementation ownership

`mediaImport.ensureImported` owns path matching, content checks, in-flight
coordination, session validation and import completion. It reports added,
reused or relinked explicitly; its outcome also preserves whether the pool held
the item at call entry and which other items hold the same content. MCP shapes
that outcome into the existing record, adding `relinked: true` for a relink;
renderer IPC keeps returning the media id. Neither goes through `runHybrid`:
both hosts call the importer directly and shape its typed outcome. A result does not promise that background derivatives or copying finished.
The session is checked again after copy enqueue returns, before reporting
completion or returning an outcome to either caller.

The host builds one `MediaImporter` per actor, and it owns the in-flight
registry; an agent's call passes its actor as `by` rather than a dispatch
adapter. Joining another import performs no writes under the joining caller. Media resource reads remain independent and read-only.
