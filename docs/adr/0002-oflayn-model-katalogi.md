# ADR-0002: Modellarsiz o'rnatish, imzolangan katalogdan avtomatik to'plam

* Holat: Qabul qilindi
* Sana: 2026-10-14
* TZ bo'limi: 2, 13

## Kontekst
Modellar bir necha GB; ular dastur yangilanganda qayta yuklanmasligi kerak. Kompyuterlar keskin farq qiladi (8 GB M1 dan 24 GB VRAM'li NVIDIA'gacha). Foydalanuvchi texnik qaror qabul qilishi shart emas.

## Qaror
Dastur modellarsiz o'rnatiladi. Birinchi ishga tushishda apparat testi o'tkaziladi va dastur imzolangan katalogdan shu kompyuterga mos **to'liq to'plamni** (ASR, alignment, VAD, diarizatsiya, ko'rish, LLM) o'zi tanlab yuklaydi. Avto-tanlov faqat R0 baholashidan o'tgan (`status: approved`, sha256 ma'lum) yozuvlardan. ASR yuklanmaguncha import yopiq; LLM yo'q bo'lsa highlight Lite rejimda ishlaydi. Internetsiz kompyuter uchun `.lzpack` (model + manifest + imzo) USB orqali.

## Oqibatlar
* Katalog — mahsulotning bir qismi: har model qo'shilishi R0 jarayonidan o'tadi (`docs/06-model-katalogi.md`).
* Katalog Ed25519 bilan imzolanadi; ochiq kalit ilovaga build vaqtida kiritiladi.
* Tarmoqqa faqat foydalanuvchi roziligi bilan (`consent: true`) murojaat qilinadi (NFR-01).

## Ko'rib chiqilgan muqobillar
| Variant | Nega tanlanmadi |
| --- | --- |
| Modellarni o'rnatuvchiga qo'shish | O'rnatuvchi juda katta; har yangilanishda qayta yuklash |
| Foydalanuvchi o'zi URL beradi | Sifat va xavfsizlik kafolati yo'q — faqat yashirin ilg'or sozlama sifatida qoldirildi |
