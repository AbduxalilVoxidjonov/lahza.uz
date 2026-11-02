# ADR-0011: Montaj plaginlari — kod emas, ma'lumot (deklarativ manifest)

* Holat: Qabul qilindi (2026-10-20; `fx/` — `lahza.fx/1`, 22 o'rnatilgan plagin, oq ro'yxat; `.lzfx` paket keyin)
* Sana: 2026-10-18
* TZ bo'limi: [`11-montaj-platformasi.md`](../11-montaj-platformasi.md) 5, 11

## Kontekst

Lahza'ga o'tishlar, kamera harakatlari, rang, matn, overlay, audio va tezlik plaginlari kerak. Ularni rasmiy jamoa ham, foydalanuvchi va tashqi mualliflar ham qo'shishi kerak bo'ladi. Bu bilan birga quyidagi talablar bajarilishi shart:

* xavfsizlik: hozir model ombori bajariladigan fayllarni rad etadi (`models/store.py`);
* faqat LGPL FFmpeg ([ADR-0004](0004-lgpl-ffmpeg-apparat-enkoder.md));
* preview va eksportning bir xilligi;
* macOS va Windows'da bir xil natija.

## Qaror

* **Plagin = JSON manifest + resurslar.** Resurslar: LUT, Lottie, PNG, WebM preview, SFX. Paket fayli — `.lzfx` (zip), ichida `SHA256SUMS` bo'ladi.
* **Bajariladigan kod yo'q.** Paketda skript, kutubxona yoki exe bo'lmaydi; GLSL shader faqat imzolangan paketda, `glsl` backend paydo bo'lgandan keyin.
* **Graf kompilyatori engine'da.** Effektni engine'ning o'z backendlari FFmpeg grafiga aylantiradi: `motion-keys`, `xfade`, `lut`, `ass-text`, `lottie`, `audio-graph`.
* **Oq ro'yxat.** Manifestda faqat ruxsat etilgan filtrlar va parametr turlari bo'ladi. Fayl o'qiydigan filtrlar va FFmpeg `configure` faylida faqat GPL bilan ishlaydigan deb belgilangan filtrlar ro'yxatga kirmaydi. CI buni tekshiradi.
* **Imzo.** Rasmiy paketlar katalog kaliti (Ed25519) bilan imzolanadi. Imzosiz paket "tekshirilmagan" belgisi bilan qabul qilinadi, lekin baribir sxema, oq ro'yxat, hajm chegarasi va zip-slip tekshiruvidan o'tadi.
* **Retsept** (`lahza.recipe/1`) — plaginlar va trigger'lar ketma-ketligi. U ham faqat ma'lumot.

## Oqibatlar

* Plagin tizimni buza olmaydi. Uning eng yomon ta'siri — noto'g'ri yoki xunuk effekt.
* Murakkab effektlar (zarrachalar, 3D) faqat backend qo'shilganda paydo bo'ladi. Bu ataylab qo'yilgan cheklov.
* AE, Premiere va DaVinci'ning tayyor plaginlarini (`.aex`, OFX va boshqalar) Lahza ichida ishlatib bo'lmaydi. Ular montaj dasturining o'zida, Lahza eksportidan keyin qo'llanadi.
* Manifest sxemasi versiyalanadi (`lahza.fx/1`) va migratsiya qoidalari bilan o'zgaradi.

## Ko'rib chiqilgan muqobillar

| Variant | Nega tanlanmadi |
| --- | --- |
| Python plaginlar (ixtiyoriy kod) | Xavfsizlik, sidecar barqarorligi, imzo zanjiri murakkabligi |
| OpenFX host bo'lish | Native plagin yuklash = bajariladigan kod; har platforma uchun alohida binar; uchinchi tomon plaginlarining litsenziya shartlari Lahza nazoratida emas |
| frei0r | FFmpeg'da `frei0r` GPL ro'yxatida ([LICENSE.md](https://github.com/FFmpeg/FFmpeg/blob/master/LICENSE.md)) |
