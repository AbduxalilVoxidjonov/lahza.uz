# ADR-0009: Dinamik kadr uchun FFmpeg `sendcmd` + `crop`

* Holat: Qabul qilindi
* Sana: 2026-10-14
* TZ bo'limi: 8, 10

## Kontekst
Kamera yo'li vaqt bo'yicha o'zgaradi. Kadrlarni Python'da qayta ishlab FFmpeg'ga uzatish sekin va xotira talab qiladi.

## Qaror
Har render bo'lagi uchun `sendcmd` fayli yoziladi: `<vaqt> crop@cN x <px>, crop@cN y <px>;`. Silliq yo'l kalit kadrlar orasida kadr qadamida interpolyatsiya qilinadi (`render/graph.py: densify`); keskin kesimlar interpolyatsiya qilinmaydi. Barcha fayllar ish papkasida, ffmpeg shu papkada (`cwd`) ishga tushadi — Windows yo'llarini filtergraph'da ekranlash muammosi yo'q. FFmpeg ≥ 7 da `-/filter_complex`, oldingisida `-filter_complex_script`.

## Oqibatlar
* Haqiqiy FFmpeg bilan uch layout + kesimlar + subtitr testlangan (`tests/test_render_e2e.py`).
* Zoom (crop o'lchamini o'zgartirish) keyingi bosqichda: hozircha `w/h` doimiy.
