# Local stickers

Montage stickers render in the engine's final composition and frame preview. No frontend,
ASR, host-plan conversion, or core clip exporter changes are required here.

## API

Both routes require the engine session token (`Authorization: Bearer <token>`; the existing
`t` query-token mechanism also applies).

* `GET /v1/stickers` returns `{items:[{id,name,path,width,height,animated,format}]}`.
  Three original transparent geometric PNGs are packaged: Spark, Heart, Arrow.
* `POST /v1/stickers:inspect` accepts `{path}` and returns
  `{path,width,height,animated,format}`. `path` is the resolved absolute local path;
  `format` is `PNG`, `WEBP`, or `GIF`. Invalid assets return HTTP 400 with an explanation.
  Inspection probes dimensions and actually decodes frames using local FFprobe.

Only local PNG, static WebP, and GIF are supported. URLs, URI schemes, UNC/network paths,
other image formats, and animated WebP are rejected. Extension alone does not establish
format. Missing, unreadable, corrupt, empty, and oversized assets fail explicitly. Rendering
validates all assets before starting segment export, including inactive stickers.

Limits per source: 16 MiB compressed, 4096 pixels per dimension, 16,777,216 pixels per frame,
600 frames, and 128,000,000 total decoded pixels. Inspection stops after the first frame
past the applicable frame/pixel limit; each probe has a 20-second timeout and a 128 MiB
single-allocation cap. FFmpeg/FFprobe file access uses a local `file,pipe` protocol whitelist.
An ordinary mounted filesystem path is still a local path from the engine's perspective.

## Geometry and timing

`StickerItem` uses normalized canvas coordinates: `x,y` specify the center; `width,height`
specify a bounding box. Images preserve aspect ratio and fit **inside** this box. Rotation
is clockwise in degrees around that center, after fitting, with a transparent expanded
bounding box. Source alpha is multiplied by `opacity`. Off-canvas pixels are clipped.

Stickers are drawn after card backgrounds, ASS captions/text and the brand logo. Ascending
`layer` wins in sequence; equal layers preserve timeline list order. The maximum is 32.
Neither sticker starts nor ends extend montage duration.

Visibility is half-open: `start_ms <= t < end_ms`. GIF animation starts at sticker start,
uses decoded GIF frame delays resampled to the montage FPS, and repeats while active,
regardless of the GIF's embedded loop count. Preview consumes the same GIF clock and
selects the frame at or before the requested relative sticker time on that FPS grid.
Transparent GIF disposal/compositing is handled by FFmpeg's decoder.

Animations share the same implementation in export and preview:

* `none`: fixed geometry and opacity.
* `fade`: alpha ramps in/out over 200 ms each, shortened to half the item duration for
  stickers shorter than 400 ms. Original transparency and item opacity remain effective.
* `pop`: grows from 65% to 100% over 180 ms, around the fixed center.

Paths are passed through FFmpeg `-i` arguments, never interpolated into filter expressions.
Only numeric contract fields enter the sticker filters. The filter allowlist adds `rotate`
and alpha `fade`; these are standard non-GPL FFmpeg filters.

## Freeze and captions

Segment freezes retain segment/timeline duration and let audio, ASS captions, and sticker
animations continue on the composition clock. The freeze branch uses frame-counted
`zoompan=z=1` repetition because the local FFmpeg's single-frame `trim` + `tpad` branch
emitted too few held frames. Final composition explicitly sets its output FPS so the last
encoded frame has the correct duration, including after concat/freeze.

## Assets and packaging

`engine/src/lahza_engine/stickers/assets/*.png` contains original programmatically drawn
shapes, with no third-party art. Reproduce them with:

```sh
engine/.venv/bin/python -m lahza_engine.stickers.generate_assets
```

`engine/pyproject.toml` adds `stickers/assets/*` to package data. No new Python runtime
dependency is needed. The tiny original transparent WebP test fixture was generated from
RGBA pixels with `cwebp -lossless`; tests do not require a WebP encoder.

## Verification

Run with the bundled runtime rather than a system FFmpeg lacking libass:

```sh
PATH="$PWD/build/local-runtime/bin:$PATH" \
LAHZA_BIN_DIR="$PWD/build/local-runtime/bin" \
engine/.venv/bin/python -m pytest engine/tests/test_stickers.py engine/tests/test_montage_render.py
```

Tests decode actual exported video and preview pixels: before/during/after visibility,
GIF frame changes and looping, source alpha times opacity, rotation, aspect fit, stable
layer order, fade/pop, authenticated API errors, actual local inspection, and a combined
GIF + freeze + ASS render with matching preview and video/audio timeline durations.
# Persistence in packaged builds

The API copies built-in images into the user's `Assets/stickers/<sha256>/` before
returning paths. Saved montages never reference PyInstaller's temporary extraction
directory, which disappears when the engine exits. Original bundled files remain
unchanged. Imported user files keep their selected local paths.

