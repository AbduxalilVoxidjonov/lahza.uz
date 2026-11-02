# ADR-0015: ASR audio dekodi PyAV'siz — LGPL FFmpeg orqali numpy massiv

* Holat: Qabul qilindi
* Sana: 2026-10-26
* TZ bo'limi: 5, 16 (ADR-0004 ni to'ldiradi)

## Kontekst
`engine[desktop]` faster-whisper 1.2.1 bilan birga `av==16.1.0` (PyAV) ni o'rnatar edi: faster-whisper
metadata'sida `av>=11` bor. PyPI'dagi PyAV g'ildiraklari o'z FFmpeg'ini (`av/.dylibs`, `av.libs`) olib
keladi va u **GPL libx264/libx265** bilan statik yig'ilgan. PyInstaller `--collect-all av` bilan ular
sidecar'ga tushardi — bu ADR-0004 ("faqat LGPL FFmpeg") ga zid va desktop to'plamni GPL qiladi
(`LICENSES-THIRD-PARTY.md` da `x264`/`x265` **GPL** deb belgilangan edi).

Tahlil:
* Engine kodida `av` to'g'ridan-to'g'ri ishlatilmaydi.
* faster-whisper `av` ni faqat `faster_whisper.audio.decode_audio()` ichida ishlatadi; u
  `WhisperModel.transcribe()` ga **fayl yo'li** berilganda chaqiriladi (`if not isinstance(audio, np.ndarray)`).
* Lekin `faster_whisper/audio.py` modul darajasida `import av` qiladi, `faster_whisper/__init__.py` esa
  uni import qiladi — ya'ni `av` bo'lmasa `import faster_whisper` ning o'zi `ImportError` beradi.
* Bizning backend (`asr/faster_whisper_backend.py`) bo'lak WAV fayl yo'lini (`str(wav)`) berar edi.

## Qaror
1. **Dekod — o'zimizning LGPL FFmpeg'da.** `lahza_engine.media.pcm.decode_pcm_f32()` `find_tool("ffmpeg")`
   (ADR-0004 yig'masi) ni alohida jarayon sifatida ishga tushirib, birinchi audio oqimni 16 kHz mono
   `f32le` ga o'giradi va `np.float32` massiv qaytaradi. `FasterWhisperBackend.transcribe_chunk()`
   `transcribe()` ga faqat shu massivni beradi — `decode_audio()`/PyAV yo'li ishlamaydi.
2. **`av` qo'riqchisi.** `lahza_engine.asr.fw_compat.import_faster_whisper()` faster-whisper import
   qilinishidan oldin `sys.modules["av"]` ga qo'riqchi modul qo'yadi: `import av` o'tadi, `av.<har qanday
   atribut>` esa `PyAvBlocked` bilan yiqiladi (jim GPL yo'l emas, aniq xato). Qo'riqchi PyAV o'rnatilgan
   dev muhitda ham qo'yiladi (reliz bilan bir xil xatti-harakat); faqat haqiqiy PyAV jarayonga allaqachon
   yuklangan bo'lsa tegilmaydi. faster-whisper'ni hamma joyda (backend, `models/local_bootstrap.py`,
   `models/setup.py`, sidecar `--packaging-check`) shu funksiya orqali yuklash shart; test buni tekshiradi.
3. **O'rnatish PyAV'siz.** `desktop` ekstrasida endi faster-whisper ham, `av` ham yo'q — faster-whisper
   1.2.1 ning qolgan runtime bog'liqliklari (ctranslate2, huggingface-hub, tokenizers, tqdm, onnxruntime)
   sanaladi. faster-whisper `pip install --no-deps -r engine/requirements-desktop-nodeps.txt` bilan
   o'rnatiladi (Makefile `setup-local`, CI va reliz workflow'lari).
4. **Uch qavatli darvoza.**
   * `scripts/build_sidecar.py`: `av` — `--exclude-module` (venv'da bo'lsa ham), `COLLECT_ALL`/`REQUIRED_BACKENDS`
     dan chiqarilgan; build'dan keyin PyInstaller TOC'larida `av`, `av/.dylibs`, `av.libs`, `libx264`,
     `libx265` izlari qidiriladi — topilsa build yiqiladi. Frozen `--packaging-check` qo'riqchi faolligini
     (`av_guard: true`) qaytaradi.
   * `scripts/gen_licenses.py` (`make licenses`, `make check-licenses`, CI `--check --reuse python`):
     sidecar'ning Python/native yopilmasida `av` yoki GPL komponent (bootloader istisnosidan tashqari)
     bo'lsa 2 bilan yiqiladi. `--no-deps` paketlarining e'lon qilingan bog'liqliklari kuzatilmaydi.
   * `engine/tests/test_asr_no_pyav.py`: dekod (haqiqiy ffmpeg), `sys.modules["av"] = None` bilan ASR yo'li,
     toza jarayonda haqiqiy faster-whisper importi, `import av` yo'qligi, ekstra/no-deps mosligi, darvozalar.

## Oqibatlar
* Desktop sidecar'da GPL x264/x265 yo'q; PyAV ichidagi 26 ta native kutubxona (LGPL-3.0 FFmpeg nusxasi
  ham) to'plamdan chiqdi — FFmpeg faqat bitta, ADR-0004 yig'masi.
* ASR bo'lagi uchun qo'shimcha `ffmpeg` jarayoni (≤ 30 s bo'lak, odatda o'nlab ms). ffmpeg topilmasa ASR
  `AudioDecodeError`/`ToolNotFound` bilan to'xtaydi — render uchun ham ffmpeg baribir majburiy.
* faster-whisper versiyasini ko'tarishda: `requirements-desktop-nodeps.txt` pinini va `desktop` ekstrasini
  yangi metadata bilan solishtirish kerak (`test_desktop_extra_installs_no_pyav` farqni ko'rsatadi);
  faster-whisper modul darajasida `av` dan boshqa narsa (masalan `av.__version__`) ishlatsa qo'riqchi buni
  aniq xato bilan ko'rsatadi.
* `pip install faster-whisper` (oddiy) yoki `engine[asr-ctranslate2]` hali ham PyAV'ni tortadi — bu
  dasturchi muhiti uchun; sidecar'ga kirmasligini build darvozasi kafolatlaydi.

## Ko'rib chiqilgan muqobillar
| Variant | Nega tanlanmadi |
| --- | --- |
| PyAV'ni manbadan o'zimizning LGPL FFmpeg'ga qarshi yig'ish (`pip install av --no-binary av` + `PKG_CONFIG_PATH` LGPL yig'maga) | Ishlaydi va litsenziya jihatidan toza bo'lardi, lekin: Cython + C kompilyator + FFmpeg sarlavhalari har platformada (Windows MSVC) kerak; PyAV ABI'si FFmpeg versiyasiga qattiq bog'liq (PyAV 19 faster-whisper'ning `metadata_errors` argumentini rad etgan); FFmpeg'ning ikkinchi nusxasi Python jarayoniga yuklanadi. Bizga faqat 16 kHz mono PCM kerak — subprocess yetarli. Agar kelajakda oqimli (streaming) dekod kerak bo'lsa, shu variantga qaytiladi. |
| faster-whisper'ga fork/patch (`audio.py` dan `import av` ni olib tashlash) | Fork yuritish narxi; qo'riqchi shim bilan bir xil natija upstream kodga tegmasdan olinadi. |
| PyAV'ni qoldirib, faqat `libx264`/`libx265` dylib'larini PyInstaller'dan olib tashlash | libavcodec ularga bog'langan — dylib yo'qligi `import av` ni sindiradi; libavcodec'ning o'zi `--enable-gpl` bilan yig'ilgan bo'lib qoladi. |
| `soundfile`/`wave` bilan WAV'ni to'g'ridan-to'g'ri o'qish | Bo'laklar hozir WAV bo'lsa ham, kirish formati/namuna chastotasi kafolatlanmagan; libsndfile yana bitta native bog'liqlik. FFmpeg baribir bor. |
