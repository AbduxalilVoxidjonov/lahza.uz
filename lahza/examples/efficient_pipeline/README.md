# Lahza Studio: lokal va tejamkor montaj uchun integratsiya qo‘llanmasi

Bu papka mavjud `lahza.timeline/1` bilan ishlaydigan mustaqil namunadir. Asosiy ilova avtomatik almashtirilmagan. Python modullari standart kutubxonadan foydalanadi; FFmpeg/FFprobe alohida kerak. ASR yoki VAD qayta yuklanmaydi, pullik xizmat chaqirilmaydi.

## 1. Matndan montaj: manba matni va chiqish vaqtini ajrating

Saqlash kontrakti:

```ts
type SourceWord = Readonly<{
  id: string;               // ASR revision + word index; matndan yasalmaydi
  mediaId: string;
  text: string;
  startMs: number;          // MANBA, integer ms
  endMs: number;            // [startMs, endMs)
  confidence?: number;
}>;

type DeleteWords = Readonly<{
  type: "delete_words";
  clipId: string;           // aynan shu foydalanish; boshqa takroriy klip saqlanadi
  transcriptRevision: string;
  expectedTimelineRevision: number;
  wordIds: readonly string[];
}>;
```

Asl transcript o‘zgarmaydi. React tanlangan ID’larni yuboradi; server o‘zidagi transcriptdan manba oraliqlarini topadi. Klip ichida ko‘rinadigan so‘zlar oldindan manba chegarasiga moslanadi. `captions.words` esa mavjud sxemadagi **chiqish vaqti** bo‘lib qoladi.

```text
output_ms = clip_output_start_ms + (source_ms - src_in_ms) / speed
```

Masalan, 8 s klipda `[2000, 3000)` o‘chirilsa:

```json
{
  "video": [
    {"id":"clip-1","media":"m1","src_in_ms":0,"src_out_ms":2000,"speed":1},
    {"id":"clip-1~3000-8000","media":"m1","src_in_ms":3000,"src_out_ms":8000,"speed":1}
  ]
}
```

Bu to‘liq timeline emas, o‘zgargan video qismi. Haqiqiy operatsiya subtitr, matn, stiker va musiqa vaqtlarini ham moslashi kerak:

```python
from examples.efficient_pipeline.edit_model import delete_source, merge_spans


def delete_words(timeline: dict, clip_id: str, selected_words: list[dict]) -> dict:
    # selected_words serverdagi asl transcriptdan ID orqali olingan bo‘lsin.
    clip = next(item for item in timeline["video"] if item["id"] == clip_id)
    intervals = [
        (max(clip["src_in_ms"], word["start_ms"]), min(clip["src_out_ms"], word["end_ms"]))
        for word in selected_words
        if word["end_ms"] > clip["src_in_ms"] and word["start_ms"] < clip["src_out_ms"]
    ]
    return delete_source(timeline, clip_id, merge_spans(intervals))
```

`edit_model.py` to‘liq implementatsiya: immutable snapshot, speed bilan bo‘lish, takroriy media ishlatilishlarini ajratish, barcha qo‘llangan vaqtli qatlamlarni ripple qilish, musiqada manba offsetini saqlash. Kesimga qisman tushgan caption so‘zi butunlay chiqariladi. Oldingi snapshot — bitta Undo amali.

Serverda operatsiyani SQLite `BEGIN IMMEDIATE` ichida bajaring: joriy revisionni o‘qing, `expectedTimelineRevision` bilan tengligini tekshiring, yangi JSON va `revision+1` ni birga saqlang; mos kelmasa HTTP 409. Ushbu namuna DB endpointini yaratmaydi. O‘chirishda ASR, VAD, LLM ishga tushmasin; faqat hosila ASS va preview rejasi yangilansin.

### Video qayta kodlanmasdan qachon kesiladi?

`-c copy` filtr ishlatmaydi. Ixtiyoriy Whisper so‘z chegarasi odatda GOP ichida bo‘ladi; bunday chegarada frame-aniq copy kafolatlanmaydi.

`smart_cut.py` konservativ dispatcher:

- Bitta uzluksiz oraliq, H.264 MP4/MOV, B-frame yo‘q, PTS=DTS, mos format/geometriya/FPS, paket chegaralarida **haqiqiy IDR NAL** dalili: video copy, audio yengil AAC encode.
- Bir nechta saqlanadigan oraliq, LUT, ASS, musiqa, noma’lum GOP yoki ixtiyoriy word kesimi: bitta hardware encode.
- `snap_tolerance_ms=0` standart; yashirincha yaqin keyframe’ga siljitmaydi. Tolerans alohida berilsa haqiqiy xato `plan.spans[*].error_ms` da qaytadi.

```python
from pathlib import Path
from examples.efficient_pipeline.single_pass import ExportConfig, ExportOptions
from examples.efficient_pipeline.smart_cut import run_smart_cut


def quick_cut(source: Path, output: Path):
    plan, result = run_smart_cut(
        source,
        [(1000, 3000)],
        ExportConfig(output, width=1920, height=1080, fps=30),
        options=ExportOptions(),
    )
    return plan.mode, plan.reasons, result.output
```

Keyframe indeksi fayl hash/stat + media revision bo‘yicha cache qilinsin. Kod uni har chaqiruvda tekshiradi; ishlab chiqarishda indeksni backgroundda bir marta quring. Universal hybrid smart-render bu namunada yo‘q: edge GOP encode + ichki GOP copy uchun extradata, B-frame DTS, audio continuity va encoder parametrlari mosligini alohida isbotlash kerak.

## 2. Silero + Whisper: `vad_cleaner.py`

Silero speech interval beradi, filler ma’nosini aniqlamaydi. Whisper so‘zlari va Silero intervallari shu **bir xil manba fayli / bir xil audio origin** ga tegishli bo‘lsin. 16 kHz sample indeksini `sample * 1000 / 16000` orqali bir marta ms ga aylantiring. Faster-whisper sekundlari ham bir marta `round(seconds * 1000)` qilinadi.

```python
from examples.efficient_pipeline.edit_model import delete_source
from examples.efficient_pipeline.vad_cleaner import Config, Word, plan_cleanup


def clean_clip(
    timeline: dict,
    clip_id: str,
    asr_words: list[dict],
    vad_seconds: list[dict],
    source_duration_ms: int,
):
    words = [
        Word(
            id=w["id"],
            text=w["text"],
            start_ms=round(w["start"] * 1000),
            end_ms=round(w["end"] * 1000),
            confidence=w.get("probability"),
        )
        for w in asr_words
    ]
    speech = [(round(v["start"] * 1000), round(v["end"] * 1000)) for v in vad_seconds]
    proposal = plan_cleanup(words, speech, source_duration_ms, Config())
    clip = next(v for v in timeline["video"] if v["id"] == clip_id)
    cuts = [
        (max(a, clip["src_in_ms"]), min(b, clip["src_out_ms"]))
        for a, b in proposal.cuts
        if a < clip["src_out_ms"] and b > clip["src_in_ms"]
    ]
    return delete_source(timeline, clip_id, cuts), proposal.review
```

Bu adapter `vad_seconds` sekundda kelganini taxmin qiladi; sample indeksini shu argumentga bevosita bermang. Tayyor Silero/Whisper natijalari kifoya; `torch` dependency qo‘shilmaydi.

Standart siyosat:

| Parametr | Qiymat va amali |
|---|---|
| silence threshold | **>600 ms**, aynan 600 ms kesilmaydi |
| retain_pause | 180 ms + ikki tomonda 80 ms xavfsizlik: uzun ichki pauzada jami 340 ms qoladi |
| word guard | har qanday so‘z atrofida 40 ms himoya; VAD xatosi so‘zni kesmaydi |
| filler | `haligi`, `anaqa`, `e-e-e` va maxsus phrase; kamida 120 ms, confidence ≥0.8 |
| `demak`, `xo‘sh` | ma’noli bo‘lishi mumkin: odatda `review` |
| confidence yo‘q/past | `review`; avtomatik kesilmaydi |
| VAD yo‘q/bo‘sh | unknown sifatida qaraladi; sukut kesilmaydi |

Foydalanuvchi tanlagan qoidada `Config(allow_terms=("demak", "xo'sh"))` bilan ma’noli fillerlarni ham avtomatlashtirish mumkin; confidence/word himoyasi saqlanadi. Apostroflar NFKC va Uzbek variantlari bilan normallanadi, butun token/phrase solishtiriladi; substring orqali haqiqiy so‘z kesilmaydi.

`auto_word_ids` — filler nomzodlari ID’lari. O‘chgan manba oraliqlari uchun authoritative natija `cuts`: qo‘shni so‘z himoyasi sabab tokenning ayrim cheti saqlanishi mumkin. To‘liq transcriptni yangilangan matnga aylantirmang; faol so‘zlarni qolgan source spanlardan hisoblang.

Modul sort + monotone interval sweep ishlatadi; audio samplelari yoki video kadrlarini qayta o‘qimaydi. Kuchli word alignment yo‘q bo‘lsa Whisper timestamp aniqligi cheklovi saqlanadi. Namuna kesimni yashirincha zero-crossing’ga surmaydi; clickga sezgir audio uchun alohida 3–5 ms boundary fade qo‘shing yoki kesimni review’da tekshiring.

## 3. Render navbatisiz preview

Implementatsiya `preview/` ichida. `preview/README.md` da tayyor React ulash kodi va JASSUB asset konfiguratsiyasi bor.

```text
timeline revision → adaptTimeline → max 2 HTMLVideoElement
                                      │ native decode / playbackRate
                                      ├── CSS crop yoki Canvas rang qatlami
                                      ├── source currentTime → output clock
                                      ├── ASS WASM manualRender(output clock)
                                      └── Web Audio: source gain + VAD duck envelope + music
```

Asosiy qoida: `performance.now()` bilan montaj vaqtini oshirmang. Native media soati — master. `waiting`, seek yoki tab yashirilganda musiqa/ASS ham to‘xtaydi. Keyingi klip ikkinchi video elementida oldindan tayyorlanadi. Seek natijasi `seeked` va kadr tayyor bo‘lgach ko‘rsatiladi; seek fizik jihatdan nol millisekund emas.

`requestVideoFrameCallback` native kadr kelganda ishlaydi; Canvas har React renderida bo‘yalmaydi. Playhead UI state yangilanishi cheklangan. ASS workerda ishlaydi, bir render bajarilayotganda eng yangi pending vaqt saqlanadi. **JASSUB’ga kesiladigan `<video>`ni bevosita bermang**: uning `currentTime`i manba soati; `manualRender({mediaTime: outputMs / 1000, ...})` ishlatiladi. Backend ishlab chiqargan ayni ASS va Inter fontni preview/exportda ishlating.

Resurs siyosati: preview balandligi max 720 px, DPR=1, bitta faol + bitta tayyorlanayotgan dekoder. 30 FPS manbadan 60 noyob kadr chiqmaydi. Ekran refresh’i, WebView va source FPS chegarasi amal qiladi; 60 FPS faqat mos qurilmada o‘lchanadigan target. JASSUB WASM birinchi ochilganda yuklanadi/compile bo‘ladi; videoni oldindan render qilish talab qilinmaydi.

WebAudio preview VAD envelope bilan musiqa gainini boshqaradi. Bu FFmpeg `sidechaincompress`ning signalga bog‘liq compressor natijasiga sample-aniq teng emas. Teng audio kerak bo‘lsa ikkala tomonda bir xil deterministik VAD envelope ishlating yoki compressor algoritmini AudioWorklet’da ham implementatsiya qiling. `DynamicsCompressorNode` alohida sidechain input bermaydi.

Asl media URL’lari uchun:

- app’ning mavjud autentifikatsiyalangan, faqat ruxsatli media ID’ni ochadigan endpointi;
- HTTP `Range`, `206`, `Content-Range`, `Accept-Ranges: bytes`;
- aniq Tauri origin uchun CORS; video `crossOrigin` qiymatini `src` dan oldin qo‘yish;
- loopback asset/fetch/worker URL’lariga tegishli CSP, audio unlock uchun foydalanuvchi Play amali.

JASSUB’ning lokal Worker/WASM/fontlarini app ichiga bundle qiling; runtime’da CDN yoki font qidirish yo‘q. Mavjud CSP’ga kerakli `worker-src 'self'` va WASM uchun `script-src 'self' 'wasm-unsafe-eval'` qo‘shilishi tekshirilsin; blob worker ishlatilsa `worker-src`ga `blob:` ham qo‘shiladi. COOP/COEP SharedArrayBuffer/multithread ishlatilgandagina mos hostlarda yoqiladi; mos kelmasa single-thread WASM. CSP ishlab chiqarish konfiguratsiyasida bu namuna tomonidan o‘zgartirilmagan.

Native WebView source codecni ochmasa fallback kerak. Default original-video preview; faqat mos bo‘lmagan media uchun bir marta cache qilinadigan proxy. LUT/transition/22 FX’ning browser adapteri bo‘lmasa preview aniq unsupported deb qaytadi; mavjud eksport preview yo‘li saqlanadi. CSS `contrast()` FFmpeg `eq` yoki 3D LUT bilan bir xil matematika emas.

## 4. Bitta encode jarayonida eksport

Qo‘llangan kontrakt: straight cuts, speed, gain/mute, aspect-preserving fit/pad, FPS/SAR normalization, global rang/LUT, chiqish vaqtiga mos ASS, bitta loop qilinadigan background music va ducking. `single_pass.py` mavjud barcha 22 FX, crop/reframe, transition, sticker yoki ko‘p musiqa qatlamini avtomatik tarjima qilmaydi. Ular uchun alohida graph adapter kerak.

Quyidagi CLI: birinchi manbadan 1–3 s, ikkinchi kesim 3.5–6 s va 1.25×; chiqish jami 4 s. Ikkala inputda audio borligi va start_time=0 taxmin qilinadi. `captions.ass` allaqachon **chiqish vaqtida**, kerakli rang yozilgan `grade.cube` va `fonts/` ish papkasida bo‘lsin. Bundled FFmpeg’da `eq` yo‘q; rang LUT orqali beriladi.

```bash
ffmpeg -hide_banner -loglevel error -nostdin -n \
  -filter_complex_threads 1 -filter_threads 1 \
  -threads 1 -ss 1 -t 2 -i source.mp4 \
  -threads 1 -ss 3.5 -t 2.5 -i source.mp4 \
  -threads 1 -stream_loop -1 -t 4 -i music.wav \
  -filter_complex "
    [0:v]trim=duration=2,setpts=PTS-STARTPTS,
      scale=640:360:force_original_aspect_ratio=decrease,
      pad=640:360:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30,format=yuv420p[v0];
    [0:a]atrim=duration=2,asetpts=PTS-STARTPTS,atempo=1,
      aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,
      apad,atrim=duration=2[a0];
    [1:v]trim=duration=2.5,setpts=(PTS-STARTPTS)/1.25,
      scale=640:360:force_original_aspect_ratio=decrease,
      pad=640:360:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30,format=yuv420p[v1];
    [1:a]atrim=duration=2.5,asetpts=PTS-STARTPTS,atempo=1.25,
      aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,
      apad,atrim=duration=2[a1];
    [v0][a0][v1][a1]concat=n=2:v=1:a=1[cutv][speech];
    [cutv]lut3d=file=grade.cube,
      ass=filename=captions.ass:fontsdir=fonts,format=yuv420p[video];
    [2:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,
      atrim=duration=4,asetpts=PTS-STARTPTS,volume=-24dB[music];
    [speech]asplit=2[voice][control];
    [music][control]sidechaincompress=threshold=0.02:ratio=6:attack=20:release=350[bed];
    [voice][bed]amix=inputs=2:duration=first:normalize=0:dropout_transition=0,
      alimiter=limit=0.95:latency=1[audio]
  " \
  -map '[video]' -map '[audio]' \
  -c:v h264_videotoolbox -allow_sw 0 -b:v 6M -pix_fmt yuv420p \
  -c:a aac -b:a 192k -ar 48000 -ac 2 -threads:a 2 \
  -t 4 -movflags +faststart -map_metadata -1 output.mp4
```

`[speech]` ikki joyda ishlatilgani uchun `asplit` majburiy. `sidechaincompress`ning birinchi inputi pasaytiriladigan musiqa, ikkinchisi boshqaruvchi nutq. Manbada audio bo‘lmasa wrapper `anullsrc` yaratadi. Tezlik 0.25–4 bo‘lsa `atempo` xavfsiz bo‘laklarga ajratiladi. Cumulative frame quantization bo‘laklar yig‘ilganda har birida alohida yumaloqlash xatosini kamaytiradi.

Python wrapperni ishlatish:

```python
from pathlib import Path
from examples.efficient_pipeline.single_pass import (
    ExportConfig,
    ExportOptions,
    Segment,
    run_export,
)


def export_video(project: Path):
    source = project / "source.mp4"
    return run_export(
        [Segment(source, 1000, 3000), Segment(source, 3500, 6000, speed=1.25)],
        ExportConfig(
            output=project / "output.mp4",
            width=640,
            height=360,
            fps=30,
            encoder="auto",
            ass_path=project / "captions.ass",
            lut_path=project / "identity.cube",
            fonts_dir=project / "fonts",
            music=project / "music.wav",
            music_gain_db=-24,
            saturation=1.05,
        ),
        options=ExportOptions(threads=2, filter_threads=1, max_segments=64),
        progress=lambda ratio: print(f"{ratio:.0%}"),
    )
```

FFmpeg system PATH’da bo‘lmasa `ExportOptions(ffmpeg="/absolute/ffmpeg", ffprobe="/absolute/ffprobe")` bering. Rangning brightness/contrast/saturation qiymatlari kichik 17³ RGB LUTga aylantiriladi; bu FFmpeg `eq` semantikasi bilan aynan bir xil deb hisoblanmaydi. `color_filter="eq"` faqat shu filtr mavjud alohida build uchun beriladi. `auto` encoder nomiga emas, kichik haqiqiy encode preflight natijasiga qaraydi: macOS’da VideoToolbox, boshqa hostlarda mavjud NVENC/AMF/QSV/MF tekshiriladi. Ushbu kompyuterda faqat VideoToolbox ishlatilgani tekshirildi. CPU `libx264` fallback faqat `allow_libx264=True` bilan; default yashirin CPU yuklama yo‘q.

Wrapper `shell=False`, timeout/cancel, stdout progress va stderr parallel drain, xavfsiz asset nomlari, kirish/chiqish collision tekshiruvi va atomik yakunlashni qo‘llaydi. Faqat kichik ASS/LUT/font assetlari staging qilinadi; video/audio intermediate yaratilmaydi. `.lahza-*.mp4` yakuniy faylning to‘liq bo‘lmagan nomi, alohida media bosqichi emas. `+faststart` moov atomini ko‘chirishi mumkin: bitta encode, lekin MP4 ichida qo‘shimcha I/O bor. Mutlaqo oqimli mux kerak bo‘lsa bu flag o‘rniga fragmented MP4 tanlovi alohida sinovdan o‘tkaziladi.

Hardware encoder CPU filtrlarni avtomatik GPUga ko‘chirmaydi: ASS, LUT, scale va audio bu graph’da CPUda. `-hwaccel videotoolbox`ni CPU filtrlar oldiga ko‘r-ko‘rona qo‘shmang; hwdownload/upload xarajati oshishi mumkin. HDR (PQ/HLG) va non-square SAR manbalari alohida tone-map/aspect adapterisiz rad etiladi; ushbu reference SDR/square-pixel uchun. Barcha segment inputlari ochilgani sabab default max64; ko‘p yuzta bo‘lak uchun per-source interval dispatcher graph yoki batch renderer talab qilinadi. Unsupported graphni cheksiz kengaytirish o‘rniga ochiq xato qaytariladi.

## 5. Ilovaga ulash tartibi va resurs chegaralari

1. `routes_montage.py` yonida revisionli text-edit endpoint: ID resolution → `delete_source` → Pydantic validation → SQLite commit → WebSocket revision.
2. `MontagePreview.tsx` yonida yangi native-video yo‘l: `adaptTimeline` + namunadagi `MontagePreview`; mos bo‘lmagan effekt/codec uchun mavjud renderer.
3. ASS’ni mavjud `subtitle` builder bilan hosil qiling; video kadrlarini talab qilmaydigan kichik asset endpointidan bering. Preview va eksport ayni fayl/fontdan foydalansin.
4. Render dispatcher: proof-backed copy → bounded single-pass → mavjud murakkab-FX renderer. Adapter qo‘llamagan narsani hech qachon tashlab ketmasin.
5. Global heavy-job semafor=1: ASR/LLM/render parallel ishlamasin. FFmpeg decoder/input=1, filter_complex=1, audio=2; ONNX intra/inter=1. Preview vaqtida background scan to‘xtasin.
6. So‘z o‘chirish va sukut tozalash LLMni ochmasin. Qwen faqat erkin buyruq → reja uchun ishlasin; bekor turganda unload qilinsin. Birinchi ishga tushirishda komponentlar manifest/hash bilan bir marta olinib, keyin offline ishlasin; bu kit yuklovchini o‘zgartirmaydi.

Modelni kattalashtirish bu to‘rtta vazifa uchun kerak emas. Eng katta yutuq — transcript/VAD cache, asl videodan preview, bir encode va og‘ir ishlarni navbatlash.

## Tekshirish

Repo root’dan:

```bash
PYTHONPATH=engine/src engine/.venv/bin/python -m pytest examples/efficient_pipeline -q
engine/.venv/bin/python -m examples.efficient_pipeline.demo
app/node_modules/.bin/tsc -p examples/efficient_pipeline/preview/tsconfig.json
node --test examples/efficient_pipeline/preview/tests.mjs
```

Tekshirilgan natija: Python 3.12 da **50 test + 14 subtest**, TypeScript strict typecheck va **9 Node testi** o‘tdi. README’dagi CLI amalda **4.000 s** MP4 chiqardi. Python bloklari syntax compile tekshiruvidan o‘tdi.

Demo 6 s **sintetik** video/audio yaratadi; oldindan berilgan Whisper/VAD vaqtlarini tozalaydi; 1.25×, LUT, ASS, Inter, musiqa, sidechaincompress va VideoToolbox bilan bitta encode qiladi. Bu ASR sifatining sinovi emas. Natija **3.600 s**, 4 segment: `build/efficient-pipeline-verification/result.mp4`, kutilgan/haqiqiy davomiylik `report.json`da. Chiqishdan olingan kadrda Inter subtitri ko‘rindi. Brauzerda haqiqiy 60 FPS va qurilma issiqligi bu tekshiruv bilan isbotlanmaydi; target kompyuterda alohida profiling kerak.

Birlamchi manbalar: [FFmpeg streamcopy](https://github.com/FFmpeg/FFmpeg/blob/n7.1.1/doc/ffmpeg.texi), [FFmpeg filters](https://github.com/FFmpeg/FFmpeg/blob/n7.1.1/doc/filters.texi), [requestVideoFrameCallback](https://developer.mozilla.org/en-US/docs/Web/API/HTMLVideoElement/requestVideoFrameCallback), [JASSUB canvas/manualRender](https://github.com/ThaUnknown/jassub), [Silero VAD](https://github.com/snakers4/silero-vad).
