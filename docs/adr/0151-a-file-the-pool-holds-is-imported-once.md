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
  source. Both paths go through realpath and are compared under the host's
  rules: case and Unicode normalization fold on Windows and macOS, not on
  Linux. A match ends the import with nothing written and answers the held
  item's id. The check runs in the same synchronous turn as the insert, so two
  imports of one file racing through their probes still land one row. The
  import diagnostic ends as `already_in_pool`, not as a failure.
- **A source already under `Media/` is recorded in place.** It is where the
  copy would put it, so its pool item gets its `Media/`-relative `path_rel`
  and no copy is queued. Subfolders of `Media/` count.
- **Anything else is copied into `Media/`, inside the project folder or not.**
  Every pooled file of a project lives under `Media/`, so one place lists the
  project's media and `path_rel` has one shape.
- **The same bytes under another path are reported, not merged.** The
  content hash is known only after the row is inserted, and merging then
  would roll back a row the user has already seen. The MCP record names the
  other items in `same_content_as`.
- **The MCP record says what happened.** An answer for an item the pool held
  before the call carries `existing: true`. The UI and MCP share the import
  arm, so both get the check; only MCP reports these fields.

## Consequences

An agent can call `import_media` for any file it is shown and get the id the
app already uses for it, which is how a mentioned file is tied to the pool.
Two items with the same bytes can still be made from two different paths,
and the user decides what to do with them. Removing a pool item still never
deletes its file, so a file recorded in place is as safe as a copy.
