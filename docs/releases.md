# Desktop releases

The desktop version is a stable SemVer (`0.1.1`, not `0.1.001`). From the repo
root, run `npm run version:release -- 0.1.2` and commit the two package.json
files and package-lock.json together. Native crate versions are independent.

On a push to `main` in `AbduxalilVoxidjonov/lahza.uz`, electron-ci compares that version with
published GitHub Releases. An unpublished, increasing version is a release
candidate. PRs, scheduled runs and manual CI runs cannot publish. Subsequent
main pushes retry an unpublished version if a previous build failed or was
cancelled; a published version is never overwritten. Version-only edits to one
package fail validation, so use the command above.

The packaging legs build NSIS (.exe) on Windows, AppImage and .deb on Linux,
and an Apple Silicon DMG on macOS, plus electron-builder's update manifests and
blockmaps. Release publishing waits for every E2E, unit/typecheck, Rust and
determinism comparison gate on all three OSes. No additional release build
bypasses these gates.

Assets are named by OS and architecture with no version: `LahzaStudio-win-x64.exe`,
`LahzaStudio-linux-x86_64.AppImage`, `LahzaStudio-linux-amd64.deb` and
`LahzaStudio-mac-arm64.dmg`. GitHub's
`https://github.com/AbduxalilVoxidjonov/lahza.uz/releases/latest/download/<asset>` is
therefore a permanent link to the current build, fit for a download page that
never needs editing. A specific build stays addressable through its tag,
`releases/download/v<version>/<asset>`. electron-updater derives the previous
release's blockmap URL by swapping the version inside that tag segment, so
differential Windows updates do not depend on a version in the file name.

The macOS build is ad-hoc signed (`identity: "-"` in electron-builder.yml) and
not notarized: Lahza has no Apple Developer ID. Ad-hoc rather than no
signature keeps the bundle's seal consistent after electron-builder rewrites
Electron's stock bundle, so Gatekeeper treats the app as an unidentified
developer's instead of reporting it damaged. Users open it once, then allow it
under System Settings → Privacy & Security → Open Anyway, or clear the
quarantine flag with `xattr -dr com.apple.quarantine`; every release's notes
carry both. Only arm64 ships: the runner, the bundled ffmpeg sidecar and the
from-source LGPL libraries are all Apple Silicon.

Only the final release job gets `contents: write`. The built-in GITHUB_TOKEN is
enough; no personal token or client-side GitHub credentials are needed. The
publisher validates all three platforms' manifests, versions, file sizes and
SHA-512 hashes, creates a draft `v<version>` at the tested commit with the
install steps prepended to the generated notes, uploads all assets, then
publishes it as Latest. Artifacts are retained in Actions for five days;
public release assets are the permanent update source.

A failed upload leaves a draft, invisible to update checks. Re-run the failed
job at the same commit to resume it. If a draft belongs to an older commit,
remove that draft before retrying a new commit (also remove its version tag if
GitHub created one). The workflow refuses existing tags without a matching
draft, and refuses lower versions. Publish a higher patch version to deliver a
fix; do not replace installers under an already published version.

Packaged Windows/Linux applications use electron-updater against the public
`AbduxalilVoxidjonov/lahza.uz` GitHub Release feed. The runtime pins the same
owner/repo as electron-builder.yml; no personal token is shipped. They check 5 seconds after startup and every six hours,
and surface an available update as an icon on the start screen and in the
editor's status bar; neither interrupts work with a notice. General
settings' second item, "Automatically install available updates when closing
the app", defaults on (including older settings files). With it enabled,
background downloads begin automatically; normal exit installs the downloaded
update after the editor's autosave flush and leaves the app closed. With it off,
checks only fetch release metadata. "Download and install" explicitly downloads
the installer, then saves and restarts to install. Turning the preference off
cancels an ongoing background download; an already completed download remains
available for an explicit restart. Turning it on downloads a known available
update immediately. An explicitly requested download is independent of this
preference.
"Later" only closes the dialog; it does not change this preference.
"Skip this version" stores that version as skipped (`skipped_update_version`):
both icons hide it, and the background download and the exit install step aside
for it. Help → Check for Updates still offers it as usual, without mentioning the
skip, and choosing Download and install or Update and restart there clears it.
A newer release is never covered by an older skip.

"Update and restart app" is a one-time action independent of that preference.
It blocks further UI operations while saving, then exits normally; the final
quit event starts installation with relaunch enabled. A failed save leaves the
project open and the update available to retry. A version-bound, one-use
`update-resume.json` handoff restores the exact current project (or start
screen) without changing the separate reopen-on-launch preference. Workspace
layout and window geometry use their existing persistence.

Windows updates show the NSIS installation progress page, skip install-location
and install-mode choices, and close automatically on success. Only an explicit
update-and-restart requests relaunch; ordinary exit updates do not reopen.
This makes the file-replacement interval visible; it is not an atomic switch
between executable versions, and shortcuts still target the installed exe.
The start screen's top-left actions end with a circular, theme-blue update
button bearing Lucide's ArrowDownToLine download icon. Release builds show this
icon-only button when a new version is known; development
keeps it visible for UI work. Its tooltip and accessible name describe the
action, and it opens the same dialog as the editor's Help → Check for Updates
entry. The editor's status bar carries the same entry as a solid theme-blue
"Update available" pill left of the Logs toggle. Its label stays fixed, since an
update outlives the transient job badges beside it; its tooltip and accessible
name carry the version and phase, and a running download draws a progress ring
around its icon. Opening the dialog is the
explicit check; simply showing either icon only reads status. The dialog shows
availability/progress/readiness, offers skip, later and download or restart
actions in one row, retries errors and links to manual downloads. Dev and
E2E builds disable update checks. Packaged macOS builds check the same public
repository at startup and every six hours. They offer a newer stable release
only when it contains the matching `LahzaStudio-mac-<arch>.dmg`. Drafts,
prereleases, content-only releases, old installers and downgrades are ignored.
The Download DMG button opens that exact release asset in the browser; it does
not quit, restart or silently replace the running app. Close the app and drag
the downloaded app into Applications to install it. macOS cannot self-update
with the current ad-hoc signature: Squirrel.Mac installs only a build whose signature satisfies the
running app's designated requirement, and an ad-hoc signature pins that to the
running build's own code hash. Prereleases and downgrades are off.

On Windows the taskbar icon and window grouping come from the app's
AppUserModelID, which the installer stamps onto the Start Menu and Desktop
shortcuts. The runtime value (`src/main/appIdentity.ts`) must equal
electron-builder's `appId`; a unit test pins them together, and this value stays
stable across releases so pinned shortcuts and notifications survive updates.
electron-builder's stock installer only re-stamps a shortcut when it recreates or
renames one, so an in-place update that keeps a same-named shortcut could leave a
rewritten exe with a stale identity and a blank taskbar icon. `build/installer.nsh`
re-asserts the AppUserModelID on every install and update to prevent that. A
machine whose per-identity taskbar record was already corrupted by an earlier
update is only reliably cleared by uninstalling and reinstalling.

Before declaring updates verified, install the actual 0.1.1 Windows/Linux
packages, publish a higher patch, and exercise checking, downloading and normal
exit installation. Confirm the saved project reopens and the app reports the
new version. Include AppImage and .deb (which may prompt for system privileges),
network failure/retry and an export left running while an update downloads.
Unit tests and release-manifest checks do not replace this installed-app test.

## Publishing updates for Lahza Studio

Use `npm run version:release -- <higher-version>` and push the verified changes
to this repository’s `main` branch. The existing release job publishes the
Windows/Linux/macOS installers and `latest*.yml` metadata after all gates pass.
A commit, branch push or tag by itself is not an update: the GitHub Release
must be published and include its installers. Keep the repository and release
assets public so installed applications can check without credentials.

Local development runs intentionally keep updates disabled. To exercise the
real feed, use a packaged application. Publishing requires an explicit release
operation; configuring the feed does not create or upload a release.

## Draft-only publishing, tag workflow and engine caveat

CI cannot stage the Lahza engine sidecar (`resources/lahza/<os>`, built outside
this repo by `scripts/stage-lahza-engine.mjs`), so CI-built installers ship
without it. To keep such a build from auto-updating every user:

- `electron-ci.yml`'s main-push release job runs `release.mjs publish` with
  `RELEASE_DRAFT_ONLY=1` unless the repository variable `LAHZA_AUTO_PUBLISH` is
  `true`. A draft is invisible to electron-updater and to the macOS check; a
  person reviews it and clicks Publish on GitHub.
- `.github/workflows/release.yml` runs on a pushed `v<version>` tag (or manual
  dispatch with the tag): it checks the tag equals the package version and is on
  `main`, builds the Windows/Linux/macOS matrix, and uploads a draft. Dispatch
  with `publish: true` to publish. The two workflows share one concurrency group
  and `release.mjs` is idempotent, so running both is safe.
- `release.mjs` rejects any asset of 2 GiB or more (GitHub's per-asset limit)
  before creating the draft, and accepts an already-pushed tag only when it
  resolves to the build's exact commit.

Auto-update needs a PUBLIC repository (clients fetch release assets without
credentials; the repo is currently public). macOS is a manual DMG download until
a Developer ID signature and notarization exist. The previous local
`make release-local` / `versiyalar/<v>/` flow (scripts/release_local.py) is not
present in this tree.

## Lahza engine bundle for CI

The engine (`resources/lahza/<os>`) is a PyInstaller sidecar and is never built in
CI. Its source is tracked (`engine/src`, `engine/pyproject.toml`,
`scripts/build_sidecar.py`); the built bundle is not (`resources/lahza/`,
`build/sidecar/`, `engine/.venv`, `__pycache__` are gitignored). CI instead
downloads a pre-built bundle with `apps/desktop/scripts/fetch-lahza-engine.mjs`
(in `electron-ci.yml` before "Package (unsigned)" and in `release.yml` before
"Package"). This is a manual, out-of-band step done by a person:

1. Build and stage the engine on a machine of the target OS/arch
   (`python scripts/build_sidecar.py`, then `node apps/desktop/scripts/stage-lahza-engine.mjs`).
   This fills `apps/desktop/resources/lahza/<os>/` with `lahza-engine[.exe]`,
   `bin/`, `catalog/` and `manifest.json`. Only macOS arm64 exists today.
2. Pack the CONTENTS of that folder (not the folder itself) as a tar.gz, which
   preserves the relative dylib symlinks and works with `tar` on every runner:
   `cd apps/desktop/resources/lahza/mac && tar -czf ../../../lahza-engine-mac-arm64.tar.gz .`
3. Compute the hash: `shasum -a 256 lahza-engine-mac-arm64.tar.gz`
   (Windows: `certutil -hashfile <file> SHA256`).
4. Upload the file as an asset of a dedicated, PUBLISHED GitHub release in this
   repo, e.g. tag `engine-<engine-version>` (separate from the app's `v<version>`
   releases, so `release.mjs` never sees it). The asset must be public: the
   download sends no credentials. Do not attach it to a `v*` app release.
5. Set repository variables (Settings > Secrets and variables > Actions >
   Variables), one pair per platform, using the asset's
   `https://github.com/AbduxalilVoxidjonov/lahza.uz/releases/download/<tag>/<file>` URL:

   | OS / arch | URL variable | SHA-256 variable |
   | --- | --- | --- |
   | macOS arm64 | `LAHZA_ENGINE_URL_MAC_ARM64` | `LAHZA_ENGINE_SHA256_MAC_ARM64` |
   | macOS x64 | `LAHZA_ENGINE_URL_MAC_X64` | `LAHZA_ENGINE_SHA256_MAC_X64` |
   | Windows x64 | `LAHZA_ENGINE_URL_WIN_X64` | `LAHZA_ENGINE_SHA256_WIN_X64` |
   | Linux x64 | `LAHZA_ENGINE_URL_LINUX_X64` | `LAHZA_ENGINE_SHA256_LINUX_X64` |

Behavior: with both variables set, the script verifies the sha256 and unpacks
into `apps/desktop/resources/lahza/<os>`; a mismatch, HTTP error or a bundle
without `lahza-engine[.exe]` at its top level fails the leg. With a variable
missing, the leg prints a `::warning::` and the installer ships WITHOUT the
engine (draft-only, see above); `release.yml` dispatched with `publish: true`
turns that into an error. Today only the macOS arm64 variables can be set; the
Windows and Linux legs will warn until their bundles are built on those OSes.
Changing a bundle means a new asset, a new hash, and updating both variables.
