# versiyalar/

Lahza Studio'ning lokal relizlari (Apple Silicon `.app`). Har yangilanish shu yerda yangi versiya sifatida qayd etiladi.

## Tuzilma

```
versiyalar/
├── README.md          # shu fayl
├── CHANGELOG.md       # versiyalar tarixi (eng yangisi tepada)
└── <versiya>/         # masalan 0.2.0/
    ├── NOTES.md       # sana, git commit, o'zgarishlar, test natijalari, build holati
    ├── SHA256SUMS     # zip va `.app/Contents/MacOS/*` xeshlari (`shasum -a 256 -c SHA256SUMS`)
    ├── Lahza Studio.app                        # ikki marta bosib ochiladi (ditto nusxa) - git'ga kirmaydi
    └── LahzaStudio-<versiya>-macos-arm64.zip   # o'sha `.app` ning ditto zip'i - git'ga kirmaydi
```

Git'ga faqat matn fayllari kiradi (`README.md`, `CHANGELOG.md`, `*/NOTES.md`, `*/SHA256SUMS`); `.app`, `.zip`, `.dmg` — `.gitignore` da.

## Ishlatish

1. Ish davomida o'zgarishlarni `CHANGELOG.md` dagi `## [Kelgusi]` bo'limiga ro'yxat qilib yozing.
2. Reliz: `make release-local V=0.3.0` (yoki `V=patch|minor|major`):
   versiya hamma manifestlarda → `make test-engine test-ui typecheck lint check-licenses` → `make build-local` →
   `versiyalar/<V>/` (`Lahza Studio.app` + `codesign --verify --deep --strict`, zip, `NOTES.md`, `SHA256SUMS`) va `[Kelgusi]` bo'limi `[<V>]` sarlavhasiga o'tadi.
3. Test yiqilsa reliz to'xtaydi. `versiyalar/<V>/` allaqachon bo'lsa — xato (ustidan yozilmaydi).
   Build yiqilsa papka "yig'ilmadi" belgisi bilan yaratiladi; tuzatgach papkani o'chirib, qayta ishga tushiring.
4. Faqat versiyani o'zgartirish: `make bump-version V=0.3.0`. Commit va `v<V>` tegi qo'lda qo'yiladi.

Ochish: `versiyalar/<V>/Lahza Studio.app` ni Finder'da ikki marta bosing (yoki `open "versiyalar/<V>/Lahza Studio.app"`). Boshqa Mac'ga o'rnatish: `ditto -x -k LahzaStudio-<V>-macos-arm64.zip /Applications`. Binar ad-hoc imzolangan (notarizatsiyasiz) — faqat lokal sinov uchun; rasmiy reliz tartibi: `docs/10-reliz-va-imzolash.md`.
