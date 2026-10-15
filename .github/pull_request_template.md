<!-- Sarlavha: `<ID>: nima o'zgardi` (ID - docs/02-yol-xaritasi.md dan). Bitta PR - bitta vazifa. -->

## Vazifa

ID: <!-- masalan M1-ASR-1 -->
Branch: `feature/<ID>-qisqa-nom`

## Nima o'zgardi va nega

<!-- Qisqacha. Foydalanuvchiga ko'rinadigan o'zgarish bo'lsa - skrinshot. -->

## Qanday tekshirildi

<!-- Buyruqlar va natija. Tekshirilmagan narsa bo'lsa - shu yerda aytilsin. -->

## PR tekshiruvi (CONTRIBUTING.md)

- [ ] Testlar qo'shilgan yoki yangilangan; `make test` yashil
- [ ] `make lint` toza
- [ ] Engine API o'zgarsa: `docs/04-engine-api.md` va `app/src/api/types.ts` yangilangan
- [ ] Sxema o'zgarsa: `db/store.py` da `SCHEMA_VERSION` va `MIGRATIONS`
- [ ] Bosqich mantig'i o'zgarsa: `StageDef.version` oshirilgan (kesh to'g'ri bekor bo'lishi uchun)
- [ ] Muhim arxitektura qarori bo'lsa: yangi ADR (`docs/adr/`)
- [ ] Yangi bog'liqlik bo'lsa: litsenziyasi `LICENSES-THIRD-PARTY.md` da (`python scripts/gen_licenses.py`)
- [ ] Hech qanday raqam yoki versiya taxmin qilinmagan: manbasi yo'q qiymat `ANIQLANSIN` yoki "R0" deb belgilangan
- [ ] Yo'l xaritasidagi katakcha shu PR'da `[x]` qilingan

## Maxfiylik (NFR-01, NFR-02)

- [ ] Loglarga transkript matni yozilmaydi
- [ ] Yangi tarmoq so'rovi yo'q (bo'lsa - ADR havolasi: )
- [ ] `eval/data/` dagi audio/video PR'ga kirmagan
