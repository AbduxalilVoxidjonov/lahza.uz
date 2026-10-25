# Reliz va imzolash

## Build tartibi

0. **Versiya:** `python3 scripts/bump_version.py 1.0.0` (yoki `make bump-version V=1.0.0`) — `engine/pyproject.toml`, `app/package.json` (+ `package-lock.json`), `app/src-tauri/Cargo.toml` (+ `Cargo.lock`), `tauri.conf.json`, `engine/src/lahza_engine/__init__.py` bir yo'la yangilanadi; tekshiruv: `python3 scripts/check_versions.py --expect 1.0.0`.
1. **Runtime'lar:** `scripts/build_runtimes.sh` (macOS) / `scripts/build_runtimes.ps1` (Windows) → `app/src-tauri/resources/bin/` (`ffmpeg`, `ffprobe`, `whisper-cli`, `llama-server` va ularning kutubxonalari).
2. **Sidecar:** `python scripts/build_sidecar.py --clean` → PyInstaller onefile → `app/src-tauri/binaries/lahza-engine-<target-triple>[.exe]` + `.sha256`; so'ng `python scripts/build_sidecar.py --verify`. Paket ma'lumotlari (`highlight/prompts`, `db/*.sql`, `render/*.json`, `subtitle/fonts/`) `--collect-data lahza_engine` bilan kiradi; majburiylari bo'lmasa build to'xtaydi. `--dry-run` hech narsa yig'may rejani ko'rsatadi.
3. **Katalog:** `catalog/catalog.json` imzolangan bo'lishi shart (`scripts/catalog_sign.py`).
4. **Litsenziyalar:** `make licenses` (`python scripts/gen_licenses.py`) — build muhitidan (venv, `package-lock.json`, `Cargo.lock` + lokal cargo registry, `runtimes.toml` va staging qilingan `bin/licenses/`, shriftlar, katalog) `LICENSES-THIRD-PARTY.md` jadvallari va UI'ning "Sozlamalar → Litsenziyalar" oynasi uchun `app/src/generated/licenses.json` yangilanadi; tarmoqqa chiqmaydi. Tekshiruv: `make check-licenses` (CI: `--check --reuse python`). Ro'yxatdagi `ANIQLANSIN` va **GPL** belgili yozuvlar relizdan oldin hal qilinadi.
5. **Ilova:** `cd app && LAHZA_CATALOG_PUBKEY=<ochiq kalit> npm run tauri build`.

Hammasi `.github/workflows/release.yml` da: `v1.0.0` tegi push qilinsa (yoki qo'lda, versiya bilan) — preflight (versiyalar, `runtimes.toml` mahkamlanganmi) → macOS/Windows build → artefaktlar va `SHA256SUMS-*.txt` → tegdan ishga tushganda GitHub'da **qoralama** reliz (qo'lda tekshirib e'lon qilinadi).

Sidecar nomi `nom-<target-triple>` bo'lishi shart: masalan `lahza-engine-aarch64-apple-darwin`, `lahza-engine-x86_64-pc-windows-msvc.exe` ([Tauri](https://v2.tauri.app/develop/sidecar/)). NSIS qayta o'rnatishda eski sidecar qolib ketgan holat qayd etilgan ([issue #15134](https://github.com/tauri-apps/tauri/issues/15134)) — `build_sidecar.py` har buildda shu triple uchun eski faylni o'chiradi, yangisining sha256 xeshini yoniga yozadi, CI esa `--verify` bilan tekshiradi.

## Lokal reliz (`versiyalar/`)

Apple Silicon'da lokal alfa yig'ish va har versiyani saqlash (CI/notarizatsiyasiz, ad-hoc imzo):

* O'zgarishlar ish davomida `versiyalar/CHANGELOG.md` dagi `## [Kelgusi]` bo'limiga yoziladi.
* `make release-local V=x.y.z` (yoki `V=patch|minor|major`, `scripts/release_local.py`): versiya bump → `make test-engine test-ui typecheck lint check-licenses` (yiqilsa to'xtaydi) → `make build-local` → `versiyalar/<V>/` ga ikki marta bosib ochiladigan `Lahza Studio.app` (`ditto` nusxa, `codesign --verify --deep --strict` bilan tekshiriladi), `LahzaStudio-<V>-macos-arm64.zip` (`ditto`), `NOTES.md` (sana, commit, o'zgarishlar, testlar, `.app` va zip hajmi), `SHA256SUMS` (zip va `.app/Contents/MacOS/*`); `[Kelgusi]` → `[<V>]`. `versiyalar/<V>/` mavjud bo'lsa xato beradi. Build yiqilsa papka "yig'ilmadi" belgisi bilan yoziladi (chiqish kodi 2).
* Faqat versiya: `make bump-version V=x.y.z`. Commit va `v<V>` tegi qo'lda.
* Binarlar (`*.app`, `*.zip`, `*.dmg`) git'ga kirmaydi; `README.md`, `CHANGELOG.md`, `*/NOTES.md`, `*/SHA256SUMS` kiradi. Tuzilma: [`versiyalar/README.md`](../versiyalar/README.md).

## macOS

* Developer ID Application sertifikati, hardened runtime (`tauri.conf.json: bundle.macOS.hardenedRuntime`).
* Ichki barcha bajariladigan fayllar (sidecar, `resources/bin/*`) alohida imzolanadi.
* Notarizatsiya va **staple majburiy**: staple qilinmagan dastur birinchi ishga tushishda Apple serveriga murojaat qiladi va internetsiz Mac'da bloklanadi ([manba](https://nektony.com/how-to/remove-non-notarized-apps-mac)). macOS Sequoia'dan boshlab imzolanmagan dasturni Control-click bilan ochib bo'lmaydi ([manba](https://eclecticlight.co/2024/08/10/gatekeeper-and-notarization-in-sequoia/)).
* CI sirlari (Tauri): `APPLE_CERTIFICATE`, `APPLE_CERTIFICATE_PASSWORD`, `APPLE_SIGNING_IDENTITY`, `APPLE_ID`, `APPLE_PASSWORD`, `APPLE_TEAM_ID`.

## Windows

* Kod imzolash sertifikati; imzosiz o'rnatuvchi har yuklashda SmartScreen ogohlantirishini chiqaradi ([manba](https://r-pkg.thecoatlessprofessor.com/shinyelectron/articles/code-signing.html)).
* NSIS, `installMode: currentUser` (administrator huquqi talab qilinmaydi).
* Sidecar va `resources/bin/*.exe` ham imzolanadi.

## Reliz tekshiruvi

- [ ] Barcha testlar yashil (engine, UI, Rust) — macOS va Windows'da
- [ ] Oltin to'plamlarda nisbiy talablar bajarilgan (`docs/09-test-va-sifat.md`)
- [ ] Katalog imzolangan; ochiq kalit build'ga kiritilgan; `approved` yozuvlar URL/sha256 bilan
- [ ] Toza VM'da internetsiz: o'rnatish → `.lzpack` import → import → highlight → eksport
- [ ] Staple tekshiruvi: `xcrun stapler validate "Lahza Studio.app"`
- [ ] `LICENSES-THIRD-PARTY.md` va `licenses.json` (`make licenses`, `make check-licenses`) hamda "Sozlamalar → Litsenziyalar" to'liq; CC-BY mualliflari ko'rsatilgan; `ANIQLANSIN` bo'limi bo'sh; LGPL manba taklifidagi aloqa manzili belgilangan
- [ ] `render/platform_limits.json` Instagram limitlari qayta tekshirilgan
- [ ] Yurist xulosasi (FFmpeg, NVENC, H.264, modellar) olingan
- [ ] Versiya raqami: `engine/pyproject.toml`, `app/package.json`, `app/src-tauri/Cargo.toml`, `tauri.conf.json` bir xil — `make check-versions` (relizda `--expect <versiya>`)
- [ ] Sidecar xeshi mos: `python scripts/build_sidecar.py --verify`

## Yangilash

Onlayn avto-yangilash ixtiyoriy va standart holatda o'chiq. Oflayn yo'l: imzolangan yangilanish fayli.
