# Lahza — Premiere Pro UXP paneli

Premiere Pro ichidagi panel. Loyihadagi klipni Lahza Engine'da tahlil qiladi, eng yaxshi lahzalarni ko'rsatadi va tanlangan lahzadan
**Premiere'ning o'zida** 9:16 (1:1, 16:9) sekvensiya quradi: kesimlar, Motion (Scale/Position) kalit kadrlari, xira fon
(Gaussian Blur), markerlar, subtitr (SRT). Montaj tabida video shablon va loyihada tanlangan kliplardan montaj yasaladi. Render'ni
Premiere qiladi. Og'ir hisob (ASR, highlight, reframe, montaj rejasi) — Lahza Engine'da (`lahza serve`, 127.0.0.1).

## Talablar

* **Premiere Pro 25.6 yoki yangiroq** (`manifest.json` → `host.minVersion: "25.6.0"`). UXP Premiere'da 25.2 da public beta, 25.6 dan
  rasmiy ([changelog](https://developer.adobe.com/premiere-pro/uxp/changelog)). Ishlatilgan API'lar "Since 25.6" (`ppro-reference`).
* UXP Developer Tool (UDT) 2.2+ (dev yuklash va `.ccx` paketlash uchun).
* Lahza Studio (engine bilan) o'rnatilgan va ishlab turgan bo'lishi. **Panel engine'ni o'zi ishga tushirmaydi** (Marketplace
  qoidasi) — panelda "Lahza Studio'ni oching" yo'riqnomasi chiqadi.
* Node 20+ (build uchun; sinalgan: Node 26).

## Build va test

```bash
cd adobe/premiere
npm install
npm run typecheck   # tsc --strict (shared/src ham)
npm test            # vitest: build mantiqi (fake host), premiere.ts (soxta premierepro), engine oqimi (mock fetch)
npm run build       # dist/ — UDT shu papkani yuklaydi
```

Bundler — Vite 8 (rasmiy `uxp-premiere-pro-samples/premiere-api` namunasi kabi), bitta CJS `dist/index.js`; `premierepro`, `uxp`,
`os`, `fs` tashqi — ularni UXP `require()` beradi. UI — React 18 (`createRoot`). `public/` (manifest, index.html, styles.css,
ikonlar) `dist/` ga ko'chiriladi.

## Dev yuklash (UXP Developer Tool)

1. `npm run build`.
2. UDT → **Add Plugin** → `adobe/premiere/dist/manifest.json` ni tanlang.
   (Yoki `public/manifest.json` ni qo'shib, **••• → Options → Advanced** da build papkasi sifatida `../dist` ni bering.)
3. Premiere ochiq bo'lsin → UDT'da **Load**. Panel: **Window → UXP Plugins → Lahza**.
4. Kod o'zgarganda: `npx vite build --watch` + UDT'da **Load & Watch**. Debug — UDT **Debug** (Chrome DevTools).

## Engine bilan ulanish

* Lahza Studio engine'ni `--discovery` bilan ishga tushiradi (yoki terminalda `lahza serve --discovery`): engine
  `<data_dir>/engine.json` (`port`, `token`) yozadi. `data_dir`: macOS `~/Library/Application Support/Lahza Studio`, Windows
  `%LOCALAPPDATA%\Lahza Studio`. Panel faylni UXP `fs` bilan o'qiydi (`localFileSystem: "fullAccess"` — `file:/` sxemasi faqat
  shu ruxsat bilan ishlaydi, [filesystem recipe](https://developer.adobe.com/premiere-pro/uxp/resources/recipes/filesystem-operations)).
* Fayl eskirgan bo'lishi mumkin (engine SIGKILL bo'lsa) — panel `pid`ga emas, `GET /v1/health` va `GET /v1/hostplan/schema`
  ga tayanadi (ikkalasi ham token bilan).
* Zaxira: panelda **Qo'lda ulash** — port va token (Lahza Studio → Sozlamalar).
* **Tarmoq ruxsati.** UXP'da domen manifestda bo'lmasa so'rov rad etiladi. `manifest.json`:
  `"network": {"domains": ["http://127.0.0.1", "http://127.0.0.1:47600", "http://127.0.0.1:47601", "http://127.0.0.1:47602"]}`.
  Port bilan yozish — [AdobeDocs/uxp-photoshop#321](https://github.com/AdobeDocs/uxp-photoshop/issues/321) da `http://127.0.0.1:11434`
  ishlagani, `localhost` satri ishlamagani haqidagi foydalanuvchi xabari asosida (rasmiy tasdiq yo'q). Shuning uchun engine
  plaginlar uchun **qat'iy portlardan** (47600–47602) birida ishlashi tavsiya etiladi (engine'ga kerakli o'zgarish).
  Dev'da tekshirish uchun vaqtincha `"domains": "all"` qo'yish mumkin.
* **macOS va `http://`.** Adobe: "macOS restricts `http://` for security reasons" ([network recipe](https://developer.adobe.com/premiere-pro/uxp/resources/recipes/network)).
  127.0.0.1 istisnosi hujjatda yo'q — **haqiqiy Premiere'da tekshirilishi kerak**. HTTP ulanmasa panel avtomatik ravishda
  **fayl-IPC** zaxirasiga o'tadi (`src/transport.ts`, protokol `lahza.ipc/1`: `<data_dir>/ipc/requests|responses/<id>.json`)
  — bu engine tomonida alohida amalga oshirilishi kerak. Panelda "fayl orqali (IPC)" belgisi ko'rinadi.
* **CORS.** Engine `null` va `file://` origin'lariga ruxsat beradi. UXP qaysi `Origin` yuborishi hujjatda yo'q. Agar engine logida
  CORS rad etilishi ko'rinsa, haqiqiy qiymatni (UDT Debug → Network → so'rov sarlavhalari) engine'ga qo'shing:
  ```bash
  LAHZA_CORS_ORIGINS="<UXP origin qiymati>" lahza serve --discovery
  ```
  Token baribir majburiy.

## Foydalanish

* **Reels**: Project panelida (yoki timeline'da) klipni tanlang → **Tahlil qilish** (engine'da "Premiere" loyihasi, `/v1/media:import`,
  progress) → lahzalar (ball, sarlavha, davomiylik, sabab; qabul/rad) → format va imlo (rasmiy / ASCII / yangi alifbo) →
  **Reels yasash** → `:hostplan` → yangi sekvensiya + "Nima o'tmadi" ro'yxati.
* **Montaj**: shablonni tanlang, loyihada bir nechta klipni tanlang → **Montaj qilish** (`/v1/montages` → job → `:hostplan`) → sekvensiya.
* Engine chiqishi (SRT, `_words.json`): `<data_dir>/premiere/<epizod>_<klip>/` (absolyut, panel ota papkani yaratadi).

## `.ccx` paketlash va o'rnatish

* `.ccx` — oddiy ZIP, lekin Adobe uni **UDT bilan** yaratishni tavsiya qiladi: UDT → plagin **••• → Package** → papka tanlang →
  `uz.lahza.premiere_premierepro.ccx` ([Package a UXP plugin](https://developer.adobe.com/premiere-pro/uxp/plugins/distribution/package)).
  UXP'da imzo/timestamp kerak emas (CEP `.zxp` dan farqli).
* O'rnatish: `.ccx` ni ikki marta bosish (Creative Cloud Desktop o'rnatadi) yoki UPIA (`UnifiedPluginInstallerAgent`) CLI.
* Marketplace uchun `manifest.json` `id` Developer Distribution portalidagi ID bilan bir xil bo'lishi kerak; boshqa kanallar uchun
  alohida ID tavsiya etiladi.

## Arxitektura

```
src/
  main.tsx              kirish: Premiere'da PremiereAdapter, brauzerda FakeAdapter
  uxp-env.ts            UXP require() o'ramlari (os, fs, premierepro)
  engineLocator.ts      engine.json topish (dataDir, parseDiscovery), qo'lda port/token, probe
  transport.ts          HTTP fetch + fayl-IPC zaxira (lahza.ipc/1)
  connection.ts         locate -> EngineClient -> health/schema
  flow.ts               analyze -> clips -> hostplan -> build; montaj
  host/adapter.ts       HostAdapter (selectedMediaPaths, projectInfo, buildFromPlan) va past darajadagi HostOps
  host/build.ts         host-reja -> HostOps ketma-ketligi (host-neytral, fallback'lar shu yerda)
  host/premiere.ts      haqiqiy UXP: require("premierepro")
  host/fake.ts          yozib oluvchi soxta host
  i18n.ts               uz (asosiy) + en
  ui/                   React komponentlari
```

Treklar: rollar pastdan yuqoriga `bg → bottom → main → top` (faqat rejada borlari). Audio: asosiy qatlam → A1, musiqa → A2,
bg/top nusxalarining audiosi A3 ga tushadi va o'chiriladi. Kliplar `createInsertProjectItemAction(..., limitShift=true)` bilan
rec_in tartibida qo'yiladi (hujjat: mavjud bo'lmagan trek indeksi berilsa trek yaratiladi). Montajdagi ustma-ust o'tishli elementlar
kesim nuqtasiga keltiriladi (manba boshi ham suriladi, ustma-ust qism o'tish uchun handle bo'ladi).

## Cheklovlar (Premiere UXP API, 26.5 holatiga)

| Imkoniyat | Holat | Panel nima qiladi |
| --- | --- | --- |
| Tezlik (speed) | API yo'q (`getSpeed` faqat o'qish) | 1x, rec davomiyligi saqlanadi, ogohlantirish |
| SRT → Captions treki | Import bor, trekka qo'yish API'si yo'q (`CaptionTrack` faqat o'qish/nom/mute) | SRT loyihaga import qilinadi; foydalanuvchi Timeline'ga sudraydi |
| Subtitr uslubi (uppercase, rang, kalit so'z) | Caption uslubini o'rnatish API'si yo'q | Premiere'ning Captions/Essential Graphics'ida qo'lda; AE plaginida karaoke |
| Matn qatlamlari (hook, CTA) | Faqat MOGRT (`insertMogrtFromPath`) | Davomiyli marker + ogohlantirish |
| Lumetri preset, LUT | Lumetri parametrlarini preset/LUT fayl bilan to'ldirish tasdiqlanmagan | Ogohlantirish |
| Musiqa fade/ducking | Audio Level kalit kadrlari va Essential Sound API'si tasdiqlanmagan | Ogohlantirish |
| Audio daraja | Volume/Level birligi hujjatda yo'q | ExtendScript formulasi bilan taxminiy (`audio_level_approx`) |
| Motion kalit kadrlari | API bor (`ComponentParam`), lekin vaqt asosi va Position birligi tasdiqlanmagan | Ishlamasa — birinchi kadr statik + ogohlantirish |
| Gaussian Blur, Crop, o'tishlar | API bor; matchName'lar runtime ro'yxatdan qidiriladi | Topilmasa — ogohlantirish |

Koddagi `// ANIQLANSIN:` izohlari — haqiqiy Premiere'da birinchi sinovda tekshiriladigan joylar (ro'yxat: `grep -rn ANIQLANSIN src`).
Bu mashinada Premiere yo'q: `premiere.ts` faqat soxta `premierepro` modeli bilan testlangan (`test/mockPpro.ts`).
