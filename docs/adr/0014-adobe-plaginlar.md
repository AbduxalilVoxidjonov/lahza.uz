# ADR-0014: Adobe plaginlari — Premiere Pro uchun UXP, After Effects uchun CEP + ExtendScript, umumiy engine va host-reja

* Holat: Taklif
* Sana: 2026-10-22
* TZ bo'limi: [`12-adobe-plaginlar.md`](../12-adobe-plaginlar.md); [`11-montaj-platformasi.md`](../11-montaj-platformasi.md) 7.3

## Kontekst

Montajchilar Lahza natijasini o'z dasturida davom ettiradi. Hozirgi yo'l — fayl almashinuvi (FCP7 XML, SRT, `words.json`; [ADR-0012](0012-lahza-timeline.md)).
U ishlaydi, lekin foydalanuvchi ikki dastur orasida yuradi va After Effects Lahza'dan timeline'ni to'g'ridan-to'g'ri olmaydi.
Foydalanuvchi qarori: Lahza Premiere Pro va After Effects **ichiga** o'rnatiladigan panel sifatida ham bo'ladi; desktop ilova (Lahza Studio) qoladi.

Cheklovlar:

* Og'ir hisob (ASR, highlight, reframe, montaj rejasi) Python engine'da. Uni Adobe ichida qayta yozib bo'lmaydi.
* Oflayn, faqat `127.0.0.1`, token ([ADR-0001](0001-tauri-python-sidecar.md)). Yangi kadr generatsiya qilinmaydi ([ADR-0013](0013-haqiqiy-kadr-tamoyili.md)).
* macOS va Windows.

Tekshirilgan faktlar (2026-10-22, manbalar [`12`, 12-bo'lim](../12-adobe-plaginlar.md#12-manbalar)):

* **Premiere UXP** — 25.2 da beta, **25.6 dan rasmiy** [U1][U4]. Sekvensiya yaratish, kliplarni joylash, kalit kadrlar, o'tishlar, effektlar, markerlar uchun
  API nomlari Adobe'ning rasmiy TS deklaratsiyalarida bor [U3].
* **After Effects UXP** — Adobe sahifasi uni beta deb ta'riflaydi [U7]. 2026-07 dagi UXP qo'llab-quvvatlash matritsasida AE yo'q [U9].
* **CEP 12** — After Effects 25.0 va Premiere 25.0 dan [U6].
* **CEP kelajagi** — sanali rasmiy hujjat yo'q. Forumdagi Adobe vakili Premiere'da CEP'ni UXP rasmiy relizidan keyin "bir kalendar yil" qo'llab-quvvatlash rejasini aytgan [U21].
  AE uchun bunday bayonot yo'q.
* **Marketplace ko'rigi** — plagin tashqi ilovani ishga tushirmasligi kerak; tashqi dasturga bog'liqlik tavsifda yozilishi kerak [U8].
* **macOS'da UXP `http://` ni cheklaydi** [U5]. Loopback'ga ta'siri tasdiqlanmagan.

## Qaror

* **Premiere Pro — UXP paneli** (manifest v5, `app: "premierepro"`), React + TS, `adobe/premiere/`.
* **After Effects — CEP paneli + ExtendScript** (`CSXS/manifest.xml`, host `AEFT`, CEP 12), React + TS UI va ES3 `jsx/host.jsx`, `adobe/after-effects/`.
* **Umumiy engine.** Ikkala panel Lahza Studio bilan bitta engine'dan foydalanadi. Engine `--discovery` bilan `<data_dir>/engine.json` (port, token) yozadi;
  panel shuni o'qib ulanadi. Panel engine'ni o'zi ishga tushirmaydi.
* **Umumiy host-reja.** Engine `lahza.hostplan/1` JSON qaytaradi (`engine/src/lahza_engine/hostplan/model.py` ↔ `adobe/shared/src/hostplan.ts`).
  Barcha montaj qarori engine'da; plagin adapteri faqat rejani host API'siga qo'yadi. Host qila olmaydigan narsa `not_translated` ga tushadi va foydalanuvchiga ko'rsatiladi.
* **Render'ni Adobe qiladi.** Adobe yo'lida Lahza FFmpeg render qilmaydi.
* **Lahza Studio saqlanadi** — to'liq mustaqil mahsulot sifatida.

## Oqibatlar

Ijobiy:

* Montajchi dasturidan chiqmaydi; natija tahrirlanadigan sekvensiya/kompozitsiya (pishirilgan video emas).
* Rejalashtirish mantiqi bitta: desktop, Premiere va AE bir xil reja beradi. Yangi host qo'shish = yangi adapter.
* Adapter qatlami soxta implementatsiya bilan Adobe'siz testlanadi.
* AE'da karaoke subtitr Adobe'ning o'z matn animatsiyasi bilan quriladi.

Salbiy va kim nima qiladi:

* **Ikki texnologiya** (UXP va CEP) — ikki manifest, ikki paket (`.ccx`, `.zxp`), ikki dev yuklash usuli. UI va `EngineClient` umumiy, shuning uchun farq adapter va qobiqda.
* **AE CEP'ga bog'langan.** AE'da UXP rasmiy bo'lganda AE paneli UXP'ga ko'chiriladi (ADB-10); `HostPlan`, UI va mijoz qayta ishlatiladi.
* **Engine alohida ishlashi kerak** (Lahza Studio ochiq yoki mustaqil servis). Panel aniq holat va yo'riqnoma ko'rsatadi.
* **Engine o'zgarishi:** discovery, CORS (UXP/CEP origin'lari, token baribir majburiy), `:hostplan` endpointlari, `GET /v1/hostplan/schema`.
* **Ochiq xavf:** macOS'da UXP loopback HTTP'ga ruxsat beradimi — birinchi haqiqiy host sinovi (ADB-0). Salbiy bo'lsa lokal TLS yoki boshqa yo'l kerak bo'ladi.
* **Sinov:** haqiqiy Adobe'da qo'lda matritsa (Premiere/AE versiyalari × macOS/Windows) — CI'da avtomatlashtirib bo'lmaydi.
* **Tarqatish:** Marketplace ko'rigi (10 ish kuni maqsad), Adobe Developer Terms; tijorat shartlari yurist bilan.

## Ko'rib chiqilgan muqobillar

| Variant | Nega tanlanmadi |
| --- | --- |
| Faqat fayl eksporti (FCP7 XML, SRT, `words.json`) | Allaqachon bor va zaxira sifatida qoladi. Lekin dasturdan chiqish kerak, AE timeline olmaydi, kalit kadrlar va karaoke o'tmaydi |
| Bitta CEP panel ikkala dasturga | Premiere'da UXP 25.6 dan rasmiy, CEP esa forumdagi Adobe vakili so'zlariga ko'ra taxminan bir yildan keyin olib tashlanishi rejalashtirilgan [U21]; yangi Premiere paneli CEP'da yozilsa tez orada qayta yozish kerak |
| Bitta UXP panel ikkala dasturga | AE'da UXP hali beta [U7], qo'llab-quvvatlash matritsasida AE yo'q [U9] |
| OpenFX / AE C++ SDK plagini | Effekt darajasidagi native C++ — timeline qurmaydi (sekvensiya, kesim, subtitr trekini yaratolmaydi); ikki platformada kompilyatsiya va imzo; [`11`](../11-montaj-platformasi.md) 7.3 da Pro g'oyasi sifatida qoladi |
| O'z NLE'mizni (Lahza Studio montaj muharriri) kuchaytirish, Adobe'siz | Studio saqlanadi, lekin professional montajchilar o'z dasturida ishlashni xohlaydi; rang, ovoz, grafika uchun Adobe o'rnini bosish maqsad emas |
| Hisobni plagin ichida (JS/WASM) bajarish | ASR/LLM modellari va Python pipeline qayta yoziladi; UXP/CEP muhitida apparat tezlashtirish va xotira cheklangan |
