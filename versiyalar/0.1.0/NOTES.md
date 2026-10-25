# Lahza Studio 0.1.0 (tarixiy yozuv)

- **Davr:** 2026-10-16 … 2026-10-25
- **Git commitlar:** `b8e8b1c` → `2aa5587` (versiya raqami hamma manifestlarda `0.1.0`)
- **Binar:** saqlanmagan — bu yozuv `versiyalar/` tizimidan oldingi holat uchun.

## O'zgarishlar

- **`b8e8b1c` (2026-10-16) — R0-ORG-3, boshlang'ich holat:** engine (VAD, CTC aligner, yuz aniqlash, tinish tiklagich, docs/04 API, DB v2, `.lzpack`, subtitr shablonlari), UI (transkript muharriri, timeline, eksport navbati, model menejeri, 4 til), CI/reliz skriptlari.
- **`6e96fa5` (2026-10-20) — RCP-1, MNT-1..3, FX-1..5, TL-1..3:** Lahza Timeline, 6 ta video shablon, 22 ta fx plagin, avtomatik montaj va 2 bosqichli render, library DB v3.
- **`d7ba061` (2026-10-23) — ADB-1..6:** Premiere Pro va After Effects plaginlari, engine discovery va fayl-IPC, host-reja.
- **`2aa5587` (2026-10-25) — lokal alfa:** AI montaj yordamchisi (lokal Qwen3), stikerlar, caption/SRT import, undo/redo, eksport profillari, `.lahzaskill`, lokal modellar bootstrap, LGPL FFmpeg, Mac `.app` (`make build-local`).

## Testlar (commit xabarlaridan)

| Commit | Natija |
|---|---|
| `b8e8b1c` | 207 test (2 skip) |
| `6e96fa5` | 327 test (2 skip) |
| `d7ba061` | engine 374, Premiere 26, AE 35 |
| `2aa5587` | engine 640 passed / 8 skipped, UI 68, Adobe 26 + 35 |
