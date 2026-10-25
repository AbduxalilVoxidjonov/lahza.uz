# Local subtitle rendering

Run from the repository root on macOS with Xcode Command Line Tools, Homebrew,
and Python 3.12+ (or Python 3.11 with tarfile's data extraction filter backport):

```sh
python3 scripts/setup_local_render.py --install-deps
source build/local-runtime/activate.sh
```

For the macOS app/package workflow, use this exact command:

```sh
engine/.venv/bin/python scripts/setup_local_render.py --stage
# First setup including Homebrew dependencies:
engine/.venv/bin/python scripts/setup_local_render.py --install-deps --stage
```

**The default command only prepares `build/local-runtime`.** A `make setup-local`
recipe invoking the script without flags must add `--stage` to populate app
resources. This script does not modify the Makefile. A custom output can be
specified with `--stage /absolute/path/to/resources/bin`.

Staging copies `ffmpeg`, `ffprobe`, and the complete non-system dylib dependency
closure to `app/src-tauri/resources/bin/lib/`. It resolves Homebrew symlinks and
`@rpath` dependencies, rewrites executables to `@loader_path/lib/...`, rewrites
dylibs to `@loader_path/...`, removes old rpaths, and ad-hoc signs modified Mach-O
files so they can execute on Apple Silicon. It audits every load dependency,
copies the staged tree to a different directory containing a space, then runs
both subtitle smoke tests there before publishing the output. Other resource
files are preserved. Release signing/notarization remains the package step.

The package must include `resources/bin/lib/**` and
`resources/bin/licenses/local-render/**` recursively alongside the executables;
a flat `resources/bin/*` copy of files is insufficient. The font and its notices
are separately included by the engine's package-data rule.

This machine's staged result has **14 arm64 Mach-O files: two executables and
12 dylibs**. Their recorded minimum macOS versions are 26.0 and 27.0, making the
combined minimum **macOS 27.0 on Apple Silicon**. This removes the Homebrew
installation requirement at execution time, but does not provide Intel support
or backward compatibility. Supporting an older deployment target requires
rebuilding FFmpeg **and its dependencies** against that target; copying current
Homebrew bottles cannot achieve it. No other physical Mac was tested.
`licenses/local-render/dylibs.json` records the per-file architecture, deployment
target and original library path for the actual staged result.
`dyld-loaded.txt` records an actual relocated FFmpeg process with
`DYLD_PRINT_LIBRARIES=1`: verification loaded all 12 copied dylibs and zero
libraries from `/opt/homebrew` or `/usr/local`.

To test the staged executables directly (both environment contracts are needed):

```sh
export LAHZA_BIN_DIR="$PWD/app/src-tauri/resources/bin"
export PATH="$LAHZA_BIN_DIR:$PATH"
export LAHZA_REQUIRE_LIBASS=1
engine/.venv/bin/python -m pytest engine/tests/test_render_e2e.py engine/tests/test_local_render.py
```

The first command installs Homebrew `libass`, `pkgconf`, and `nasm`, downloads the
official FFmpeg 7.1.1 source archive with a pinned SHA-256, and builds `ffmpeg` and
`ffprobe` in `build/local-runtime/bin`. It never replaces the system FFmpeg or
changes shell startup files. All build outputs are ignored by the existing
`build/` git rule. Homebrew may update dependencies as part of installation.
Without `--install-deps`, existing dependencies are used. On Linux, install a C
compiler, make, pkg-config, libass development headers and zlib development headers
using your package manager first; that build path has not been verified here.

Re-running validates and smoke-tests the installed runtime without rebuilding.
Use `--rebuild` to reconfigure/rebuild after dependency changes or an interrupted
installation, and `--jobs N` to limit compilation concurrency. A checksum mismatch
stops setup; remove only the named downloaded archive and retry. Build diagnostics
are in `build/local-runtime/build.log`.

Activation sets both `LAHZA_BIN_DIR` (the first lookup in
`engine/src/lahza_engine/media/tools.py`) and `PATH` (used by test fixtures and
direct subprocess calls). It also sets `LAHZA_REQUIRE_LIBASS=1`, so missing libass
causes a test failure instead of a silent subtitle-test skip. Activate in each
shell before launching the engine or tests. A child setup process cannot change
the calling shell's environment.

Install the engine's test/font dependencies if needed, then verify:

```sh
python3 -m venv engine/.venv
engine/.venv/bin/python -m pip install -e 'engine[dev,fonts]'
source build/local-runtime/activate.sh
engine/.venv/bin/python -m pytest engine/tests/test_sub_fonts.py engine/tests/test_local_render.py engine/tests/test_render_e2e.py
```

Setup checks the reported LGPL license, rejects `--enable-gpl`,
`--enable-nonfree`, and `--enable-version3`, and requires **both** `ass` and
`subtitles` filters. Its smoke test renders Uzbek text with each filter and decodes
frames to check for visible bright subtitle pixels on black. The MP4 from the
`subtitles` test is retained at `build/local-runtime/smoke/subtitled.mp4`; the
generated ASS and SRT are alongside it. The existing E2E tests exercise ASS render
layouts/cuts and the analyze/export pipeline using fake ASR and real FFmpeg.
The render command explicitly sets `RenderJob.fps` as the output frame rate:
FFmpeg 7 otherwise propagates concat's 1/1000000 time base to the native MPEG-4
fallback, which cannot encode a denominator above 65535.

## Fonts

The engine package includes unmodified Inter (upright variable TTF) in
`engine/src/lahza_engine/subtitle/fonts/`, matching `StyleTemplate.font_family`.
`SOURCE.txt` records the pinned Google Fonts commit, exact source URLs and file
hashes; `OFL.txt` contains its SIL Open Font License 1.1 and copyright notice.
The font test checks every `REQUIRED_GLYPHS` character, including Uzbek Cyrillic,
U+02BB/U+02BC, and the proposed Latin letters. No system font installation is
required. The existing package-data rule includes font, license and source files.
`LAHZA_FONTS_DIR` can override the bundled directory; unset it to use Inter.

## Configuration and licensing

This prepares a local development runtime and optional macOS package inputs.
FFmpeg uses its native codecs, libass and zlib, with autodetection of unrelated
external libraries disabled. GPL, nonfree and version3 features are explicitly
disabled; libx264/libx265 are absent. On macOS, VideoToolbox and AudioToolbox are
explicitly enabled. Existing E2E tests use native `mpeg4` as the software fallback;
production H.264 selection remains governed by the engine's existing policy.

The FFmpeg build reports LGPL 2.1-or-later. Its `COPYING.LGPLv2.1`, `LICENSE.md`,
source archive, extracted source and `manifest.json` (source hash, actual build
configuration and license output) remain under `build/local-runtime`. See
[FFmpeg's licensing guidance](https://ffmpeg.org/legal.html).
Libass is ISC licensed; Homebrew's dynamically linked dependencies carry their
own licenses (including FreeType, HarfBuzz and FriBidi). The unstaged executables
depend on installed Homebrew libraries. `--stage` copies dependency notices,
Homebrew install receipts and SPDX SBOMs to `licenses/local-render/` and makes
the library load paths relative.
Redistribution needs dependency/source/license handling beyond this setup; it
does not copy a GPL Homebrew FFmpeg into app resources.
