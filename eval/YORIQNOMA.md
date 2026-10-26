# Transkripsiya yo'riqnomasi (etalon matn uchun)

Etalon transkriptlar bir xil qoidada yozilmasa, WER raqamlari solishtirib bo'lmaydigan bo'lib qoladi. Har bir transkript ikki kishi tomonidan tekshiriladi.

## Umumiy

1. Eshitilgan narsani yozing — "to'g'rilangan" yoki adabiy variantini emas. Sheva so'zlari aytilganidek, lotin yozuvida.
2. Yozuv: o'zbek lotin, amaldagi rasmiy imlo. Oʻ/Gʻ uchun ʻ (U+02BB), tutuq uchun ʼ (U+02BC). Klaviaturada `'` yozilsa ham bo'ladi — baholashdan oldin `normalize()` hammasini bir xil qiladi.
3. Har spiker almashganda yangi qator: `[A] matn…`, `[B] matn…`.
4. Gap oxirida tinish belgisi: `.`, `?`, `!`. Vergul ixtiyoriy (WER'da hisobga olinmaydi).

## Raqamlar

5. Raqamlar **so'z bilan**, aytilganidek: "ikki ming yigirma oltinchi yil", "o'n besh foiz". (Ba'zi modellar raqam chiqaradi, ba'zilari so'z — raqam→so'z normallashtirish R0 vazifasi; etalon har doim so'zda.)

## Chet so'zlar va aralash nutq

6. Rus va ingliz so'zlari **o'zbek lotin yozuvida, eshitilganidek**: "voobshe", "startap", "kontent". Brend va ismlar umumiy qabul qilingan yozuvda: "Instagram", "YouTube".
7. Butun gap boshqa tilda bo'lsa — o'sha tilning lotin transliteratsiyasida, boshiga `{ru}` yoki `{en}` belgisi.

## Nutqdan tashqari tovushlar

8. To'ldiruvchilar yoziladi: `ee`, `mm`, `aa`.
9. Kulgi, olqish, musiqa — kvadrat qavsda: `[kulgi]`, `[olqish]`, `[musiqa]`. WER hisobida e'tiborga olinmaydi, lekin kulgi detektorini baholashda ishlatiladi.
10. Tushunib bo'lmaydigan joy: `[tushunarsiz]`. Ustma-ust gapirish: ikkala spikerni ham alohida qatorda, oldiga `[ustma-ust]`.

## So'z chegaralari (Align-Eval)

11. Chegaralar to'lqin shaklida, so'z birinchi tovushining boshi va oxirgi tovushining oxiri bo'yicha qo'yiladi; nafas va pauza so'zga kirmaydi.

## Highlight belgilash (UzHighlight-Eval)

12. Har mutaxassis epizodni mustaqil ko'radi va 5–10 ta "Reels uchun yaxshi" lahzani belgilaydi: boshlanish va tugash (gap chegarasida), qisqa sabab, 1–5 baho.
13. Boshqa mutaxassislarning belgilarini ko'rmaydi.

## ASR benchmark (FLEURS uz) — takrorlanuvchi o'lchov

ASR'ga tegadigan har o'zgarishdan (VAD, `plan_chunks`, dekoder parametrlari, normalizatsiya, model) keyin raqam bilan solishtirish uchun.

**Test to'plami:** Google FLEURS `uz_uz` `test` (CC-BY-4.0, `google/fleurs` revision `70bb2e84…` — `eval/fleurs_uz.py`da qat'iy). NavAI modellari bu split'da o'qitilmagan (model kartasi). Birinchi ishga tushirishda arxivning birinchi 260 wav'i oqimda yuklanadi (`build/asr-eval/download/`, git'ga kirmaydi — `build/` `.gitignore`da) va deterministik tanlanadi: TSV tartibida, raqamsiz gaplar (raqam→so'z hali yo'q), har jumla ID'sidan bittadan.

* `short` — 80 ta alohida gap (~16 daq), har biri o'z VAD → `plan_chunks` yo'lidan o'tadi;
* `long` — 3 ta ~2.5 daq yaxlit audio (12 tadan boshqa gap, 0.4–2.5 s sukunat bilan ulangan) — uzun fayl/bo'laklash muammolari;
* `manifest.json` — tanlangan fayllar va sha256.

**Ishga tushirish** (repozitoriy ildizidan):

```bash
make asr-eval                                     # base + small, --direct bilan, oxirida jadval
make asr-eval ASR_MODELS=small ASR_EVAL_ARGS="--limit 5"   # tez tekshiruv
engine/.venv/bin/python -I eval/run_asr_eval.py --set fleurs-uz --model base [--direct]
engine/.venv/bin/python -I eval/run_asr_eval.py --set fleurs-uz --model build/local-asr-compare/navai-small-ct2
engine/.venv/bin/python -I eval/run_asr_eval.py --table build/asr-eval/results-*.json
```

`--model`: `base` / `small` (o'rnatilgan `custom:navai-whisper-*-uzbek`), istalgan o'rnatilgan model ID yoki CTranslate2 papkasi. Foydalanuvchi model ombori o'zgartirilmaydi — skript vaqtinchalik omborda engine `build_services()` ni chaqiradi (VAD — foydalanuvchining standart Silero modeli).

**Nima o'lchanadi:** har fayl engine'ning o'z bosqichlaridan o'tadi — `core/analyze.py` `stage_vad` → `stage_asr` (`plan_chunks`, ffmpeg bo'laklari, `transcribe_chunk`, `dedupe_overlaps`, `transcript_density`) → `stage_normalize`; kod nusxalanmaydi. Etalon va gipoteza `eval_metrics.normalize_for_wer` (→ `text/orthography.normalize` + `fold_for_match`: kichik harf, tinishsiz, defis → bo'sh joy, oʻ/gʻ/ʼ variantlari bir xil) bilan solishtiriladi.

* WER, CER — korpus bo'yicha vaznli; S/D/I — almashtirish/tushib qolish/qo'shilish (qo'shilish ko'p bo'lsa — gallyutsinatsiya);
* RTF — (VAD + ASR + normalize) sof soat vaqti / audio davomiyligi; model yuklanishi va birinchi (isitish) chaqiruv kirmaydi. Parallel CPU yuki RTF'ni buzadi — solishtirishni bir xil sharoitda qiling;
* so'z/daq — `transcript_density` (nutq daqiqasiga so'z, VAD nutqi bo'yicha) va etalon so'z/daq;
* cho'zilgan so'zlar, eng uzun so'z, siyrak fayllar — `transcript_density`;
* `--direct` — taqqoslash qatori (`short:direct`, `long:direct`): butun fayl VAD/bo'laklashsiz to'g'ridan-to'g'ri backend'ga. Pipeline xatosini model xatosidan ajratadi.

**Natija:** `build/asr-eval/results-<sana>-<model>.json` — umumiy ko'rsatkichlar, har fayl (gipoteza matni, bo'laklar soni, eng uzun so'zlar) va **`code_state`**: git HEAD, `engine/src` dagi commit qilinmagan fayllar, engine kodining sha256'i va asosiy fayllar xeshi, `SileroOnnxVad` standartlari va ishlagan qiymatlari (`pad_ms`, `min_silence_ms`, …), `plan_chunks` standartlari (`pad_ms`, `max_ms`), `ASR_TARGET_CHUNK_MS`, `AsrOptions` (temperature, beam_size), `faster_whisper_backend.py` dagi dekoder qatorlari, kutubxona versiyalari. Ikki natijani solishtirishdan oldin `code_state` farqini ko'ring.

**Ablyatsiya** (engine kodiga tegmasdan, faqat shu jarayonda; `code_state.overrides` ga yoziladi, `--tag` fayl nomiga qo'shiladi):

```bash
P="engine/.venv/bin/python -I eval/run_asr_eval.py --set fleurs-uz --model base"
$P --tag vad-old --vad-pad-ms 30 --vad-min-silence-ms 100   # eski Silero sozlamasi
$P --tag temp-fallback --temperature fallback               # faster-whisper (0.0..1.0) zanjiri
$P --tag no-gain-norm --no-gain-norm                        # asr/preprocess.normalize_wav_file o'chiq
$P --tag all-old --vad-pad-ms 30 --vad-min-silence-ms 100 --temperature fallback --no-gain-norm
```
