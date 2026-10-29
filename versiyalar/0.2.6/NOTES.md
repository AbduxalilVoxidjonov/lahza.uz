# Lahza Studio 0.2.6

- **Sana:** 2026-10-29 20:49 +05
- **Git commit:** `9a64be5fec9b` (Ilova yopilishi: qayta ishga tushirish kill bilan poygalashmaydi) + commit qilinmagan o'zgarishlar (working tree toza emas)
- **Platforma:** macOS 27.0.1, arm64
- **Oldingi versiya:** 0.2.5

## O'zgarishlar

- **Tuzatish — YouTube havolasi topilmasdi:** havola maydoni faqat Loyihalar sahifasida, loyiha tanlangandan keyin chiqardi. Endi u Boshlash sahifasining 1-qadamida, fayl tanlash bilan yonma-yon turadi; chap menyuda "YouTube havolasi" bandi bor. Loyiha so'ralmaydi (avtomatik "YouTube" loyihasi), yuklangan video montaj manbasiga o'zi qo'shiladi; playlist/kanal tanlash va komponent o'rnatish shu joyning o'zida.

## Testlar

| Tekshiruv | Natija |
|---|---|
| `make test-engine` | 1351 passed, 13 skipped, 2 deselected (155 s) |
| `make test-ui` | 136 passed, 0 failed (1 s) |
| `make typecheck` | ok (2 s) |
| `make lint` | ok (0 s) |
| `make check-licenses` | ok (0 s) |

## Binar

- `make build-local`: muvaffaqiyatli (1.3 daqiqa)
- `Lahza Studio.app`: 188.5 MB - shu papkada, ikki marta bosib ochiladi (ad-hoc imzo, notarizatsiyasiz - faqat lokal sinov; `codesign --verify --deep --strict`: ok)
- `LahzaStudio-0.2.6-macos-arm64.zip`: 110.7 MB - o'sha `.app` ning `ditto` arxivi (boshqa Mac'ga ko'chirish uchun; ochish: `ditto -x -k <zip> /Applications`)
- Xeshlar: `SHA256SUMS` (zip va `.app/Contents/MacOS/*`)
- Birinchi ochishda Gatekeeper to'xtatsa: o'ng tugma -> Open.
- Binar git'ga kirmaydi (`.gitignore`).
