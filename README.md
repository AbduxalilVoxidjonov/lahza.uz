# Lahza Studio

Uzun o'zbekcha podkast va videolardan eng qiziq lahzalarni AI yordamida topib, 9:16 formatdagi, o'zbekcha subtitrli Instagram Reels kliplarini yasaydigan **to'liq oflayn** desktop dastur — macOS (Apple Silicon) va Windows uchun. Video kompyuterdan chiqmaydi; modellar bir marta katalogdan, kompyuterga mos ravishda yuklanadi.

**Lokal alfa ustida amaliy tekshiruv (2026-10-24):** CPU ASR bootstrap va boshlash oynasidan model yuklash, libass'li LGPL FFmpeg, Inter shrifti va Mac `.app` yig'ish yo'li qo'shildi. Haqiqiy o'zbekcha videoda texnik eksport ishladi, lekin oddiy Whisper base transkripti sifatsiz chiqdi — bu model sifat tasdig'i emas. Joriy ko'rsatmalar: [lokal modellar](docs/local-models.md), [render](docs/local-render.md), [desktop build](docs/local-desktop.md). [Tashqi montaj fayllari](docs/13-external-assets.md): `.cube` LUT qo'llanadi, SRT/preset/MOGRT ma'lumotlari tekshiriladi; Adobe native plaginlarini Adobe'siz bajarish qo'llanmaydi.

**Yangi lokal imkoniyatlar:** stikerlar (PNG/WebP/GIF), caption/SRT, stop-kadr va o'rnatiladigan `.lahzaskill` montaj retseptlari. NavAI Uzbek small bilan haqiqiy videoda 318 so'z, 3 klip va subtitrli eksport tekshirildi; transkript hali tahrir talab qiladi. Amaliy holat va cheklovlar: [lokal alfa qaydi](docs/local-alpha.md).

**AI montajning birinchi bosqichi:** haqiqiy lokal Qwen3 modelidan qat'iy reja,
tekshiriladigan executor va undo bilan draftga qo'llash qo'shildi. Model taklifi
ma'no jihatdan xato bo'lishi mumkin; qo'llashdan oldin ko'rib chiqiladi.
O'rnatish: `make setup-local-llm` (~2.5 GB, ixtiyoriy tarmoq amali).
[AI yordamchi](docs/local-ai-editing.md) · [yo'l xaritasi](docs/14-agentic-roadmap.md).
Erkin o'zbekcha promptdan to'g'ri reja va 12 soniyali MP4/SRT olindi; ayrim
iboralarda ("yoq"/"yo'q") model adashadi, shuning uchun reja avtomatik qo'llanmaydi.
Shu model LLM highlight uchun bo'sh javob berdi — highlight Lite rejimda qoladi.

Tejamkor montaj namunasi (matndan kesish, VAD tozalash, bir o'tishli render,
alohida test bilan): [`examples/efficient_pipeline/`](examples/efficient_pipeline/README.md).

```sh
make setup-local   # Mac: bog'liqliklar, FFmpeg, boshlang'ich model (internetdan yuklaydi)
make build-local   # lokal .app
make smoke-local VIDEO=/absolute/podcast.mp4
```

> **Holat: lokal alfa.** Manba testlari (2026-10-29, `make ci` offline): engine **1302 passed, 13 skipped** (paket tekshiruvlari alohida opt-in bajariladi), UI **124 passed**, Adobe plaginlari **26 + 35 passed**; Ruff va UI build o'tadi. Apple Silicon macOS 27+ uchun lokal `.app` yig'ildi. Haqiqiy NavAI small bilan transkripsiya va subtitrli render tekshirildi; o'zbekcha aniqlik hali etalon bilan baholanmagan. Windows NSIS o'rnatuvchisi (per-user, adminsiz) yig'ilgan, lekin imzosiz va toza kompyuterda sinalmagan; eski macOS versiyalari, haqiqiy modellar bilan uzoq video chidamliligi va production imzolash hali tugallanmagan. Batafsil: [`docs/local-alpha.md`](docs/local-alpha.md), [`docs/02-yol-xaritasi.md`](docs/02-yol-xaritasi.md).
>
> Foydalanuvchi qo'llanmasi: [`docs/qollanma.md`](docs/qollanma.md).
>
> **Adobe plaginlari (loyiha):** [`docs/12-adobe-plaginlar.md`](docs/12-adobe-plaginlar.md) — Lahza paneli Premiere Pro (UXP) va After Effects (CEP) ichida: tahlil, lahzalar va dastur ichida Reels sekvensiyasi/kompozitsiyasi; desktop ilova bilan bitta engine. Kod: [`adobe/`](adobe/README.md).
>
> **Kengaytma (qisman amalga oshirildi — video shablonlar va montaj):** [`docs/11-montaj-platformasi.md`](docs/11-montaj-platformasi.md) — Lahza Montaj: video yoki YouTube havola → Reels, montaj plaginlari va retseptlar, video to'plamidan avtomontaj, Premiere / DaVinci / Filmora / After Effects bilan ko'prik, "haqiqiy kadr" tamoyili.

## Repozitoriy xaritasi

```
lahza.uz/
├── docs/                    TZ, arxitektura, yo'l xaritasi, ADR'lar, spetsifikatsiyalar
│   ├── qollanma.md          foydalanuvchi qo'llanmasi
│   ├── 00-TZ.md             to'liq texnik topshiriq
│   ├── 01-arxitektura.md    qatlamlar, jarayon modeli, xavfsizlik
│   ├── 02-yol-xaritasi.md   0 dan Pro gacha: bosqichlar, vazifalar, darvozalar
│   ├── 03-…10-*.md          muhit, API, ma'lumot modeli, katalog, pipeline, imlo, test, reliz
│   ├── 11-montaj-platformasi.md  kengaytma: shablonlar, plaginlar, avtomontaj, NLE ko'prigi (qisman)
│   ├── 12-adobe-plaginlar.md     Premiere Pro va After Effects plaginlari (loyiha)
│   └── adr/                 arxitektura qarorlari
├── engine/                  Python engine (FastAPI sidecar + CLI)
│   ├── src/lahza_engine/    text, asr, vad, align, diarize, highlight, reframe, subtitle, render, montage, templates, fx, models, core, db, api
│   └── tests/               pytest
├── app/                     Desktop ilova
│   ├── src/                 React + TypeScript UI
│   └── src-tauri/           Tauri 2 (Rust): sidecar boshqaruvi
├── adobe/                   Premiere Pro (UXP) va After Effects (CEP) ichidagi Lahza paneli — shared/, premiere/, after-effects/, scripts/
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
