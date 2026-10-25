# O'zgarishlar tarixi

Eng yangisi tepada. Keyingi reliz o'zgarishlari `## [Kelgusi]` bo'limiga yoziladi —
`make release-local V=x.y.z` ularni versiya sarlavhasiga o'tkazadi.

## [Kelgusi]

## [0.2.1] — 2026-10-26

- **Tuzatish — yetim `lahza-engine serve` jarayonlari:** ilova yopilgandan keyin engine endi qolmaydi. Sabab: Tauri faqat PyInstaller bootloader'ini SIGKILL qilardi (Python bolasi yetim qolardi) va `/v1/events` WebSocket handler'i uzilishni sezmay SIGTERM'dagi to'xtashni abadiy to'sardi. Endi: jarayon guruhiga SIGTERM → 2,5 s → SIGKILL (`engine.rs`), engine'da tez to'xtash + majburiy `os._exit` + bola jarayonlarni o'ldirish, ota jarayon watchdog'i (`--parent-pid`, `--watch-stdin`; `core/lifecycle.py`). Batafsil: `docs/01-arxitektura.md` "Engine hayot sikli".

Tafsilotlar: [`0.2.1/NOTES.md`](0.2.1/NOTES.md)

## [0.2.0] — 2026-10-26

- **PRO-3 — hook oldinga:** klipning eng kuchli 2–4 soniyalik jumlasi klip boshiga qo'yiladi (`highlight/hook_front.py`, keshdagi signallar, ~0,5 ms/klip). Hostplan va montaj manbasi hook'ni hali hisobga olmaydi.
- **PRO-4 — kirill subtitr:** lug'atli lotin → kirill transliteratsiya (`text/translit.py`, `text/data/cyrillic.json`), uslub sozlamasida yozuv tanlovi. Qolgani: lug'atni tilshunos ko'rib chiqishi.
- **PRO-5 — partiyaviy tahlil navbati:** bir nechta epizod navbatda (`core/batch.py`, `/v1/queue` API, `lahza batch` CLI, UI navbat paneli).
- **YT-1 — YouTube havolasidan import:** `media/youtube.py`, ixtiyoriy `make setup-youtube`; standart holatda **o'chiq** — yurist xulosasi kutilmoqda (ADR-0010).
- **V1-5 — litsenziyalar oynasi:** "Sozlamalar → Litsenziyalar", `make licenses` / `make check-licenses` (`LICENSES-THIRD-PARTY.md` + `app/src/generated/licenses.json`, oflayn). Qolgani: ANIQLANSIN yozuvlari (asosan Windows crate'lari).
- **Reliz:** `versiyalar/` papkasi, `make bump-version`, `make release-local` (`scripts/release_local.py`).

Tafsilotlar: [`0.2.0/NOTES.md`](0.2.0/NOTES.md)

## [0.1.0] — 2026-10-16 … 2026-10-25

Tarixiy yozuv (binarsiz; versiya raqami bu davrda o'zgarmagan). Tafsilotlar: [`0.1.0/NOTES.md`](0.1.0/NOTES.md)

- `2aa5587` (2026-10-25) — Lokal alfa: AI montaj yordamchisi (lokal Qwen3 GGUF), stikerlar, `.lahzaskill` retseptlari, Mac `.app`.
- `d7ba061` (2026-10-23) — ADB-1..6: Premiere Pro (UXP) va After Effects (CEP) plaginlari.
- `6e96fa5` (2026-10-20) — RCP-1, MNT-1..3, FX-1..5, TL-1..3: video shablonlar va avtomatik montaj.
- `b8e8b1c` (2026-10-16) — R0-ORG-3: boshlang'ich holat — M1/M2/M3 kod darajasida.
