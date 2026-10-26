# Lahza Studio 0.2.2

- **Sana:** 2026-10-26 01:08 +05
- **Git commit:** `ce4bc2fec42b` (0.2.1: hook oldinga, kirill subtitr, navbat, YouTube import, litsenziyalar, versiyalar) + commit qilinmagan o'zgarishlar (working tree toza emas)
- **Platforma:** macOS 27.0.1, arm64
- **Oldingi versiya:** 0.2.1

## O'zgarishlar

- **Tuzatish — YouTube import eksporti:** yt-dlp AV1 formatni tanlardi, bundled LGPL FFmpeg esa AV1'ni dekodlay olmaydi → eksport 69 kodi bilan yiqilardi. Endi avc1 (H.264) → vp9 tartibida tanlanadi; 0.2.1 da yuklangan AV1 nusxalar bir marta avtomatik qayta yuklanadi (`media/youtube.py`, `MARKER_VERSION = 2`). Jonli sinov: https://youtu.be/prxGMABkASI — yuklash, tahlil, lotin/kirill eksport, hook.
- **Tuzatish — dekodlanmaydigan kodek:** import paytida birinchi kadr dekodlab tekshiriladi; AV1 fayllar epizod yaratilishidan oldin tushunarli `unsupported_codec` xatosi bilan rad etiladi (4 tilda), render ham xom ffmpeg logi o'rniga shu kodni qaytaradi (`media/codec_check.py`).
- **Tuzatish — chala MP4:** muvaffaqiyatsiz render eksport papkasida buzuq fayl qoldirmaydi (`render/graph.py`).
- **Tuzatish — hook subtitri:** subtitr kartochkalari hook prefiksi oxirida majburan bo'linadi (SRT, VTT, ASS, host caption) — hook matni klip boshidagi matn bilan bitta kartochkaga qo'shilmaydi (`subtitle/layout.py`, `subtitle/ass.py`).

## Testlar

| Tekshiruv | Natija |
|---|---|
| `make test-engine` | 868 passed, 8 skipped (43 s) |
| `make test-ui` | 95 passed, 0 failed (1 s) |
| `make typecheck` | ok (1 s) |
| `make lint` | ok (0 s) |
| `make check-licenses` | ok (0 s) |

## Binar

- `make build-local`: muvaffaqiyatli (1.1 daqiqa)
- `Lahza Studio.app`: 213.3 MB - shu papkada, ikki marta bosib ochiladi (ad-hoc imzo, notarizatsiyasiz - faqat lokal sinov; `codesign --verify --deep --strict`: ok)
- `LahzaStudio-0.2.2-macos-arm64.zip`: 136.2 MB - o'sha `.app` ning `ditto` arxivi (boshqa Mac'ga ko'chirish uchun; ochish: `ditto -x -k <zip> /Applications`)
- Xeshlar: `SHA256SUMS` (zip va `.app/Contents/MacOS/*`)
- Birinchi ochishda Gatekeeper to'xtatsa: o'ng tugma -> Open.
- Binar git'ga kirmaydi (`.gitignore`).
