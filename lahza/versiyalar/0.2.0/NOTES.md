# Lahza Studio 0.2.0

- **Sana:** 2026-10-26 00:09 +05
- **Git commit:** `2aa5587ec31e` (Lokal alfa: AI montaj yordamchisi, stikerlar, skill'lar, Mac .app) + commit qilinmagan o'zgarishlar (working tree toza emas)
- **Platforma:** macOS 27.0.1, arm64
- **Oldingi versiya:** 0.1.0

## O'zgarishlar

- **PRO-3 — hook oldinga:** klipning eng kuchli 2–4 soniyalik jumlasi klip boshiga qo'yiladi (`highlight/hook_front.py`, keshdagi signallar, ~0,5 ms/klip). Hostplan va montaj manbasi hook'ni hali hisobga olmaydi.
- **PRO-4 — kirill subtitr:** lug'atli lotin → kirill transliteratsiya (`text/translit.py`, `text/data/cyrillic.json`), uslub sozlamasida yozuv tanlovi. Qolgani: lug'atni tilshunos ko'rib chiqishi.
- **PRO-5 — partiyaviy tahlil navbati:** bir nechta epizod navbatda (`core/batch.py`, `/v1/queue` API, `lahza batch` CLI, UI navbat paneli).
- **YT-1 — YouTube havolasidan import:** `media/youtube.py`, ixtiyoriy `make setup-youtube`; standart holatda **o'chiq** — yurist xulosasi kutilmoqda (ADR-0010).
- **V1-5 — litsenziyalar oynasi:** "Sozlamalar → Litsenziyalar", `make licenses` / `make check-licenses` (`LICENSES-THIRD-PARTY.md` + `app/src/generated/licenses.json`, oflayn). Qolgani: ANIQLANSIN yozuvlari (asosan Windows crate'lari).
- **Reliz:** `versiyalar/` papkasi, `make bump-version`, `make release-local` (`scripts/release_local.py`).

## Testlar

| Tekshiruv | Natija |
|---|---|
| `make test-engine` | 835 passed, 8 skipped (39 s) |
| `make test-ui` | 91 passed, 0 failed (1 s) |
| `make typecheck` | ok (1 s) |
| `make lint` | ok (0 s) |
| `make check-licenses` | ok (0 s) |

## Binar

- `make build-local`: muvaffaqiyatli (1.2 daqiqa)
- `Lahza Studio.app`: 213.3 MB - shu papkada, ikki marta bosib ochiladi (ad-hoc imzo, notarizatsiyasiz - faqat lokal sinov; `codesign --verify --deep --strict`: ok)
- `LahzaStudio-0.2.0-macos-arm64.zip`: 136.2 MB - o'sha `.app` ning `ditto` arxivi (boshqa Mac'ga ko'chirish uchun; ochish: `ditto -x -k <zip> /Applications`)
- Xeshlar: `SHA256SUMS` (zip va `.app/Contents/MacOS/*`)
- Birinchi ochishda Gatekeeper to'xtatsa: o'ng tugma -> Open.
- Binar git'ga kirmaydi (`.gitignore`).
