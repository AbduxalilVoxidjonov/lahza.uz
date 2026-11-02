# Dasturchi muhiti

Bu yerda loyihani kompyuterda noldan ishga tushirish tartibi. Ishlab chiqarish platformalari — macOS (Apple Silicon) va Windows x64; Linux faqat dasturchi muhiti va CI uchun.

## Talablar

| Vosita | Versiya | Nima uchun |
| --- | --- | --- |
| Python | 3.12 (≥ 3.11) | Engine |
| Node.js | 22 LTS | UI build |
| Rust | stable (rustup) | Tauri qobig'i |
| FFmpeg + ffprobe | dasturchi muhitida **libass bilan** yig'ilgan istalgan versiya; relizda LGPL yig'ma | Render, ingest, subtitr (`ass` filtri) |
| Git | — | — |

**macOS:** `xcode-select --install`, so'ng `brew install python@3.12 node` va rustup; FFmpeg — pastdagi bo'limga qarang.
**Windows:** Visual Studio Build Tools ("Desktop development with C++"), WebView2 (Windows 11 da bor), Python 3.12, Node 22, rustup, FFmpeg (PATH'da; masalan `choco install ffmpeg` — gyan.dev yig'masi libass bilan).
**Linux (dev/CI):** `sudo apt-get install ffmpeg` — Debian/Ubuntu paketi libass bilan yig'ilgan.

### FFmpeg va libass

Subtitrlar ASS formatida FFmpeg'ning `ass` filtri bilan videoga yoqib yoziladi, bu filtr faqat `--enable-libass` bilan yig'ilgan FFmpeg'da bor. Tekshirish:

```bash
ffmpeg -hide_banner -filters | grep -w ass      # bo'sh bo'lsa - libass yo'q
```

* **macOS:** Homebrew'ning standart `ffmpeg` formulasi libass'siz bo'lishi mumkin (masalan, ffmpeg 9.0 bottle'ida `ass` filtri yo'q). Variantlar:
  * `brew tap homebrew-ffmpeg/ffmpeg && brew install homebrew-ffmpeg/ffmpeg/ffmpeg` (avval `brew uninstall ffmpeg`; manbadan yig'ilishi mumkin — vaqt oladi);
  * yoki o'zimizning LGPL yig'mamiz: `scripts/build_runtimes.sh` (`third_party/runtimes.toml` da `--enable-libass`; versiya R0-RT-1 da mahkamlangach ishlaydi) va `PATH` ga `app/src-tauri/resources/bin` qo'shish.
* libass bo'lmasa `engine/tests/test_render_e2e.py` dagi subtitr render testlari sababi ko'rsatilgan holda **skip** bo'ladi (`pytest -rs` bilan ko'rinadi). CI'da `LAHZA_REQUIRE_LIBASS=1` o'rnatilgan — u yerda skip emas, yiqiladi.

## 1. Engine

```bash
cd engine
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e ".[dev,onnx,fonts]"
pytest                             # FFmpeg bo'lsa render testlari ham; libass'siz bo'lsa ular skip
pytest -rs                         # skip sabablarini ko'rish
LAHZA_NO_NETWORK=1 pytest          # NFR-01: tashqi tarmoqqa urinish testni yiqitadi
ruff check src tests
```

Ixtiyoriy og'ir backendlar (faqat kerakli platformada):

```bash
pip install -e ".[vad,vision]"            # Silero VAD, MediaPipe
pip install -e ".[asr-ctranslate2]"       # faster-whisper (Windows + NVIDIA)
pip install -e ".[diarization]"           # pyannote.audio 4
```

## 2. Engine'ni server sifatida ishga tushirish

```bash
export LAHZA_DEV=1 LAHZA_TOKEN=dev-token LAHZA_CATALOG=$PWD/../catalog/catalog.json
python -m lahza_engine serve --port 8765
# boshqa terminalda:
curl -H "Authorization: Bearer dev-token" http://127.0.0.1:8765/v1/health
```

* **WebSocket.** `/v1/events` uchun uvicorn'ga `websockets` paketi kerak — u engine'ning asosiy bog'liqligi (`engine/pyproject.toml`: `websockets>=12`), alohida o'rnatish shart emas. Paket yo'q bo'lsa uvicorn WS ulanishini qabul qilmaydi va UI progress hodisalarini olmaydi. Token noto'g'ri bo'lsa ulanish `4401` kodi bilan yopiladi.
* **CORS.** Engine faqat ma'lum kelib chiqishlarga (origin) javob beradi: doim Tauri webview (`tauri://localhost`, `http(s)://tauri.localhost`); `LAHZA_DEV=1` bo'lsa Vite dev server (`http://127.0.0.1:1420`, `http://localhost:1420`). Boshqa origin kerak bo'lsa (masalan, boshqa port yoki IP), vergul bilan ajratib qo'shing: `LAHZA_CORS_ORIGINS=http://127.0.0.1:5173,http://192.168.1.10:1420`. Token baribir majburiy.

## 3. UI'ni brauzerda (Tauri'siz) ishga tushirish

```bash
cd app
npm ci
VITE_ENGINE_URL=http://127.0.0.1:8765 VITE_ENGINE_TOKEN=dev-token npm run dev
# http://127.0.0.1:1420
```

Brauzer rejimida UI to'liq ishlaydi (onboarding, galereya, klip muharriri, transkript, eksport navbati, sozlamalar), faqat Tauri'ga xos qismlar yo'q:

* fayl/papka dialogi yo'q — video, `.lzpack`, eksport va diagnostika papkasi yo'llarini maydonga qo'lda kiriting;
* engine `LAHZA_DEV=1` bilan ishga tushirilgan bo'lishi kerak (aks holda `:1420` origin CORS'dan o'tmaydi — yuqoriga qarang);
* "Papkani ochish" (`system:reveal`) engine ishlayotgan kompyuterda Finder/Explorer'ni ochadi.

## 4. To'liq desktop ilova (Tauri dev)

Tauri sidecar faylini kutadi: `app/src-tauri/binaries/lahza-engine-<target-triple>`.

```bash
python scripts/build_sidecar.py --dry-run   # triple, paket ma'lumotlari va PyInstaller buyrug'i
python scripts/build_sidecar.py             # PyInstaller -> binaries/ ga nusxa + .sha256
python scripts/build_sidecar.py --verify    # binaries/ dagi fayl xeshi mosmi
cd app && npm run tauri dev
```

Target triple `rustc -vV` dan olinadi; Rust o'rnatilmagan bo'lsa `--target aarch64-apple-darwin` bering (aks holda platformadan taxmin qilinadi va ogohlantirish chiqadi). Har buildda shu triple uchun eski sidecar o'chiriladi (NSIS eski sidecar muammosi, docs/10).

Tezroq ishlash uchun sidecar o'rniga engine'ni qo'lda ishga tushirib, UI'ni brauzerda ishlatish ham mumkin (3-qadam).

## 5. CLI bilan uchidan-uchigacha (M1)

```bash
lahza hw                                              # apparat va daraja
lahza bundle --catalog ../catalog/catalog.json         # mos model to'plami
lahza analyze podkast.mp4 --project-dir /tmp/ep1 --lite
lahza clips --project-dir /tmp/ep1
lahza export --project-dir /tmp/ep1 --clip <ID> --out ./eksport --orthography official --dev-encoder
```

`analyze` uchun o'rnatilgan ASR modeli kerak (`Models/asr/...`). R0 tugaguncha modelni qo'lda joylashtiring: `Models/installed.json` registriga yozuv qo'shish yoki katalogda `approved` yozuv yaratish (`docs/06-model-katalogi.md`).

## 6. Native runtime'lar

```bash
scripts/build_runtimes.sh        # macOS/Linux: whisper.cpp, llama.cpp, FFmpeg (LGPL)
scripts/build_runtimes.ps1       # Windows
```

Versiyalar `third_party/runtimes.toml` da; bo'sh qoldirilgan versiya bilan skript ishlamaydi (R0-RT-1 da mahkamlanadi). Natija `app/src-tauri/resources/bin/` ga tushadi.

## Makefile qisqa buyruqlari

```bash
make setup           # engine venv (dev, onnx, fonts) + npm ci
make test            # engine testlari + UI typecheck
make test-offline    # LAHZA_NO_NETWORK=1 bilan engine testlari (NFR-01)
make lint            # ruff: engine, eval, scripts
make build-ui        # tsc + vite build
make check-versions  # pyproject / package.json / Cargo.toml / tauri.conf.json versiyalari bir xilmi
make licenses        # LICENSES-THIRD-PARTY.md dagi Python va npm jadvallarini yangilash
make ci              # check-versions + lint + test-offline + build-ui (cargo check - faqat CI'da)
make sidecar-dry     # sidecar build rejasi (yig'masdan)
make dev-engine
make dev-ui
```

Windows ekvivalentlari: `.\scripts\dev.ps1 <buyruq>`.

## CI

`.github/workflows/ci.yml`: versiyalar mosligi, ruff, engine testlari (macOS 14, Windows, Ubuntu; libass'li FFmpeg `.github/actions/ffmpeg-libass` orqali), NFR-01 tarmoqsiz testlar (Ubuntu, `unshare -rn` + `LAHZA_NO_NETWORK=1`), UI typecheck + build, Tauri `cargo check --locked` (macOS, Windows), sidecar artefakti (main'ga push, qo'lda yoki PR'da `sidecar` yorlig'i bilan). Reliz: `.github/workflows/release.yml` (docs/10).

## Ma'lumotlar papkasi

| OS | Yo'l |
| --- | --- |
| macOS | `~/Library/Application Support/Lahza Studio/` |
| Windows | `%LOCALAPPDATA%\Lahza Studio\` |
| Linux (dev) | `~/.local/share/lahza-studio/` |

Ichida: `Models/<vazifa>/<model_id>/`, `Models/installed.json`, `Library/library.db`, `Library/<Shou>/<Epizod>.lahza/`, `Logs/`. `LAHZA_DATA_DIR` bilan almashtiriladi.
