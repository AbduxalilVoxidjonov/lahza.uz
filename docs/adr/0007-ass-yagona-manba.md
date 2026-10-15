# ADR-0007: Subtitr uchun yagona manba — ASS fayl

* Holat: Qabul qilindi
* Sana: 2026-10-14
* TZ bo'limi: 9

## Kontekst
Preview va eksport subtitri farq qilsa, foydalanuvchi ekranda ko'rganini olmaydi.

## Qaror
Subtitr ASS (PlayRes 1080×1920) sifatida bir marta yaratiladi (`subtitle/ass.py`) va render paytida libass (`ass` filtri) bilan chiziladi. Preview uchun M2'da libass WASM yoki engine preview kadrlari tanlanadi. Karaoke — har so'z faol bo'lgan oraliq uchun alohida Dialogue qatori.

## Oqibatlar
* Ishlab chiqarish FFmpeg yig'masida `--enable-libass` majburiy.
* Shriftlar ilova bilan yetkaziladi (`fontsdir`), glif testi bilan (M3-SUB-3).
