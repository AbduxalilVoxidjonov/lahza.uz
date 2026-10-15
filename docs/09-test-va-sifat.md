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
| Chidamlilik | qo'lda | 4 soatlik video, ketma-ket 20 epizod |
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
```
