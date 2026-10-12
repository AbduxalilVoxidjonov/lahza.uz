# 0112 — Position is the transform anchor for all visual clips

Status: Accepted

## Context

Media and Group Position described the unrotated top-left; Text Position
already described the anchor. Scaling from the inspector and dragging a resize
handle therefore had different behavior. A resize gesture needed position
compensation, adding position keys even when the user only intended to scale.

## Decision

Schema v4 makes Position the anchor's composition-space location for all clips
with a Transform. The renderer and gizmo use
`world = Position + R·S·(local − anchor·naturalSize)`. Scale writes only scale;
rotation writes only rotation. Moving the on-canvas anchor compensates Position
with `R·S·deltaPivot` to leave the picture stationary. Numeric anchor edits leave
Position fixed. Text box handles retain their existing layout resize behavior.

New media/Motifs keep their previous footprint by initializing Position to half
the source size. Plain Groups use half their referenced composition dimensions;
the ungroup eligibility checks use this same identity. Crop and proxy dimensions
do not redefine the anchor or Position. Text creation remains centered.

## Existing projects

The v3 → v4 import-free wire step offsets old media/Group positions by
`anchor × naturalSize × abs(scale)`. Text needs no conversion. Constant offsets
translate keys or Path nodes while preserving curve structure. Otherwise the
step bakes XY at existing composition frames and at the exact mapped instants
of all nested Group instances, including transition handle ranges. A log entry
identifies each baked clip and its sample count. Between samples and after
future timing changes the result can differ; the original file remains available.

Source dimensions must be available in media metadata, the exact Motif manifest
version or the referenced composition. The host may supply missing media sizes,
but never guesses from proxy dimensions. Refuse missing facts, unsupported clocks,
more than 4096 samples per curve or more than 2,000,000 composition instants.

ADR 0047's wire step import ban remains. The new dependency injection seam
supplies external source facts and the canonical **v3 numerical evaluation**
contract only. It may not supply current model defaults or perform serialization.
Any future evaluator semantic changes must preserve that versioned contract;
pre/post geometry tests cover spline/procedural curves, extrapolation, signed
scale, Path, crop and exact Group phases.

Before replacing the current workspace, opening verifies a byte-for-byte
`project.pre-vN.json` backup. Identical backups are reused; different backups
are retained with numbered siblings for the new input. Backup failure refuses
opening. This strengthens the earlier best-effort backup policy in ADR 0047.
The first normal save writes v4. Rollback uses the backup and an older compatible
build; newer-schema files remain rejected by older builds, with no downgrade.

## Validation

Frozen v1–v3 fixtures remain untouched; v4 has its own canonical fixture.
Migration tests compare old/new frame geometry, preservation of authored
constant-offset curves, nested retime samples, repeat-load behavior and atomic
failures. Gesture tests assert fixed Position during scale and compensated
Position during anchor dragging, including rotation, flips, crop and Path.
