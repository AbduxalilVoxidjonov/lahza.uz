# Lahza — Adobe plaginlari

Premiere Pro va After Effects ichidagi Lahza paneli. Panel videoni Lahza Engine'da tahlil qiladi, eng yaxshi lahzalarni ko'rsatadi va
"Reels yasash" bosilganda dastur ichida 9:16 sekvensiya yoki kompozitsiya quradi. Kesimlar, kadr kalit kadrlari va o'zbekcha subtitr ham shu yerda qo'yiladi.
Render'ni Adobe qiladi. Hisob (ASR, highlight, reframe, montaj rejasi) Lahza Engine'da (`127.0.0.1`) bajariladi; Lahza Studio desktop ilovasi bilan engine bitta.

Spetsifikatsiya: [`docs/12-adobe-plaginlar.md`](../docs/12-adobe-plaginlar.md) · Qaror: [ADR-0014](../docs/adr/0014-adobe-plaginlar.md)

> Holat: kod darajasida (soxta adapter va mock'lar bilan testlanadi). Haqiqiy Premiere / After Effects'da hali sinalmagan.

## Tuzilma

```
adobe/
├── shared/          umumiy TS: hostplan.ts (lahza.hostplan/1 turlari + assertHostPlan), engine.ts (EngineClient, discovery), types.ts
├── premiere/        Premiere Pro UXP paneli (manifest v5, React + TS, Vite) — src/host/ adapter (premiere.ts, fake.ts)
├── after-effects/   After Effects CEP paneli (CSXS/manifest.xml, React + TS) + jsx/host.jsx (ExtendScript, ES3)
├── scripts/         dev o'rnatish yordamchilari (CEP extensions papkasiga symlink, PlayerDebugMode)
└── README.md
```

Har plagin o'z `package.json` iga ega; `shared/` ni nisbiy import yoki bundler alias orqali oladi. `shared/` ni faqat host-reja yoki engine shartnomasi o'zgarganda yangilang —
u `engine/src/lahza_engine/hostplan/model.py` bilan bir xil bo'lishi shart.

## Talablar

| Nima | Versiya / izoh | Manba |
| --- | --- | --- |
| Adobe Creative Cloud obunasi | Premiere Pro va/yoki After Effects o'rnatilgan, kamida bir marta ishga tushirilgan | — |
| Premiere Pro | **25.6+** (UXP rasmiy); ba'zi API'lar 26.3 dan — `adobe/premiere/README.md` ga qarang | [changelog](https://developer.adobe.com/premiere-pro/uxp/changelog) |
| After Effects | **25.0+** (CEP 12) | [CEP 12 Cookbook](https://github.com/Adobe-CEP/CEP-Resources/blob/master/CEP_12.x/Documentation/CEP%2012%20HTML%20Extension%20Cookbook.md) |
| UXP Developer Tool | 2.2+ (Premiere panelini dev rejimida yuklash) | [network recipe](https://developer.adobe.com/premiere-pro/uxp/resources/recipes/network) |
| ZXPSignCmd | `.zxp` ni imzolash (faqat AE paketini tarqatish uchun) | [CEP-Resources](https://github.com/Adobe-CEP/CEP-Resources) |
| Node | 22+ (repo bo'yicha; plagin build'lari uchun) | — |
| Lahza Engine | repo'dagi `engine/` (Python 3.12) yoki o'rnatilgan Lahza Studio | — |
| OS | macOS (Apple Silicon) yoki Windows 11 x64 | — |

## Tez boshlash

**1. Engine'ni discovery bilan ishga tushiring.** Panel engine'ni `<data_dir>/engine.json` orqali topadi
(macOS `~/Library/Application Support/Lahza Studio`, Windows `%LOCALAPPDATA%\Lahza Studio`).

```bash
cd engine && source .venv/bin/activate
lahza serve --discovery          # yoki: LAHZA_DISCOVERY=1 lahza serve
```

Lahza Studio o'rnatilgan bo'lsa, uning engine'i ham ishlaydi. Panel engine'ni o'zi ishga tushirmaydi (Adobe Marketplace qoidasi).

**2. Premiere Pro paneli (UXP).**

```bash
cd adobe/premiere && npm install && npm test && npm run build
```

Premiere → Settings → Plugins → **Developer Mode** yoqiladi, UXP Developer Tool'da `dist/manifest.json` qo'shiladi va **Load** bosiladi.
Panel: Window → UXP Plugins → Lahza. Batafsil va `.ccx` paketlash: [`premiere/README.md`](premiere/README.md).

**3. After Effects paneli (CEP).**

```bash
cd adobe/after-effects && npm install && npm run check
```

Imzosiz panel uchun `PlayerDebugMode` yoqiladi:
macOS — `defaults write com.adobe.CSXS.12 PlayerDebugMode 1`; Windows — `HKEY_CURRENT_USER\Software\Adobe\CSXS.12` da `PlayerDebugMode` = `"1"` (string).
So'ng panel papkasi CEP extensions papkasiga (macOS `~/Library/Application Support/Adobe/CEP/extensions`, Windows `%APPDATA%\Adobe\CEP\extensions`) symlink qilinadi —
`adobe/scripts/` yordamchilari bilan. AE: Window → Extensions → Lahza. Batafsil va `.zxp` imzolash: [`after-effects/README.md`](after-effects/README.md).

## Testlar (Adobe'siz)

* `shared/` — `EngineClient` (mock `fetch`), discovery.
* `premiere/` — `HostPlan` → soxta adapter chaqiruvlari ketma-ketligi, typecheck, build.
* `after-effects/` — `host.jsx` ES3 sintaksis tekshiruvi (acorn) va Node'dagi soxta AE obyekt modeli; typecheck, build.
* Haqiqiy host'dagi qo'lda sinov matritsasi: [`docs/12`, 8-bo'lim](../docs/12-adobe-plaginlar.md#8-test-strategiyasi).

## Xavfsizlik

Tarmoq so'rovlari faqat `127.0.0.1` dagi engine'ga, har so'rov `engine.json` dagi token bilan. Tashqi serverlar, telemetriya yo'q.
