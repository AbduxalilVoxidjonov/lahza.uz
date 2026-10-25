# Local editing skills

Settings → Editing skills installs local `.lahzaskill` ZIP packages or standalone
JSON manifests. These are Lahza editing recipes, unrelated to coding-agent skills.
They contain data only: no scripts, imports, expressions, shell commands, arbitrary
FFmpeg graphs, custom plugins, URLs, downloads or network permissions.

The two original bundled examples are **Caption and pause** (`caption-freeze`) and
**Gentle zoom** (`gentle-zoom`). Their JSON manifests ship as Python package data.
GET exposes their local paths; the example buttons use the normal installation API.

## Manifest

ZIP layout: root `skill.json`, plus optional `assets/` PNG, static WebP or GIF files.
Standalone `.json` uses the identical manifest but cannot refer to assets.

```json
{
  "schema": "lahza.skill/1",
  "id": "my-title-pause",
  "name": "My title and pause",
  "version": "1.0.0",
  "description": "Title over a short held frame; audio continues.",
  "permissions": ["timeline.modify"],
  "actions": [
    {"type": "caption", "text": "{title}", "duration_ms": 2000},
    {"type": "freeze", "duration_ms": 800}
  ]
}
```

All manifest, action and request objects reject unknown fields. IDs are lower-case
ASCII slugs matching `[a-z][a-z0-9-]{0,63}`. Version is three numeric components
(each 1–4 digits); schema must be exactly `lahza.skill/1`. Names: 1–100 characters;
descriptions: up to 1000. There must be 1–32 actions. Permissions default to
`["timeline.modify"]`; only `timeline.modify` and `assets.read` are allowed,
without duplicates. Stickers require both. Permissions describe fixed capabilities,
not executable grants.

| Action | Fields beyond `type` | Effect |
| --- | --- | --- |
| `caption` | `text` (default `{title}`, 1–500), `position` upper/middle/lower (middle), `animation` none/fade/pop/slide_up (fade) | Append TextItem overlay |
| `freeze` | duration 100–5000 ms (800 default) | Append built-in freeze FX; audio and total duration unchanged |
| `motion` | `preset`: push-in/punch-in/pan/shake/zoom-out (push-in default) | Append registry motion FX with its validated default parameters |
| `color` | required `preset`: warm/cool/bw/vivid/film | Replace montage-wide color preset |
| `sticker` | required `asset`: `assets/name.png`, `.webp`, `.gif`; x/y, width/height, rotation, opacity, layer, animation | Append StickerItem from installed local asset |

All timed actions accept `at_ms` (default 0, 0–600000) and `duration_ms` (default
1000 except freeze, 100–600000). Color has neither. Times are output milliseconds
relative to the selected video's start, plus the apply request's `start_ms`.
Actions are ordered, append rather than replace overlays/FX, and are not idempotent:
applying twice adds two sets of edits. Only color replaces its corresponding field.

Caption substitution supports only the literal `{title}` token. No evaluation or
format-string processing occurs. Other braces and backslashes are rejected in
caption templates and request titles, preventing ASS markup injection. Request
title defaults to empty; a resulting blank caption or one exceeding 500 characters
rejects the entire apply. This is an overlay, not automatic transcription.

Sticker coordinates are normalized, center based: x/y 0–1 (0.5); width/height
0.02–2 (0.25); rotation -180–180 (0); opacity 0–1 (1); layer 0–1000 (0);
animation none/fade/pop (none). Relative asset names accept ASCII letters, digits,
underscores, hyphens, dots and `/`; empty, `.` and `..` segments are rejected.
No absolute paths, URLs, backslashes or path placeholders are accepted.

## HTTP contract

Every route requires the existing engine session authentication.

- `GET /v1/skills` → `{items: Skill[], builtins: (Skill & {path: string})[]}`.
  Installed items include full actions, metadata and permissions for inspection.
- `POST /v1/skills:install` with `{path: string, replace?: boolean}` → installed
  Skill. Path explicitly selects a local `.lahzaskill` or `.json`; no URL fetch.
  Existing IDs return 409 unless `replace: true`. Validation failure preserves
  the prior installed version. Examples use their GET-provided `path` here.
- `POST /v1/skills/{id}:apply` with `{montage_id, title?, video_id?, start_ms?,
  expected_timeline?}` → `{ok: true, timeline, user_edited: true}`. `video_id`
  defaults to the first video; `start_ms` defaults to zero relative to that video.
  `expected_timeline` optionally supplies SHA-256 of the DB's exact stored
  `timeline_json` string; stale hashes return 409. This low-level optional guard
  requires access to that exact serialization; the Settings UI does not send it.
- `DELETE /v1/skills/{id}` → `{ok: true}`. Missing installation returns 404.

Apply requires status `ready`, a saved timeline and a video. Unknown video, offset
outside the selected video, actions starting outside it, or a freeze with under
100 ms remaining fail with 400. Durations clip to the video end. Existing video
transitions determine absolute overlay start times. The whole transformed timeline
is revalidated by MontageTimeline, including the existing 32-sticker limit, before
one SQLite update persists the result and marks the montage user edited. A failure
leaves the stored timeline unchanged. Read/transform/write share the existing State
DB lock and transaction; installation/removal/application also share an engine-local
skill lock. Multiple simultaneous engine processes sharing data are unsupported.

**Save pending editor drafts before applying.** The Settings panel explicitly shows
this notice. The endpoint operates on the current saved timeline only; it never
reads or discards an editor draft. Settings targets the first video at zero; advanced
targeting is API-only. Existing caches are invalidated after successful apply.

## Storage and safety limits

Installations live only under `data_dir/Skills/<id>`. Extraction stages privately
under that root, validates everything, then renames into place. Explicit replacement
uses a temporary backup and restores it if publication fails. The engine lock
prevents readers seeing partial replacements. A process/OS crash during the
replacement's two renames can leave a hidden `.replaced-*` backup requiring manual
recovery; no cross-process or crash-consistent filesystem transaction is claimed.

Limits: compressed input 32 MiB, expanded total 32 MiB, 128 ZIP entries, 16 MiB per
asset, manifest 64 KiB. ZIP paths, duplicate members, duplicate JSON keys, encrypted
members, symlinks, special files and executable bits are rejected. Only `skill.json`
and allowed raster assets are extracted. Invalid schema, permissions, fields,
placeholders and actions fail closed. Images use the existing bounded sticker
inspection/decoder (dimensions/frame/decoded-pixel limits), not arbitrary file or
code execution. Engine-owned media tools may decode these assets; recipe content
never supplies a program, command, plugin implementation or network input.

Applied stickers are copied by content hash into the montage's `skill-assets/`
directory. They survive recipe replacement and uninstall. Uninstall only removes
the selected installed skill directory, does not reverse timeline edits, and leaves
montage asset cleanup to the existing montage lifecycle. A failed application may
leave an unused retained asset file, but no partial timeline. Local storage must
be trusted against concurrent filesystem tampering outside the engine.

No undo/history API, arbitrary parameters, asset downloads, external plugin hosting,
parameter forms beyond title, batch targeting, transcription or arbitrary code are
provided in this first version. Caption rendering requires the existing libass
runtime. Motion/color/freeze use the existing registry and render pipeline unchanged.

## Verification

```sh
source build/local-runtime/activate.sh
engine/.venv/bin/pytest engine/tests/test_editing_skills.py
engine/.venv/bin/ruff check engine/src/lahza_engine/editing_skills engine/src/lahza_engine/api/routes_skills.py engine/tests/test_editing_skills.py
cd app
npm run build
```

Tests cover install/list/replace/apply/remove, strict manifests and ZIP safety,
size limits, authorization, all action families, preserved assets, failed-apply
atomicity and an actual caption+freeze export/preview through the existing renderer.
