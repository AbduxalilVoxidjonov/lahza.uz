# Lahza Studio — foydalanuvchi qo'llanmasi

Lahza Studio uzun o'zbekcha podkast yoki videodan eng qiziq lahzalarni topadi. Ulardan 9:16 formatdagi, o'zbekcha subtitrli Reels kliplarini yasaydi. Hammasi **kompyuteringizda, internetsiz** ishlaydi: video hech qayerga yuborilmaydi.

> **Versiya holati.** Bu qo'llanma joriy (R0 / M2, 2026-10-20) holatni tasvirlaydi. Barcha tasvirlangan imkoniyatlar oynada (UI) mavjud. Faqat model katalogi hali R0 bosqichida — [2-bo'lim](#2-birinchi-ishga-tushirish-va-modellar).

## Mundarija

1. [Tizim talablari va o'rnatish](#1-tizim-talablari-va-ornatish)
2. [Birinchi ishga tushirish va modellar](#2-birinchi-ishga-tushirish-va-modellar)
3. [Internetsiz kompyuter: .lzpack](#3-internetsiz-kompyuter-lzpack)
4. [Shou yaratish va video import](#4-shou-yaratish-va-video-import)
5. [Kliplar galereyasi](#5-kliplar-galereyasi)
6. [Klip muharriri](#6-klip-muharriri)
7. [Transkript tahriri](#7-transkript-tahriri)
8. [Eksport](#8-eksport)
9. [Video shablonlar va montaj](#9-video-shablonlar-va-montaj)
10. [Klaviatura yorliqlari](#10-klaviatura-yorliqlari)
11. [Imlo rejimlari](#11-imlo-rejimlari)
12. [Maxfiylik](#12-maxfiylik)
13. [Diagnostika](#13-diagnostika)
14. [Muammolar va yechimlar](#14-muammolar-va-yechimlar)

---

## 1. Tizim talablari va o'rnatish

Dastur kompyuterni tekshiradi va unga **daraja** beradi. Qaysi modellar yuklanishi shu darajaga bog'liq.

| Kompyuter | Daraja |
| --- | --- |
| Mac, Apple Silicon (M1 va yangi), 32 GB+ RAM | Pro |
| Mac, Apple Silicon, 16 GB+ RAM | Standard |
| Mac, Apple Silicon, 8 GB+ RAM | Lite |
| Intel protsessorli Mac | Qo'llanmaydi |
| Windows, NVIDIA 16 GB+ VRAM va 32 GB+ RAM | Pro |
| Windows, NVIDIA 8 GB+ VRAM va 16 GB+ RAM | Standard |
| Windows, 16 GB+ RAM (mos NVIDIA GPU'siz) | Lite (CPU rejimi) |
| Windows, 16 GB dan kam RAM | Qo'llanmaydi |

macOS 14 yoki yangisi talab qilinadi.

**macOS.** `.dmg` faylni oching va **Lahza Studio** ni `Applications` papkasiga torting. Dastur Apple tomonidan tasdiqlangan (notarizatsiya qilingan), shuning uchun birinchi ochilishda ham internet talab qilinmaydi.

**Windows.** O'rnatuvchi (`.exe`) faqat sizning foydalanuvchingiz uchun o'rnatadi, administrator huquqi so'ralmaydi.

O'rnatuvchi ichida AI modellar yo'q. Ular keyingi qadamda bir marta, kompyuteringizga mos to'plam sifatida yuklanadi.

## 2. Birinchi ishga tushirish va modellar

Modellar o'rnatilmagan bo'lsa, dastur **Boshlash** sahifasini ochadi.

1. **Kompyuter** kartasida daraja (Lite / Standard / Pro), uning sababi, protsessor, RAM, bo'sh disk va GPU ko'rsatiladi.
2. **Yuklanadigan modellar** jadvali har vazifa uchun bitta qatordan iborat:
   * vazifalar: nutqni matnga (ASR), so'z vaqtlari, nutqni aniqlash (VAD), spikerlarni ajratish, yuz va aktiv spiker, highlight topuvchi LLM;
   * har qatorda: majburiy yoki ixtiyoriy, model nomi, litsenziyasi, mosligi (*Tavsiya etiladi*, *Ishlaydi, lekin sekin*, *Mos emas*) va hajmi.
3. **Boshlash — modellarni yuklab olish** tugmasi bosilganda modellar internetdan bir marta yuklanadi. Tugmani bosish — yuklab olishga rozilik. Katalog imzolangan, har fayl sha256 xeshi bilan tekshiriladi; jarayon progress satrida ko'rinadi.
4. **Keyinroq** — yuklamasdan loyihalarga o'tish.

> **R0 bosqichi.** Model katalogi hozircha baholash bosqichida. Unda tasdiqlangan ASR modeli yo'q, shuning uchun yuklab olish tugmasi o'chiq. Ekranda "Katalog hali R0 bosqichida…" yozuvi chiqadi.

O'rnatilgan modellarni **Sozlamalar → O'rnatilgan modellar** bo'limida ko'rasiz. **Papkani qayta skanerlash** tugmasi qo'lda joylangan modellarni topadi. Katalogdan tashqari modellar *"Katalogdan tashqari — sifat kafolatlanmaydi"* belgisi bilan chiqadi.

## 3. Internetsiz kompyuter: .lzpack

Internet bo'lmagan kompyuterga modellar `.lzpack` fayl orqali ko'chiriladi. Buning uchun **Sozlamalar → O'rnatilgan modellar** ostida **Internetsiz ko'chirish (.lzpack)** bo'limi bor.

1. **Internetli kompyuterda** modellarni yuklang. So'ng **Paket saqlanadigan papka** ni tanlab, **Paket yaratish** ni bosing. Papkada `lahza-models-<sana>.lzpack` fayli paydo bo'ladi. Paket ichida modellar, manifest (har faylning sha256 xeshi va hajmi) va, sozlangan bo'lsa, imzo bo'ladi. Jarayon progress satrida ko'rinadi, oxirida "Tayyor." yozuvi chiqadi.
2. Faylni USB orqali ko'chiring.
3. **Internetsiz kompyuterda** **.lzpack fayli** maydonida paketni tanlab, **Import qilish** ni bosing. Bu maydon **Boshlash** sahifasida ham bor (modellar o'rnatilmagan bo'lsa, "Internetsiz kompyuterda modellar boshqa kompyuterdan .lzpack fayli orqali ko'chiriladi." yozuvi ostida). Import paytida:
   * har bir faylning xeshi va hajmi manifest bilan solishtiriladi;
   * imzo tekshiriladi;
   * xavfli tarkib (papkadan tashqariga yo'llar, bajariladigan fayllar, manifestda yo'q fayllar) rad etiladi.

## 4. Shou yaratish va video import

**Loyihalar** sahifasida:

1. **Shou nomi** maydoniga nom yozing (masalan, podkast nomi) va **Yaratish** ni bosing.
2. Shou kartasini tanlang. Uning epizodlari jadvalda ko'rinadi.
3. **Video import qilish** kartasida:
   * **Ustuvor mavzu (ixtiyoriy)** — highlight qidirishda ustunlik beriladigan mavzu;
   * **LLM'siz (Lite) rejim** — kliplar til modelisiz, signallar (ovoz, pauzalar, savol-javob va h.k.) bo'yicha topiladi. Bu tezroq, lekin kamroq aniq;
   * **Video import qilish** tugmasi — MP4, MOV yoki MKV faylni tanlang.

Asl video ko'chirilmaydi, dastur faqat unga havola saqlaydi. Shuning uchun faylni tahlil va eksport tugaguncha o'chirmang yoki boshqa joyga ko'chirmang.

Tahlil quyidagi bosqichlardan o'tadi:

1. Import
2. Nutqni topish
3. Transkripsiya
4. Imlo
5. So'z vaqtlari
6. Spikerlar
7. Gaplar
8. Signallar
9. Highlight

Joriy bosqich va foizi ko'rinib turadi. Epizod sahifasida tahlilni **Bekor qilish** mumkin. Epizod holatlari: *Yangi*, *Tahlil qilinmoqda*, *Tayyor*, *Xato*.

## 5. Kliplar galereyasi

Epizodni ochsangiz, topilgan **klip nomzodlari** kartochkalar ko'rinishida chiqadi. Har kartochkada:

* muqova kadri;
* lahza bali (0–100), turi (maslahat, hikoya, kulgili, bahsli fikr, fakt, savol-javob);
* davomiyligi va boshlanish vaqti;
* sarlavha va "nega tanlandi" izohi;
* holati: nomzod, qabul, rad yoki eksport qilingan. Qo'lda yaratilgan kliplar alohida belgilanadi.

Saralash va filtrlar:

* saralash — ball, vaqt yoki davomiylik bo'yicha;
* filtr — klip turi, holati va eng kichik ball (slayder).

Amallar:

* **Qabul** / **Rad** — klipni belgilash (kartochka tanlangan bo'lsa, `A` / `R`);
* **Tahrirlash** — klip muharririni ochish;
* **o'xshashini topish** — shu klipga o'xshash yangi nomzodlar qo'shiladi;
* bir nechta klipni belgilab, hammasini birga eksport qilish (`Cmd/Ctrl+E`). Bitta tugma bilan barcha qabul qilinganlarni tanlash ham mumkin;
* **qayta tahlil** — boshqa ustuvor mavzu bilan yoki Lite rejimni o'zgartirib. Epizod Lite rejimda tahlil qilingan bo'lsa-yu, endi LLM modeli o'rnatilgan bo'lsa, dastur qayta tahlilni taklif qiladi.

## 6. Klip muharriri

Chap tomonda 9:16 telefon ko'rinishidagi preview bor.

* Ijro paytida subtitr taxminiy ko'rinishda chiziladi. To'xtatilganda dvigatel haqiqiy 1080×1920 kadrni chizadi — eksportda xuddi shu ko'rinish chiqadi.
* **Xavfsiz zona** — Instagram interfeysi yopadigan joylar (tepadan 14%, pastdan 35%, yonlardan 6%) belgilanadi. Matn va yuzlarni shu zonadan tashqarida saqlang.
* Ijro paneli: ⏪ (J), ▶/⏸ (Space), ⏩ (L), klip oralig'i va kesimlardan keyingi davomiylik.

**Vaqt chizig'i** (preview ostida) — to'lqin shakli, so'zlar, spikerlar, kesilgan joylar va ijro nuqtasi.

* Bosilgan joyga o'tadi.
* Boshlanish va tugash tutqichlarini sudrab klipni qisqartirasiz yoki uzaytirasiz. Tutqich eng yaqin **so'z chegarasiga** yopishadi, shuning uchun klip hech qachon so'z o'rtasida kesilmaydi. Klip kamida 0,5 s bo'ladi.
* Tutqich fokusda bo'lsa, `←` / `→` uni oldingi yoki keyingi so'z chegarasiga suradi.
* Ishonchi past so'zlar ajratib ko'rsatiladi — ularni tekshirib chiqing.

Muharrirda to'rtta tab bor.

### Matn

Klip matni gaplar bo'yicha ko'rsatiladi; matn orqali kesish shu yerda qilinadi.

* So'zni bossangiz, u tanlanadi va video shu joyga o'tadi. `Shift` + bosish tanlovni kengaytiradi. Gap vaqtini bossangiz, butun gap tanlanadi.
* Tanlangan so'zlarni **kesish** mumkin: ular videodan va subtitrdan chiqariladi, ijro ularni sakrab o'tadi.
* Kesilganni bitta-bitta yoki hammasini birdan **tiklash** mumkin.

So'zning matnini tuzatish bu tabda emas — [Transkript tahriri](#7-transkript-tahriri) ga qarang.

### Kadr

9:16 kadrlash. Ro'yxat bo'sh bo'lsa, kadrlash avtomatik.

* Layout: *focus* (bitta odam), *split* (ikki odam ustma-ust), *fit + blur* (butun kadr, foni xira).
* Joriy vaqtga kalit kadr qo'shish: markaz `cx`, `cy` (0–1) va kattalashtirish (1–3). Split uchun yuqori yoki pastki qism tanlanadi.
* Jadvalda vaqtni bossangiz, video o'sha joyga o'tadi; ✕ kalit kadrni o'chiradi.
* **Saqlash** ni bosing — qo'lda qo'yilgan kalit kadrlar eksportda avtomatik kadrlashdan ustun turadi.

### Uslub

Subtitr ko'rinishi. Uslub barcha kliplar uchun umumiy: o'zgartirsangiz, keyingi eksportlarga ham ta'sir qiladi.

* **Matn:** shrift (ro'yxatda faqat o'zbek harflarini — oʻ, gʻ, ʼ — to'g'ri chiqaradigan shriftlar), o'lcham, qalin, KATTA HARFLAR, joylashuv (pastda, o'rtada, tepada), ekrandagi so'zlar soni (1–8), qatorlar soni (1–3).
* **Ranglar:** asosiy rang, faol so'z rangi, kontur rangi va qalinligi, soya, fon plashkasi (rangi va shaffofligi).
* **Animatsiya:** *karaoke* (so'zlar navbatma-navbat yonadi), *pop* (faol so'z kattalashadi, masshtabi sozlanadi) yoki *none*. Kalit so'zlar ro'yxatidagi so'zlar alohida ajratiladi.
* **Tozalash:** imlo rejimi ([10-bo'lim](#10-imlo-rejimlari)), parazit so'zlarni (ee, mmm, hmm…) olib tashlash, so'kinishlarni yashirish (so'zlar ro'yxati bilan).
* **Logotip:** rasm fayli (PNG, JPG, WEBP), burchagi va shaffofligi.
* **Uslublar kutubxonasi:** uslubni nom bilan saqlash, yuklash, yangilash va o'chirish. `.json` faylga eksport yoki import qilib, boshqa kompyuterga ko'chirish mumkin.

### Ma'lumot

* **Sarlavha**, **Izoh matni**, **Heshteglar** (bo'sh joy bilan ajratiladi) → **Saqlash**. Eksportda shulardan caption fayli yasaladi.
* **Nega tanlandi** — highlight izohi; lahza bali va uning tarkibiy ballari; manba (avtomatik yoki qo'lda).

Muharrir tepasida **Qabul**, **Rad** va **Eksport** tugmalari ham bor.

## 7. Transkript tahriri

Epizod sahifasining tepasidagi **Transkript** tugmasi butun epizod transkriptini ochadi. **Kliplarga qaytish** havolasi galereyaga qaytaradi. Tahlil tugamagan bo'lsa, "Transkript hali tayyor emas." yozuvi chiqadi.

* **So'zni tanlash.** So'zni bosing — tanlanadi; `Shift` bilan bosish oraliqni tanlaydi ("Tanlandi: N so'z").
* **So'zni tuzatish.** So'zni ikki marta bosing yoki uni tanlab `Enter` / `F2` ni bosing. `Enter` saqlaydi, `Esc` bekor qiladi. Bo'sh qoldirilsa, so'z o'chadi. Bo'sh joy bilan yozilsa, so'z bir nechtaga bo'linadi. Asl matn saqlanib qoladi.
* **Ishonchi past so'zlar** (*past ishonch*) ajratib ko'rsatiladi; ustiga kelsangiz, vaqti va ishonch foizi chiqadi.
* **Qidirish va almashtirish.** Qidiruv katta-kichik harfni farqlamaydi. `Enter` — keyingi topilgan joy, `Shift+Enter` — oldingisi. **Almashtirish matni** ni yozib, **Almashtirish** (birma-bir) yoki **Hammasini almashtirish** ni bosing.
* **Spiker nomi.** Spiker yorlig'ini (S1, S2…) bosib haqiqiy ismini yozing. Bo'sh qoldirsangiz, asl yorliq tiklanadi.
* **Lug'atga qo'shish.** Tanlangan matnni **Lug'atga qo'shish** orqali shou lug'atiga yozing: **To'g'ri yozilishi**, **Xato variantlar (vergul bilan)** va **Turi** (*Ism*, *Brend*, *Atama*). Lug'at keyingi tahlillarda ASR'ga ishora sifatida beriladi. Barcha yozuvlarni **Sozlamalar → Lug'at** bo'limida ko'rish va o'chirish mumkin.
* **Tanlovdan klip yaratish.** So'zlarni tanlab, **Klip sarlavhasi (ixtiyoriy)** ni yozing va **Klip yarat** ni bosing — klip gap chegaralari bo'yicha kesiladi va galereyada qo'lda yaratilgan sifatida chiqadi.

So'z tuzatilganda faqat o'sha gapning so'z vaqtlari qayta hisoblanadi; tuzatishlar keyinchalik lug'atni yaxshilash uchun saqlanadi.

## 8. Eksport

Eksportni klip muharriridagi **Eksport** tugmasi, `Cmd/Ctrl+E` yoki galereyada belgilangan kliplar orqali boshlaysiz. Eksport papkasi tanlanmagan bo'lsa, birinchi marta papka so'raladi va keyin eslab qolinadi.

Har bir klip uchun quyidagi fayllar yasaladi:

| Fayl | Tarkibi |
| --- | --- |
| `<nom>.mp4` | 1080×1920 video, subtitr videoga yoqib yozilgan; AAC ovoz 48 kHz |
| `<nom>.srt`, `<nom>.vtt` | Alohida subtitr fayllari |
| `<nom>_caption.txt` | Sarlavha, izoh matni va heshteglar — Instagram'ga nusxalash uchun |
| `<nom>_cover.jpg` | Muqova (klip o'rtasidagi kadr) |

* **Fayl nomi** shabloni standart holatda `{shou}_{epizod}_{nn}_{sarlavha}` (masalan, `test-shou_12-son_01_…`). Bu yerda `nn` — klipning epizoddagi tartib raqami. Shablonni **Eksport** sahifasida o'zgartirish mumkin.
* Tanlangan **imlo rejimi** subtitrga, SRT/VTT fayllarga, sarlavha va izoh matniga qo'llanadi (heshteglarga emas).
* Eksportdan keyin klip holati *eksport qilingan* bo'ladi.

**Eksport navbati** sahifasida:

* eksport papkasi va fayl nomi shabloni;
* har bir vazifaning holati;
* jarayondagini **Bekor qilish**;
* xato bo'lgan yoki bekor qilinganini qayta urinish;
* tayyor faylni papkada ko'rsatish.

## 9. Video shablonlar va montaj

Bu bo'lim bir yoki bir nechta videodan tayyor montaj yasashni tushuntiradi. **Video shablon** — montaj retsepti: tuzilma (intro, kadrlar, outro), davomiylik, o'tishlar, harakat effektlari, rang, subtitr va musiqa. Lahza yangi kadr chizmaydi: montajdagi har bir kadr faqat siz tanlagan videolardan olinadi.

Chap menyuda **Montaj** guruhi bor. Unda ikki bo'lim: **Shablonlar** va **Montajlar**.

### Shablon tanlash

**Shablonlar** sahifasi ("Video shablonlar") — shablonlar galereyasi. Yuqorida toifalar: **Podkast**, **E'lon**, **Tadbir**, **Mahsulot**, **Intervyu**, **Ta'lim**, **Boshqa** va **Mening shablonlarim**. O'rnatilgan 6 ta shablon:

| Shablon | Toifa | Qisqacha |
| --- | --- | --- |
| Podkast — kuchli hook | Podkast | 30–45 s, eng kuchli lahza bilan boshlanadi, karaoke subtitr, urg'uli joyda punch-in, oxirida obunaga chaqiruv |
| Tadbir — ritmli lavhalar | Tadbir | 20–30 s, 1,2–3 s lik yorqin kadrlar musiqa ostida, dissolve o'tishlar; **musiqa majburiy** |
| Mahsulot — promo | Mahsulot | 15–20 s, sarlavha kartasi, yorqin rang, tez kadrlar, oxirida CTA kartasi, logotip |
| Intervyu — toza | Intervyu | ~55 s, eng yaxshi lahzalar, boshida shou nomi pastki yozuv sifatida |
| Kurs e'loni | Ta'lim | ~40 s, sarlavha va ro'yxatdan o'tishga chaqiruv |
| Kun hikoyasi | Boshqa | ~30 s, videolardan xronologik hikoya, iliq ranglar, boshida sarlavha |

Kartochkada shablon nomi, tavsifi, format va asosiy sozlamalar (**Effektlar**, **Subtitr**, **Musiqa majburiy**) ko'rinadi. **Qo'llash** — shu shablon bilan yangi montajni boshlaydi. **Ko'rish** — shablonni ochadi (o'rnatilgan shablon — faqat o'qish uchun).

### Yangi montaj

**Qo'llash** yoki **Montajlar → Yangi montaj** "Yangi montaj" sahifasini ochadi. U uch qadamdan iborat.

**1. Shablon.** Shablonni tanlaysiz; tanlangani "Tanlandi: <nom>" deb ko'rsatiladi.

**2. Videolar.** **Manba turi** ni tanlang:

* **Fayllar** — **Videolarni tanlash** tugmasi (bir nechta faylni birdaniga tanlash mumkin) yoki **Video fayl yo'li** maydoniga yo'l yozib **Qo'shish**;
* **Epizod kliplari** — **Loyiha** va **Epizod** ni tanlab, kerakli kliplarni qo'shing yoki **Hammasini qo'shish (N)**;
* **Butun epizod** — epizodning to'liq videosi manba bo'ladi.

Tanlanganlar **Tanlangan videolar** ro'yxatida. Tartibni ↑/↓ tugmalari yoki elementda `Alt+↑/↓` bilan o'zgartirasiz, `Delete` — olib tashlash. Shablonning tartib qoidasi "Berilgan tartibda" bo'lsa, montaj shu tartibda yig'iladi.

**3. Sozlamalar.** Hammasi ixtiyoriy — bo'sh qolsa shablondagi qiymat olinadi ("Shablondan …"):

* **Montaj nomi**, **Davomiylik** (5–600 s), **Format** (9:16, 1:1, 16:9);
* **Musiqa fayli** — shablon musiqa talab qilsa majburiy (`*` va "Musiqa majburiy" belgisi). Faqat o'zingizga tegishli yoki litsenziyali musiqa ishlating;
* **Sarlavha**, **CTA matni**, **Shou nomi** — shablon kartalaridagi o'rinbosarlar o'rniga qo'yiladi (pastda — [O'rinbosarlar](#orinbosarlar));
* **Subtitr** (Shablondan / Yoqilgan / O'chirilgan), **O'tish**, **Rang**;
* **Logotip fayli (PNG)** — shablon logotip kutsa-yu, fayl tanlanmasa, montaj logotipsiz bo'ladi.

**Montaj qilish** ni bosing. "Montaj rejalashtirilmoqda": avval **Videolar tahlili** (sahnalar, keskinlik, harakat, ovoz energiyasi, nutq), keyin **Reja tuzish**. Reja deterministik: bir xil videolar va bir xil shablon har doim bir xil montaj beradi. Tayyor bo'lgach montaj muharriri ochiladi.

### Montaj muharriri

Yuqorida — preview ("Montaj preview (9:16)"), uning ostida **Timeline** uch qator bilan: **Video**, **Matn**, **Musiqa**. O'tishlar video elementlari orasida belgilanadi.

* Timeline'ni bosib vaqtni tanlaysiz; preview shu kadrni ko'rsatadi. **Xavfsiz zona** ni yoqib qo'yish mumkin.
* **Kattalashtirish** / **Kichiklashtirish** — timeline masshtabi.

O'ng tarafda to'rt tab:

* **Element** — tanlangan video element: **Manba oralig'i** (**Boshi** / **Oxiri**, bir kadrlik qadam bilan), **Tezlik**, **Ovoz** (**Ovozsiz**, **Balandlik**), **Kadr** (**Qo'lda kadrlash**, **Zoom**), **O'tish**, **Effektlar** (**Effekt qo'shish**, **Boshlanishi**, **Davomiyligi** — 0 bo'lsa element oxirigacha). Effekt yonida manbasi: "Shablondan" yoki "Qo'lda". **Chapga surish** / **O'ngga surish**, **Takrorlash**, o'chirish. Element **Manba** va **Nega tanlandi** ma'lumotini ham ko'rsatadi. Tahrirlangan element "Qo'lda tahrirlangan" deb belgilanadi.
* Matn elementi tanlansa — **Matn**, **Turi** (Karta, Sarlavha, Hook, CTA, Pastki yozuv), **Joyi**, **Animatsiya** (Yo'q, Paydo bo'lish, Sakrash, Pastdan chiqish), **Fon**, **Boshi** / **Oxiri**. Yangi matn — **Matn qo'shish**.
* **Umumiy** — butun montaj: **Subtitr uslubi**, **Rang**, **Musiqa** (**Musiqa qo'shish** / **Almashtirish** / **Olib tashlash**, **Nutq ustida pasaytirish**, **Musiqa balandligi**, **Kirish** / **Chiqish**), **Manbalar balandligi**, **Balandlikni me'yorlash**, **Kesimdagi fade**, logotip.
* **Render** — pastda alohida.
* **Hisobot** — har bir kadr qaysi manbadan, qaysi oraliqdan va nega olingani (`_edl.json` ning ko'rinishi).

O'zgarishlarni **Saqlash** (`Cmd/Ctrl+S`) bilan saqlang.

**Qayta reja** — shablon bo'yicha rejani qaytadan tuzadi. Saqlanmagan o'zgarishlar bo'lsa, ogohlantirish chiqadi; qo'lda tahrirlangan elementlar bo'lsa, ular almashtirilishi haqida alohida so'raladi. Qayta reja muvaffaqiyatsiz bo'lsa, avvalgi timeline saqlanib qoladi.

Videolarda transkript bo'lmasa, subtitr chiqmaydi ("Manbalarda transkript yo'q - subtitr chiqmaydi."). Rejalashtiruvchi biror narsani qo'ya olmagan bo'lsa (masalan, hook matni uchun joy yetmasa), **Reja ogohlantirishlari** da yoziladi.

### Render

**Render** tabida **Eksport papkasi** va **Fayl nomi** ni kiriting, so'ng **Render** (`Cmd/Ctrl+E`). Jarayon tab ichida va **Eksport** sahifasida ko'rinadi; bekor qilish mumkin. Tayyor bo'lgach "Render tayyor" va fayllar chiqadi:

| Fayl | Tarkibi |
| --- | --- |
| `<nom>.mp4` | Montaj (tanlangan formatda), matn kartalari va subtitr videoga chizilgan |
| `<nom>_edl.json` | Montaj hisoboti (pastda) |
| `<nom>.srt` | Subtitr fayli — subtitr yoqilgan va transkript bo'lsa |

Oldingi renderlar ro'yxati — **Oldingi renderlar (N)**. Barcha montajlar **Montajlar** sahifasida: holati (Rejalashtirilmoqda / Tayyor / Xato), **Ochish**, o'chirish. Montaj o'chirilsa, render qilingan fayllar o'chirilmaydi.

### Shablon yaratish, nusxa, import va eksport

* **Nusxa olish** — o'rnatilgan shablon nusxasi **Mening shablonlarim** ga qo'shiladi. **Nusxa olib tahrirlash** — nusxani darhol muharrirda ochadi. O'rnatilgan shablonning o'zini o'zgartirib bo'lmaydi.
* **Yangi shablon** — bo'sh shablondan boshlash.
* Shablon muharriri bo'limlari: **Asosiy** (Nomi, Tavsif, Toifa, Format, Kadr/s, Davomiylik), **Kadrlarni tanlash** (Tanlash usuli — Eng yaxshi lahzalar / Sahnalar / To'liq videolar; Tartib — Berilgan tartibda / Xronologik / Ball bo'yicha; Min. kadr, Maks. kadr, Bitta manbadan maks., Gap o'rtasida kesmaslik), **Ko'rinish** (Kadrlash, O'tish, O'tish davomiyligi, Rang), **Effekt qoidalari**, **Subtitr**, **Tuzilma** (Intro kartasi, Hook matni, Outro / CTA), **Ovoz va brend** (Musiqa, Manbalar ovozini o'chirish, Logotip qo'yish).
* **Effekt qoidalari**: **Qoida qo'shish** → **Plagin**, **Qachon** (Boshida, Oxirida, Har kesimda, Urg'uli joyda, Spiker almashganda, Har N-elementda), **Ko'pi bilan** (0 — cheklovsiz), **Min. oraliq**.
* **Import (.json)** — shablon fayli yo'lini kiriting; tekshiruvdan o'tsa "Import qilindi: <nom>". **Eksport** — shablonni `.json` faylga saqlaydi. Fayl boshqa kompyuterdagi Lahza'ga import qilinadi. Shablon faqat ma'lumot (kod emas); noma'lum plagin yoki noto'g'ri qiymat bo'lsa, import aniq xabar bilan rad etiladi.

### O'rinbosarlar

Karta matnida (intro, hook, outro) quyidagilar ishlatiladi:

| O'rinbosar | Nima qo'yiladi |
| --- | --- |
| `{sarlavha}` | Yangi montajdagi **Sarlavha** maydoni |
| `{shou}` | **Shou nomi** maydoni |
| `{cta}` | **CTA matni** maydoni |

Standart qiymat ikki nuqtadan keyin yoziladi: `{cta:Obuna bo'ling!}` — CTA matni berilmasa, "Obuna bo'ling!" chiqadi. Qiymat ham, standart ham bo'lmasa va karta bo'sh qolsa, karta qo'yilmaydi.

### "Haqiqiy kadr" va `_edl.json`

Lahza montajda yangi kadr generatsiya qilmaydi: piksellar faqat sizning videolaringizdan olinadi; qo'shiladigan narsalar — o'tishlar, kadrlash/zoom, rang, matn kartalari, subtitr, logotip va musiqa. Buni har render yonidagi `<nom>_edl.json` tasdiqlaydi: unda `"haqiqiy_kadr": true` va har bir kadr uchun — manba fayl, manbadagi oraliq, montajdagi oraliq, qo'llangan o'tish, effekt va rang, kadr nega tanlangani. Xuddi shu ma'lumot muharrirdagi **Hisobot** tabida.

### Cheklovlar

* Kadrlarni tanlash qoida asosida (LLM'siz); musiqa zarbiga moslash, multicam va bir nechta variant hozircha yo'q.
* YouTube havoladan import, Premiere / DaVinci / Filmora uchun eksport, Lottie animatsiyalar va `.lzfx` plagin paketlari — keyingi versiyalarda.
* FFmpeg libass'siz bo'lsa (dasturchi muhiti) matn kartalari va subtitr videoga chizilmaydi; "Subtitrsiz eksport" tanlovi belgilansa render ogohlantirish bilan davom etadi, SRT alohida yoziladi.
* Musiqa va videolar huquqi — sizning javobgarligingizda.

## 10. Klaviatura yorliqlari

Yorliqlar matn maydonida yozayotganingizda ishlamaydi. Mac'da `Cmd`, Windows'da `Ctrl` ishlatiladi.

**Klip muharriri:**

| Tugma | Amal |
| --- | --- |
| `Space` | Ijro / pauza. Ijro klip oxirida to'xtaydi. |
| `J` | 5 soniya orqaga (klip boshidan oldinga o'tmaydi) |
| `K` | Pauza; tezlik 1× ga qaytadi |
| `L` | Ijro. Ijro paytida yana bosilsa, tezlik 1,5× va 2× gacha oshadi. |
| `I` | Klip boshini ijro nuqtasidagi so'z boshiga qo'yish |
| `O` | Klip oxirini ijro nuqtasidagi so'z oxiriga qo'yish |
| `A` | Klipni qabul qilish |
| `R` | Klipni rad etish |
| `Cmd/Ctrl+E` | Klipni eksport qilish |
| `←` / `→` | Vaqt chizig'ida fokusdagi tutqichni oldingi yoki keyingi so'z chegarasiga surish |

**Galereya:**

| Tugma | Amal |
| --- | --- |
| `A` / `R` | Tanlangan kartochkani qabul qilish / rad etish |
| `Cmd/Ctrl+E` | Belgilangan kliplarni (yoki belgilangan bo'lmasa, tanlangan kartochkani) eksport qilish |

**Montaj muharriri:**

| Tugma | Amal |
| --- | --- |
| `←` / `→` | Bir kadr orqaga / oldinga |
| `Shift+←` / `Shift+→` | Oldingi / keyingi element |
| `Delete` | Tanlangan elementni o'chirish |
| `Cmd/Ctrl+S` | Saqlash |
| `Cmd/Ctrl+E` | Render |

**Yangi montaj (tanlangan videolar ro'yxati):** `Alt+↑` / `Alt+↓` — tartibni o'zgartirish, `Delete` — olib tashlash.

## 11. Imlo rejimlari

Transkript ichida doim rasmiy imloda saqlanadi. Eksportda uch ko'rinishdan biri tanlanadi (Uslub → Imlo):

| Rejim | Misol | Qachon tanlash kerak |
| --- | --- | --- |
| Rasmiy (oʻ, gʻ) | oʻzbek, togʻ, maʼno | Standart. Toʻgʻri belgi — ʻ (U+02BB). |
| Oddiy (o', g') | o'zbek, tog', ma'no | Ijtimoiy tarmoqlarda keng tarqalgan, har qanday shriftda chiqadi |
| Yangi alifbo (ö, ğ, ş, ç) | özbek, toğ, şahar, çiroy | Yangi alifbo bilan yozish uchun |

Yangi alifboda `oʻ→ö`, `gʻ→ğ`, `sh→ş`, `ch→ç`. Tutuq belgisi bilan ajratilgan `sʼh` (masalan, *Isʼhoq*) o'zgarmaydi. Batafsil: [docs/08-ozbek-imlosi.md](08-ozbek-imlosi.md).

## 12. Maxfiylik

* **Videolar kompyuterdan chiqmaydi.** Tahlil, transkripsiya va render to'liq lokal bajariladi.
* **Telemetriya yo'q.** Dastur foydalanish statistikasini yubormaydi.
* **Internet** faqat siz modellarni yuklab olishni bosganingizda ishlatiladi. Shundan keyin dastur internetsiz ishlaydi.
* **Loglarga transkript matni yozilmaydi.**
* Ma'lumotlar papkasi:

  | OS | Yo'l |
  | --- | --- |
  | macOS | `~/Library/Application Support/Lahza Studio/` |
  | Windows | `%LOCALAPPDATA%\Lahza Studio\` |

  Ichidagi papkalar: `Models/` (modellar), `Library/` (shoular va epizodlar), `Logs/` (loglar).

## 13. Diagnostika

**Sozlamalar → Diagnostika paketi** bo'limida **Saqlanadigan papka** ni tanlab, **Paket yaratish** ni bosing. Tayyor bo'lgach "Saqlandi: <yo'l>" yozuvi va **Papkani ochish** tugmasi chiqadi. Paket faqat siz bosganingizda yaratiladi va hech qayerga avtomatik yuborilmaydi — uni o'zingiz yuborasiz.

Paket — `lahza-diagnostika-<sana>-<vaqt>.zip` fayli. Uning ichida:

* dastur va tizim versiyalari;
* apparat va daraja;
* o'rnatilgan modellar ro'yxati;
* oxirgi xatolar;
* logning oxirgi qatorlari.

Transkript matni, klip matnlari va fayl yo'llari paketga **kirmaydi**.

Loglarning o'zi ma'lumotlar papkasidagi `Logs/engine.log` faylida (eng ko'pi 5 ta fayl, har biri 2 MB gacha).

## 14. Muammolar va yechimlar

| Muammo | Sabab va yechim |
| --- | --- |
| "Engine bilan aloqa yo'q" | Dasturning ichki engine'i ishga tushmadi. Dasturni qayta oching. Takrorlansa, `Logs/engine.log` ni tekshiring. |
| Modellarni yuklash tugmasi o'chiq | Katalogda kompyuteringizga mos tasdiqlangan ASR modeli yo'q (R0 bosqichi) — [2-bo'lim](#2-birinchi-ishga-tushirish-va-modellar). |
| Daraja: "Qo'llanmaydi" | Intel Mac, 8 GB dan kam RAM'li Mac yoki 16 GB dan kam RAM'li Windows — [1-bo'lim](#1-tizim-talablari-va-ornatish). |
| Tahlil "Xato" bilan tugadi | Video fayl o'chirilgan yoki ko'chirilgan bo'lishi mumkin. Faylni joyiga qaytaring va qayta tahlil qiling. |
| Kliplar kam yoki sifati past | LLM modeli o'rnatilgach, Lite rejimni o'chirib qayta tahlil qiling. Ustuvor mavzu ham yordam beradi. |
| Subtitrda harflar noto'g'ri chiqadi | Shrift o'zbek harflarini qo'llamaydi. Uslub tabida boshqa shrift tanlang yoki "Oddiy (o', g')" imlosiga o'ting. |
| Subtitrda so'z xato yozilgan | Transkript tahririda tuzating. Takrorlanadigan ism yoki atamalarni lug'atga qo'shing. |
| Brauzer yoki dasturchi rejimida eksport ishlamaydi | Eksport papkasi tanlanmagan. Uni **Eksport** sahifasida belgilang. |
| Subtitrsiz video / render xatosi (dasturchi muhiti) | Tizimdagi FFmpeg libass'siz yig'ilgan. Rasmiy o'rnatuvchida FFmpeg dastur bilan birga keladi. Dasturchilar uchun: [docs/03-dasturchi-muhiti.md](03-dasturchi-muhiti.md#ffmpeg-va-libass). |
| "Bu shablon uchun musiqa fayli majburiy." | Shablon musiqa talab qiladi (masalan, "Tadbir — ritmli lavhalar"). Yangi montajda **Musiqa fayli** ni tanlang yoki boshqa shablon oling. |
| Montajda subtitr yo'q | Manba videolarda transkript yo'q (oddiy fayllar). Subtitr uchun videoni avval shouga import qilib tahlil qiling va **Epizod kliplari** yoki **Butun epizod** manbasidan foydalaning. |
| macOS: "dasturni ochib bo'lmaydi" | Rasmiy `.dmg` dan o'rnating. Imzolanmagan nusxalarni macOS bloklaydi. |
