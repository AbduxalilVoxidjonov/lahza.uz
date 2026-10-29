# Dependency security verification — 2026-10-30

Verified on macOS ARM64 with Node 24.20.0 and Rust 1.98.1.
RustSec checks used cargo-audit 0.22.2 and advisory-db commit
`ee1a49a2769a24a596afc1c20cb33748d2769586` (2026-10-29).

## Final scope

npm updates:

- `@hono/node-server`: 2.0.12 → 2.1.5.
- `qs`: 6.16.0 → 6.17.1, including the minimum version in the
  `typed-rest-client` override.
- Retained `shadcn` as a devDependency at its original locked version, 4.22.1,
  with the original CSS import. Its remaining low-severity deepmerge advisory
  has no published fix; the development tool is retained without suppressions.

Rust updates are limited to TLS/certificate verification, persistent collection
safety, and FFmpeg's archive extraction dependency:

| Crate | Before | After |
|---|---|---|
| imbl | 7.0.1 | 7.0.2 |
| imbl-sized-chunks | 0.1.3 | 0.2.0 |
| bitmaps | 3.2.1 | removed by the imbl update |
| rustls | 0.23.45 | 0.23.46 |
| rustls-webpki | 0.103.15 | 0.103.16 |
| webpki-root-certs / webpki-roots | 1.0.9 | 1.0.11 |
| ffmpeg-sidecar | 2.5.2 | 2.7.0 |
| zip | 4.6.1 | 9.1.3 |

The ZIP update adds its required `nix` and `typed-path` dependencies and removes
`arbitrary` / `derive_arbitrary`. Zstd, Tokio, quinn-proto and chacha20 retain
their original versions. Rust manifests, source files and all PoCs are unchanged.

## Audit results

npm: **3 low-severity dependency alerts**, down from 6. All three are the same
underlying deepmerge advisory, propagated through @shadcn/registry and shadcn.
There are no moderate, high or critical npm alerts.

The retained native Cargo.lock matches **8 vulnerability records and 11 unsound
warnings**: the remaining records concern quinn-proto, Zstd/zstd-safe and Tokio.
The current feature set does not enable quinn-proto; application Zstd calls use
bulk compression/decompression rather than the stream, dictionary and seekable
APIs identified by the advisories. This is a scoped update, not a claim of zero
RustSec findings or a formal proof that every remaining issue is unreachable.
No advisory exclusions or severity filters were added.

## Verification of the final dependency combination

| Check | Result |
|---|---|
| Locked, offline Rust core library tests | 787 passed, 9 ignored |
| media_conformance tests | 20 passed |
| Rust eval / conversion tests | 63 / 14 passed |
| Workspace Clippy, all targets, `-D warnings` | passed |
| Production core addon (`napi:build`) | rebuilt successfully |
| `npm run typecheck` | passed |
| MCP unit tests | 26 files, 225 tests passed |
| Lockfile scope check | only the crates listed above and their required dependency changes |
| `git diff --check` | passed |

Core/eval/conversion were tested together with `test-noop`; Clippy covered the
whole workspace with bundled macOS FFmpeg. Incremental Rust compilation was
disabled for the final checks to keep build-cache disk use bounded.

The earlier, broader dependency combination also passed the full JavaScript
and build-script suites and targeted Electron tests. Those results are not
represented here as fresh full-suite validation of this final combination.
Cross-platform validation is performed by the main branch CI. Windows-only PoCs
and installer packaging were not run locally.
