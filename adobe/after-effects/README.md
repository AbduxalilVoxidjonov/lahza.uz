# Lahza — After Effects paneli (CEP 12)

After Effects ichidagi panel: tanlangan footage'ni Lahza Engine'da tahlil qiladi, eng yaxshi lahzalarni ko'rsatadi va
host-reja (`lahza.hostplan/1`) bo'yicha AE kompozitsiyasini yasaydi (kesimlar, reframe kalit kadrlari, xira fon, split,
o'tishlar, matnlar, markerlar, musiqa + ducking). Alohida tugma — **karaoke subtitr** (so'z vaqtlari bo'yicha Text Animator
highlight). Render'ni After Effects qiladi; og'ir hisob (ASR, highlight, reframe, montaj) — engine'da (`127.0.0.1`).

## Talablar

| | Qiymat | Manba |
| --- | --- | --- |
| CEP | 12 (`ExtensionManifest Version="12.0"`, `RequiredRuntime CSXS 12.0`) | CEP-Resources `CEP_12.x/Samples/CEP_HTML_Test_Extension-12.0/CSXS/manifest.xml` |
| After Effects | `AEFT` 25.0+ (manifest: `[25.0,99.9]`) | CEP 12 HTML Extension Cookbook — host jadvali: After Effects `25.0 (CEP 12)` |
| Brauzer dvigateli | CEF 99 / Chromium 99, Node.js 17.7.1 | Cookbook — CEF jadvali (bundle `target: chrome99`) |
| Engine | `lahza serve --discovery` (`engine.json`) | `docs/04-engine-api.md` — "Adobe plaginlari" |

## Tuzilma

```
CSXS/manifest.xml   CEP manifest (AEFT, CSXS 12, --enable-nodejs --mixed-context, ScriptPath ./jsx/host.jsx)
.debug              faqat dev: Chrome DevTools porti 8098 (.zxp ga kirmaydi)
index.html          ./dist/main.js va ./dist/main.css ni nisbiy yo'l bilan oladi (file:// da ishlaydi)
jsx/host.jsx        ExtendScript (ES3): lahza_selectedFootagePaths, lahza_projectInfo, lahza_buildComp, lahza_buildKaraoke, lahza_ping
jsx/json2.jsx       Crockford json2.js (Public Domain) — ExtendScript'da JSON yo'q
src/host/bridge.ts  window.__adobe_cep__.evalScript promise o'rami (CSInterface.js ishlatilmaydi)
src/host/discovery.ts  engine.json ni CEP Node bilan o'qish
src/ui/*            React UI (uz/en)
test/*              vitest: ES3 sintaksis, soxta AE obyekt modeli, bridge, yordamchilar
```

`adobe/shared/src` (engine mijozi, host-reja turlari) nisbiy import bilan bundle'ga kiradi.

## Build va test

```bash
cd adobe/after-effects
npm install
npm run typecheck   # tsc --strict
npm test            # vitest
npm run build       # esbuild -> dist/main.js (IIFE, chrome99)
npm run watch       # dev: o'zgarishda qayta build (inline sourcemap)
```

## Dev o'rnatish

macOS:

```bash
adobe/scripts/cep-dev-install.sh            # symlink + PlayerDebugMode (CSXS.11, CSXS.12)
adobe/scripts/cep-dev-install.sh --uninstall
```

Windows (PowerShell):

```powershell
powershell -ExecutionPolicy Bypass -File adobe\scripts\cep-dev-install.ps1
powershell -ExecutionPolicy Bypass -File adobe\scripts\cep-dev-install.ps1 -Uninstall
```

Skriptlar nima qiladi (Cookbook bo'yicha):
* foydalanuvchi extensions papkasi: macOS `~/Library/Application Support/Adobe/CEP/extensions`,
  Windows `%APPDATA%\Adobe\CEP\extensions` — u yerga `uz.lahza.ae` nomli symlink/junction shu papkaga;
* imzosiz panel: macOS `defaults write com.adobe.CSXS.12 PlayerDebugMode 1`, Windows `HKCU\Software\Adobe\CSXS.12`
  `PlayerDebugMode` = `"1"` (String). macOS plist keshi uchun `cfprefsd` qayta ishga tushiriladi (yoki qayta kiring);
* sudo/administrator kerak emas; tizim papkalariga (`/Library/...`, `Program Files`) yozilmaydi.

So'ng AE'ni qayta ishga tushiring: **Window → Extensions → Lahza**. Papka yo'lida `#` bo'lmasin (CEP yuklamaydi).

Tarqatish uchun imzo: [`adobe/scripts/sign-zxp.md`](../scripts/sign-zxp.md).

## Debug

* Panel ochiq turganda Chrome'da `http://localhost:8098` → panel sahifasi → DevTools (`.debug` dagi port).
* UI'ni yangilash: `npm run build` (yoki `watch`) va DevTools'da `Cmd/Ctrl+R`.
* ExtendScript: `host.jsx` o'zgarsa panelni qayta yuklash yetmasligi mumkin (ExtendScript dvigateli funksiyalarni saqlaydi) —
  bridge `typeof lahza_buildComp` bo'lmasa qayta yuklaydi; ishonch uchun AE'ni qayta oching.
* CEP loglari: `defaults write com.adobe.CSXS.12 LogLevel 6` (macOS), loglar `~/Library/Logs/CSXS/`.
* Engine'ni qo'lda ulash: Node yoqilmagan yoki `engine.json` topilmasa panel port/token so'raydi (localStorage'da saqlanadi).

## Ish oqimi

1. **Engine**: `engine.json` → `GET /v1/health` + `GET /v1/hostplan/schema` (eskirgan fayl va versiya mosligi tekshiriladi).
2. **Reels**: Project panelida footage (yoki faol comp'da qatlam) tanlanadi → `ensureProject("After Effects")` →
   `/v1/media:import` → job polling → lahzalar (qabul/rad) → format (9:16/1:1/16:9) va imlo → `:hostplan` (out_dir — saqlangan
   loyiha papkasi yoki uy papkasi ostida `Lahza`, absolyut) → `lahza_buildComp`. **Karaoke subtitr** — o'sha reja bilan
   `lahza_buildKaraoke(plan, compName)`.
3. **Montaj**: shablon + tanlangan footage'lar → `/v1/montages` → job → `/v1/montages/{id}:hostplan` → `lahza_buildComp`.
4. **Natija**: kompozitsiya nomi, qatlamlar soni va "Nima o'tmadi" (host ogohlantirishlari + `not_translated`).

## host.jsx: rejadan AE'ga

| Host-reja | After Effects |
| --- | --- |
| `sequence` | `items.addComp(name, w, h, 1, duration, fps)` (`Lahza` papkasida, nom band bo'lsa ` (2)`) |
| `media` | `importFile(new ImportOptions(File))` — loyihada shu fayl bo'lsa qayta ishlatiladi |
| `VideoClipItem` | `layers.add(footage)`: `stretch = 100/speed`, `startTime = rec_in − src_in/speed`, `inPoint/outPoint = rec_in/rec_out`; ovoz faqat bitta qatlamda (main/top), `volume_db` → `ADBE Audio Levels`, `mute` → `audioEnabled=false` |
| `HostLayer.keys` | anchor = manba markazi; `ADBE Scale`/`ADBE Position`/`ADBE Rotate Z` kalit kadrlari (vaqt = `rec_in + t`); `hold` → HOLD, `ease` → BEZIER + `KeyframeEase(0, 33.33)` (soni `propertyValueType` bo'yicha), `linear` → LINEAR |
| `gaussian_blur` | `ADBE Gaussian Blur 2`, Blurriness = `amount` (60), Repeat Edge Pixels |
| `crop_rect` (split) | kompozitsiya o'lchamidagi precomp (ichida transform) + kompozitsiya koordinatasida to'rtburchak mask (`ADBE Mask Atom` / `ADBE Mask Shape`) |
| `cross_dissolve` (va `push`/`wipe`/`zoom`) | yangi element qatlamlari opacity 0→100 (`dur_s`). Montajda elementlar allaqachon ustma-ust; klip rejasida (ustma-ust yo'q) oldingi element manba yetgancha cho'ziladi |
| `dip_to_black/white` | qora/oq solid, opacity 0→100→0; ustma-ust bo'lsa almashish uning o'rtasida |
| `TextOverlay` | Text qatlam (uslub `captions.style`), `card` — to'liq kadr rangli solid + matn; boshqalarda `background` — matn ortidagi plashka |
| `markers` | `comp.markerProperty.setValueAtTime(t, new MarkerValue(...))`, `label` turi bo'yicha |
| `MusicItem` | audio qatlam, Audio Levels kalit kadrlari: fade in/out (−60 dB), `duck` — `captions.lines` nutq bo'laklarida −10 dB |
| `captions` (karaoke) | har qator — Text qatlam (in/out = qator vaqti), xavfsiz zona (pastdan 35%, yuqoridan 14%, yonlardan 6% — kengroq bo'lsa kichraytiriladi); Text Animator "Lahza highlight": `ADBE Text Fill Color` = `highlight_color`, Range Selector Units = Index, `Index Start/End` HOLD kalit kadrlari so'z vaqtlarida; `keywords` — doimiy highlight; `uppercase`, `box`, kontur |

## Cheklovlar

* After Effects bu repoda ishga tushirilmagan: host.jsx faqat soxta AE obyekt modelida testlangan (`test/mock-ae.ts`).
  Haqiqiy AE'da birinchi sinov kerak (quyidagi ANIQLANSIN ro'yxati).
* `lumetri_preset`, `lut` AE'da qo'llanmaydi (ogohlantirish); `pop` animatsiyasi — rang highlight; `shadow` qo'shilmaydi;
  `push/wipe/zoom` — cross dissolve.
* `font_family` → PostScript nom taxmini (`Inter-Bold`); shrift o'rnatilmagan bo'lsa AE o'rinbosar qo'yadi.
* Ducking — kalit kadrlar bilan (AE'da Essential Sound yo'q).
* Node faqat `engine.json` uchun; tarmoq so'rovlari faqat `127.0.0.1` dagi engine'ga (Origin `null` — engine CORS ruxsat beradi).

### ANIQLANSIN (haqiqiy AE'da tekshirilsin)

* `ADBE Text Range Units` dropdown qiymati `2` = Index (rasmiy matchName jadvalida qiymatlar yo'q). O'rnatilmasa foiz bilan ishlaydi.
* `ADBE Gaussian Blur 2-0003` (Repeat Edge Pixels) — faqat skill qoidasida; xato bo'lsa e'tiborsiz qoldiriladi.
* `ADBE Audio Levels` qiymati `[dB, dB]` (2 kanal) — matchName rasmiy, qiymat shakli umumiy amaliyot.
* `TextDocument.font` PostScript nomi; `strokeOverFill`.
* `$.evalFile` bilan json2/host qayta yuklash (`$.fileName` birinchi yuklangan JSX'da noto'g'ri — Cookbook; shuning uchun yo'l panel tomonidan beriladi).
