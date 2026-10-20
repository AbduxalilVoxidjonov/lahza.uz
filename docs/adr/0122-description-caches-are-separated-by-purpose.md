---
status: accepted
---

# Description caches are separated by purpose

## Context

The clip content command and the individual-shot buttons shared one incremental
description cache. A whole-clip result covered every shot, so identifying a shot
could reuse broad clip prose without running the model. New shot prose could
also replace the clip's description. Renderer state and compute singleflight
keys carried the same ambiguity.

## Decision

Every description has a purpose, `clip` or `shot`, independent of prompt focus.
The renderer entry points state it explicitly. `describe_clip` defaults to
`clip` for existing callers and accepts `shot` for individual-shot requests.
Disk keys, compute job keys and renderer result maps all separate the purposes.
Model execution and the one-at-a-time renderer gate remain shared.

Purpose also travels in description job snapshots and events. The Shots Panel
selects only `shot` jobs for row progress, panel progress and cancellation;
missing purpose on an older record means `clip`. Phase-tooltip and error-state
interfaces require an explicit purpose. Clearing one purpose's error does not
clear the other's. Clip commands do not open the Shots Panel; their progress
and Cancel remain on timeline job bands and in the existing status surfaces.

`media://{id}/description` reads clip content. The separate
`media://{id}/shot-description` reads shot descriptions. Both use the same model,
sampling, focus and language settings as their writes and never run inference
on a cache miss. Shot rows and their undescribed count use only shot results;
clip content has its own section in the panel and remains the search index's
description source.

Old disk entries contain no reliable provenance. Neither purpose reads them:
the new cache-key namespace invalidates them without deleting files. A user
must explicitly generate each purpose once; subsequent requests reuse only
that purpose's covered ranges. Changing model settings or language clears both
renderer views and re-reads their respective disk entries.

## Consequences

Describing a whole clip no longer marks its shots as identified. The first use
of each purpose may require a separate model run. Prompt focus remains a user
setting rather than an implicit substitute for cache ownership.
