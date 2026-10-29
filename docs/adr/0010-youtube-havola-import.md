# ADR-0010: YouTube havolasidan import — yagona foydalanuvchi boshlaydigan tarmoq amali

* Holat: Qabul qilindi (amalga oshirilgan, standart yoqilgan — 2026-10-28 egasi qarori)
* Sana: 2026-10-18
* TZ bo'limi: [`11-montaj-platformasi.md`](../11-montaj-platformasi.md) 3.2, 12; NFR-01

## Kontekst

Talab: video faylini yuklash bilan bir qatorda YouTube havolasini berib ham Reels olish. Lahza esa oflayn dastur, va yangi tarmoq so'rovi faqat ADR orqali qo'shiladi (`CONTRIBUTING.md`, NFR-01).

Bu qarorga ta'sir qiluvchi tekshirilgan faktlar:

* **YouTube shartlari.** Kontentni Servis aniq ruxsat bermagan yoki egalar oldindan yozma ruxsat bermagan holda yuklab olish taqiqlanadi. Avtomatlashtirilgan vositalar bilan kirish ham taqiqlanadi ([Terms](https://www.youtube.com/static?template=terms)).
* **YouTube Studio orqali rasmiy yuklab olish** mavjud: MP4, 720p yoki 360p, 24 soatda 5 martagacha ([Google yordam](https://support.google.com/youtube/answer/56100)).
* **yt-dlp litsenziyasi.** PyPI paketi Unlicense ostida. Rasmiy PyInstaller exe'lari esa GPLv3+ kodni o'z ichiga oladi ([yt-dlp](https://github.com/yt-dlp/yt-dlp)).
* **JavaScript runtime.** 2025.11.12 dan boshlab YouTube'ni to'liq qo'llash uchun `yt-dlp-ejs` va JavaScript runtime kerak. Tavsiya etilgani Deno, kamida 2.3.0 versiya ([EJS wiki](https://github.com/yt-dlp/yt-dlp/wiki/EJS)).

## Qaror

1. **Funksiya standart holatda o'chiq.** Sozlamalarda yoqiladi. Har importda foydalanuvchi huquqni tasdiqlaydi ("menga tegishli yoki ruxsatim bor") va YouTube shartlari haqidagi ogohlantirishni qabul qiladi. API'da `consent: true` maydoni majburiy. *(2026-10-28 da o'zgardi — [Yangilanish](#yangilanish-2026-10-28))*
2. **Komponentlar katalogdan olinadi.** `yt-dlp` (PyPI paketi), `yt-dlp-ejs` va Deno ilovaga qo'shilmaydi. Ular katalogdan **komponent** sifatida (imzo, sha256) birinchi ishlatishda yuklanadi va katalog orqali yangilanadi. *(2026-10-28 da o'zgardi — [Yangilanish](#yangilanish-2026-10-28))*
3. **Alohida jarayon.** Yuklovchi alohida jarayonda ishlaydi va unga faqat havola hamda chiqish papkasi beriladi. Tarmoq faqat shu jarayon ichida va amal davomida ishlatiladi.
4. **Interfeysdagi tavsiya:** avval asl fayl, keyin YouTube Studio yoki Takeout yo'riqnomasi. Havola orqali yuklash — oxirgi variant.
5. **Yurist sharti.** YT-1 vazifasi yurist xulosasidan oldin relizga kirmaydi (TZ 11, Q2). *(2026-10-28 da o'zgardi — [Yangilanish](#yangilanish-2026-10-28))*

## Yangilanish (2026-10-28)

Qaror amalga oshirildi; 1-, 2- va 5-bandlar loyiha egasi qarori bilan quyidagicha o'zgardi. 3- va 4-bandlar o'zgarmagan.

* **1-band → funksiya standart yoqilgan.** Sozlamalarda o'chiriladi (`/v1/settings/youtube-import`). Har importdagi rozilik (huquq + YouTube shartlari) va API'dagi majburiy `consent: true` saqlanadi.
* **5-band → yurist sharti relizni to'smaydi.** Yurist xulosasi (TZ 11, Q2) hali ochiq; huquqiy xavf "Oqibatlar" bo'limidagidek ogohlantirish va har importdagi rozilik bilan kamaytiriladi.
* **2-band → komponentlar ilovaning o'zidan, yangilanish asl manbalardan.** Boshlang'ich versiyalar `media/youtube_components.py` da mahkamlangan (versiya, hajm, sha256) va Sozlamalardagi tugma bilan yuklanadi. Yangilanish katalog orqali emas, **asl manbalardan**: PyPI JSON API va GitHub releases API e'lon qilgan sha256 bilan (`pip` bilan bir xil ishonch), qat'iy xost/paket ro'yxati, versiya pasaymaydi. Sabab: repozitoriy yopiq va alohida imzolangan manifest uchun server/kalit yo'q; yt-dlp esa YouTube o'zgarishlariga tez-tez moslashadi — yangilanish ilova relizini kutmasligi kerak. `make setup-youtube` faqat dasturchi muhiti uchun qoldi.

## Oqibatlar

* Asosiy pipeline oflayn qoladi. Tarmoq faqat foydalanuvchi bosgan tugma (YouTube yuklash, komponentlarni o'rnatish/yangilash) va model katalogi uchun ishlatiladi.
* ~~Katalog sxemasiga `Task.tool` (komponent) turi qo'shiladi.~~ Amalda katalog ishlatilmadi ([Yangilanish](#yangilanish-2026-10-28)): komponentlar `media/youtube_components.py` orqali sha256 bilan tekshirib o'rnatiladi va faqat engine ichidagi oq ro'yxatdagi yo'l orqali ishga tushiriladi.
* YouTube o'zgarsa, funksiya ishlamay qolishi mumkin. Tuzatish yangi komponent versiyasi bilan yetkaziladi (Sozlamalardagi "Yangilanishni tekshirish"), dastur relizi kerak bo'lmaydi.
* Huquqiy xavf saqlanib qoladi; uni ogohlantirish, rozilik va yurist xulosasi kamaytiradi.

## Ko'rib chiqilgan muqobillar

| Variant | Nega tanlanmadi |
| --- | --- |
| yt-dlp rasmiy exe'sini o'rnatuvchiga qo'shish | Exe'da GPLv3+ kod bor ([yt-dlp](https://github.com/yt-dlp/yt-dlp)); qotirilgan versiya tez eskiradi |
| Funksiyani umuman qilmaslik | Talabning 1-bandiga zid; 2-yo'l (YouTube Studio) baribir qo'llab-quvvatlanadi |
