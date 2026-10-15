# ADR-0008: Ichki saqlash rasmiy imloda, o'girish faqat render paytida

* Holat: Qabul qilindi
* Sana: 2026-10-14
* TZ bo'limi: 9

## Kontekst
ASR va klaviaturalar apostrofning turli variantlarini chiqaradi. 2026-yil sentabrda Senat yangi alifboni (Ö, Ğ, Ş, Ç) ma'qulladi; kuchga kirish sanasi noma'lum.

## Qaror
Barcha matn ichkarida rasmiy amaldagi imloda saqlanadi: oʻ/gʻ uchun U+02BB, tutuq uchun U+02BC (`text/orthography.py: normalize`). "Rasmiy", "ASCII" va "Yangi alifbo" — faqat ko'rsatish/render rejimlari (`convert`).

## Oqibatlar
* Qidiruv, lug'at, qoidalar bitta ko'rinishda ishlaydi (`fold_for_match`).
* Yangi alifbo qoidalari qonun matni e'lon qilingach qayta tekshiriladi (TZ 19-bo'lim).
