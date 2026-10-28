---
status: accepted
---

# Temporary cache space follows the Workspace's disk size

Date: 2026-10-28

## Context

ADR 0101 gave Settings one temporary cache space value. It defaulted to a fixed
2 GiB on every machine, while the memory target already scales with host RAM.
That 2 GiB is used twice: as the global disk-LRU target for filmstrips,
thumbnails, waveforms, audio-effect bakes and Motif frames across every
Workspace opened in the session, and as the admission limit for Motif frames
in the open Workspace.

Real projects do not fit. The lyric video's Motif cache measured 4.0 GB with
LZ4 and is still about 2.7 GB with zstd (ADR 0145), so its preparation pauses
under the default. Because the Motif directories in use are retained during a
sweep, a full budget evicts the cheap timeline derivatives instead, and they
are regenerated again and again. A single 10-minute stereo audio-effect bake is
about 230 MB. Everything this value covers can be rebuilt, so a larger default
can only cost disk space.

Other editors size this from the disk too. Premiere Pro's media cache limit and
After Effects' disk cache (from CS6) default to 10% of the cache volume's total
size; After Effects caps it at 100 GB. Both show the result as a plain GB value.

## Decision

- **`disk_cache_mib: null` means automatic, and it is the default.** The
  automatic value is 10% of the total size of the disk holding the open
  Workspace, rounded down to 256 MiB and kept within 4–64 GiB. Before a
  Workspace opens, the disk holding the app profile stands in. An unknown size
  resolves to 4 GiB.
- **Total size, not free space.** Total size does not drift as the cache fills,
  so the budget never shrinks because of its own growth. Main re-measures only
  when a Workspace opens; if the result changes, it reconfigures the native
  authority and republishes settings so the UI shows the value in force.
- **Settings shows the value in force,** as it does for the memory target. An
  explicit value still wins, within the existing 256 MiB–1 TiB range.
  Restoring defaults returns to automatic.
- **Policy version 2.** Version 1 wrote its 2048 MiB default into every saved
  policy, so a version-1 value of exactly 2048 is read as automatic. Other
  version-1 values are kept. From version 2, an explicit 2048 stays explicit.

## Consequences

- A 256 GB disk gets about 23 GiB, a 512 GB disk about 47 GiB, and 1 TB or
  larger the 64 GiB cap; disks under 40 GiB get 4 GiB. That fits the measured
  Motif projects, the timeline derivatives and several effect bakes together.
- A nearly full disk does not shrink the target. Writes that hit a full disk
  already pause preparation (`ENOSPC`); the value is a cache target, not a
  guarantee of free space.
- A user who deliberately chose 2 GiB under version 1 is moved to automatic
  once. Setting the value again keeps it.
