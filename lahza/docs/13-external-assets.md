# External editing assets: first interoperability slice

Settings → External editing assets opens the system local-file picker in the desktop app. Browser development mode accepts an absolute engine-local path. Inspection is data-only: it does not install plugins, run code, extract archives, resolve external XML entities, or launch Adobe.

## Supported behavior

| Extension | Result | Apply/import status |
| --- | --- | --- |
| `.cube` | UTF-8 3D LUT, declared size 2–64, exactly size³ finite RGB triples; finite increasing DOMAIN_MIN/MAX | Apply as global montage color using the existing LUT renderer |
| `.srt` | UTF-8 numbered cues with exact start/end milliseconds and multiline text | Timed text report only; no word timing inference or timeline insertion |
| `.prfpset` | XML name/effect-name/match-name fields | Inspection only; no parameter or keyframe conversion |
| `.mogrt` | ZIP entry names and bounded `definition.json` / `manifest.json` text | Inspection only; requires compatible Adobe host, effects, fonts and media |
| `.ffx`, `.aep`, `.prproj`, `.aex`, `.plugin`, `.ccx`, `.zxp` | Extension recognition | Unsupported project translation/native execution |
| Other | Unknown format | Unsupported |

A similarly named Adobe effect is not evidence of identical rendering or parameter units. Consequently this slice has **no supported `.prfpset` effect mappings**. Names are informational, never silently translated. MOGRT metadata is untrusted text, never executable HTML or code. Adobe host fidelity and full native plugin compatibility are not provided.

## API and real LUT apply

`POST /v1/interop/inspect`, with the existing session Bearer token (or existing token query mechanism), accepts `{"path":"/absolute/local/file.cube"}`. Paths refer to the engine machine. There is no upload or filesystem scan. Invalid/missing/oversized files produce HTTP 400; missing/invalid authentication produces 401.

The response contains `path`, `format`, `can_apply`, `importability`, `unsupported_features`, and `normalized`. A valid cube includes:

```json
{
  "format": "cube",
  "can_apply": true,
  "importability": "timeline_color",
  "normalized": {
    "size": 2,
    "samples": 8,
    "fx": {
      "plugin": "uz.lahza.color.lut",
      "params": {"file": "/absolute/local/file.cube"},
      "source": "qolda"
    }
  }
}
```

The Settings action explicitly replaces the selected ready montage's global color. It reinspects the file, fetches `GET /v1/montages/{id}`, sets `timeline.color` to `normalized.fx`, and sends the complete timeline object directly to `PUT /v1/montages/{id}/timeline` (no wrapper). Success is displayed only after PUT succeeds. The existing renderer copies this local cube into its render work directory and emits `lut3d=file=...`. Existing per-item effects remain part of the fetched timeline.

The LUT remains a local file reference. Keep the file in place; no managed asset copy or immutable snapshot is created. External file changes after inspection can affect rendering. Avoid applying while another editor is saving the same montage: the existing PUT endpoint has no revision/ETag conflict mechanism. This slice does not change that endpoint.

## Bounds

Only absolute paths resolving to regular files are read; directories (including macOS `.plugin` bundles) return an explicit unsupported-directory error. Files are limited to 16 MiB and opened nonblocking with descriptor-based regular-file validation. Text must be UTF-8 (BOM accepted). Cube 1D/combined data and unknown directives are rejected. SRT has at most 10,000 cues, strict timestamps and positive cue durations; markup remains literal text, and overlapping cues are preserved.

XML DTD/entity declarations are forbidden. At most 20,000 parsed XML nodes are accepted, within the file bound. ZIPs allow at most 256 entries, 64 MiB total declared expanded size, 16 MiB per member and a 200:1 compression ratio. Absolute, traversal, drive-style, backslash, symlink and encrypted entries are rejected. Only recognized metadata is decompressed, capped at 256 KiB per metadata entry; other entries are listed without reading/extraction. This is metadata inspection, not a full archive integrity check.

## Integration notes for PM

New UI dictionaries live solely in `app/src/i18n/interop/index.ts`, exported as `interopEn`, `interopUz`, `interopUzCyrl`, `interopRu`, and `interopDictionaries`. The panel reads the existing locale store directly; existing i18n dictionaries/index are untouched. These exports can be merged into the central translation system later if desired. Engine registration is limited to the new route import and register call in `api/app.py`; Settings has the new panel import and render.

Verification: `engine/.venv/bin/python -m pytest engine/tests/test_interop.py`; `cd app && npm run build`. Focused tests cover malformed LUTs, XML entities, malformed XML/ZIP, archive traversal and compression limits, auth/path/file bounds, timed SRT text, native format rejection, actual timeline persistence and the renderer's normalized LUT resolution/copy. Desktop picker interaction requires a running Tauri host and is not covered by these tests.
