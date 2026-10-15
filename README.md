# Lahza Studio

Uzun o'zbekcha podkast va videolardan eng qiziq lahzalarni AI yordamida topib, 9:16 formatdagi, o'zbekcha subtitrli Instagram Reels kliplarini yasaydigan **to'liq oflayn** desktop dastur — macOS (Apple Silicon) va Windows uchun. Video kompyuterdan chiqmaydi; modellar bir marta katalogdan, kompyuterga mos ravishda yuklanadi.

> **Holat: M2 desktop alfa (kod darajasida), R0 kutilmoqda.** Engine testlari: **207 passed, 2 skipped** (libass'siz FFmpeg) — `make test`; `ruff` toza; UI typecheck + build o'tadi. Ishlaydi: import, VAD, imlo, tinish tiklash, gaplar, Lite highlight, reframe (avtomatik split, kalit kadrlar, sahna kesimlari), ASS/SRT/VTT subtitr, FFmpeg render, eksport navbati, `.lzpack`, diagnostika, to'liq Engine API; UI'da transkript muharriri, matn orqali montaj, timeline, preview, model menejeri, 4 til. **R0 ga bog'liq:** haqiqiy ASR/LLM/VAD/aligner/pyannote/BlazeFace modellari bilan o'lchov (kod tayyor), katalogda `approved` modellar, runtime'lar, imzolash, real shriftlar, libass'li render sinovi. CI workflow'lari ([`.github/workflows/`](.github/workflows/)) yozilgan, hali ishga tushirilmagan. Batafsil: [`docs/02-yol-xaritasi.md`](docs/02-yol-xaritasi.md).
>
> Foydalanuvchi qo'llanmasi: [`docs/qollanma.md`](docs/qollanma.md).

## Repozitoriy xaritasi

```
lahza.uz/
├── docs/                    TZ, arxitektura, yo'l xaritasi, ADR'lar, spetsifikatsiyalar
│   ├── qollanma.md          foydalanuvchi qo'llanmasi
│   ├── 00-TZ.md             to'liq texnik topshiriq
│   ├── 01-arxitektura.md    qatlamlar, jarayon modeli, xavfsizlik
│   ├── 02-yol-xaritasi.md   0 dan Pro gacha: bosqichlar, vazifalar, darvozalar
│   ├── 03-…10-*.md          muhit, API, ma'lumot modeli, katalog, pipeline, imlo, test, reliz
│   └── adr/                 arxitektura qarorlari
├── engine/                  Python engine (FastAPI sidecar + CLI)
│   ├── src/lahza_engine/    text, asr, vad, align, diarize, highlight, reframe, subtitle, render, models, core, db, api
│   └── tests/               pytest
├── app/                     Desktop ilova
│   ├── src/                 React + TypeScript UI
│   └── src-tauri/           Tauri 2 (Rust): sidecar boshqaruvi
├── catalog/catalog.json     model katalogi (imzolanadi)
├── eval/                    baholash skriptlari va transkripsiya yo'riqnomasi
├── scripts/                 sidecar, runtime'lar, katalog imzosi, versiya va litsenziya skriptlari
├── third_party/runtimes.toml  whisper.cpp, llama.cpp, FFmpeg versiyalari
└── .github/                 CI va reliz (workflows/), PR va issue shablonlari
```

## Tez boshlash (dasturchi)

Talablar: Python 3.12, Node 22, **libass bilan yig'ilgan FFmpeg** (subtitr render testlari uchun — macOS'da `brew install ffmpeg` libass'siz bo'lishi mumkin, [`docs/03`](docs/03-dasturchi-muhiti.md#ffmpeg-va-libass)), Tauri uchun Rust.

```bash
make setup          # engine venv (dev, onnx, fonts) + UI paketlari
make test           # engine testlari + UI typecheck
make lint           # ruff
make ci             # CI'ning lokal ekvivalenti: versiyalar + lint + tarmoqsiz testlar + UI build
make dev-engine     # engine: http://127.0.0.1:8765 (token: dev-token)
make dev-ui         # UI: http://127.0.0.1:1420
```

FFmpeg libass'siz bo'lsa subtitrni yoqib yozadigan render testlari sababi ko'rsatilgan holda **skip** qilinadi (`pytest -rs`); CI'da esa ular majburiy.

Reliz yordamchilari: `make check-versions` (versiyalar bir xilmi), `python3 scripts/bump_version.py 1.0.0`, `make licenses` (`LICENSES-THIRD-PARTY.md` jadvallari), `make sidecar-dry` (sidecar build rejasi).

Windows: `.\scripts\dev.ps1 setup | test | lint | check-versions | ci | engine | ui | sidecar`. To'liq yo'riqnoma: [`docs/03-dasturchi-muhiti.md`](docs/03-dasturchi-muhiti.md).

## Qanday ishlaydi

```
video → ingest → VAD → ASR (o'zbekcha) → imlo → so'z vaqtlari → spikerlar → gaplar → signallar → highlight (LLM yoki Lite)
klip → reframe 9:16 (focus / split / xira fon) → karaoke subtitr (ASS) → FFmpeg (apparat enkoder) → MP4 + SRT + caption + muqova
```

Asosiy qarorlar:

* **Tauri + Python sidecar** — kichik o'rnatuvchi, ML ekotizimi Python'da ([ADR-0001](docs/adr/0001-tauri-python-sidecar.md)).
* **Modellarsiz o'rnatish, imzolangan katalog** — dastur kompyuterga mos to'plamni o'zi yuklaydi ([ADR-0002](docs/adr/0002-oflayn-model-katalogi.md)).
* **LLM gap ID qaytaradi, vaqtni kod hisoblaydi** — klip hech qachon so'z o'rtasida kesilmaydi ([ADR-0005](docs/adr/0005-llm-gap-id.md)).
* **LGPL FFmpeg + apparat enkoderlari** ([ADR-0004](docs/adr/0004-lgpl-ffmpeg-apparat-enkoder.md)).
* **Uch imlo rejimi**: rasmiy (oʻ, gʻ), ASCII (o', g'), yangi alifbo (ö, ğ, ş, ç) ([ADR-0008](docs/adr/0008-ichki-imlo-rasmiy.md)).

## Keyingi qadam

R0 bosqichi: o'z podkastlaringizdan **UzPodcast-Eval** to'plamini yig'ish va [`eval/YORIQNOMA.md`](eval/YORIQNOMA.md) bo'yicha transkripsiya qilish — ASR modelini tanlash shunga bog'liq.

## Litsenziyalar

[`LICENSES-THIRD-PARTY.md`](LICENSES-THIRD-PARTY.md)
