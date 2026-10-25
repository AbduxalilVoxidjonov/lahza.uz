# O'zbek imlosi

Kod: `engine/src/lahza_engine/text/orthography.py`, testlar: `engine/tests/test_orthography.py`.

## Belgilar

| Belgi | Kod | Ishlatilishi |
| --- | --- | --- |
| ʻ | U+02BB MODIFIER LETTER TURNED COMMA | Oʻ, Gʻ — rasmiy yagona to'g'ri variant ([manba](https://en.wikipedia.org/wiki/O%CA%BB)) |
| ʼ | U+02BC MODIFIER LETTER APOSTROPHE | Tutuq belgisi: maʼno, taʼlim |
| ‘ ’ | U+2018, U+2019 | O'zbek lotinida qo'shtirnoq vazifasini bajaradi — harf sifatida ishlatilmaydi |

## Normallashtirish (`normalize`)

1. Unicode NFC.
2. `o / O / g / G` dan keyingi har qanday apostrof varianti (`' ` ‘ ’ ʻ ʼ ´ ʹ`) → `ʻ` (U+02BB).
3. Ikki harf orasidagi qolgan apostrof variantlari → `ʼ` (U+02BC).
4. So'z chegarasidagi apostroflar (qo'shtirnoq) o'zgarmaydi.

Funksiya idempotent: ikki marta qo'llash natijani o'zgartirmaydi.

## Ko'rsatish rejimlari (`convert`)

| Rejim | Misol | Qachon |
| --- | --- | --- |
| `official` | oʻzbek, togʻ, maʼno | Standart; ichki saqlash shu ko'rinishda |
| `ascii` | o'zbek, tog', ma'no | Ijtimoiy tarmoqlarda keng tarqalgan, har qanday shriftda chiqadi |
| `new` | özbek, toğ, şahar, çiroy | Yangi alifbo |

## Yangi alifbo

Senat 2026-yil 10-sentabrda qonunni ma'qulladi: alifbo 26 harf va 3 harf birikmasi o'rniga 28 harf va 1 tutuq belgisidan iborat bo'ladi; Gʻ → Ğ, Oʻ → Ö, Sh → Ş, Ch → Ç ([gov.uz](https://gov.uz/oz/cirns/news/view/217333)). Qonun loyihasiga ko'ra "ng" alifbodan chiqariladi ([kun.uz](https://kun.uz/news/2026/07/07/ozbekistonda-alifbo-islohoti-boyicha-qonun-qabul-qilindi-4cf07b)). Kuchga kirish sanasi — ANIQLANSIN.

O'girish qoidalari:

* `oʻ → ö`, `Oʻ → Ö`, `gʻ → ğ`, `Gʻ → Ğ`
* `sh → ş`, `Sh / SH → Ş`, `ch → ç`, `Ch / CH → Ç`
* Tutuq bilan ajratilgan `sʼh` (masalan, Isʼhoq) digraf emas — o'zgarmaydi.
* "ng" yozuvda o'zgarmaydi (u harf sifatida chiqariladi, lekin `n` + `g` qoladi).

Qonun matni rasmiy e'lon qilingach, bu qoidalar uning matni bo'yicha qayta tekshiriladi va testlar yangilanadi.

## Kirill (Pro)

Lotin → kirill o'girish lug'at bilan (e/э, ц, ё, ю, я kabi bir ma'noli bo'lmagan holatlar uchun) — PRO-4.

Kod: `engine/src/lahza_engine/text/translit.py`, lug'at: `text/data/cyrillic.json`, testlar: `engine/tests/test_translit.py`. Subtitr uslubida `script: "latin" | "cyrillic"` (standart `latin`); eksport/preview so'rovida ham `script` bilan almashtirish mumkin. Kirill tanlansa imlo rejimi e'tiborga olinmaydi.

* `oʻ→ў`, `gʻ→ғ`, `sh→ш`, `ch→ч`, `q→қ`, `h→ҳ`, `x→х`, `j→ж`, `y→й`; `ng → нг`.
* `ye/yo/yu/ya → е/ё/ю/я`, lekin `yoʻ → йў` (yoʻl → йўл).
* `e` so'z boshida va unlidan keyin → `э`, qolgan joyda → `е`.
* `ts` so'z boshida/oxirida va `tsi`+unli oldidan → `ц` (operatsiya → операция); boshqa joyda `т+с` (ketsa → кетса).
* Tutuq `ʼ → ъ` (maʼno → маъно); `sʼh`/`cʼh` dagi tutuq tushadi (Isʼhoq → Исҳоқ).
* Lug'at: `words` — butun so'z (sentyabr → сентябрь), `stems` — so'z boshi, qo'shimchalar umumiy qoida bilan (obyektlar → объектлар), `keep` — o'girilmaydigan nomlar. `CyrillicLexicon.merged()` / `load_lexicon(extra=...)` bilan kengaytiriladi.
* URL, e-pochta, `@nom`, raqamlar va lotin brendlar (c/w yoki o'zbek lotinida yo'q harfli, ichida katta harfli — iPhone, YouTube) o'zgarmaydi.

## Shrift talabi

Dastur bilan yetkaziladigan har shrift quyidagi gliflarni o'z ichiga olishi shart (`REQUIRED_GLYPHS`): `ʻ ʼ Ö ö Ğ ğ Ş ş Ç ç Ў ў Қ қ Ғ ғ Ҳ ҳ`. Testdan o'tmagan shrift ro'yxatda ko'rsatilmaydi (M3-SUB-3).
