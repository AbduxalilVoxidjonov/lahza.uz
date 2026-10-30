// Stages the Lahza engine sidecar (Uzbek ASR, highlight detection, 9:16 reframe,
// Uzbek karaoke subtitles) into resources/lahza/<os>/ from a Lahza Studio
// checkout. The engine is a self-contained PyInstaller executable built by
// lahza.uz's scripts/build_sidecar.py; its runtimes (ffmpeg with libass,
// llama-server and their DLLs) ride in bin/, and the signed model catalog and
// its public key in catalog/. Nothing is downloaded: run it after the Lahza
// sidecar is built.
//
//   node scripts/stage-lahza-engine.mjs [--from <lahza.uz checkout>]
//
// The checkout defaults to $LAHZA_ROOT, then ../../../lahza.uz beside the repo.
import { cpSync, existsSync, mkdirSync, rmSync, writeFileSync } from 'node:fs'
import { join, dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const here = dirname(fileURLToPath(import.meta.url))
const desktop = resolve(here, '..')
const osDir = process.platform === 'win32' ? 'win' : process.platform === 'darwin' ? 'mac' : 'linux'
const flag = process.argv.indexOf('--from')
const root = resolve(flag > 0 ? process.argv[flag + 1] : process.env.LAHZA_ROOT ?? join(desktop, '../../../lahza.uz'))

/** The Tauri sidecar name for this host's target triple. */
function sidecarName() {
  if (process.platform === 'win32') return 'lahza-engine-x86_64-pc-windows-msvc.exe'
  if (process.platform === 'darwin') return `lahza-engine-${process.arch === 'arm64' ? 'aarch64' : 'x86_64'}-apple-darwin`
  return `lahza-engine-${process.arch === 'arm64' ? 'aarch64' : 'x86_64'}-unknown-linux-gnu`
}

const tauri = join(root, 'app/src-tauri')
const sources = {
  engine: join(tauri, 'binaries', sidecarName()),
  bin: join(tauri, 'resources/bin'),
  catalog: join(root, 'build/sidecar/catalog'),
}
for (const [what, path] of Object.entries(sources)) {
  if (!existsSync(path)) {
    console.error(`[stage-lahza-engine] missing ${what}: ${path}\n  Build the Lahza sidecar first (python scripts/build_sidecar.py in ${root}).`)
    process.exit(1)
  }
}

const dest = join(desktop, 'resources/lahza', osDir)
rmSync(dest, { recursive: true, force: true })
mkdirSync(dest, { recursive: true })
const exe = process.platform === 'win32' ? 'lahza-engine.exe' : 'lahza-engine'
cpSync(sources.engine, join(dest, exe))
cpSync(sources.bin, join(dest, 'bin'), { recursive: true })
cpSync(sources.catalog, join(dest, 'catalog'), { recursive: true })
writeFileSync(join(dest, 'manifest.json'), JSON.stringify({ source: root, engine: sidecarName(), staged_at: new Date().toISOString() }, null, 2) + '\n')
console.log(`[stage-lahza-engine] staged ${root} -> ${dest}`)
