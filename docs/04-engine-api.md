# Engine API

Manba: `engine/src/lahza_engine/api/app.py`. Engine faqat `127.0.0.1` da. Har so'rov `Authorization: Bearer <token>`; `<video>` va WebSocket uchun `?t=<token>`. Xato javobi: `{"detail": "<o'zbekcha xabar>"}` va HTTP kodi.

CORS: UI engine'ga boshqa origin'dan murojaat qiladi, shuning uchun `CORSMiddleware` faqat Tauri webview origin'lariga (`tauri://localhost`, `http(s)://tauri.localhost`) ruxsat beradi; `LAHZA_DEV=1` da Vite dev server (`http://127.0.0.1:1420`, `http://localhost:1420`) ham qo'shiladi; Adobe plaginlari uchun `null` va `file://` (CEP paneli; `LAHZA_ADOBE_CORS=0` bilan o'chiriladi — "Adobe plaginlari" bo'limiga qarang); qo'shimchalari — `LAHZA_CORS_ORIGINS` (vergul bilan). Token baribir majburiy. WebSocket uchun engine `websockets` paketiga bog'liq (uvicorn'ning o'zida WS yo'q).

Bu ro'yxat TZ 3-bo'limdagi endpointlarni aniqlashtiradi: transkript va kliplar epizod bazasida saqlangani uchun yo'llar `/v1/episodes/{id}/...` ko'rinishida.

## Tizim

| Metod | Yo'l | Tana | Javob |
| --- | --- | --- | --- |
| GET | `/v1/health` | — | `{"version": "0.1.0", "ok": true}` |
| GET | `/v1/hardware` | — | `{"profile": {...}, "tier": "standard", "reasons": [...]}` |
| GET | `/v1/capabilities?refresh=false` | — | `{"ffmpeg": bool, "libass": bool, "encoders": string[], "vad": "silero"\|"energy", "aligner": bool, "diarizer": bool, "face_detector": bool, "llm": bool}` |
| POST | `/v1/diagnostics` | `{"out_dir"}` | `{"path"}` — zip |
| POST | `/v1/system:reveal` | `{"path"}` | `{"ok": true}` |

* `capabilities`: `libass` — `ffmpeg -filters` da `ass` filtri bor-yo'qligi (`render.capabilities.has_filter`); `encoders` — mavjud H.264/HEVC enkoderlari (`-encoders` ro'yxati, sinov kodlashsiz). Natija sessiyada keshlanadi; model o'rnatish/o'chirishdan keyin yoki `refresh=true` bilan yangilanadi.
* `diagnostics`: `lahza-diagnostika-<vaqt>.zip` = `diagnostics.json` (engine/Python/paket versiyalari, apparat profili va darajasi, imkoniyatlar, o'rnatilgan modellar ID/vazifa/versiya, barcha epizodlardagi `failed/cancelled` bosqichlar — xato matni 200 belgigacha va uzun satrlar yashirilgan) + `engine.log.txt` (oxirgi 500 satr). Transkript (`sentences`/`words`), klip matnlari va media yo'llari **kirmaydi** (NFR-02). `out_dir` ota-papkasi mavjud bo'lmasa — 400.
* `system:reveal`: macOS `open -R <yo'l>`, Windows `explorer /select,<yo'l>`, Linux `xdg-open <papka>`; shell'siz, argumentlar massivi (NFR-08). Yo'l mavjud bo'lmasa — 404.

## Loglar

`lahza serve` `Logs/engine.log` faylini yoqadi (aylanma: 2 MB × 5 fayl). Formatter (`core/logs.SafeFormatter`) 64 belgidan uzun satr argumentlarini, ro'yxat/lug'at argumentlarini va `Word/Sentence/Transcript/Clip` obyektlarini `<matn: N belgi>` ko'rinishida yashiradi, istisno xabarini 300 belgigacha qisqartiradi. Qoida: transkript matni log xabariga f-string bilan qo'shilmaydi.

## Modellar

| Metod | Yo'l | Tana | Javob |
| --- | --- | --- | --- |
| GET | `/v1/catalog/bundle` | — | `{"tier", "items": [{"task", "entry", "compat", "reason", "mandatory"}]}` |
| GET | `/v1/models` | — | `{"models": [...], "defaults": {"asr": "<id>"}}` |
| POST | `/v1/models:install` | `{"consent": true, "entry_ids": null}` | Job (`kind: install`) |
| POST | `/v1/models:bootstrap` | `{"consent": true}` | Job (`kind: install`, `meta.op: bootstrap`) — lokal alfa Whisper base, katalog tasdig'isiz |
| POST | `/v1/models:scan` | — | `{"added": [...]}` — `Models/llm/*.gguf` |
| DELETE | `/v1/models/{id}` | — | `{"ok": true}` |
| POST | `/v1/models/{id}:default` | — | `{"ok": true}` |
| POST | `/v1/models/{id}:test` | — | `{"ok": bool, "detail"}` |
| POST | `/v1/models:export-pack` | `{"path": "....lzpack", "model_ids?": string[]}` | Job (`kind: pack`, `meta.op = "export"`) |
| POST | `/v1/models:import-pack` | `{"path"}` | Job (`kind: pack`, `meta.op = "import"`) |
| GET | `/v1/asr-quality` | — | `{"mode": "fast\|accurate\|custom\|none", "current_model_id", "fast": {"model_id","installed"}, "accurate": {"model_id","installed","download_bytes","download_available"}}` |
| POST | `/v1/asr-quality` | `{"mode": "fast\|accurate", "consent"?, "pack_path"?}` | holat + `"job"`: o'rnatilgan bo'lsa darhol standart ASR almashadi (`job: null`); "Aniq" (NavAI small) o'rnatilmagan bo'lsa — Job (`kind: install`, `meta.op: asr-quality`, bosqichlar `download`/`import-pack`/`verify`). Tez modeli yo'q — 409 `model_missing`. Tarmoqdan yuklash faqat `LAHZA_ASR_ACCURATE_PACK_URL` (https) sozlanganda; aks holda `pack_path` (.lzpack). |

* `consent` bo'lmasa — 400 (NFR-01). `entry_ids` berilmasa, avtomatik to'plam o'rnatiladi; ASR birinchi.
* `models:bootstrap` katalogni o'zgartirmaydi: mahkamlangan upstream modelini `source=custom`, `verified=false` sifatida o'rnatadi va ASR standarti qiladi. Faqat foydalanuvchi roziligidan keyin model fayllari yuklanadi; video yuborilmaydi. `entry_ids` bilan chaqirilsa 400. Tafsilotlar: [`local-models.md`](local-models.md).
* `DELETE`: fayllar (faqat `Models/` ichida) va registry yozuvi o'chiriladi; model standart bo'lsa — shu vazifadagi boshqa modelga o'tadi, boshqasi bo'lmasa standart o'chiriladi. Noma'lum ID — 404.
* `:test`: fayllar mavjudligi → katalogda bo'lsa har fayl sha256 → backend yuklanishi (faqat shu model bilan `build_services`). Natija `installed.json` dagi `self_test_ok` ga yoziladi.
* `.lzpack` (zip): `manifest.json` (`format`, `registry` — yo'llar `Models/` ga nisbiy, `files: [{"path","sha256","size"}]`), `Models/...` fayllari, ixtiyoriy `signature` (manifest baytlarining Ed25519 imzosi, base64; eksportda kalit `LAHZA_PACK_PRIVKEY`). Import: har fayl sha256/hajmi doim tekshiriladi; `LAHZA_PACK_PUBKEY` sozlangan bo'lsa imzo majburiy (`LAHZA_DEV=1` da imzosiz ham qabul); zip-slip (`..`, absolyut yo'l, `\\`, `Models/` dan tashqari), symlink, bajariladigan fayllar (sarlavha: MZ/ELF/Mach-O/`#!`; kengaytma: `.exe .dll .so .dylib .sh .py ...`), manifestda yo'q yoki yetishmayotgan fayl — rad. Fayllar avval vaqtinchalik papkada tekshiriladi, keyin joyiga ko'chiriladi. Job natijasi: eksport `{"path","models","files"}`, import `{"imported","files"}`.

## Loyihalar va import

| Metod | Yo'l | Tana | Javob |
| --- | --- | --- | --- |
| GET | `/v1/projects` | — | `[{"id", "name", "created_at"}]` |
| POST | `/v1/projects` | `{"name": "Biznes podkast"}` | `{"id", "name"}` |
| GET | `/v1/projects/{id}/episodes` | — | `[{"id", "show_id", "title", "status", "project_dir", "highlight_mode", "created_at"}]` |
| POST | `/v1/media:import` | `{"project_id", "path", "title?", "focus?", "num_speakers?", "force_lite?"}` | `{"episode_id", "job"}` |
| GET | `/v1/episodes/{id}` | — | `{"id","show_id","title","status","project_dir","media": {"duration_ms","fps","width","height","path"} \| null, "highlight_mode": "llm"\|"lite"\|null}` |
| POST | `/v1/episodes/{id}:reanalyze` | `{"force_lite?": bool, "focus?": string, "num_speakers?": int}` | Job (`kind: analyze`) |

* Import va qayta tahlil shou lug'atini (shu shou + umumiy, `show_id = null`) tahlilga uzatadi: `hotwords` — atamalar (ASR), `lexicon_map` — `variant.lower() → atama` (normalize bosqichi). Shuningdek `aligner` (`Services.aligner`) uzatiladi.
* Tahlil tugaganda `episodes.status` = `ready`/`failed`, `episodes.highlight_mode` = `llm`/`lite`.
* `:reanalyze`: asl fayl `media.path` dan olinadi (yo'q bo'lsa 400; media yozuvi yo'q — 409; shu epizod allaqachon tahlilda — 409). Kesh tufayli o'zgarmagan bosqichlar qayta hisoblanmaydi.

## YouTube havolasidan import (YT-1, ADR-0010)

Funksiya **standart holatda yoqilgan** (egasi qarori; Sozlamalarda o'chiriladi, o'chirilgani `library.db` da saqlanadi) — har importda rozilik so'raladi ([ADR-0010](adr/0010-youtube-havola-import.md)). Asl fayl importi (`/v1/media:import`) o'zgarmagan.

| Metod | Yo'l | Tana | Javob |
| --- | --- | --- | --- |
| GET | `/v1/settings/youtube-import` | — | `YoutubeImportStatus` |
| PUT | `/v1/settings/youtube-import` | `{"enabled": bool}` | `YoutubeImportStatus` |
| POST | `/v1/settings/youtube-import:check-updates` | — | `{"installed", "latest", "update_available", "download_bytes"}` (tarmoq; xato — 502) |
| POST | `/v1/settings/youtube-import:install-components` | `{"consent": true, "update?": bool}` | `{"job"}` (`kind: install`, `meta.op: youtube-components`) |
| POST | `/v1/media:import-url` | `{"project_id", "url", "consent": true, "title?", "focus?", "num_speakers?", "force_lite?"}` | `{"job"}` (`kind: download`) |

`YoutubeImportStatus`: `{"enabled", "installed", "version", "ejs", "js_runtime", "ffmpeg", "components_ready", "components_download_bytes", "install_job", "component_versions"}` — `enabled` `library.db` → `settings` (`key = "youtube_import"`, `{"enabled": bool}`; sxema o'zgarmagan); `installed`/`version` — yt-dlp topildimi; `ejs` — yt-dlp-ejs; `js_runtime` — `deno | node | bun | null`; `ffmpeg` — birlashtirish uchun FFmpeg.

* Komponentlar (`:install-components`, `media/youtube_components.py`): yt-dlp va yt-dlp-ejs — PyPI'dagi sof Python g'ildiraklari (Unlicense; rasmiy exe emas), Deno — GitHub relizi (MIT). Versiya, hajm va sha256 kodda mahkamlangan; mos kelmasa hech narsa joylanmaydi. `<data_dir>/Components/yt-dlp` va `Components/deno` ga `.staging-*` orqali atomik joylanadi, versiya belgisi `lahza-component.json`. `consent` `true` emas — 400; o'rnatish allaqachon ketmoqda — 409. Progress: `job.stage` — yuklanayotgan komponent, `job.meta.download = {"component", "downloaded_bytes", "total_bytes"}`. Uzilsa arxivlar `Components/.downloads` da qoladi va davom ettiriladi. **Yangilanish ilova relizisiz:** `:check-updates` va `update: true` oxirgi versiyani asl manbalardan oladi — PyPI JSON API (`yt-dlp`; `yt-dlp-ejs` versiyasi yt-dlp `requires_dist` talabidan) va GitHub releases API (`denoland/deno`, faqat 2.x, `digest` sha256). Faqat `files.pythonhosted.org` dagi `py3-none-any` g'ildiragi va `github.com/denoland/deno/releases/download/` qabul qilinadi; versiya mahkamlangandan pasaymaydi. Tarmoq faqat foydalanuvchi tugmani bosganda. yt-dlp sidecar'ga kirmaydi (`build_sidecar.py` `--exclude-module`), unga kerakli stdlib modullari esa kiritiladi.
* `:import-url` xatolari (shu tartibda tekshiriladi): funksiya o'chiq — **403**; `consent` `true` emas yoki yo'q — **400**; havola qabul qilinmadi — 400 (faqat `youtube.com|www.|m.` → `/watch?v=ID`, `/shorts/ID`, `/live/ID` va `youtu.be/ID`; ID — 11 belgi `[A-Za-z0-9_-]`; boshqa domen, playlist, kanal, login/port bor havola rad etiladi); loyiha topilmasa — 404; `num_speakers` 1..20 dan tashqari — 400; yt-dlp o'rnatilmagan — **409** ("komponent o'rnatilmagan"); shu video allaqachon yuklanmoqda — 409.
* Yuklash `download` vazifasida (I/O oqimi), **yt-dlp esa alohida jarayonda** (`multiprocessing` spawn, `media/youtube.py`): bolaga faqat kanonik havola (`https://www.youtube.com/watch?v=ID`, playlist parametrlarisiz), chiqish papkasi va sozlamalar beriladi; engine jarayoni `yt_dlp` ni import qilmaydi. Tarmoq faqat shu jarayonda va amal davomida (NFR-01). `remote_components = []` — yt-dlp-ejs internetdan olinmaydi.
* yt-dlp qidiruvi: `LAHZA_YTDLP_PATH` (papka(lar), `os.pathsep` bilan), `<data_dir>/Components/yt-dlp` (katalog komponenti uchun joy), engine muhiti (dasturchi: `make setup-youtube` = `pip install -e "engine[youtube]"`). JS runtime: `<data_dir>/Components/{deno,node,bun}/`, `LAHZA_BIN_DIR`, sidecar `bin/`, PATH.
* Format: mp4, balandligi ≤ 1080 (`bv*[height<=1080][ext=mp4]+ba[ext=m4a]/b[height<=1080][ext=mp4]/…`), birlashtirish loyihadagi FFmpeg bilan (`find_tool("ffmpeg")`); FFmpeg yo'q bo'lsa faqat bitta fayldagi format.
* Fayl: `<data_dir>/Imports/youtube/<video_id>/<video_id>.mp4`. Uzilsa `.part` saqlanadi va qayta urinishda davom ettiriladi (`continuedl`). Muvaffaqiyatli yuklangan video qayta import qilinsa, tarmoqsiz qayta ishlatiladi (`lahza-download.json`).
* Progress: `job.stage = "download"`, `job.progress` 0..1 (video+audio — 0.85/0.15 ulush), `job.meta.download = {"downloaded_bytes", "total_bytes", "speed", "eta"}`, `job.meta.title` — video sarlavhasi.
* Bekor qilish: `POST /v1/jobs/{id}:cancel` — bola jarayon o'ldiriladi, video papkasi (qisman fayllar) o'chiriladi. Engine to'xtayotganda qisman fayllar qoldiriladi.
* Xato: `job.status = failed`, `job.error` — o'zbekcha tushuntirish, `job.meta.error_code`: `not_installed | network | private | age_restricted | login_required | unavailable | live | js_runtime | format_unavailable | ffmpeg | crashed | invalid_url | unknown`.
* Tayyor bo'lgach oddiy import oqimi: `create_episode` (sarlavha — `title` yoki video sarlavhasi, `/ \ : * ? " < > |` → `_`) + `analyze` vazifasi (`meta.source_url`). `job.result = {"episode_id", "analysis_job_id", "path", "title", "reused"}`, `job.meta.episode_id` ham to'ldiriladi.
* Partiyaviy navbatga (`/v1/queue`) URL elementi hali qo'shilmagan (ochiq masala).

## Litsenziya (V1-3, ADR-0016)

Funksiya **standart holatda o'chiq** (`Settings.licensing_enabled`, sinov uchun `LAHZA_LICENSING=1`); o'chiq bo'lsa hech narsa bloklanmaydi. Tarmoq ishlatilmaydi. Format va chiqarish: [litsenziya-kaliti.md](litsenziya-kaliti.md).

| Metod | Yo'l | Tana | Javob |
| --- | --- | --- | --- |
| GET | `/v1/license` | — | `LicenseStatus` |
| PUT | `/v1/license` | `{"key": "LAHZA-…"}` | `LicenseStatus` |
| DELETE | `/v1/license` | — | `LicenseStatus` |

`LicenseStatus`: `{"enabled", "state", "device_id", "license", "reason", "app_version", "activated_at?"}`; `state`: `disabled | not_configured | unlicensed | valid | expired | not_yet_valid | wrong_version | wrong_device | clock_rollback | invalid`; `license`: `{"id", "licensee", "edition", "issued", "expires", "perpetual", "max_devices", "device_locked", "min_version", "max_version"}`. Saqlash: `library.db` → `settings` (`license`, `license_clock`; sxema o'zgarmagan).

* PUT/DELETE bayroq o'chiq bo'lsa — **409**; yaroqsiz kalit — **400**, `detail` = `"<kod>: <xabar>"`, kod: `malformed | unsupported | bad_signature | not_configured | expired | not_yet_valid | wrong_version | wrong_device | clock_rollback`. Yaroqsiz kalit saqlanmaydi.

## Partiyaviy tahlil navbati (PRO-5)

| Metod | Yo'l | Tana | Javob |
| --- | --- | --- | --- |
| GET | `/v1/queue?project_id=` | — | `[QueueItem]` — `position` tartibida, tugaganlari ham |
| POST | `/v1/queue` | `{"project_id", "paths": string[], "focus?", "num_speakers?", "force_lite?"}` | `[QueueItem]` — qo'shilganlari |
| DELETE | `/v1/queue/{id}` | — | `{"ok": true}` |
| POST | `/v1/queue/{id}:cancel` | — | QueueItem |
| POST | `/v1/queue/{id}:retry` | — | QueueItem |
| POST | `/v1/queue:reorder` | `{"ids": string[]}` | `[QueueItem]` |
| POST | `/v1/queue:clear` | `{"project_id?"}` | `{"removed": int}` |

`QueueItem`: `{"id", "project_id", "episode_id", "path", "title", "options": {"focus", "num_speakers", "force_lite"}, "position", "status", "progress", "stage", "error", "job_id", "created_at", "started_at", "finished_at"}`. `status`: `queued | running | done | failed | cancelled`.

* Navbat `library.db` → `analysis_queue` da saqlanadi (docs/05). Bir vaqtda faqat **bitta** element ishlaydi: navbat keyingi elementni oldingisi tugagach "heavy" oqimga yuboradi, shuning uchun tartib va olib tashlash ishga tushgunga qadar kuchda. Har element `/v1/media:import` bilan bir xil oqimdan o'tadi: ishga tushganda epizod yaratiladi (`episode_id` to'ldiriladi) va `analyze` vazifasi (`meta.queue_item_id`) yuboriladi. Progress — shu vazifaning `job` hodisalari; `progress`/`stage` faqat `running` element uchun.
* Bitta elementning xatosi (fayl yo'qolgan, ASR xatosi va h.k.) navbatni to'xtatmaydi: element `failed` + `error`, keyingisi boshlanadi.
* `POST /v1/queue`: loyiha topilmasa — 404; `paths` bo'sh — 400; birorta fayl topilmasa — 400 (`detail` da yo'llar, hech biri qo'shilmaydi); `num_speakers` 1..20 dan tashqari — 400; ko'pi bilan 500 fayl.
* `:cancel`: kutayotgan element darhol `cancelled`; ishlayotganining vazifasi bekor qilinadi (holat vazifa to'xtaganda yoziladi). Tugagan element — 409.
* `DELETE`: ishlayotgan element — 409 ("avval bekor qiling"). Noma'lum ID — 404 (`navbat elementi topilmadi`).
* `:retry`: faqat `failed`/`cancelled` (aks holda 409); element navbat oxiriga qo'yiladi, epizodi bo'lsa o'sha epizod qayta tahlil qilinadi.
* `:reorder`: `ids` — kutayotgan (`queued`) elementlar, yangi tartibda birinchi; qolgan kutayotganlar eski tartibda keyin. Kutmayotgan/noma'lum yoki takroriy ID — 400.
* `:clear`: `done/failed/cancelled` elementlarni ro'yxatdan o'chiradi (epizodlar qoladi).
* Tiklanish: engine ishga tushganda `running` elementlar `queued` ga qaytariladi va navbat avtomatik davom etadi (o'sha epizod, bosqich keshi bilan). Engine to'xtayotganda bekor qilingan vazifa elementni `cancelled` qilmaydi.

## Vazifalar

| Metod | Yo'l | Javob |
| --- | --- | --- |
| GET | `/v1/jobs/{id}` | `{"id", "kind", "status", "progress", "stage", "error", "result", "meta", "created_at"}` |
| POST | `/v1/jobs/{id}:cancel` | Job |
| POST | `/v1/jobs/{id}:retry` | Job (yangi; `meta.retry_of` = eski ID) |
| GET | `/v1/exports` | `[{"job": Job, "episode_id", "clip_id", "montage_id", "title"}]` |

* `kind`: `analyze | export | install | pack | montage | download`. `status`: `queued | running | done | failed | cancelled`. `stage`: `ingest | vad | asr | normalize | align | diarize | sentences | signals | highlight`, montajda `analyze | plan`, montaj renderida `render`, o'rnatilayotgan model ID'si yoki `export-pack`/`import-pack`. `created_at` — Unix vaqt (s).
* Oqimlar: tahlil va montaj rejalashtirish (`montage`) — bitta umumiy "heavy" oqim; eksport (klip va montaj render) — `LAHZA_EXPORT_WORKERS` (standart 2, 1..8); `install`/`pack`/`download` (YouTube) — alohida 1 ta I/O oqimi.
* `:retry` faqat `failed`/`cancelled` eksport uchun (aks holda 409), xuddi shu parametrlar bilan (klip va montaj eksporti).
* `/v1/exports` — joriy engine sessiyasidagi eksport vazifalari (klip va montaj), yangisi oldin. Klip eksportida `episode_id`/`clip_id`, montajda `montage_id` to'ldirilgan (qolganlari `null`). Doimiy tarix: klip — `project.db` → `exports`, montaj — `library.db` → `montage_exports`.

## Transkript

| Metod | Yo'l | Tana | Javob |
| --- | --- | --- | --- |
| GET | `/v1/episodes/{id}/transcript` | — | `{"sentences": [Sentence]}`; `Sentence = {"id", "start_ms", "end_ms", "speaker", "words": [Word], "text"}` |
| PATCH | `/v1/episodes/{id}/words` | `{"sentence_id", "ord", "text"}` | `{"ok": true, "sentence": Sentence}` |
| GET | `/v1/episodes/{id}/waveform?buckets=2000` | — | `{"duration_ms", "peaks": number[]}` |
| GET | `/v1/episodes/{id}/speakers` | — | `[{"label", "display_name": string\|null}]` |
| PATCH | `/v1/episodes/{id}/speakers/{label}` | `{"display_name"}` | `{"ok": true}` |

* `PATCH words`: matn NFC/imloga normallashtiriladi. Bo'sh matn — so'z o'chiriladi va `ord` 0..n-1 qayta raqamlanadi; bo'shliqli matn — bir nechta so'zga bo'linadi (eski so'z vaqt oralig'i harf soniga proporsional taqsimlanadi). So'ng faqat shu gap qayta tekislanadi: `Services.aligner` bo'lsa `align.realign.realign_sentence` (wav: `<loyiha>/cache/audio16k.wav`), bo'lmasa so'z vaqtlari saqlanadi. `sentences.text` yangilanadi; matn o'zgargan bo'lsa `corrections` ga `before/after` yoziladi (`audio_chunk_path = "cache/audio16k.wav#<start_ms>-<end_ms>"`). Shu tuzatishdan so'z darajasidagi "xato → to'g'ri" juftliklari shaxsiy lug'atga yig'iladi (PRO-1, pastda). Gap/so'z topilmasa — 404.
* `waveform`: `buckets` 10..20000; har bo'lakdagi |maks| amplituda, butun fayl maksimumiga normallangan (0..1). `cache/waveform-<buckets>-<mtime>.json` da keshlanadi. Audio hali yo'q — 404.
* `speakers`: yorliqlar gaplardagi `speaker_id` dan; ism `project.db → speakers` da saqlanadi. Bo'sh ism — `null`. Noma'lum yorliq — 404.

## Kliplar

| Metod | Yo'l | Tana | Javob |
| --- | --- | --- | --- |
| GET | `/v1/episodes/{id}/clips` | — | `[Clip]` |
| POST | `/v1/episodes/{id}/clips` | `{"start_sentence_id", "end_sentence_id", "title?"}` | `Clip` |
| PATCH | `/v1/episodes/{id}/clips/{cid}` | `{"start_ms?", "end_ms?", "title?", "caption?", "hashtags?", "status?"}` | `{"ok": true}` |
| PUT | `/v1/episodes/{id}/clips/{cid}/cuts` | `{"cuts": [[start_ms, end_ms], ...]}` | `Clip` |
| GET | `/v1/episodes/{id}/clips/{cid}/keyframes` | — | `[{"t_ms","layout","cx","cy","zoom","lane","source"}]` |
| PUT | `/v1/episodes/{id}/clips/{cid}/keyframes` | `{"keyframes": [...]}` | `{"ok": true}` |
| POST | `/v1/episodes/{id}/clips/{cid}:preview` | `{"t_ms", "style": StyleTemplate, "orthography?"}` | `image/jpeg` |
| POST | `/v1/episodes/{id}/clips/{cid}:similar` | — | `[Clip]` (≤3) |
| POST | `/v1/episodes/{id}/clips/{cid}:export` | `{"out_dir", "style", "orthography?", "filename_template?", "allow_no_subs?": false, "platform?": "instagram_reels"}` | Job (`kind: export`) |
| GET | `/v1/episodes/{id}/proxy` | — | `video/mp4` (540p proksi) |

* `status` qiymatlari: `nomzod | qabul | rad | eksport_qilingan` (boshqasi — 422). `qabul`/`rad` `feedback` jadvaliga yoziladi. `PATCH`: noma'lum klip — 404; `end_ms <= start_ms` yoki `start_ms < 0` — 400.
* `POST clips` (qo'lda): gap oralig'i `highlight.boundaries.snap` bilan vaqtga aylantiriladi (pre/post-roll, qo'shni gapga kirmaydi; boshlanish pauzaga surilmaydi, minimal davomiylik majburiy emas, maksimum `hard_max_ms`). `source = "qolda"`, `status = "nomzod"`, `user_edited = 1`. `title` berilmasa — birinchi gap matni (80 belgi). Teskari tartib — 400, noma'lum gap — 404.
* `PUT cuts`: har kesim `start < end` va klip ichida bo'lishi shart (aks holda 400); so'z o'rtasiga tushgan chegara butun so'zni olib tashlaydigan qilib kengaytiriladi; kesimlar saralanadi va ustma-ust/tutash bo'lganlari birlashtiriladi. Kesimlardan keyin < 1 s qolsa — 400. Natija `user_edited = 1`, `feedback`ga `tahrir`.
* `keyframes`: `t_ms` — chiqish (kesimlardan keyingi) vaqti, 0..klip davomiyligi; `layout`: `focus|split|fit_blur|manual`; `cx, cy` 0..1; `zoom` 0.5..4; `lane`: `a|b`. PUT klipning barcha kalit kadrlarini almashtiradi va `source = "qolda"` saqlaydi; bir yo'lakda bir xil `t_ms` — 400.
* `:preview`: `core.export.render_preview_frame` (1080×1920 kadr; libass yo'q bo'lsa subtitrsiz). `t_ms` klip davomiyligiga qisiladi. Funksiya mavjud bo'lmasa — 501.
* `:similar`: Lite nomzodlar (signallar `signals` bosqichi keshidan, bo'lmasa qayta hisoblanadi) orasidan rad etilmagan mavjud kliplar bilan ham, bir-biri bilan ham ustma-ust tushmaydigan, signal bali va davomiyligi berilgan klipga eng yaqin ≤3 ta tanlanadi va `ai_lite` nomzod sifatida saqlanadi. `kind` aniqlanmaydi (`null`).
* `:export`: libass yo'q va `allow_no_subs = false` bo'lsa — **422** (`detail` — aniq o'zbekcha xabar), vazifa yaratilmaydi. `project.db → exports` ga yozuv (`queued → running → done/failed/cancelled`, `job_id`, `path`, `error`, `finished_at`). `export_clip` ga shou nomi, epizod sarlavhasi, klip tartib raqami (vaqt bo'yicha, 1 dan), `filename_template` (standart `{shou}_{epizod}_{nn}_{sarlavha}`), `allow_no_subs`, `platform` uzatiladi.
* Eksport natijasi (`job.result`): `{"video", "srt", "vtt", "caption", "cover", "encoder", "warnings": string[], "export_id"}`.

## Lug'at, uslublar, shriftlar

| Metod | Yo'l | Tana | Javob |
| --- | --- | --- | --- |
| GET | `/v1/lexicon?project_id=` | — | `[{"id","show_id","term","variants": string[],"kind": "ism"\|"brend"\|"atama"}]` |
| POST | `/v1/lexicon` | `{"show_id?","term","variants","kind"}` | yozuv |
| DELETE | `/v1/lexicon/{id}` | — | `{"ok": true}` |
| GET | `/v1/styles` | — | `[{"id","name","template": StyleTemplate}]` |
| POST | `/v1/styles` | `{"name","template"}` | yozuv |
| PUT | `/v1/styles/{id}` | `{"name","template"}` | yozuv |
| DELETE | `/v1/styles/{id}` | — | `{"ok": true}` |
| POST | `/v1/styles:import` | `{"path"}` (.json) | yozuv |
| POST | `/v1/styles/{id}:export` | `{"path"}` | `{"ok": true}` |
| GET | `/v1/fonts` | — | `[{"family","path","ok","missing": string[]}]` |

* `lexicon?project_id=X` — shu shou va umumiy (`show_id = null`) yozuvlar; parametrsiz — hammasi. `term`/`variants` normallashtiriladi, takror va `term` ga teng variantlar olib tashlanadi.
* Uslublar `library.db → style_templates` da; `template.name` yozuv nomiga tenglanadi. Import fayli: `{"name","template"}` yoki yalang'och `StyleTemplate` JSON (≤ 1 MB); yaroqsiz — 400. Eksport `{"name","template"}` yozadi (`.json` kengaytmasi qo'shiladi).
* `fonts`: `subtitle.fonts.list_fonts()` (shrift o'zbek glifflarini qamraydimi).

## Pro: shaxsiy lug'at va ball vaznlari (PRO-1, PRO-6)

To'liq oflayn. Kod: `text/personal_dict.py`, `highlight/learning.py`, `api/routes_learning.py`.

| Metod | Yo'l | Tana | Javob |
| --- | --- | --- | --- |
| GET | `/v1/dictionary` | — | `{"entries": [DictEntry], "min_count": 2, "conf_threshold": 0.85}`; `DictEntry = {"id","wrong","right","kind": "ism"\|"atama"\|"soz","count","active","last_episode_id","updated_at"}` |
| DELETE | `/v1/dictionary/{id}` | — | `{"ok": true}` (yo'q — 404) |
| GET | `/v1/dictionary:export` | — | `{"format": "lahza.dictionary/1", "entries": [DictEntry]}` |
| POST | `/v1/dictionary:export` | `{"out_path"}` | `{"path","entries"}` |
| GET | `/v1/dictionary/finetune-manifest?project_id=` | — | `application/x-ndjson` (pastda) |
| POST | `/v1/dictionary/finetune-manifest:export` | `{"out_path","project_id?"}` | `{"path","segments"}` |
| GET | `/v1/episodes/{id}/clip-metrics` | — | `{clip_id: {"clip_id","views","likes","recorded_at"}}` |
| PUT | `/v1/episodes/{id}/clips/{cid}/metrics` | `{"views": int>=0, "likes?": int>=0\|null}` | `{"metrics", "weights": WeightsInfo}` (loyiha darajasi) |
| DELETE | `/v1/episodes/{id}/clips/{cid}/metrics` | — | `{"ok": true}` (yo'q — 404) |
| GET | `/v1/highlight/weights?project_id=` | — | `WeightsInfo = {"scope","weights": {"weight_llm","weight_signals"},"defaults","source": "project"\|"global"\|"default","learned","n_samples","min_samples"}` |
| POST | `/v1/highlight/weights:reset` | `{"project_id?"}` | `WeightsInfo` |

* **Lug'at yig'ish**: `PATCH words` dagi har tuzatishda gapning oldingi/keyingi matni so'z yadrolari (tinish belgilarisiz) bo'yicha solishtiriladi (`difflib`); faqat almashtirishlar (1..3 so'z → 1..3 so'z) juftlik bo'ladi, qo'shilgan/o'chirilgan so'z — yo'q. Faqat tinish belgisi o'zgarishi juftlik emas; bosh harf tuzatilishi (`toshkent → Toshkent`) — juftlik. `wrong` kichik harfda; `kind`: bosh harf — `ism`, ko'p so'zli/uzun — `atama`, aks holda `soz`.
* **Faol lug'at**: `count >= 2` va shu `wrong` uchun ulush >= 80% (ziddiyatli tuzatishlar qo'llanmaydi); zanjirlar (A→B, B→C) qo'llanmaydi.
* **Qo'llash (tahlil)**: `submit_analysis` (import, qayta tahlil, navbat) (a) faol `ism`/`atama` yozuvlarning `right` qiymatlarini lexicon hotwords'idan keyin qo'shadi (≤ 40; Whisper `hotwords`/`initial_prompt`), (b) ASR bosqichining oxirida (`asr.base.dedupe_overlaps` → `personal_dict.apply_active`) post-tuzatish qiladi: faqat butun so'z mos kelganda (so'z ichidagi qism almashtirilmaydi; ko'p so'zli juftlik ichida tinish belgisi bo'lsa — yo'q), ASR `conf` ma'lum va `>= 0.85` bo'lsa tegilmaydi, `edited` so'zlar tegilmaydi; birinchi so'zning old va oxirgi so'zning ort tinish belgilari saqlanadi, gap boshidagi bosh harf saqlanadi; so'z soni o'zgarsa oraliq teng bo'linadi. ASR keshi `hotwords` parametri bo'yicha yangilanadi (yangi `right` qiymati qo'shilsa ASR qayta ishlaydi).
* **Fine-tune manifesti**: har `(epizod, gap)` uchun (`corrections.sentence_id`) bitta JSON qator — `{"audio": "<loyiha>/cache/audio16k.wav" (mutlaq yo'l), "audio_exists", "start_ms", "end_ms", "duration_ms", "text" (joriy, yakuniy matn), "asr_text" (birinchi tuzatishdagi `before_text`), "language": "uz", "episode_id", "project_id", "sentence_id"}`. Audio ko'chirilmaydi. Matni ASR matniga qaytarilgan gaplar o'tkaziladi. `out_path` papka bo'lsa — `lahza-finetune.jsonl` / `lahza-dictionary.json`; kengaytma majburan qo'yiladi; ota papka yo'q — 400.
* **Vaznlarni o'rganish**: namuna — klip `scores_json` dagi `llm` va `signal` (kiritish paytida saqlanadi) + `y = log1p(views) + 0.5·log1p(likes)`. Ikkala komponent bo'lgan namunalar ishlatiladi (Lite kliplari — yo'q). Rang (Spearman uslubi) bo'yicha ridge regressiya → musbat xom koeffitsiyent ulushlari → Bayes qisqartirish `a = n/(n+20)` standart vaznlarga → har vazn `[0.1, 0.9]` × yig'indi, yig'indi standartdagidek (1.0). `n < 8`, xususiyat o'zgarmas yoki musbat bog'liqlik yo'q — o'rganilmaydi (`weights_json = NULL`). Har `PUT/DELETE metrics` loyiha va `global` vaznlarini barcha namunalardan qayta hisoblaydi (yig'ilib boruvchi siljish yo'q).
* **Qo'llash**: tahlilda vaznlar `project` → `global` → standart tartibida tanlanadi va `HighlightConfig.weight_llm/weight_signals` ga qo'yiladi (global `Settings` o'zgarmaydi); `highlight` bosqichi keshi parametrlar bo'yicha yangilanadi.
* **Tiklash**: `weights:reset` shu darajaning vaznini `NULL` qiladi va `since_id = MAX(clip_metrics.id)` — eski namunalar keyingi o'rganishga kirmaydi. Loyiha tiklansa va global o'rganilgan bo'lsa — `source = "global"`. Noma'lum loyiha — 404.

## Montaj: plaginlar, video shablonlar, avtomontaj

Manba: `api/routes_montage.py` (docs/11 5-6, 10-bo'limlar; ADR-0011/0012/0013). Modellar: `montage/model.py` (`MontageTimeline`, `lahza.timeline/1`), `templates/model.py` (`Template`, `lahza.template/1`), `fx/registry.py` (`FxManifest`, `lahza.fx/1`). Og'ir modullar (`fx.registry`, `templates.store`, `montage.analyze`, `montage.planner`, `render.montage_render`) endpoint ichida yuklanadi; modul yo'q bo'lsa — **501**.

| Metod | Yo'l | Tana | Javob |
| --- | --- | --- | --- |
| GET | `/v1/fx?kind=` | — | `FxManifest[]` |
| GET | `/v1/templates` | — | `Template[]` (avval o'rnatilganlar, keyin foydalanuvchiniki; `builtin` maydoni) |
| GET | `/v1/templates/{id}` | — | `Template` |
| POST | `/v1/templates` | `Template` (`id` ixtiyoriy) | `Template` |
| PUT | `/v1/templates/{id}` | `Template` | `Template` |
| DELETE | `/v1/templates/{id}` | — | `{"ok": true}` |
| POST | `/v1/templates/{id}:duplicate` | `{"name?"}` | `Template` (foydalanuvchi nusxasi) |
| POST | `/v1/templates:import` | `{"path"}` (.json) | `Template` |
| POST | `/v1/templates/{id}:export` | `{"path"}` | `{"ok": true}` |
| GET | `/v1/montages?project_id=` | — | `[{"id","name","template_id","status","duration_ms","created_at","updated_at","project_id"}]` |
| POST | `/v1/montages` | `{"name?","project_id?","template_id","sources": [Source],"overrides?": Overrides}` | `{"montage_id","job"}` (Job `kind: montage`) |
| GET | `/v1/montages/{id}` | — | `{"id","name","template_id","project_id","status","duration_ms","created_at","updated_at","sources","overrides","timeline": MontageTimeline\|null,"error","user_edited","job_id","exports": [MontageExport]}` |
| PUT | `/v1/montages/{id}/timeline` | `MontageTimeline` | `{"ok": true, "timeline"}` |
| POST | `/v1/montages/{id}:replan` | `{"template_id?","overrides?","force?": false}` | Job (`kind: montage`) |
| POST | `/v1/montages/{id}:preview` | `{"t_ms", "timeline?": MontageTimeline}` | `image/jpeg` |
| POST | `/v1/montages/{id}/media` | `{"path", "role": "music"}` | `{"media": MediaRef}` |
| POST | `/v1/montages/{id}:render` | `{"out_dir","filename?","allow_no_subs?": false}` | Job (`kind: export`, `meta: {montage_id, title, export_id}`) |
| GET | `/v1/montages/{id}/sources/{media_id}/thumb?t_ms=` | — | `image/jpeg` (320 px kenglik) |
| DELETE | `/v1/montages/{id}` | — | `{"ok": true}` |

`Source`: `{"kind":"file","path"}` \| `{"kind":"clip","episode_id","clip_id"}` \| `{"kind":"episode","episode_id"}`. `Overrides` (hammasi ixtiyoriy): `target_duration_ms` (5000..600000), `aspect` (`9:16|1:1|16:9`), `music_path`, `title`, `cta`, `shou`, `captions`, `caption_style` (StyleTemplate), `logo_path`, `transition`, `color` (plagin id). `MontageExport`: `{"id","job_id","path","status","error","created_at","finished_at"}`, `status`: `queued | running | done | failed | cancelled`.

**Shablonlar**

* O'rnatilgan shablonlar (`templates/builtin/*.json`, `uz.lahza.tpl.*`) o'zgartirilmaydi: PUT/DELETE — **409**. Foydalanuvchi shablonlari `library.db → user_templates` da.
* POST: `id` bo'lmasa, bo'sh, o'rnatilgan shablon id'si yoki band bo'lsa — yangi `user.<uuid12>` beriladi; boshqa holatda berilgan id saqlanadi (`templates.store` id qoidasi: kichik lotin harflari, raqam, `.`, `-`, `_`). `builtin` doim `false`. PUT'da tanadagi `id` e'tiborsiz (yo'ldagi id ishlatiladi); noma'lum id — 404.
* Validatsiya: pydantic + `templates.store.validate_template` (o'rinbosarlar `{sarlavha}`, `{shou}`, `{cta}`, intro/outro davomiyligi, o'tish uzunligi, plagin id'lari fx reestrida va turi mosligi). Xato — **400**, `detail` o'zbekcha (`shablon yaroqsiz: ...`).
* `:duplicate`: istalgan (o'rnatilgan ham) shablondan `user.<uuid12>` nusxa; `name` berilmasa `"<nom> (nusxa)"`.
* `:import`: faqat `.json`, hajmi ≤ 1 MB; `templates.store.load_template_file` (`schema` = `lahza.template/1` majburiy). Yaroqsiz — 400. id qoidasi POST bilan bir xil. `:export`: `.json` kengaytmasi qo'shiladi, ota-papka mavjud bo'lmasa — 400; fayl `builtin=false` bilan yoziladi.

**Montaj yaratish va reja**

* Manbalar: 1..50 ta (aks holda 400). `file` — fayl mavjud bo'lishi kerak (400). `episode`/`clip` — epizod (404), `media` yozuvi (yo'q bo'lsa 409 — tahlil qilinmagan), asl fayl (400), klip (404). Shablon — 404, `project_id` — 404, `music_path`/`logo_path` mavjud bo'lishi (400), `transition`/`color` reestrda bo'lishi (400). Har manbaga tartib bo'yicha `media_id` = `src1`, `src2`, ... va yechilgan asl fayl `path` beriladi (javobdagi `sources` da ko'rinadi; timeline'dagi `MediaRef.id` shu).
* `montages` qatori `status = planning` bilan yoziladi va `montage` vazifasi ("heavy" navbat) yuboriladi: har manba uchun `montage.analyze.analyze_file` (kesh: `Library/_montage/<id>/cache/`), progress `analyze` 0..0.9; so'ng `montage.planner.plan_montage` (`plan`, 0.9..1) → `timeline_json`, `duration_ms`, `status = ready`, `user_edited = 0`. Xato (`PlanError` va boshqalar) — `status = failed`, `error` (o'zbekcha). Bekor qilish — `error = "rejalashtirish bekor qilindi"`.
* Epizod manbalari **asl fayldan** tahlil qilinadi (proksi yoki `audio16k.wav` dan emas), so'ng `analyze.enrich_with_transcript` bilan epizod `project.db` gaplari, rad etilmagan kliplari (highlight) va `signals` bosqichi keshi (bo'lmasa qayta hisoblanadi) qo'shiladi. `MediaRef.origin`: `file` \| `clip:<episode_id>/<clip_id>` \| `episode:<episode_id>`.
* Klip manbasi: tahlil klip oralig'i bilan cheklanadi — kesimlar (`clip_cuts`) chiqarib tashlanadi; shotlar va nutq oraliqlari saqlangan bo'laklarga kesiladi, gaplar (so'zlari kesim ichida bo'lganlari olib tashlanadi), emphasis va spiker almashuvlari filtrlanadi; `highlights` — klipning saqlangan bo'laklari (har biri `clip_id` bilan, ball 0..1).
* Engine qayta ishga tushganda `planning` da qolib ketgan montaj o'qilganda avtomatik tiklanadi: timeline bo'lsa `ready`, bo'lmasa `failed` (`error` — qayta rejalashtirish taklifi).
* `:replan`: `planning` holatida — 409. Montaj qo'lda tahrirlangan bo'lsa (`user_edited` yoki biror `VideoItem.user_edited`) va `force` bo'lmasa — **409** (qayta reja tahrirlarni almashtiradi). `template_id`/`overrides` berilsa saqlanadi, aks holda avvalgilari. Tahlil keshi qayta ishlatiladi. Qayta reja xatosida avvalgi timeline saqlanadi (`status = ready`, `error` to'ldiriladi).

**Timeline tahriri, preview, render**

* `PUT timeline`: `planning` da — 409. `MontageTimeline` validatsiyasi (element media'si mavjud, `src_out > src_in`, manba davomiyligi, takroriy id, birinchi elementda o'tish yo'q) — xato 400 (`timeline yaroqsiz: ...`). Har `media[].path` montajning mavjud media/manba yo'llaridan biri yoki mavjud fayl bo'lishi kerak; `brand.logo_path` mavjud bo'lishi; plagin id'lari (fx, o'tish, rang) reestrda bo'lishi — aks holda 400. Saqlanganda `user_edited = 1`, `status = ready`, `error = null`.
* `:preview`: `render.montage_render.render_montage_frame` (bitta kadr; libass yo'q bo'lsa matnsiz). `t_ms` montaj davomiyligiga qisiladi. Ish fayli `Library/_montage/<id>/work/preview/` da yaratilib, javobdan keyin o'chiriladi. Timeline yo'q — 409.
  Ixtiyoriy `timeline` (saqlanmagan draft) berilsa kadr shu bo'yicha chiziladi, saqlangan timeline o'zgarmaydi. Draft `PUT .../timeline` kabi validatsiya qilinadi (yaroqsiz — 400, noma'lum plagin — 400), lekin uning `media` yo'llari **faqat** montajning mavjud media'laridan (saqlangan timeline `media` + manbalar) bo'lishi mumkin — yangi fayl yo'li 400; saqlangan timeline'dagi media id'sining yo'lini almashtirish ham 400 (musiqa avval `POST .../media` bilan qo'shiladi). Draftda video elementlar yo'q — 409. UI draft o'zgarganda (debounce ~400 ms) shu maydonni yuboradi.
* `POST /media` (muharrirdan musiqa): fayl `montage.analyze.probe_media` bilan tekshiriladi — topilmasa, o'qilmasa yoki **audio oqimi bo'lmasa** 400. Natija `MediaRef` (id `music`, band bo'lsa `music2`, `music3`...; `width/height/fps = 0`, `hash`) saqlangan timeline `media` lug'atiga qo'shiladi va montaj `user_edited` bo'ladi; xuddi shu fayl qayta qo'shilsa mavjud id qaytadi. `MusicItem` ni UI draft'ga yozadi va odatdagi `PUT .../timeline` bilan saqlaydi. `planning` yoki timeline yo'q — 409; `role` faqat `"music"` (boshqasi 422).
* `:render`: timeline yo'q, `planning` yoki video elementsiz — 409. libass yo'q, `allow_no_subs = false` va timeline'da matn qatlami (`text`) yoki so'zli subtitr (`captions.enabled` + `words`) bor — **422** (aniq o'zbekcha xabar), vazifa yaratilmaydi. `out_dir` (yoki uning ota-papkasi) mavjud bo'lmasa — 400. Fayl nomi: `filename` yoki montaj nomi; `/ \ : * ? " < > |` → `_`, `.mp4` qo'shiladi, mavjud fayl ustiga yozilmaydi (`_2`, `_3`, ...). Enkoder klip eksportidagi kabi tanlanadi (`choose_encoder`, GPU). `render_montage` ish papkasi `Library/_montage/<id>/work/<job_id>/` (tugagach o'chiriladi). Natija (`job.result`): `{"video","edl","srt","warnings","encoder","export_id","montage_id"}`. `montage_exports` ga yozuv (`queued → running → done/failed/cancelled`).
* `thumb`: `media_id` timeline `media` yoki `sources` dan; fayl yo'q — 404. `ffmpeg -ss t -i <fayl> -frames:v 1 -vf scale=320:-2` (yo'l faqat `-i` kirishi sifatida), `Library/_montage/<id>/thumbs/<media_id>-<t_ms>.jpg` da keshlanadi; `t_ms` media davomiyligiga qisiladi.
* `DELETE`: rejalashtirish vazifasi ishlayotgan bo'lsa bekor qilinadi; `montages` (va kaskad bilan `montage_exports`) qatori va `Library/_montage/<id>/` papkasi o'chiriladi. Render qilingan videolar o'chirilmaydi.

## Claude

Manba: `api/routes_claude.py`, `claude_bridge/` ([15-claude-montaj.md](15-claude-montaj.md)). Funksiya **standart holatda o'chiq**; o'chiq bo'lsa `status`, `settings` va `cancel` dan boshqa endpointlar (Claude rejali `editing-agent:plan` ham) **409** `claude_disabled` qaytaradi.

| Metod | Yo'l | Tana | Javob |
| --- | --- | --- | --- |
| GET | `/v1/claude/status?refresh=` | — | `ClaudeStatus` |
| PUT | `/v1/claude/settings` | `{"enabled": bool}` | `ClaudeStatus` |
| POST | `/v1/claude/check-auth` | — | `ClaudeStatus` |
| POST | `/v1/claude/connect` | `{"target": "claude_code"\|"claude_desktop", "dry_run?"}` | `{"actions": [str], "status": ClaudeStatus}` |
| POST | `/v1/claude/disconnect` | xuddi shunday | xuddi shunday |
| POST | `/v1/claude/cancel` | — | `{"cancelled": bool}` |

`ClaudeStatus`: `{"enabled", "cli": {"installed","path","version"}, "desktop": {"installed","path"}, "auth": {"state","detail","checked_at"}, "mcp": {"claude_code","claude_desktop"}, "mcp_command": [str]}`. Montaj rejasi: `POST /v1/editing-agent:plan` tanasida `"planner": "claude"` (standart `"local"`); javobda ham `planner`. Xato `detail` = `"<kod>: <xabar>"`, kod: `claude_disabled | claude_not_installed | claude_not_logged_in | claude_timeout | claude_bad_plan | claude_busy | claude_cancelled | claude_config_invalid | claude_error`.

## Adobe plaginlari

Premiere Pro (UXP) va After Effects (CEP) plaginlari engine'ni topadi, klip yoki montaj uchun **host-reja** (`lahza.hostplan/1`, `hostplan/model.py`) oladi va uni o'z dasturi API'si orqali sekvensiya/kompozitsiyaga qo'yadi. Render'ni Adobe qiladi.

### Engine'ni topish (discovery)

`lahza serve --discovery` (yoki `LAHZA_DISCOVERY=1`) ishga tushganda `<data_dir>/engine.json` yoziladi (`core/discovery.py`):

```json
{"port": 51234, "token": "…", "pid": 4321, "version": "0.1.0", "started_at": "2026-10-22T09:15:00Z"}
```

* `data_dir`: macOS `~/Library/Application Support/Lahza Studio`, Windows `%LOCALAPPDATA%\Lahza Studio` (`LAHZA_DATA_DIR` ustun).
* Port: `--port` berilsa — o'sha. Aks holda `--discovery` rejimida **qat'iy** 47600 → 47601 → 47602 (UXP manifest `network.domains` portlarni oldindan sanaydi); uchalasi band bo'lsa o'zbekcha xato (stderr) va chiqish kodi 2. Tauri sidecar rejimi (`--port 0`, discovery'siz) — avvalgidek tasodifiy bo'sh port. Token: `--token`/`LAHZA_TOKEN` berilmasa tasodifiy (`secrets.token_urlsafe(24)`).
* Fayl huquqi `0600` (Windows'da foydalanuvchi profilining odatiy ACL'i); yozish atomar (shu papkadagi vaqtinchalik fayl + `os.replace`).
* To'xtaganda o'chiriladi: `uvicorn.run` dan keyin (`finally`), FastAPI lifespan ilgagi (`app.state.shutdown_hooks`), `atexit`, POSIX'da `SIGHUP`. SIGINT/SIGTERM'ni uvicorn ushlaydi va graceful to'xtaydi. Fayl faqat undagi `pid` o'zimizniki bo'lsa o'chiriladi.
* Eski fayl (o'lik `pid`) ustiga yoziladi. Tirik boshqa engine fayli ham ustiga yoziladi (oxirgisi ustun, logda ogohlantirish). `SIGKILL` dan keyin fayl qolishi mumkin — plagin `pid` va `GET /v1/health` bilan tekshiradi.
* Tauri sidecar rejimi (`--discovery` siz) o'zgarmagan: fayl yozilmaydi.

### Fayl-IPC (`lahza.ipc/1`) — zaxira transport

UXP'da HTTP ishlamasa (permission yoki macOS `http://` cheklovi) plagin (`adobe/premiere/src/transport.ts`) fayl orqali so'raydi. Engine tomoni — `core/ipc.py` (`IpcServer`); `--discovery` rejimida yoki `LAHZA_IPC=1` da yoqiladi (token bo'lishi shart).

* Papkalar: `<data_dir>/ipc/requests/` va `<data_dir>/ipc/responses/`, huquqi `0700`.
* So'rov: plagin `requests/<id>.json.tmp` yozadi va `requests/<id>.json` ga rename qiladi:
  `{"v":1,"id","method","path":"/v1/...","headers":{"Authorization":"Bearer <token>"},"body":JSON|null,"created_at"}`.
* Engine server event loop'idagi polling sikli (150 ms, lifespan fon vazifasi) faylni o'qiydi, **o'chiradi** va mavjud FastAPI ilovasini ichki ASGI chaqiruvi bilan bajaradi (`httpx.ASGITransport`, tarmoqsiz). Token tekshiruvi, validatsiya va xato matnlari oddiy HTTP bilan aynan bir xil (noto'g'ri token — `401`). Headerlardan faqat `Authorization` o'tadi; `body` JSON bo'lib yuboriladi.
* Javob: `responses/<id>.json.tmp` → rename `responses/<id>.json`: `{"v":1,"id","status","body"}`. Plagin o'qib o'chiradi.
* `id` faqat `[A-Za-z0-9-]{8,64}`; boshqa nomdagi fayl javobsiz o'chiriladi. `.tmp` e'tiborsiz. So'rov > 1 MB — `413`; JSON emas, `v != 1`, `id` fayl nomiga mos emas, yo'l `/v1/` bilan boshlanmaydi — `400`; metod `GET/POST/PUT/PATCH/DELETE` dan boshqa — `405`. Ilova ichidagi kutilmagan xato — `500`. Javobi JSON bo'lmagan endpointlar (`:preview` JPEG, proksi video) — `502` (`detail`: faqat HTTP orqali).
* 5 daqiqadan eski so'rov/javob (va `.tmp`) fayllari tozalanadi (har 10 s). Bir vaqtda ≤ 8 so'rov bajariladi.

### CORS

| Mijoz | Origin | Manba |
| --- | --- | --- |
| CEP paneli (After Effects) | `null` (HTML `file://` dan yuklanadi, Chromium/CEF), zaxira `file://` | CEP 12 HTML Extension Cookbook — "CORS checks": CEP 11+ CORS tekshiruvi qat'iy, endpoint `Access-Control-Allow-Origin` qaytarishi kerak |
| Premiere UXP | rasmiy hujjatda aniq qiymat yo'q (kutilgan: sarlavha yo'q yoki `null`) — **ANIQLANSIN** haqiqiy host'da | developer.adobe.com/premiere-pro/uxp/resources/recipes/network — "Request blocked by CORS" → serverda `Access-Control-Allow-Origin` |

`null` origin har qanday sandbox iframe'da ham bo'ladi, shuning uchun himoya — token (har so'rovda majburiy), `allow_credentials=false` va faqat `127.0.0.1`. O'chirish: `LAHZA_ADOBE_CORS=0`.

Eslatma (plagin uchun): Premiere UXP hujjati macOS'da `http://` URL cheklanishini aytadi; `http://127.0.0.1` ga ruxsat bor-yo'qligi haqiqiy host'da tekshirilsin (engine HTTPS bermaydi).

### Endpointlar

| Metod | Yo'l | Tana | Javob |
| --- | --- | --- | --- |
| GET | `/v1/hostplan/schema` | — | `{"schema": "lahza.hostplan/1", "engine": "0.1.0"}` |
| POST | `/v1/episodes/{eid}/clips/{cid}:hostplan` | `{"out_dir", "style"?: StyleTemplate, "orthography"?: "official"\|"ascii"\|"new", "aspect"?: "9:16"\|"1:1"\|"16:9"}` | `HostPlan` |
| POST | `/v1/montages/{id}:hostplan` | `{"out_dir"}` | `HostPlan` |

* `out_dir` absolyut yo'l bo'lishi kerak; mavjud bo'lmasa yaratiladi, lekin ota papkasi mavjud bo'lishi shart (aks holda 400). Fayl (papka emas) — 400.
* Klip: `out_dir/<slug>.srt` (mavjud `build_srt`, imlo/to'ldiruvchi/so'kinish qoidalari bilan) va `out_dir/<slug>_words.json` (`{"schema": "lahza.words/1", "orthography", "words": [{text,t0,t1}], "lines": [...], "style"}`) yoziladi; `slug` — klip sarlavhasidan. Epizod tahlil qilinmagan yoki asl fayl yo'q — 409; klip yo'q — 404.
* Montaj: `planning` yoki timeline/video elementsiz — 409; yo'q — 404. Subtitr faqat `captions.enabled` va so'zlar bo'lsa (`<montaj-nomi-slug>.srt`, `_words.json`).
* Hisob — `hostplan/build.py` (`plan_from_clip`, `plan_from_montage`), sinxron (yuz detektori bo'lsa va saqlangan reja bo'lmasa, klip uchun reframe rejasi shu so'rovda hisoblanadi).

### Host-reja koordinata qoidalari

* Vaqt — soniya. `rec_*` — sekvensiya vaqti; `src_*` — manba fayl vaqti; `TransformKey.t` — **element boshidan** (rec).
* Qatlam anchor'i = manba kadr markazi. `scale_pct` — manba masshtabi (100 = asl), `pos_x/pos_y` — manba markazi tushadigan sekvensiya pikseli.
* Crop oynasi `(x, y, w, h)` (manba px, `reframe.planner.crop_rect`) → `scale = W / w`, `pos_x = W/2 + (sw/2 − (x + w/2))·scale`, `pos_y = H/2 + (sh/2 − (y + h/2))·scale`. Render (`render/graph.py`: crop → `scale=W:H`) bilan gorizontal aniq bir xil; vertikal farq faqat crop enini juft songa yaxlitlashdan (≤ 0,3%). Isbot: `tests/test_hostplan_math.py`.
* Kalit kadrlar: `CropKey.cut=True` → oldingi kalit `interp: "hold"`. Kamera kadr chetiga tegadigan (clamp) nuqtalarda qo'shimcha kalit qo'yiladi — host chiziqli interpolyatsiyasi render yo'lidan ≤ 2,5 manba px farq qiladi. Bo'lak ichida masshtab doimiy (birinchi kalit `zoom`'i, render kabi).
* Layoutlar: `focus`/`manual` → bitta `main`; `fit_blur` → `bg` (to'ldirish: `max(W/sw, H/sh)`, `gaussian_blur` amount 60 ≈ ffmpeg `gblur=sigma=30`) + `main` (sig'dirish: `min(...)`), ikkalasi markazda; `split` → `top` `crop_rect=(0,0,W,H/2)` va `bottom` `(0,H/2,W,H/2)`, har biri o'z kamerasi bilan yarim kadr markaziga.
* Klip: render bo'laklari (timeline segmenti × layout segmenti) → `VideoClipItem`lar ketma-ket (`transition_in: cut`). Layout manbai: qo'lda kalit kadrlar > saqlangan avto reja > (detektor bo'lsa) yangi reja; detektorsiz — xira fon (bazaga yozilmaydi).
* SRT'ga `style.uppercase` engine'ning o'zida qo'llanadi (Premiere captions uslubini API orqali qo'yib bo'lmaydi); `captions.lines` va `_words.json` asl registrda.
* Subtitr qatorlari — `subtitle/layout` (`style.max_words/max_lines`, xavfsiz zona eni), so'zlar rec vaqtida, imlo + so'kinish maskasi qo'llangan, to'ldiruvchilar olib tashlangan; `uppercase` va ranglarni plagin `captions.style` dan qo'llaydi. Qator ≤ 400 ms keyingisigacha ushlab turiladi (ASS kabi).
* Markerlar: hook gapi (`kind: "hook"`), signallar keshi bo'lsa — signal bali ≥ 70 gaplar (`emphasis`). Montajda `role = "hook"` elementi boshida.
* Montaj xaritasi: o'tishlar `dissolve/fade → cross_dissolve`, `fadeblack → dip_to_black`, `fadewhite → dip_to_white`, `wipe* → wipe`, `slide* → push`, `zoomin → zoom`, `cut → cut`, boshqasi → `cross_dissolve` + `not_translated`. O'tishli element `rec_in` oldingi element oxiri bilan `dur_s` ga ustma-ust (`MontageTimeline.item_starts`). Harakat (`punch-in`, `push-in`, `pan`, `zoom-out`) → `TransformKey`lar (montaj render `_camera`/`zoompan` formulasi bo'yicha hisoblanib, easing nuqtalari bilan); `shake`, `freeze`, audio fade, matn animatsiyasi, logotip, loudnorm → `not_translated`. Rang preset → `lumetri_preset`, LUT → `lut` (butun montaj rangi har elementga). `volume_db` = element + `audio.source_gain_db`.

## Hodisalar (WebSocket)

`ws://127.0.0.1:<port>/v1/events?t=<token>` — noto'g'ri token bilan ulanish qabul qilinadi va darhol `4401` kod bilan yopiladi (qabulsiz yopish mijozga faqat HTTP 403 bo'lib ko'rinardi).

```json
{"type": "job", "ts": 1791957683.1, "job": {"id": "a1b2c3", "kind": "analyze", "status": "running", "progress": 0.42, "stage": "asr", "meta": {"episode_id": "e1"}}}
```

Partiyaviy navbat o'zgarganda (qo'shish, holat, tartib, o'chirish) — `{"type": "queue", "ts": ..., "item": QueueItem | null}` (`null` — bir nechta element o'zgardi yoki element o'chirildi; mijoz `/v1/queue` ni qayta so'raydi).

## Turlar

### Platforma profillari (lokal alfa)

* `GET /v1/export-profiles` → `{profiles: ExportProfile[]}`. Har profilning `id`,
  `recommended_format`, `safe_zone`, `restrictions`, `recommendations`, `sources`
  va `verified_at` maydonlari bor. `custom` joriy foydalanuvchi safe zone'ini qaytaradi.
* `POST /v1/export-profiles:check` → `{errors: string[], warnings: string[]}`.
  Body: `{timeline: MontageTimeline}`; bu endpoint timeline'ni o'zgartirmaydi.
* Timeline'da `target_platform`: `instagram_reels | youtube_shorts | youtube_video | custom`.
  Eski fayl uchun standart `custom`. Shu maydon yangi montajning `overrides`ida ham beriladi.
* Noma'lum profil — 422. Shorts cheklovini buzgan montaj render so'rovi — vazifa
  navbatiga qo'yilmasdan 400. Tavsiyalar renderni bloklamaydi.

Rasmiy manbalar va cheklovlar: [platformalar](local-platforms.md).

TypeScript turlari: `app/src/api/types.ts`. Python modellari: `engine/src/lahza_engine/types.py`, `subtitle/style.py`, `models/catalog.py`, `montage/model.py`, `templates/model.py`, `fx/registry.py`. Ikkalasi bir xil bo'lishi CI'da qo'lda tekshiriladi (M2'da OpenAPI'dan avtomatik generatsiya rejalashtirilgan).
