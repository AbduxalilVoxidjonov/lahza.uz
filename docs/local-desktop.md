# macOS local desktop alpha

This builds a native Apple Silicon `.app` for local testing. It is not a signed,
notarized production release. Build on the target architecture: PyInstaller does
not cross-compile the engine.

`make build-local` also applies an ad-hoc development signature to the complete
bundle and verifies it with `codesign --verify --deep --strict`. This is not a
Developer ID identity or notarization. Copy the entire `.app`, not just its executable.
The frozen entry point calls `multiprocessing.freeze_support()` before CLI parsing
so native inference libraries' resource-tracker helpers do not run as CLI commands.
The opt-in frozen check also exercises shared-memory cleanup in a spawned helper.

## Build

Use the engine virtualenv, with the engine installed editable and PyInstaller
installed (`pip install -e "engine[dev,desktop]"` followed by
`pip install --no-deps -r engine/requirements-desktop-nodeps.txt`). The desktop extra
holds faster-whisper's runtime dependencies; faster-whisper itself is installed without
dependencies so PyAV (`av`, whose PyPI wheels bundle a GPL libx264/libx265 FFmpeg) is
never installed (ADR-0015). The sidecar collects `faster_whisper`, `ctranslate2`,
`tokenizers` and `onnxruntime` including their native libraries and package data when
present; `av` is always excluded, and the build fails if PyInstaller's TOC still lists
PyAV or libx264/libx265. Check the printed
backend list and `build/sidecar/sidecar.json`; a successful build without these
packages does not establish ASR functionality.

Prepare the native runtimes in `app/src-tauri/resources/bin/` and the subtitle
fonts using the runtime/font setup workflow before the final packaging pass.
Then, from the repository root:

```sh
engine/.venv/bin/python scripts/build_sidecar.py --clean
engine/.venv/bin/python scripts/build_sidecar.py --verify
cargo check --manifest-path app/src-tauri/Cargo.toml
engine/.venv/bin/python -m pytest engine/tests/test_desktop_packaging.py
LAHZA_TEST_REQUIRE_ASR=1 \
  LAHZA_TEST_SIDECAR="$PWD/app/src-tauri/binaries/lahza-engine-aarch64-apple-darwin" \
  engine/.venv/bin/python -m pytest engine/tests/test_desktop_packaging.py
cd app
npm run tauri build -- --config src-tauri/tauri.local.conf.json --bundles app
```

Expected output: `app/src-tauri/target/release/bundle/macos/Lahza Studio.app`.
No DMG is needed for this local check. Rebuild the sidecar after Python source,
backend dependencies or font data change, then rebuild the app.

The local override requires macOS 27 because the locally prepared FFmpeg/libass
dependency closure includes libraries built for macOS 27. The base configuration's
macOS 14 target is not validated by this build. Producing a macOS 14 release requires
rebuilding and testing the entire native dependency closure for that deployment
target; changing only the plist cannot establish compatibility.

## Catalog trust

By default (when `LAHZA_CATALOG_PUBKEY` is absent), the sidecar build generates
`build/sidecar/catalog/catalog.json` from the source catalog and signs it with a
fresh ephemeral Ed25519 key. The private key stays in memory and is never saved.
The public key is staged alongside the catalog and embedded by `build.rs`.
This trust applies only to that local build.

When `LAHZA_CATALOG_PUBKEY` is explicitly set, packaging validates the key and
verifies the source `catalog/catalog.json` against it, then copies that signed
catalog unchanged and stages the explicit public key. Empty, malformed or
mismatched keys fail; they never fall back to ephemeral trust. Release CI supplies
the production public key to both sidecar packaging and Tauri. The source catalog
must already carry its matching production signature; no private release key is
needed or stored by packaging. `build.rs` rejects an explicit key that differs
from the staged key.

Tauri bundles the staged catalog. The launcher sets `LAHZA_DEV=0` and passes the
embedded public key, retaining catalog verification and session authentication.
Do not rebuild the sidecar/catalog concurrently with a Rust app build: both must
use the same staged identity. Packaging never rewrites the source catalog.

For a clean checkout's Cargo check, install the base engine dependencies and run
`python scripts/build_sidecar.py --catalog-only` before checking. This prepares
only the signed catalog, without PyInstaller or touching sidecar binaries. CI also
creates a placeholder binary for Cargo checks; that does not validate a packaged
engine. `--dry-run` leaves all artifacts untouched.

Windows has CI configuration, but this local macOS work does not establish Windows
packaging or runtime verification.

## Frozen engine smoke check

The opt-in packaging test first runs the binary's `--packaging-check` diagnostic,
which imports the collected backends and local bootstrap module inside the frozen
process. `LAHZA_TEST_REQUIRE_ASR=1` requires all four ASR packages to be present.
Set `LAHZA_TEST_MODEL_REGISTRY` to an existing `Models/installed.json` to also
exercise the API's model self-test with its default ASR model. The test copies the
registry to temporary data storage, retains its absolute model file paths, and
does not modify the original registry.
Also set `LAHZA_TEST_ASR_AUDIO` to an absolute path to a short speech WAV to run
actual CPU int8 transcription in the frozen executable using that default model.
The diagnostic requires at least one recognized word; this is an inference smoke
check, not a transcription quality benchmark.
It then starts the actual frozen binary from a temporary
working directory and data directory, reads its selected port, verifies health,
requires an unauthenticated request to return 401, and requests the signed catalog
bundle without a development bypass. It terminates the engine afterward. This
checks packaged startup and catalog trust; it does not establish transcription,
render quality, model download availability or UI functionality.

To test the binary inside the generated app, set `LAHZA_TEST_SIDECAR` to
`.../Lahza Studio.app/Contents/MacOS/lahza-engine` and `LAHZA_TEST_CATALOG` to
`.../Lahza Studio.app/Contents/Resources/catalog`.

Set `LAHZA_TEST_RUNTIME` to `.../Lahza Studio.app/Contents/Resources/bin` to also
run the bundled FFmpeg with an isolated system-only `PATH`, no inherited DYLD
overrides, and `DYLD_PRINT_LIBRARIES=1`. The test renders a short ASS subtitle
sample through libass, requires the bundled libass to load, and rejects Homebrew,
`/usr/local`, or the source runtime build directory in the loader trace.

Full opt-in check from the repository root (the WAV must contain speech):

```sh
LAHZA_TEST_REQUIRE_ASR=1 \
LAHZA_TEST_MODEL_REGISTRY="$HOME/Library/Application Support/Lahza Studio/Models/installed.json" \
LAHZA_TEST_ASR_AUDIO="$PWD/build/sidecar/asr-smoke.wav" \
LAHZA_TEST_SIDECAR="$PWD/app/src-tauri/target/release/bundle/macos/Lahza Studio.app/Contents/MacOS/lahza-engine" \
LAHZA_TEST_CATALOG="$PWD/app/src-tauri/target/release/bundle/macos/Lahza Studio.app/Contents/Resources/catalog" \
LAHZA_TEST_RUNTIME="$PWD/app/src-tauri/target/release/bundle/macos/Lahza Studio.app/Contents/Resources/bin" \
engine/.venv/bin/python -m pytest engine/tests/test_desktop_packaging.py
```

Packaging uses `--collect-submodules lahza_engine` and `--collect-data lahza_engine`,
so new routes and non-Python package assets (including `stickers/assets/*`) are
collected on the next rebuild. Ensure new asset globs also appear in the engine's
setuptools package-data declaration. The build prints its data inventory and saves
it in `build/sidecar/sidecar.json`; inspect that inventory after adding assets.
