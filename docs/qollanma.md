# Lahza Studio — foydalanuvchi qo'llanmasi

Lahza Studio uzun o'zbekcha podkast yoki videodan eng qiziq lahzalarni topadi. Ulardan 9:16 formatdagi, o'zbekcha subtitrli Reels kliplarini yasaydi. Hammasi **kompyuteringizda, internetsiz** ishlaydi: video hech qayerga yuborilmaydi.

> **Versiya holati.** Bu qo'llanma joriy (R0 / M2) holatni tasvirlaydi. Barcha tasvirlangan imkoniyatlar oynada (UI) mavjud. Faqat model katalogi hali R0 bosqichida — [2-bo'lim](#2-birinchi-ishga-tushirish-va-modellar).

## Mundarija

1. [Tizim talablari va o'rnatish](#1-tizim-talablari-va-ornatish)
2. [Birinchi ishga tushirish va modellar](#2-birinchi-ishga-tushirish-va-modellar)
3. [Internetsiz kompyuter: .lzpack](#3-internetsiz-kompyuter-lzpack)
4. [Shou yaratish va video import](#4-shou-yaratish-va-video-import)
5. [Kliplar galereyasi](#5-kliplar-galereyasi)
6. [Klip muharriri](#6-klip-muharriri)
7. [Transkript tahriri](#7-transkript-tahriri)
8. [Eksport](#8-eksport)
9. [Klaviatura yorliqlari](#9-klaviatura-yorliqlari)
10. [Imlo rejimlari](#10-imlo-rejimlari)
11. [Maxfiylik](#11-maxfiylik)
12. [Diagnostika](#12-diagnostika)
13. [Muammolar va yechimlar](#13-muammolar-va-yechimlar)

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

## 9. Klaviatura yorliqlari

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

## 10. Imlo rejimlari

Transkript ichida doim rasmiy imloda saqlanadi. Eksportda uch ko'rinishdan biri tanlanadi (Uslub → Imlo):

| Rejim | Misol | Qachon tanlash kerak |
| --- | --- | --- |
| Rasmiy (oʻ, gʻ) | oʻzbek, togʻ, maʼno | Standart. Toʻgʻri belgi — ʻ (U+02BB). |
| Oddiy (o', g') | o'zbek, tog', ma'no | Ijtimoiy tarmoqlarda keng tarqalgan, har qanday shriftda chiqadi |
| Yangi alifbo (ö, ğ, ş, ç) | özbek, toğ, şahar, çiroy | Yangi alifbo bilan yozish uchun |

Yangi alifboda `oʻ→ö`, `gʻ→ğ`, `sh→ş`, `ch→ç`. Tutuq belgisi bilan ajratilgan `sʼh` (masalan, *Isʼhoq*) o'zgarmaydi. Batafsil: [docs/08-ozbek-imlosi.md](08-ozbek-imlosi.md).

## 11. Maxfiylik

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

## 12. Diagnostika

**Sozlamalar → Diagnostika paketi** bo'limida **Saqlanadigan papka** ni tanlab, **Paket yaratish** ni bosing. Tayyor bo'lgach "Saqlandi: <yo'l>" yozuvi va **Papkani ochish** tugmasi chiqadi. Paket faqat siz bosganingizda yaratiladi va hech qayerga avtomatik yuborilmaydi — uni o'zingiz yuborasiz.

Paket — `lahza-diagnostika-<sana>-<vaqt>.zip` fayli. Uning ichida:

* dastur va tizim versiyalari;
* apparat va daraja;
* o'rnatilgan modellar ro'yxati;
* oxirgi xatolar;
* logning oxirgi qatorlari.

Transkript matni, klip matnlari va fayl yo'llari paketga **kirmaydi**.

Loglarning o'zi ma'lumotlar papkasidagi `Logs/engine.log` faylida (eng ko'pi 5 ta fayl, har biri 2 MB gacha).

## 13. Muammolar va yechimlar

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
| macOS: "dasturni ochib bo'lmaydi" | Rasmiy `.dmg` dan o'rnating. Imzolanmagan nusxalarni macOS bloklaydi. |
