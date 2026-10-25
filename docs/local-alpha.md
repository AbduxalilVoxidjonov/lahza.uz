# Lokal alfa — 2026-10-24

Lahza Studio mustaqil desktop ilova: Adobe obunasi yoki GPU server talab qilinmaydi.
Hozirgi lokal yig'ma Apple Silicon va macOS 27+ uchun. Bu Developer ID bilan
imzolangan/notarizatsiyalangan reliz emas; Windows `.exe` bu Mac'da tekshirilmagan.

## Ishga tayyorlash

```sh
make setup-local  # bir martalik internet: paketlar, FFmpeg, NavAI base + Silero
make build-local
make smoke-local VIDEO=/absolute/podcast.mp4
```

Natija: `app/src-tauri/target/release/bundle/macos/Lahza Studio.app`.
Shu Mac'da tekshirilgan nusxa `~/Applications/Lahza Studio.app`ga joylandi;
ad-hoc imzo `codesign --verify --deep --strict` bilan o'tdi. Kutubxonada
`Lahza sinov — Maqolim` loyihasi va platforma/prompt sinov montajlari mavjud.
Yig'ishdan oldin Xcode Command Line Tools, Rust, Homebrew va Node o'rnatilgan bo'lishi kerak.
Setup va model o'rnatish — foydalanuvchi boshlaydigan tarmoq amallari; video tahlili lokal.

## Qo'shilgan imkoniyatlar

* Boshlash oynasidan rozilik bilan o'zbekchaga moslashtirilgan NavAI base ASR yuklash.
* Inter shrifti va ko'chiriladigan LGPL FFmpeg yordamida karaoke subtitrli MP4.
* Montaj muharririda PNG/WebP/GIF stikerlar: vaqt, joy, o'lcham, aylanish,
  shaffoflik, qatlam tartibi, fade/pop. Uchta original stiker bilan birga keladi.
* Qo'lda caption yozish, haqiqiy transkript so'zlarini tahrirlash va SRT import.
  SRT vaqtlaridan soxta so'z vaqtlari yasalmaydi.
* Klipni ko'rsatkichda bo'lish, caption/matn/stikerlarni mos surib oraliqni yopib
  o'chirish, trim/tartib/nusxalash va 100 qadamli undo/redo.
  FX/o'tish bilan xavfsiz kesib bo'lmaydigan joylarda amal bloklanadi.
* Instagram Reels, YouTube Shorts, oddiy YouTube video va Custom uchun alohida
  eksport profillari. Formatni qo'llash alohida amal; video jim qisqartirilmaydi.
  Shorts'ning kvadrat/tik va 180 soniya talabi eksportdan oldin tekshiriladi.
* Qisqa promptdan tahrir rejasini ko'rish va bitta undo qadami bilan qo'llash.
  Lokal buyruqlar parseri va haqiqiy Qwen3 GGUF bilan AI yordamchi alohida
  rejimlar. AI hozir format/caption/rang/stop-kadr bilan cheklangan; o'zbekcha
  ma'noni adashtirishi mumkin, reja ko'rib chiqilishi shart.
* Stop-kadr: tanlangan vaqtni 100–5000 ms ushlab turish; ovoz davom etadi,
  timeline davomiyligi uzaymaydi.
* Tashqi fayllar: `.cube` LUT montajga qo'llanadi; `.srt`, `.prfpset`, `.mogrt`
  ma'lumotlari o'qiladi. Adobe bajariladigan plaginlari va `.aep` loyihalarini
  Adobe'siz ishlatish qo'llanmaydi.
* `.lahzaskill` yoki JSON montaj skill'larini o'rnatish, qo'llash, olib tashlash.
  Skill faqat caption, stiker, rang, harakat va stop-kadr retseptidir; kod/shell emas.

## Haqiqiy video sinovi

Foydalanuvchi bergan [Maqolim videosi](https://www.youtube.com/watch?v=nauuJZeQb0I)
ning 01:00–03:30 parchasi (150 soniya, 640×360) bilan ishlatildi.
To'liq video yoki boshqa foydalanuvchi ma'lumotlari hech qayerga yuborilmadi.

* Oddiy multilingual Whisper base mos kelmadi: noto'g'ri matn va takroriy belgilar.
* Lokal standart sifatida NavAI Uzbek small + Silero tanlandi. Toza keshli yakuniy
  sinov: **318 so'z, 3 klip, 57.77 soniya**; birinchi klipning 1080×1920 MP4/SRT
  eksporti muvaffaqiyatli. Video/ovoz davomiyligi farqi **0.020017 soniya**.
* Bu tezlik aynan shu Mac va shu parcha uchun; umumiy ishlash kafolati emas.
* Matn ancha tushunarli, lekin sezilarli ASR xatolari bor. Qo'lda etalon transkript
  yo'q; WER yoki sifat foizi hisoblanmadi. Muharrir tahriri kerak.
* Manbada tasvir 6.214522 soniyadan, ovoz esa deyarli noldan boshlanadi.
  Render bu vaqtni saqlaydi: boshlang'ich yo'q tasvir o'rniga qora kadr,
  yo'q ovoz o'rniga sukut ishlatiladi. Audio/video har biri alohida nolga surilmaydi.

Kuchliroq small modelning oflayn paketi:
`build/local-asr-compare/navai-small-uzbek-silero.lzpack` (~252 MB).
Yangi kompyuterda import qilingach model menejerida uni ASR standarti qilib tanlash kerak.
Bir bosishli boshlang'ich yuklash esa kichikroq NavAI **base** modelini o'rnatadi.

Sinov artefaktlari (Git'ga kirmaydi):

* `build/local-verification/uzbek-smoke-final.log` — to'liq, keshsiz oqim.
* `build/local-smoke/5bf10fcd08ba/report.json` — o'lcham va sinxronlik.
* `build/local-demo/lahza-demo.mp4` — caption, stiker, karaoke va stop-kadr namuna.
* `build/local-demo/timeline.json` — namunaning tahrirlanadigan holati.
* `build/local-verification/packaged-tests.log` — yig'ilgan `.app` ichidagi haqiqiy
  ASR, imzolangan katalog, token, multiprocessing va izolyatsiyalangan FFmpeg:
  **13 passed**. Manba engine testlari alohida: **640 passed, 8 skipped** (2026-10-25).
* `build/local-verification/packaged-flow-report.json` — odatiy lokal kutubxonada
  caption + stiker + stop-kadr + `gentle-zoom` skill'i bilan MP4/SRT eksporti.
  O'rnatilgan stiker fayllari engine yopilgandan keyin ham mavjudligi tekshirildi.
* `build/local-verification/ui-tests.log` — **47 passed**: split/ripple,
  undo/redo va server saqlashi, profillar, prompt tahlili va eskirgan reja himoyasi.
* `build/local-verification/platform-report.json` — uch formatdagi haqiqiy MP4;
  `build/local-verification/prompt-flow-report.json` — prompt yaratgan timeline eksporti.

## Hali tekshirilmagan

* Desktop oynasidagi to'liq click-through sinovi: kompyuter boshqaruvi ekran olishda
  ScreenCaptureKit `-3811` xatosi bilan to'xtadi. Build va packaged engine/render
  tekshiruvlari buning o'rnini to'liq bosmaydi.
* Uzoq videolar, turli shevalar, shovqin va ustma-ust nutqda sifat/tezlik benchmarki.
* Windows o'rnatuvchisi, macOS 14–26 uchun kutubxonalar va toza kompyuter sinovi.
* Haqiqiy LLM, aktiv spiker va diarizatsiya modellarining sifat bahosi; hozir Lite
  highlight, ASR so'z vaqtlari va xira fon zaxirasi bilan ishlash mumkin.

Tafsilotlar: [modellar](local-models.md), [render](local-render.md),
[desktop](local-desktop.md), [vaqtlar](local-timing.md), [stikerlar](local-stickers.md),
[tahrirlash](local-montage-editing.md), [skill'lar](local-skills.md),
[platformalar](local-platforms.md), [tashqi fayllar](13-external-assets.md).
Prompt misollari: [lokal promptlar](local-prompts.md).
Haqiqiy model: [AI yordamchi](local-ai-editing.md),
[bosqichli rivojlantirish](14-agentic-roadmap.md).
