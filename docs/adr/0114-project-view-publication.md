# 0114 — One versioned project view publication protocol

Status: Accepted

## Context

The actor already provides one write authority. Its renderer consumers did not
have an equivalent publication authority: change events, mutation callbacks and
crop commands could fetch and apply independent full summaries. A response
ordering guard prevented stale publication but still allowed redundant work.
Command success also did not imply that selection and subsequent UI actions
could read the edited state.

## Decision

The main-process actor host owns a monotonic `{ session, revision }` identity.
Session changes when a workspace is replaced, reopened, saved under a new
location or closed; project UUID and history cursor cannot serve this purpose.
Actor broadcasts advance revision, including undo, unrecorded preferences, MCP
edits and native job writebacks. Lifecycle transitions publish only their settled
project and directory. Failed transitions preserve the previous view unless an
actual actor/workspace replacement has already occurred.

`project_publication` returns an atomic `{ version, summary }` full projection.
Only an actually closed workspace has a null summary. Renderer change events
carry the same version. The new preload `invokePublished` returns the original
command value plus a publication receipt; raw IPC and MCP contracts are unchanged.
An async command's receipt may cover concurrent commits completed before it
returns. It identifies a sufficient view, not exclusive ownership of a commit.

`ProjectPublicationClient` owns version comparison, one in-flight read, the newest
desired version, stale reply suppression, bounded stale-response retries and
waiters. Both events and receipts enter this module. Only this owner applies
backend projections to the renderer project store. Replacing or stopping an
owner prevents its outstanding reads from publishing.

Ordinary editor code uses the existing command functions:

```ts
const layerId = await addColorLayer(options);
// The mounted project store now includes this edit (or a newer same-session view).
// Selection and follow-up actions can read it immediately.
```

The IPC bridge unwraps the original value after the receipt is applied. Panels
must not call `apply(await projectSummary())`. Legacy `onMutated` callbacks can
call `settleProjectStore()`; when caught up this performs no read. A deliberate
`refreshProjectStore()` rechecks external file availability, which can change at
the same actor revision. Projection reads bypass command barriers to avoid a
read waiting on itself. Startup Open/New can return before App's owner mounts;
the initial publication seed owns readiness in that case.

Failures preserve the last good view. `CommandPublicationError.accepted === true`
distinguishes an accepted mutation whose view synchronization failed from a
rejected command. Recovery retries the projection read, never the mutation.
Waiters for a replaced session reject rather than continuing selection work in
another workspace.

## Consequences

Command completion means accepted and applied to the mounted renderer store.
It does not mean painted, saved, or flushed to durable storage. Autosave and
explicit save retain their separate contracts.

This is a full-snapshot protocol; transport, projection and index work are still
proportional to project size. Versioning establishes a seam for future deltas
without exposing scheduling to panels. Snapshot memoization must account for
filesystem-derived availability rather than assuming revision alone is a cache
key. Tests exercise the protocol's public behavior and actual Electron IPC,
including delayed replies, close/reopen, duplicate refresh suppression and
post-command store reads.
