# Test va sifat

Sifat o'z oltin to'plamlarimizda o'lchanadi; birinchi o'lchov (baseline) R0'da olinadi, keyingi har reliz undan yomonlashmasligi shart (TZ 15-bo'lim).

## Test darajalari

| Daraja | Qayerda | Nima |
| --- | --- | --- |
| Unit | `engine/tests/test_*.py` | Imlo, gaplar, chegaralar, qoidalar, signallar, LLM sxema, ASS, timeline, reframe, katalog, yuklab olish, CTC, metrikalar |
| Integratsiya | `engine/tests/test_render_e2e.py` | Haqiqiy FFmpeg: uch layout + kesim + subtitr; soxta ASR bilan butun pipeline + eksport; kesh. Markerlar: `ffmpeg`, `libass` |
| API | `engine/tests/test_api.py` | Token, loyihalar, katalog, rozilik, WebSocket auth |
| UI | `app/` | `npm run typecheck`, `npm run build`; E2E (Tauri WebDriver) — M2 |
| Rust | `app/src-tauri/` | `cargo check` / `cargo clippy` |
| Platforma matritsasi | CI (`.github/workflows/ci.yml`) | macOS arm64, Windows x64, Linux (dev) |
| Tarmoqsiz (NFR-01) | CI `offline` jobi | Ubuntu: `unshare -rn` + `LAHZA_NO_NETWORK=1` — butun test to'plami va `lahza hw` |
| Toza o'rnatish | qo'lda / CI VM | Internetsiz VM'da o'rnatuvchi + `.lzpack` |
| Chidamlilik (V1-1) | `engine/tests/stress/` (`make test-stress`) | 4 soatlik sintetik video to'liq pipeline + eksport; navbatda ketma-ket 20 epizod. Soxta ASR/LLM; RSS, fd, oqim, temp va DB izchilligi tekshiriladi; JSON hisobot `build/stress-report.json` |
| Tezlik (M3-PERF-1) | `scripts/bench.py` (`make bench`) | Bosqichlar bo'yicha vaqt, TZ 2-bo'lim maqsadi bilan solishtirish, apparat darajasi |
| Inson bahosi | oyiga bir marta | SMM paneli eski va yangi versiya kliplarini ko'r-ko'rona solishtiradi |

## Oltin to'plamlar

| To'plam | Tarkibi | O'lchov | Skript |
| --- | --- | --- | --- |
| UzPodcast-Eval | 3–5 soat audio + qo'lda transkript | WER, CER, ismlar, "o'ylab topish", RTF | `eval/run_asr_eval.py` |
| Align-Eval | 30 daqiqa, so'z chegaralari | median, p95 (ms) | `eval/run_align_eval.py` |
| UzHighlight-Eval | 10 epizod × 3 mutaxassis | precision@5, topish ulushi (IoU ≥ 0.5) | `eval/run_highlight_eval.py` |
| Reframe-Eval | 10 video, aktiv spiker belgilangan | aktiv spiker kadrda bo'lgan ulush, keraksiz harakatlar | M3 |
| Render-Eval | uslub × layout kombinatsiyalari | kadr snapshotlari (SSIM), ASS snapshotlari | M3 |

Ma'lumotlar `eval/data/` da (repozitoriyga audio kiritilmaydi — faqat izohlar va yo'llar; `.gitignore`). Natijalar `eval/results/<model_id>.json`.

## Mutlaq talablar (har relizda 100%)

* Hech bir klip so'z o'rtasida boshlanmaydi yoki tugamaydi — `test_snap_never_cuts_words_and_respects_bounds`.
* LLM javoblari 100% JSON sxemadan o'tadi — grammatika bilan cheklangan dekodlash + `parse_response`.
* Oflayn rejimda 0 ta tarmoq so'rovi — CI `offline` jobi: tarmoqsiz namespace'da butun test to'plami, jumladan soxta ASR bilan to'liq pipeline + eksport (`test_full_pipeline_lite_then_export`). Lokal: `make test-offline`.
* Eksport 1080×1920, ovoz va video sinxron — `test_render_all_layouts_with_cuts_and_subtitles`.
* Transliteratsiya jadval testlari 100% — `test_orthography.py`.

## Nisbiy talablar

WER, highlight precision@5 va aktiv spiker ulushi oldingi relizdan yomonlashsa — reliz to'xtatiladi. Chegara qiymatlari baseline'dan keyin belgilanadi (ANIQLANSIN).

## Test muhiti va markerlar

| Marker / o'zgaruvchi | Ma'nosi |
| --- | --- |
| `ffmpeg` | `ffmpeg` va `ffprobe` PATH'da bo'lmasa skip |
| `libass` | `ffmpeg -filters` da `ass` filtri bo'lmasa skip (sabab: "ffmpeg libass'siz yig'ilgan…"); o'rnatish — `docs/03-dasturchi-muhiti.md` |
| `LAHZA_REQUIRE_LIBASS=1` | libass yo'q bo'lsa skip qilmaslik — test ishlaydi va yiqiladi (CI'da yoqilgan) |
| `stress` | Chidamlilik testlari: oddiy `pytest` da tanlanmaydi (deselect); `-m stress` yoki `LAHZA_STRESS=1` bilan ishlaydi. Parametrlar: `LAHZA_STRESS_HOURS` (4), `LAHZA_STRESS_EPISODES` (20), `LAHZA_STRESS_EP_MIN` (3), `LAHZA_STRESS_RSS_MB`, `LAHZA_STRESS_LEAK_MB` (150), `LAHZA_STRESS_REPORT` |
| `LAHZA_NO_NETWORK=1` | `socket.connect` / `getaddrinfo` loopback'dan tashqariga urinsa `NetworkBlockedError` (NFR-01) |

## Buyruqlar

```bash
cd engine && pytest                       # hammasi (FFmpeg bo'lsa render ham)
pytest -rs                                # skip sabablari bilan
pytest -m "not ffmpeg"                    # FFmpeg'siz
pytest -m "not libass"                    # subtitr yoqib yozuvchi testlarsiz
LAHZA_NO_NETWORK=1 pytest                 # NFR-01
ruff check src tests
cd app && npm run typecheck && npm run build
cd app/src-tauri && cargo check
make ci                                   # yuqoridagilarning lokal yig'indisi (cargo'siz)
make test-stress                          # V1-1: 4 soat + 20 epizod (~4 daq, M5)
make test-stress STRESS_ENV="LAHZA_STRESS_HOURS=0.5 LAHZA_STRESS_EPISODES=5"
make bench BENCH_ARGS="--minutes 10"       # M3-PERF-1 (sintetik nutq); --video /abs/podcast.mp4 - haqiqiy
```

## Chidamlilik natijalari (V1-1)

2026-10-26, Apple M5 (10 yadro), 16 GB, macOS 27.0.1, Homebrew ffmpeg (libass'siz - eksport subtitrsiz, SRT/VTT bilan). ASR va LLM soxta; qolgan hamma bosqich haqiqiy. `make test-stress` (to'liq parametrlar) - 2 test o'tdi, 217 s.

| Sinov | Natija |
| --- | --- |
| 4 soatlik video (320x180, 5 fps, 403 MB) | Tahlil 136.5 s (ingest/proksi 92.5, ASR bo'laklash 39.7 (1440 ta ffmpeg kesimi), signallar 2.0, VAD 1.3); 1 klip eksport 3.0 s; 4608 gap, 34 559 so'z, 10 klip; DB `integrity_check` ok, 9 bosqich `done` |
| Xotira (4 soat) | RSS cho'qqisi **210 MB** (bazaviy 78 MB; chegara 3900 MB); tahlildan keyin 156 MB (+78 MB ushlanib qolgan); ffmpeg bolalari <= 124 MB. V1-1 optimallashtirishgacha: cho'qqi 2242 MB, +337 MB ushlanib qolgan - `read_wav_mono` 16 kHz WAV'ni to'liq float32 massivga o'qir edi (4 soat = ~920 MB + int16 nusxa). Endi VAD, ASR bo'laklash, signallar va montaj tahlili `open_wav_mono`/`WavPcm` (oraliq o'qish, ~1M namunali bloklar; natija bit-darajada bir xil, `tests/test_wav_stream.py`) orqali ishlaydi; ushlanib qolgan xotira ham shu katta massiv bo'shatilgandan keyingi allokator qoldig'i edi (kesh/global massiv topilmadi) |
| Temp va fd (4 soat) | `tempfile` papkasida qoldiq fayl yo'q; fd 14 -> 14; kesh 1409 MB (WAV 460 MB + proksi) |
| Navbat: 20 epizod x 3 daq | 54.3 s (2.7 s/epizod); 20/20 `done`, bir vaqtda faqat bitta `running`; kutubxona DB ok, osilib qolgan element yo'q |
| Oqish (20 epizod) | RSS 5-epizoddan keyin 220 MB -> oxirida 178 MB (o'sish -42 MB, chegara +150 MB); fd 17 -> 17; oqimlar 1 -> 2 (heavy pool); temp qoldig'i yo'q |

## Tezlik o'lchovi (M3-PERF-1)

2026-10-26, Apple M5 (10 yadro: CPU+GPU), 16 GB, macOS 27.0.1 - avtomatik daraja **Standard** (maqsad: 60 daq video tahlili <= 20 daq, TZ 2-bo'lim). `scripts/bench.py --minutes 10`: sintetik 10 daq video (1920x1080 30 fps H.264, macOS `say` tr_TR ovozi o'zbekcha matn o'qiydi - faqat tezlik uchun, WER emas); o'rnatilgan modellar; bundled ffmpeg (libass bor) va llama-server. O'lchov paytida mashinada boshqa testlar ham ishlagan - natija +-10-20% shovqinli.

| Bosqich | Vaqt (10 daq video), s | RTF | 60 daq ga ekstrapolyatsiya, daq | Usul / model |
| --- | ---: | ---: | ---: | --- |
| Dekod (16 kHz WAV) | 0.3 | 0.000 | 0.0 | ffmpeg |
| Proksi (540p) | 17.3 | 0.029 | 1.7 | ffmpeg mpeg4 |
| VAD | 2.3 | 0.004 | 0.2 | Silero v5.1.2 ONNX |
| ASR | 140.3 | 0.234 | 14.0 | navai-whisper-base-uzbek (faster-whisper, CPU int8) |
| Align | - | - | - | **o'lchanmadi**: CTC aligner o'rnatilmagan (ASR vaqtlari) |
| Diarize | - | - | - | **o'lchanmadi**: diarizatsiya modeli o'rnatilmagan |
| Highlight (LLM) | 498.4 | 0.831 | ~49.8 | Qwen3-4B Q4_K_M, llama-server (Metal); 10 daq = 2 oyna |
| **Tahlil jami** | **658.6** | **1.098** | **~65.9** | maqsad <= 20 daq - **bajarilmadi** |
| Tahlil, LLM'siz (lite) | 160.2 | 0.267 | ~16.0 | maqsadga sig'adi |
| Render, 1 klip 49.5 s | 9.9 | - | - | h264_videotoolbox + libass, 5.0x real vaqt (yuz detektorisiz) |

### LLM highlight tezlashtirish (M3-PERF-2) - avval / keyin

Profil (bitta 8 daq oyna, llama-server `timings`, Metal `-ngl 999`): prompt 1780 token, prefill 1.6 s (~1100 tok/s) - muammo emas. Chiqish **6992 token** (~29 ms/token, 34 tok/s) - shundan ~5000 token Qwen3 `<think>` matni (`reasoning_content`, 12 300 belgi), qolgani `sabab`/`izoh_matni` maydonlarida takrorlanuvchi halqa (pydantic `max_length` 400/2200 - grammatika uni to'xtatmadi). Oyna 204 s. Grammatika (json_schema) tezlikka sezilarli ta'sir qilmadi (34-37 tok/s).

| Tuzatish (o'lchov, 1 oyna) | Chiqish, token | Vaqt, s |
| --- | ---: | ---: |
| Avval (thinking yoqiq, keng sxema) | 6992 | 204.3 |
| `enable_thinking=false` (+ server `--reasoning-budget 0`) | 1751 | 47.5 |
| + LLM sxemasida chegaralar (sarlavha 80, sabab 200, izoh 300 belgi, <= 5 heshteg, `maxItems` = 4) + promptda qisqalik qoidasi | 1304 | 40.1 |
| + DRY takror jazosi (`dry_multiplier` 0.8), `max_tokens` 1536, `cache_prompt` | 934 | 26.1 |
| + 2 parallel slot (2 oyna birga; 2 x 8192 kontekst = avvalgi 1 x 16384 bilan bir xil KV xotira) | ~900 x 2 | 31.6 / 2 oyna = **15.8 / oyna** |
| (4 slot - 13.7 s/oyna, lekin KV xotira 2x; tanlanmadi) | | |

Sozlamalar `HighlightConfig.llm_*` (`config.py`): `llm_thinking=False`, `llm_max_tokens=1536`, `llm_max_candidates=4`, `llm_dry_multiplier=0.8`, `llm_parallel=2`, `llm_slot_ctx=8192`.

| `bench.py` (Standard, M5 16 GB) | Avval: Highlight, s | Keyin: Highlight, s | Keyin: tahlil jami | 60 daq ga |
| --- | ---: | ---: | ---: | --- |
| `--minutes 10` (2 oyna) | 498.4 | **43.3** (11.5x) | 206.4 s (ASR 130.7, proksi 28.2) | ekstrapolyatsiya 20.6 daq |
| `--minutes 60 --no-render` (9 oyna, haqiqiy o'lchov) | ~2990 (ekstrapolyatsiya) | **256.4** (4.3 daq) | 1471.6 s = **24.5 daq** (ASR 1044.4, proksi 154.1) | o'lchandi |

O'lchov paytida mashinada boshqa agentlarning testlari ishlagan (load average 8-15) - ASR va proksi avvalgi o'lchovdan sekinroq chiqdi (ASR RTF 0.29 vs 0.23). Natija: LLM endi tor joy emas (60 daq videoda 4.3 daq, avval ~50 daq); 60 daq tahlilning qolgan ~20 daqiqasi asosan ASR (17.4 daq) - Standard maqsad (<= 20 daq) uchun keyingi qadam ASR (alohida vazifa). Shovqinsiz mashinada (ASR RTF 0.23 => ~14 daq) jami ~19-20 daq kutiladi.

Sifat: 60 daq o'lchovda xato yo'q, 10/10 klip `ai_llm` (LLM nomzodlari `parse_response` dan o'tdi), davomiyligi 44-59 s (maqsad 30-60), NMS bilan ustma-ust tushmaydi. Profil so'rovlarida har oyna 4/4 nomzod qat'iy tekshiruvdan o'tdi, `finish_reason=stop` (max_tokens'ga yetmadi). Sintetik `say` nutqi ASR'dan keyin ma'nosiz bo'lgani uchun semantik sifatni (precision@5) bu o'lchov baholamaydi - UzHighlight-Eval bilan tekshirilsin. Thinking o'chirilgach `sabab`/`izoh_matni` takrorlanish halqalari yo'qoldi, ballar nomzodlar orasida farqlanadigan bo'ldi (avval hammasi 10).

Xulosa (M3-PERF-1, avval): Standard darajada tor joy - LLM highlight (~250 s / 8 daqiqalik oyna). Ekstrapolyatsiya chiziqli (oynalar soni davomiylikka proporsional); haqiqiy 60 daq o'lchov: `make bench BENCH_ARGS="--minutes 60"` yoki haqiqiy podkast bilan `--video`. Optimallashtirish yo'nalishlari: Qwen3 "thinking" rejimi yoqilganligini tekshirish (taxmin, tasdiqlanmagan), LLM promptini qisqartirish, oynani kattalashtirish, kichikroq LLM (Qwen3.5-2B/4B) va ASR'ni GPU'da (whisper.cpp Metal) ishlatish.
