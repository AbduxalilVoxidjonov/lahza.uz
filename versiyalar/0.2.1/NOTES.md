# Lahza Studio 0.2.1

- **Sana:** 2026-10-26 00:31 +05
- **Git commit:** `2aa5587ec31e` (Lokal alfa: AI montaj yordamchisi, stikerlar, skill'lar, Mac .app) + commit qilinmagan o'zgarishlar (working tree toza emas)
- **Platforma:** macOS 27.0.1, arm64
- **Oldingi versiya:** 0.2.1

## O'zgarishlar

- **Tuzatish — yetim `lahza-engine serve` jarayonlari:** ilova yopilgandan keyin engine endi qolmaydi. Sabab: Tauri faqat PyInstaller bootloader'ini SIGKILL qilardi (Python bolasi yetim qolardi) va `/v1/events` WebSocket handler'i uzilishni sezmay SIGTERM'dagi to'xtashni abadiy to'sardi. Endi: jarayon guruhiga SIGTERM → 2,5 s → SIGKILL (`engine.rs`), engine'da tez to'xtash + majburiy `os._exit` + bola jarayonlarni o'ldirish, ota jarayon watchdog'i (`--parent-pid`, `--watch-stdin`; `core/lifecycle.py`). Batafsil: `docs/01-arxitektura.md` "Engine hayot sikli".

## Testlar

| Tekshiruv | Natija |
|---|---|
| `make test-engine` | 842 passed, 8 skipped (42 s) |
| `make test-ui` | 91 passed, 0 failed (1 s) |
| `make typecheck` | ok (1 s) |
| `make lint` | ok (0 s) |
| `make check-licenses` | ok (0 s) |

## Binar

- `make build-local`: muvaffaqiyatli (1.1 daqiqa)
- `Lahza Studio.app`: 213.3 MB - shu papkada, ikki marta bosib ochiladi (ad-hoc imzo, notarizatsiyasiz - faqat lokal sinov; `codesign --verify --deep --strict`: ok)
- `LahzaStudio-0.2.1-macos-arm64.zip`: 136.2 MB - o'sha `.app` ning `ditto` arxivi (boshqa Mac'ga ko'chirish uchun; ochish: `ditto -x -k <zip> /Applications`)
- Xeshlar: `SHA256SUMS` (zip va `.app/Contents/MacOS/*`)
- Birinchi ochishda Gatekeeper to'xtatsa: o'ng tugma -> Open.
- Binar git'ga kirmaydi (`.gitignore`).
