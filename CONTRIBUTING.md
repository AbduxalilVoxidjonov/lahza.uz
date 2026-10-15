# Hissa qo'shish tartibi

## Branch va commit

* `main` — har doim yashil (CI o'tadi). Ish `feature/<ID>-qisqa-nom` branchlarida, masalan `feature/M1-ASR-1-whisper-cpp`.
* Commit xabari: `<ID>: nima o'zgardi` — ID `docs/02-yol-xaritasi.md` dan.
* Har PR bitta vazifa; yo'l xaritasidagi katakcha shu PR'da `[x]` qilinadi.

## PR tekshiruvi

Ro'yxat `.github/pull_request_template.md` da avtomatik chiqadi. Push'dan oldin lokal: `make ci` (Windows: `.\scripts\dev.ps1 ci`).

- [ ] Testlar qo'shilgan yoki yangilangan; `make test` yashil
- [ ] `make lint` toza
- [ ] Engine API o'zgarsa: `docs/04-engine-api.md` va `app/src/api/types.ts` yangilangan
- [ ] Sxema o'zgarsa: `db/store.py` da `SCHEMA_VERSION` va `MIGRATIONS`
- [ ] Bosqich mantig'i o'zgarsa: `StageDef.version` oshirilgan (kesh to'g'ri bekor bo'lishi uchun)
- [ ] Muhim arxitektura qarori bo'lsa: yangi ADR (`docs/adr/`)
- [ ] Yangi bog'liqlik bo'lsa: litsenziyasi `LICENSES-THIRD-PARTY.md` da (`make licenses`)
- [ ] Hech qanday raqam yoki versiya taxmin qilinmagan: manbasi yo'q qiymat `ANIQLANSIN` yoki "R0" deb belgilangan

Xato va takliflar: `.github/ISSUE_TEMPLATE/` shakllari (bug, taklif). Issue'ga video, audio yoki transkript matnini biriktirmang.

## Kod uslubi

| Til | Vosita | Qoida |
| --- | --- | --- |
| Python | ruff (`engine/pyproject.toml`) | 100 belgi, type hint'lar, pydantic modellar |
| TypeScript | `tsc --strict` | `noUncheckedIndexedAccess`, komponentlar kichik, server holati TanStack Query'da |
| Rust | rustfmt, clippy | `unwrap()` faqat testlarda |

Kod izohlari va foydalanuvchiga ko'rinadigan matnlar o'zbekcha (lotin); identifikatorlar inglizcha. Foydalanuvchi matnlari faqat `app/src/i18n/` lug'atlari orqali.

## Maxfiylik qoidalari

* Loglarga transkript matni yozilmaydi (NFR-02).
* Yangi tarmoq so'rovi qo'shish — faqat ADR bilan (NFR-01).
* `eval/data/` dagi audio/video repozitoriyga kirmaydi.
