# Lahza Studio — Oflayn AI Reels kesuvchi: to'liq TZ

Oct 13, 2026 · @Ischool

## Hujjat haqida

Lahza Studio (ishchi nom) — uzun o'zbekcha podkast va videolardan eng qiziq lahzalarni AI yordamida topib, 9:16 formatdagi, o'zbekcha subtitrli Instagram Reels kliplarini yasaydigan **to'liq oflayn desktop dastur** (macOS va Windows). Hujjat 2026-yil oktabr holatidagi ochiq manbalarga tayangan; har bir raqam manbaga ega, manbasi yo'q qiymatlar `ANIQLANSIN` deb belgilangan yoki "maqsadli ko'rsatkich" deb atalgan.

**Gemini TZ'siga nisbatan tuzatishlar (muhim):**

| Gemini TZ'da | Muammo | Bu TZ'da |
| --- | --- | --- |
| Gemini API, Gemini Audio, Cloudflare R2 | Internet talab qiladi — oflayn shartga zid | Barcha model lokal: ASR, LLM, ko'rish modellari qurilmada ishlaydi |
| PostgreSQL, Celery/RabbitMQ, MinIO | Server steki; desktop dasturga ortiqcha og'irlik | SQLite + jarayon ichidagi navbat + lokal fayl kesh |
| Faster-Whisper hamma joyda | CTranslate2 Apple Silicon GPU (Metal) ni qo'llamaydi — Mac'da faqat CPU | Mac: whisper.cpp (Metal/Core ML) yoki MLX; Windows NVIDIA: faster-whisper (CUDA) |
| WhisperX bilan so'z vaqtlari | O'zbek tili uchun standart alignment modeli yo'q | O'zbekcha CTC alignment modeli alohida tanlanadi (5- va 6-bo'lim) |
| "30–60 soniya" qat'iy | Instagram limitlari manbalarda turlicha | Davomiylik sozlanadi; limit relizdan oldin tekshiriladi |
| libx264 bilan render | libx264 GPL — yopiq tijorat dasturga to'g'ridan-to'g'ri qo'shib bo'lmaydi | LGPL FFmpeg + apparat enkoderlari (VideoToolbox, NVENC, Media Foundation) |
| O'zbek imlosi: faqat o', g' | 2026-yil sentabrda Senat yangi alifboni (Ö, Ğ, Ş, Ç) ma'qulladi | Subtitr ikki imloni ham qo'llaydi, bir tugma bilan almashtiriladi |
| Bitta model "eng yaxshi" deb tanlangan | O'zbekcha modellar sifati audio turiga qarab keskin farq qiladi | Model o'z podkast ma'lumotingizda o'lchab tanlanadi (R0 bosqichi) |

## 1. Maqsad, foydalanuvchilar va qamrov

Maqsad: 1 soatlik o'zbekcha podkastdan muharrir aralashuvisiz 5–15 ta nashrga tayyor Reels nomzodini chiqarish, muharrir esa ularni bir necha daqiqada tasdiqlab, tahrir qilib, eksport qiladi.

**Foydalanuvchilar**

- **SMM mutaxassisi / montajchi** — asosiy foydalanuvchi; har hafta bir nechta podkastdan kliplar chiqaradi.
- **Podkast egasi / bloger** — texnik bilimi kam; "yukla → tanla → eksport" oqimi kerak.
- **Media-studiya / o'quv markazi** — brend shablonlari, partiyaviy (batch) ishlov, bir nechta loyiha.

**v1.0 ichida**

- Lokal video import: MP4, MOV, MKV (bitta yoki ikki kamerali yozuv).
- O'zbekcha transkripsiya (lotin), so'z darajasidagi vaqt belgilari, spikerlarni ajratish.
- AI orqali highlight topish: sarlavha, hook, sabab, ball, heshteglar.
- 9:16 smart reframe: 1 spiker, 2 spiker (split), xira fon, qo'lda kadr.
- Animatsiyali (karaoke) subtitr, brend shablonlari, imlo tanlovi.
- Transkript va klip muharriri, eksport navbati, 1080×1920 MP4.

**v1.0 tashqarisida (keyingi bosqichlar)**

- YouTube havoladan yuklab olish (internet talab qiladi; 17-bo'limda ixtiyoriy plagin sifatida).
- AI dublyaj, AI B-roll generatsiyasi, ijtimoiy tarmoqqa avtomatik joylash.
- Jamoaviy ishlash va bulutli sinxronizatsiya.
- Kirill yozuvidagi subtitr — v1.1 (transliteratsiya orqali).

## 2. Asosiy cheklovlar va apparat darajalari

Dastur ishlash vaqtida internetga **umuman murojaat qilmaydi**: telemetriya yo'q, bulut API yo'q, video kompyuterdan chiqmaydi. Internet faqat ixtiyoriy ikki holatda kerak bo'lishi mumkin: model paketlarini bir marta yuklab olish (yoki uning o'rniga USB/fayl orqali oflayn import) va ixtiyoriy yangilanish tekshiruvi (sozlamada o'chiriladi).

**Qo'llab-quvvatlanadigan platformalar (v1.0 qarori)**

- macOS 14+ va faqat Apple Silicon (M1 va yangi). Intel Mac — qo'llanmaydi: lokal model ishlashi uchun Metal/Neural Engine kerak.
- Windows 10 22H2 / Windows 11, x64. NVIDIA GPU — eng tez yo'l; AMD/Intel GPU — Vulkan/DirectML orqali; GPU yo'q — CPU rejimi (sekin, lekin ishlaydi).
- Windows on ARM va Linux — v1.0 dan keyin.

**Apparat darajalari (tier).** Dastur birinchi ishga tushganda apparatni aniqlaydi va mos model to'plamini avtomatik tanlaydi. Vaqt ko'rsatkichlari maqsadli bo'lib, R0 benchmarkidan keyin tasdiqlanadi.

| Daraja | Mac | Windows | Lokal LLM (4-bit) | Maqsad: 60 daq video tahlili |
| --- | --- | --- | --- | --- |
| Lite | M1/M2, 8 GB | 16 GB RAM, GPU yo'q | Qwen3.5-4B (\~3 GB) | ≤ 60 daq (ANIQLANSIN) |
| Standard | M-seriya, 16 GB | NVIDIA 8 GB VRAM, 16 GB RAM | Qwen3.5-9B (\~6 GB) | ≤ 20 daq (ANIQLANSIN) |
| Pro | M-Pro/Max, 32 GB+ | NVIDIA 16 GB+ VRAM, 32 GB RAM | Gemma 4 26B A4B yoki 31B | ≤ 10 daq (ANIQLANSIN) |

Qwen3.5 kichik modellarining 4-bit xotira hajmi: 9B \~6 GB, 4B \~3 GB, 2B va 0.8B 2 GB dan kam ([Artificial Analysis](https://artificialanalysis.ai/articles/qwen3-5-small-models)). Qaysi LLM ishlatilishi 7-bo'limdagi baholashdan keyin yakunlanadi.

**Disk:** dastur + Lite model paketi va Pro paketi hajmi model tanlovidan keyin aniqlanadi (ANIQLANSIN). Har bir loyiha uchun proksi video va kesh uchun manba video hajmicha bo'sh joy talab qilinadi; joy yetmasa dastur ishni boshlamasdan ogohlantiradi.

## 3. Arxitektura

Dastur uch qatlamdan iborat: Tauri 2 oboloq (Rust + React UI), Python'da yozilgan "Lahza Engine" sidecar jarayoni va engine chaqiradigan native runtime'lar. UI hech qachon model yoki FFmpeg'ni bevosita chaqirmaydi — faqat engine API'si orqali.

&#91;embedded content: arxitektura · oboloq, engine, native runtime'lar\]

Engine qulasa, Rust yadro uni qayta ishga tushiradi va navbatdagi vazifalar davom etadi; UI esa ochiq qoladi.

**Texnologik stek (qaror)**

| Qatlam | Texnologiya | Nima uchun |
| --- | --- | --- |
| Oboloq | Tauri 2 (Rust) | Kichik o'rnatuvchi, tizim WebView'i; PyInstaller bilan yig'ilgan Python sidecar rasman qo'llanadi ([Tauri](https://v2.tauri.app/develop/sidecar/)) |
| UI | React + TypeScript + Vite, Zustand, TanStack Query | Video preview, timeline va libass WASM preview uchun web-ekotizim boy |
| Engine | Python 3.12, FastAPI + WebSocket, PyInstaller | ML kutubxonalari Python'da |
| ASR | whisper.cpp (Mac; AMD/Intel GPU), faster-whisper (NVIDIA) | 5-bo'lim |
| LLM | llama.cpp `llama-server` | Metal, CUDA, Vulkan; JSON grammatika |
| Ko'rish | ONNX Runtime (Mac'da Core ML, Windows'da CUDA/DirectML provayderlari) | Bitta model fayli — ikki platforma |
| Diarizatsiya | pyannote.audio 4.0 | 6-bo'lim |
| Video | FFmpeg (LGPL) + libass | 10-bo'lim |
| Saqlash | SQLite (WAL) | Server kerak emas, fayl sifatida ko'chadi |

**Ko'rib chiqilgan muqobillar.** Electron — yetuk, lekin o'rnatuvchi va xotira og'irroq. Flutter desktop — jamoa Flutter'ni bilsa mumkin, ammo subtitr preview va video timeline uchun tayyor kutubxonalar kamroq. Engine API o'zgarmagani uchun UI keyinchalik almashtirilsa ham engine qayta yozilmaydi.

**Engine API (asosiy endpointlar)**

```
POST  /v1/projects                  loyiha yaratish
POST  /v1/media:import              video import, tahlilni boshlash
GET   /v1/jobs/{id}                 vazifa holati
WS    /v1/events                    progress, xatolar, bildirishnomalar
GET   /v1/media/{id}/transcript     gaplar va so'zlar
PATCH /v1/words                     transkript tahriri (qayta tekislash bilan)
GET   /v1/clips?media={id}          klip nomzodlari
PATCH /v1/clips/{id}                chegaralar, layout, uslub, holat
POST  /v1/clips/{id}/preview        preview kadr yoki qisqa proksi
POST  /v1/exports                   eksport navbatiga qo'shish
GET   /v1/models | POST /v1/models:install
```

## 4. Pipeline bosqichlari

Har bir bosqich alohida, qayta ishga tushiriladigan va keshlanadigan vazifa: natija kaliti = `manba_hash + bosqich_versiyasi + model_id + parametr_hash`. Biror parametr o'zgarsa, faqat undan keyingi bosqichlar qayta hisoblanadi; dastur qulasa, ish oxirgi tugagan bosqichdan davom etadi.

1. **Ingest** — `ffprobe` bilan metadata; fayl xeshi (xxHash, birinchi/oxirgi 64 MB + hajm — tezlik uchun); 16 kHz mono WAV (ASR uchun), asl audio nusxasi (render uchun), 540p proksi video (UI preview uchun). Asl fayl ko'chirilmaydi, faqat havola saqlanadi.
2. **Vizual tahlil** — sahna/kesim chegaralari (PySceneDetect), 5 fps da yuz aniqlash va treking (chastota sozlanadi).
3. **VAD** — nutq bo'laklarini ajratish (Silero VAD); sukut, musiqa va shovqin ASR'ga yuborilmaydi — Whisper "gallyutsinatsiyasi"ning asosiy oldini olish.
4. **ASR** — nutq bo'laklarini ≤30 s qismlarga bo'lib transkripsiya (5-bo'lim).
5. **Normalizatsiya** — apostrof variantlarini yagona belgiga keltirish, imlo, raqamlar, lug'at bo'yicha tuzatish (9-bo'lim).
6. **Forced alignment** — har bir so'zga boshlanish/tugash vaqti va ishonch bali (6-bo'lim).
7. **Diarizatsiya** — har bir so'zga spiker yorlig'i (6-bo'lim).
8. **Signal xususiyatlari** — ovoz balandligi, nutq tezligi, pauza tuzilmasi, kulgi/olqish detektori, savol-javob juftliklari.
9. **Highlight topish** — LLM nomzodlari + signal bali + chegaralarni gap/pauza bo'yicha tekislash (7-bo'lim).
10. **Reframe rejasi** — har bir klip uchun aktiv spiker va silliq kamera yo'li (8-bo'lim).
11. **Subtitr maketlash** — qatorlarga bo'lish, uslub, xavfsiz zona (9-bo'lim).
12. **Render** — faqat foydalanuvchi eksportni bosganda, navbat orqali (10-bo'lim).

1–9-bosqichlar import qilingandan keyin avtomatik ishlaydi. 10–11-bosqichlar har bir klip uchun tez (soniyalar ichida) qayta hisoblanadi, shuning uchun foydalanuvchi tahrirlari darhol ko'rinadi.

**Resurs boshqaruvi:** GPU xotirasini tejash uchun modellar ketma-ket yuklanadi va bo'shatiladi (ASR → alignment → diarizatsiya → LLM). Bir vaqtda bitta og'ir model GPU'da turadi; Pro darajada parallel ishlash ruxsat etiladi.

## 5. ASR moduli: o'zbek nutqini aniq tanish

Highlight, subtitr va kesish chegaralari shu modul natijasiga tayanadi, shuning uchun model "eng mashhuri" bo'yicha emas, sizning podkastlaringizdan yig'ilgan test to'plamida o'lchab tanlanadi. Asl Whisper o'zbek tilida yomon: FLEURS'da eng yaxshi WER 90.2% bo'lgan ([whisper-small-uz](https://huggingface.co/BlueRaccoon/whisper-small-uz/blob/main/README.md)), large-v3 zero-shot CER esa 28.45% ([BuzzASR](https://huggingface.co/BuzzASR/uzbek)). Demak, faqat o'zbekchaga fine-tune qilingan modellar ko'rib chiqiladi.

**Nomzodlar (2026-yil oktabr holati, raqamlar model kartalaridan)**

| Model | Asos | Litsenziya | Natija (WER) | E'tibor berish kerak |
| --- | --- | --- | --- | --- |
| [idrock/piyola-v2](https://huggingface.co/idrock/piyola-v2) | Parakeet TDT 0.6B (617M) | CC-BY-4.0 | FeruzaSpeech 6.08%, FLEURS 10.67%, USC 11.86%, spontan/shovqinli 25.57% | Faqat kichik harf, tinish belgisi va raqam yo'q; 0.1–20 s kliplarda o'qitilgan, uzun audio bo'laklanadi; NeMo |
| [Abduqayum/whisper-uzbek-medium-callcenter](https://friendli.ai/models/Abduqayum/whisper-uzbek-medium-callcenter) | Whisper medium | ANIQLANSIN | FeruzaSpeech 7.88%, Common Voice 17 13.37%, FLEURS 14.40% | \~780 soat audiokitob, podkast, texnik suhbat; sukutda jim turishga o'rgatilgan; faqat lotin |
| [BuzzASR/uzbek](https://huggingface.co/BuzzASR/uzbek) | Whisper large-v3 | MIT | Common Voice 25 11.84%, FLEURS 25.64% | Faqat o'qilgan nutq (FLEURS + Common Voice) bilan o'qitilgan — podkastda sinash shart |
| [islomov/rubaistt\_v2\_medium](https://huggingface.co/islomov/rubaistt_v2_medium/blob/main/README.md) | Whisper medium | Apache-2.0 | \~17% (test to'plami ko'rsatilmagan) | \~475 soat: podkastlar, Toshkent shevasi, yangiliklar, IT; yarmi Gemini bilan avto-belgilangan |
| [Meta Omnilingual ASR](https://ai.meta.com/blog/omnilingual-asr-advancing-automatic-speech-recognition/) | wav2vec2 CTC / LLM-ASR, 300M–7B | Apache-2.0 | O'zbekcha raqam ANIQLANSIN | CTC-1B \~3 GiB VRAM ([model kartasi](https://huggingface.co/ziywang50/omniASR-LLM-300M)); alignment uchun ham nomzod |

WER raqamlari turli test to'plamlarida o'lchangan va to'g'ridan-to'g'ri solishtirib bo'lmaydi. piyola-v2 muallifi ham ta'kidlaganidek, bir model toza o'qilgan nutqda \~6%, spontan shovqinli nutqda \~26% xato beradi — podkast aynan ikkinchi turga yaqin.

**R0 tanlov tartibi (majburiy)**

1. "UzPodcast-Eval" to'plami: 3–5 soat real podkast audio, kamida 10 spiker, erkak/ayol, shevalar (Toshkent, Farg'ona vodiysi, Samarqand, Xorazm), rus/ingliz so'zlari aralash nutq, musiqa kirishi, ustma-ust gaplashish.
2. Qo'lda yozilgan etalon transkript: yagona yo'riqnoma bo'yicha (apostrof, raqam, chet so'zlar qanday yoziladi).
3. O'lchovlar: normallashtirilgan WER va CER, ismlar/brendlar aniqligi, sukut/musiqada "o'ylab topilgan" so'zlar ulushi, har bir apparat darajasida tezlik (RTF).
4. Qaror qoidasi: daraja bo'yicha tezlik maqsadiga sig'adigan modellar ichidan eng past WER — asosiy; eng tezi — zaxira.

**Ishga tushirish (runtime) talablari**

- Whisper oilasidagi model ikki formatga o'giriladi: CTranslate2 (faster-whisper, Windows CUDA/CPU) va GGML/GGUF (whisper.cpp: Mac'da Metal va Core ML, Windows AMD/Intel'da Vulkan). CTranslate2 Apple Silicon GPU'ni qo'llamaydi ([manba](https://pyvideotrans.com/blog/ctranslate2-whisper)); whisper.cpp esa Metal, Core ML, CUDA, Vulkan'ni qo'llaydi ([manba](https://www.sourcepulse.org/projects/2125572)).
- NeMo/Parakeet modeli tanlansa — ONNX eksport va platformalararo ishlashi R0'da isbotlanadi; isbotlanmasa, u faqat zaxira bo'ladi.
- Dekodlash: til qat'iy `uz`; oldingi matnga tayanish o'chirilgan (takrorlanish halqasiga qarshi); n-gram takrorlanish jazosi; harorat fallback; VAD dan keyingi ≤30 s bo'laklar.
- Lug'at (hotwords): mehmon ismlari, brendlar, atamalar loyiha darajasida kiritiladi va dekoderga uzatiladi.
- Tinish belgilari va katta harf: model bermasa, keyingi bosqichda lokal LLM yoki qoidaviy tiklagich qo'yadi.
- Ishonch bali: har bir so'z uchun saqlanadi; past ishonchli so'zlar muharrirda sariq rangda ko'rinadi.

**O'z-o'zini yaxshilash (Pro).** Muharrir har bir tuzatishi "audio bo'lak + to'g'ri matn" juftligi sifatida lokal saqlanadi. Lug'at avtomatik to'ldiriladi; yetarli ma'lumot yig'ilganda (hajmi ANIQLANSIN) foydalanuvchi o'z GPU kompyuterida fine-tune paketini ishga tushirishi mumkin.

## 6. So'z vaqtlari, VAD va spikerlarni ajratish

Karaoke subtitr va so'z chegarasida aniq kesish uchun har bir so'z boshlanish/tugash vaqtiga ega bo'lishi shart. WhisperX buni wav2vec2 alignment bilan qiladi, lekin har til uchun alohida model kerak va o'zbek tili standart ro'yxatda yo'q — bunday holda WhisperX xato beradi va modelni qo'lda ko'rsatishni so'raydi ([misol](https://github.com/mahmoudashraf97/whisper-diarization/issues/21)).

**So'z vaqtlari — uch yo'l, ustuvorlik tartibida**

1. **CTC forced alignment** (asosiy): tayyor transkript o'zbekcha CTC akustik modelga `torchaudio.functional.forced_align` orqali tekislanadi. Nomzod — Omnilingual CTC (Apache-2.0); o'zbek tili qo'llanishi va aniqligi R0'da tekshiriladi. Meta MMS forced aligner 1 130 tilni qo'llaydi, lekin litsenziyasi CC-BY-NC-4.0 (notijorat) ([manba](https://huggingface.co/chordai/mms-fa-aligner-coreml)) — tijorat versiyada ishlatilmaydi.
2. **TDT davomiyliklari**: Parakeet asosidagi ASR tanlansa, model har token uchun davomiylik beradi — alohida aligner kerak bo'lmaydi.
3. **Whisper DTW** (zaxira): whisper.cpp va faster-whisper ichidagi so'z vaqtlari; aniqligi pastroq, faqat birinchi ikki yo'l ishlamasa.

Talab: qo'lda belgilangan 30 daqiqalik to'plamda so'z chegarasi xatosining medianasi ≤ 80 ms, 95-persentil ≤ 250 ms (maqsad, R0'da tasdiqlanadi). Muharrirda foydalanuvchi matnni tuzatsa, faqat o'sha gap qayta tekislanadi (soniyalar ichida).

**VAD.** Silero VAD (MIT) nutq bo'laklarini ajratadi. Undan uch joyda foydalaniladi: ASR'ga faqat nutq yuborish, klip chegarasini pauzaga "yopishtirish", sukutlarni qisqartirish (jump-cut) funksiyasi.

**Diarizatsiya (kim qachon gapirdi).** pyannote `speaker-diarization-community-1` (pyannote.audio 4.0): CC-BY-4.0 litsenziya, internet ulanmasdan lokal papkadan yuklanadi, ASR vaqtlari bilan oson moslashtirish uchun "exclusive" (bir vaqtda bitta spiker) rejimiga ega ([model kartasi](https://huggingface.co/pyannote-community/speaker-diarization-community-1)). Apple uchun Core ML portlari mavjud ([misol](https://huggingface.co/aufklarer/Pyannote-Community-1-CoreML)). Litsenziya muallifni ko'rsatishni talab qiladi — "Haqida" oynasida ko'rsatiladi.

- Spikerlar soni: avtomatik yoki foydalanuvchi ko'rsatadi (podkast uchun odatda 2–3).
- Foydalanuvchi spikerlarga bir marta ism beradi ("Boshlovchi", "Mehmon"); ovoz embeddinglari shou darajasida lokal saqlanadi va keyingi epizodlarda avtomatik taniladi.
- Ustma-ust gapirish belgilanadi: reframe split-layoutga o'tadi, subtitr asosiy spikerni ko'rsatadi.

## 7. Highlight topish: lokal LLM + signal xususiyatlari

Asosiy qaror: LLM vaqt belgilarini emas, **gap ID raqamlarini** qaytaradi. Kichik lokal modellar soniyalarni o'ylab topishga moyil; gap ID'lari esa tekshirib bo'ladigan diapazon va kod ularni aniq vaqtga o'giradi.

**Ikki bosqichli tanlov**

1. **Nomzod yig'ish (map):** transkript gaplarga bo'linadi va har bir gap `{id, spiker, matn, davomiylik, signal_bayroqlari}` ko'rinishida uzatiladi. Uzun video ustma-ust oynalarga bo'linadi (oyna uzunligi va ustma-ustlik R0'da tanlanadi); har oynadan LLM 0–N nomzod qaytaradi.
2. **Saralash (reduce):** bir-birini qoplagan nomzodlar birlashtiriladi; eng yaxshi 2×N nomzod LLM tomonidan juftlab solishtiriladi; yakuniy ball hisoblanadi.

**Majburiy JSON sxema** (llama.cpp grammatika/JSON-schema rejimida — model sxemadan chiqib ketolmaydi):

```json
{
  "start_id": 412, "end_id": 431, "hook_id": 415,
  "turi": "maslahat | hikoya | kulgili | bahsli_fikr | fakt | savol_javob",
  "mustaqil": true,
  "ballar": {"hook": 8, "mustaqillik": 9, "hissiyot": 6, "foyda": 9, "aniqlik": 8},
  "sarlavha": "...", "sabab": "...", "izoh_matni": "...", "heshteglar": ["..."]
}
```

**Yakuniy "Lahza bali" (0–100)** = LLM mezonlari + signal ballari − jarimalar. Vaznlar konfiguratsiyada saqlanadi va foydalanuvchi qaroridan (qabul/rad) o'rganadi.

- Signal ballari: ovoz balandligi cho'qqilari, kulgi/olqish, nutq tezligining o'zgarishi, spiker almashinuvi zichligi, savol bilan boshlanish.
- Jarimalar: gap o'rtasida boshlanish; "va", "lekin", "shuning uchun" bilan boshlanish; kontekstsiz olmosh ("u", "bu narsa") bilan boshlanish; davomiylik maqsaddan tashqarida; boshqa klip bilan katta ustma-ustlik.
- Bu ball virusli bo'lishni bashorat qilmaydi — u klip sifatini baholaydi. Foydalanuvchi keyinchalik real natijalarni (ko'rishlar soni) qo'lda kiritsa, vaznlar shunga moslashadi (Pro).

**Chegaralarni tekislash (kod, LLM emas)**

- Boshlanish: gap boshiga, oldidagi pauza ≥ 150 ms bo'lgan nuqtaga; oldiga 100–200 ms "nafas" qo'shiladi.
- Tugash: gap oxiri + 300 ms; so'z hech qachon kesilmaydi.
- Davomiylik foydalanuvchi diapazoniga sig'masa, eng yaqin gap chegarasigacha qisqartiriladi yoki uzaytiriladi.
- Ixtiyoriy "hook oldinga": eng kuchli jumla (hook\_id) klip boshiga 2–4 s qo'yiladi, keyin asosiy qism davom etadi (Pro).

**Foydalanuvchi boshqaruvi:** kliplar soni, davomiylik oralig'i (standart 30–60 s, 15–180 s oralig'ida), ustuvor mavzu yoki kalit so'zlar ("faqat ta'lim haqidagi qismlar"), istisno mavzular, "shunga o'xshash yana top" tugmasi.

**LLM nomzodlari va tanlov**

| Model | Litsenziya | Hajmlar | Nima uchun nomzod |
| --- | --- | --- | --- |
| [Qwen3.5](https://rits.shanghai.nyu.edu/ai/qwen-3-5-small-models-9b-parameters-that-beat-120b) | Apache-2.0 | 0.8B, 2B, 4B, 9B (+ 27B, 35B-A3B) | Kichik o'lchamda kuchli; Qwen3 oilasi "Northern Uzbek" tilini rasman qo'llaydi ([manba](https://dev.to/projedefteri/qwen3-hybrid-thinking-and-superior-performance-in-119-languages-proje-defteri-56d2)) |
| [Gemma 4](https://www.bernama.com/en/news.php?id=2540584) | Apache-2.0 | E2B, E4B, 26B A4B, 31B | 140+ tilda o'qitilgan; 128K–256K kontekst; llama.cpp birinchi kundan qo'llaydi |
| [NeuronAI-2B](https://huggingface.co/NeuronUz/NeuronAI-2B) | ANIQLANSIN | 2B (Qwen3.5-2B asosida) | O'zbekcha davomli pretrain va o'zbekcha tokenizator |
| [alloma-8B-Instruct](https://featherless.ai/models/uzlm/alloma-8B-Instruct) | ANIQLANSIN | 8B (Llama) | O'zbekcha tokenizator: so'zga \~1.7 token (asl Llama'da \~3.5) |

Tanlov "UzHighlight-Eval" to'plamida: 10 epizod, har birida 3 nafar SMM mutaxassisi mustaqil belgilagan highlightlar. O'lchovlar: precision@5, mutaxassis highlightlarini topish ulushi (IoU ≥ 0.5), JSON yaroqliligi, o'zbekcha sarlavha sifati (inson bahosi 1–5), tezlik (token/s). Ko'rsatma tili (o'zbekcha yoki inglizcha prompt) ham shu to'plamda solishtiriladi.

**Runtime:** llama.cpp (`llama-server`, MIT) dastur ichida yetkaziladi — foydalanuvchi Ollama yoki boshqa narsani alohida o'rnatmaydi. Mac'da Metal, Windows'da CUDA yoki Vulkan; GGUF Q4\_K\_M kvantlash.

**Zaxira: LLM'siz rejim (Lite).** LLM standart to'plamda dastur tomonidan avtomatik yuklanadi (13-bo'lim). Agar kompyuterga mos LLM bo'lmasa yoki u hali yuklanmagan bo'lsa, dastur to'xtamaydi: nomzodlar signal ballari, gap chegaralari va jarima qoidalari bo'yicha tanlanadi, sarlavha sifatida klipning birinchi kuchli jumlasi taklif qilinadi. LLM paydo bo'lgach, mavjud epizodlar uchun "Highlight'larni qayta topish" tugmasi chiqadi. Ikki rejim sifati UzHighlight-Eval'da alohida o'lchanadi.

## 8. Smart reframe: 16:9 dan 9:16 ga

Reframe "kim gapiryapti" degan savolga ikki manbadan javob oladi — ovoz (diarizatsiya) va tasvir (lab harakati) — va kamerani silliq, odam montajchidek boshqaradi.

**Komponentlar**

- **Yuz aniqlash:** MediaPipe BlazeFace (Apache-2.0), ONNX va Core ML portlari mavjud. Muqobillar chiqarildi: SCRFD vaznlari notijorat, YOLOv8-Face AGPL-3.0, YuNet o'qitish ma'lumotlari (WIDER FACE) shartlari noaniq ([taqqoslash](https://huggingface.co/Heliosoph/mediapipe-face-onnx)).
- **Treking:** IoU + Kalman filtr (SORT uslubi) — yuz izlari. Yuzni tanib olish (biometrik embedding) ishlatilmaydi.
- **Aktiv spikerni aniqlash (ASD):** LR-ASD (MIT, IJCV 2025); ONNX ko'rinishida audio va vizual qismlar jami \~3 MB ([DeepTalk-ASD](https://pypi.org/project/deeptalk-asd/)). Yakuniy qaror = ASD bali + diarizatsiya bo'yicha shu daqiqadagi spiker + lab nuqtalari harakati.
- **Sahna kesimlari:** PySceneDetect; kesimda kamera yo'li qayta boshlanadi.

**Kamera yo'li qoidalari**

- O'lik zona: yuz kadr markazidagi chegara ichida bo'lsa, kamera qimirlamaydi.
- Silliqlash: tezlik va tezlanishga chegara qo'yilgan optimal yo'l (AutoFlip uslubi) yoki One-Euro filtr — R0'da ikkalasi solishtiriladi.
- Spiker almashganda va ular kadrda uzoq tursa — pan emas, **keskin kesim**.
- Yuz kadrning yuqori uchdan biriga joylashtiriladi — pastki qism subtitr va Instagram interfeysi uchun bo'sh qoladi.

**Layoutlar (segment bo'yicha avtomatik tanlanadi, qo'lda o'zgartiriladi)**

| Layout | Qachon | Ko'rinishi |
| --- | --- | --- |
| Focus | Bitta spiker gapiryapti | 9:16 crop, yuz kuzatiladi |
| Split | Ikki spiker tez almashib gapiryapti yoki ustma-ust | Yuqori va pastki yarim: har biri 1080×960 |
| Fit + xira fon | Yuz topilmadi, ekran ko'rsatuvi, keng plan | To'liq kadr markazda, orqasida xiralashtirilgan nusxa |
| Qo'lda | Foydalanuvchi tanlaydi | Kalit kadrlar bilan crop holati |

Layout tez-tez almashib ketmasligi uchun minimal ushlab turish vaqti bor (qiymati R0'da tanlanadi).

**Sifat ogohlantirishi.** 1920×1080 manbadan 9:16 crop eni 607 px bo'ladi (1080 × 9/16), u 1080 px ga \~1.78 marta kattalashtiriladi va yumshoqlashadi. Dastur manba o'lchamini ko'rsatadi va 4K yozishni tavsiya qiladi; 1080p manbada yuqori sifatli masshtablash filtri ishlatiladi.

**Ikki kamerali yozuv (Pro):** ikki fayl audio kross-korrelyatsiya bilan avtomatik sinxronlanadi; reframe crop o'rniga kerakli kamerani tanlaydi.

## 9. Subtitr va o'zbek imlosi

Subtitr bitta manbadan — ASS (Advanced SubStation Alpha) faylidan — ham muharrir preview'ida, ham yakuniy renderda chiziladi, shuning uchun ekranda ko'ringan narsa eksportda aynan shunday chiqadi.

**Render texnologiyasi**

- Yakuniy render: FFmpeg `ass` filtri (libass, ISC litsenziya; FFmpeg `--enable-libass` bilan yig'iladi).
- Preview: libass'ning WebAssembly porti (masalan, JASSUB) yoki engine tomonidan chizilgan preview kadrlar — R0'da tezlik bo'yicha tanlanadi.
- Karaoke effekti: har bir so'z alohida vaqt bilan; hozir aytilayotgan so'z rangi/masshtabi o'zgaradi; "pop-in" va kalit so'zni ajratish animatsiyalari.
- Qo'shimcha eksport: SRT va VTT (Instagram'ning o'z subtitr funksiyasi yoki boshqa platformalar uchun).

**Maketlash qoidalari**

- Bir ekranda 1–4 so'z yoki 1–2 qator (uslubga bog'liq); qator uzunligi shrift o'lchamidan avtomatik hisoblanadi.
- Bo'linish: avval pauza va tinish belgisida; ism-familiya, son va birlik, "so'z + -chi/-mi" kabi bog'liq juftliklar ajratilmaydi.
- Xavfsiz zona: Meta 9:16 uchun yuqoridan 14%, pastdan 35%, yonlardan 6% joyni interfeys egallashini ko'rsatadi ([manba](https://www.hopperhq.com/blog/instagram-reel-size/)); subtitr shu zonadan tashqarida joylashmaydi, muharrirda zona chiziqlari ko'rsatiladi.
- Tozalash (ixtiyoriy): to'ldiruvchi so'zlar ("ee", "mmm") ro'yxati, so'kinish so'zlarini yashirish — ikkala ro'yxat ham foydalanuvchi tomonidan tahrirlanadi.

**O'zbek imlosi — uch rejim**

| Rejim | Misol | Izoh |
| --- | --- | --- |
| Rasmiy (amaldagi) | oʻzbek, togʻ, maʼno | Oʻ/Gʻ uchun faqat U+02BB (ʻ); U+2018/U+2019 o'zbek lotinida qo'shtirnoq vazifasini bajaradi ([manba](https://en.wikipedia.org/wiki/O%CA%BB)) |
| Oddiy ASCII | o'zbek, tog', ma'no | Ijtimoiy tarmoqlarda keng tarqalgan; har qanday shriftda chiqadi |
| Yangi alifbo | özbek, toğ, şahar, çiroy | Senat 2026-yil 10-sentabrda ma'qulladi: Gʻ→Ğ, Oʻ→Ö, Sh→Ş, Ch→Ç ([gov.uz](https://gov.uz/oz/cirns/news/view/217333)); kuchga kirish sanasi ANIQLANSIN |

- **Kirishni normallashtirish:** ASR va foydalanuvchi kiritgan `'`, `‘`, `’`, `` ` ``, `ʼ` belgilari o yoki g dan keyin bo'lsa ʻ (U+02BB) ga, boshqa joyda tutuq belgisi ʼ (U+02BC) ga keltiriladi. Ichki saqlash har doim rasmiy rejimda.
- **Yangi alifboga o'tkazish:** oʻ→ö, gʻ→ğ, sh→ş, ch→ç; tutuq bilan ajratilgan sʼh (masalan, Isʼhoq) o'zgarmaydi. Qoidalar to'plami qonun rasmiy e'lon qilingach, uning matni bo'yicha tekshiriladi. Qonun loyihasiga ko'ra "ng" alifbodan chiqariladi ([kun.uz](https://kun.uz/news/2026/07/07/ozbekistonda-alifbo-islohoti-boyicha-qonun-qabul-qilindi-4cf07b)).
- **Kirill (v1.1):** lotin→kirill o'girish lug'at bilan (e/э, ц, ё, ю, я kabi bir ma'noli bo'lmagan holatlar uchun).
- **Shriftlar:** dastur bilan faqat OFL/ochiq litsenziyali shriftlar yetkaziladi. Har bir shrift ʻ, ʼ, Ö, Ğ, Ş, Ç va o'zbek kirill harflari (Ў, Қ, Ғ, Ҳ) bo'yicha avtomatik glif testidan o'tadi; o'tmagan shrift ro'yxatda ko'rsatilmaydi.

**Brend shablonlari:** shrift, o'lcham, ranglar, kontur, soya, fon qutisi, joylashuv, animatsiya, harf registri, logotip/suv belgisi joyi — JSON shablon sifatida saqlanadi va fayl orqali almashiladi.

## 10. Render va eksport

Render FFmpeg'ning LGPL yig'masida, operatsion tizim yoki GPU ichidagi apparat enkoderlari bilan bajariladi — bu ham tez, ham litsenziya jihatidan xavfsiz yo'l.

**FFmpeg yig'masi**

- `--enable-gpl` **yo'q**, libx264/libx265 **yo'q**: ular GPL va FFmpeg'ni GPL'ga o'tkazadi ([FFmpeg LICENSE](https://code.ffmpeg.org/Traneptora/FFmpeg/src/commit/c8b50ff8f9b3c102765e8b8902db82e9ebf7332c/LICENSE.md)).
- Kerakli kutubxonalar: libass, freetype, harfbuzz, fribidi (subtitr); apparat dekoder/enkoderlar.
- NVENC: FFmpeg'ning eski LICENSE matnida LGPL yig'mada ham `--enable-nonfree` talab qilingan, keyingi tahrirda nvenc bu bo'limdan olib tashlangan ([eski matn](https://ffmpeg.org/doxygen/3.4/md_LICENSE.html)). Ishlatiladigan FFmpeg versiyasi bo'yicha yurist xulosasi — ANIQLANSIN.

**Enkoderlar (ustuvorlik tartibida)**

| Platforma | 1-tanlov | Zaxira |
| --- | --- | --- |
| macOS | `h264_videotoolbox` | `hevc_videotoolbox` (ixtiyoriy HEVC) |
| Windows + NVIDIA | `h264_nvenc` | `h264_mf` |
| Windows + AMD | `h264_amf` | `h264_mf` |
| Windows + Intel | `h264_qsv` | `h264_mf` |
| Windows, GPU yo'q | `h264_mf` (Media Foundation) | ANIQLANSIN (dasturiy H.264 litsenziyasi) |

**Standart eksport profili**

- 1080×1920, 9:16, H.264 High, MP4 (`+faststart`), AAC-LC 48 kHz stereo.
- Kadr tezligi: manbaniki saqlanadi (25/30/60).
- Bitreyt: 8–15 Mbps oralig'ida sozlanadi ([manba](https://argil.ai/blog/instagram-reel-size-e350f)).
- Ovoz: EBU R128 `loudnorm`, maqsad LUFS sozlanadi; standart qiymat jamoa tomonidan tasdiqlanadi (Instagram rasmiy talab e'lon qilmagan — ANIQLANSIN).
- Boshida/oxirida 100–200 ms audio fade (klik tovushiga qarshi).

**Instagram cheklovlari — relizdan oldin qayta tekshiriladi.** 1080×1920 va 9:16 barcha manbalarda bir xil. Maksimal davomiylik bo'yicha manbalar farq qiladi: 90 s ([Moda](https://moda.app/resources/sizes/instagram-reel)), 3 daqiqa ([Argil](https://argil.ai/blog/instagram-reel-size-e350f)); fayl ≤ 4 GB, minimal o'lcham 720×1280 ([Moda](https://moda.app/resources/sizes/instagram-reel)). Shu sababli limitlar kodga qattiq yozilmaydi, konfiguratsiya faylida saqlanadi.

**Render grafi (bitta klip):** aniq trim → kalit kadrlar bo'yicha crop/masshtab → layout (split uchun vstack, xira fon uchun gblur + overlay) → ASS subtitr → logotip → audio trim + loudnorm + fade → enkoder. Render proksidan emas, asl fayldan; mumkin bo'lsa apparat dekodlash.

**Eksport navbati:** parallel vazifalar soni sozlanadi; fayl nomi shabloni `{shou}_{epizod}_{nn}_{sarlavha}.mp4`; har klip yonida: muqova kadri (1080×1920 JPG), `.srt`, `caption.txt` (sarlavha, matn, heshteglar). Eksport tugagach papka ochiladi.

## 11. UI/UX: ekranlar va oqim

Asosiy oqim to'rt qadam: **import → avtomatik tahlil → kliplarni ko'rib chiqish → eksport**. Oddiy foydalanuvchi faqat shu to'rt qadamni ko'radi; chuqur tahrir vositalari kerak bo'lganda ochiladi.

| Ekran | Vazifasi | Asosiy elementlar |
| --- | --- | --- |
| Birinchi ishga tushirish | Sozlash | Interfeys tili; apparat testi va daraja; katalogdan kompyuterga mos to'liq model to'plamini avtomatik yuklab olish; imlo rejimi; birinchi brend shablon |
| Loyihalar | Shou → epizodlar | Drag & drop import; epizod kartalari holati bilan; qidiruv |
| Tahlil | Jarayonni kuzatish | Bosqichlar ro'yxati va foiz; qolgan vaqt; bekor qilish; fon rejimi; tugaganda tizim bildirishnomasi |
| Kliplar galereyasi | Tanlash | Kartalar: muqova, davomiylik, Lahza bali, tur, sarlavha, sabab; saralash/filtr; qabul/rad; "o'xshashini top"; transkriptdan qo'lda klip |
| Klip muharriri | Tahrir | Chapda 9:16 preview (xavfsiz zona chiziqlari bilan); o'ngda tablar: Matn, Kadr, Uslub, Ma'lumot; pastda timeline: to'lqin shakli, so'zlar, spiker lentalari |
| Transkript muharriri | Butun epizod matni | Spiker yorliqlari; past ishonchli so'zlar sariq; qidirish/almashtirish; lug'atga qo'shish |
| Eksport navbati | Render | Navbat, progress, qayta urinish, papkani ochish |
| Sozlamalar | Boshqaruv | Model menejeri, apparat, imlo, papkalar, klaviatura yorliqlari, maxfiylik |

**Matn orqali montaj (v1.0 da).** Transkriptda so'z yoki gapni o'chirish videodan ham o'chiradi (jump-cut); matnni belgilab "Klip yarat" bosilsa, yangi klip paydo bo'ladi. Trim tutqichlari timeline'da so'z chegarasiga yopishadi.

**Klaviatura:** Space — ijro; J/K/L — orqaga/to'xtash/oldinga; I/O — boshlanish/tugash; A/R — klipni qabul/rad; Cmd/Ctrl+E — eksport. Barcha amallar sichqonchasiz bajariladi.

**Interfeys tillari:** o'zbek (lotin), o'zbek (kirill), rus, ingliz. Barcha matnlar i18n fayllarida; sanalar va raqamlar lokal formatda.

**Xatolar foydalanuvchi tilida:** texnik xabar o'rniga "Videoda ovoz yo'lagi topilmadi — boshqa fayl tanlang" kabi aniq harakat; texnik tafsilot "Batafsil" ostida va log faylida.

## 12. Ma'lumot modeli va loyiha formati

Har bir epizod — o'z papkasi (`Epizod.lahza/`), ichida SQLite baza (WAL rejimi) va kesh; umumiy narsalar (shoular, spikerlar, lug'at, shablonlar) alohida kutubxona bazasida. Vaqt hamma joyda butun son millisekundda; matn Unicode NFC, rasmiy imloda.

**Fayl tuzilmasi**

```
Kutubxona/
  library.db              # shoular, spikerlar, lug'at, shablonlar, sozlamalar
  Shou nomi/
    Epizod-12.lahza/
      project.db          # transkript, kliplar, tahrirlar
      cache/              # audio.wav, proxy.mp4, yuz izlari, embeddinglar
      thumbs/
```

**Asosiy jadvallar**

| Jadval | Muhim maydonlar |
| --- | --- |
| media | id, yo'l, xesh, davomiylik\_ms, fps, eni, bo'yi, audio\_kanallar |
| stage\_runs | media\_id, bosqich, versiya, model\_id, parametr\_xesh, holat, natija\_yo'li, xato |
| sentences | id, media\_id, start\_ms, end\_ms, speaker\_id, matn, ishonch |
| words | id, sentence\_id, tartib, matn, start\_ms, end\_ms, ishonch, tahrirlangan, asl\_matn |
| speakers | id, show\_id, yorliq, ko'rinadigan\_ism, ovoz\_embedding |
| clips | id, media\_id, start\_ms, end\_ms, sarlavha, matn, heshteglar, tur, ball, ballar\_json, sabab, holat, manba (ai/qo'lda), llm\_model\_id |
| clip\_cuts | clip\_id, start\_ms, end\_ms — matn orqali o'chirilgan oraliqlar |
| reframe\_keyframes | clip\_id, t\_ms, layout, cx, cy, zoom, manba (avto/qo'lda) |
| style\_templates | id, nom, json |
| exports | id, clip\_id, yo'l, profil\_json, holat, xato |
| feedback | clip\_id, harakat (qabul/rad/tahrir), vaqt, metrikalar\_json |
| lexicon | id, show\_id, atama, variantlar, tur (ism/brend/atama) |
| corrections | id, audio\_bo'lak\_yo'li, oldin, keyin — ASR'ni yaxshilash uchun |

**Qoidalar**

- Klip holatlari: `nomzod → qabul | rad → eksport_qilingan`; rad etilgan klip o'chirilmaydi (o'rganish uchun kerak).
- Qo'lda qilingan tahrir (so'z, kalit kadr, chegara) qayta tahlilda ustiga yozilmaydi.
- Sxema versiyalanadi va avtomatik migratsiya qilinadi; eski versiyadagi loyiha ochilganda zaxira nusxa olinadi.
- Loyihani boshqa kompyuterga ko'chirish: papkani nusxalash yetarli; manba video yo'li topilmasa, dastur uni qayta ko'rsatishni so'raydi.

## 13. O'rnatish, modellar, yangilash va litsenziya

Dastur va modellar alohida yetkaziladi: dastur o'rnatuvchisi kichik qoladi, og'ir modellar "model paketi" sifatida bir marta o'rnatiladi va dastur yangilanganda qayta yuklanmaydi.

**O'rnatuvchilar va imzolash**

- **macOS:** `.dmg`, Developer ID bilan imzolangan, notarizatsiyadan o'tgan va tiket **staple qilingan**. Staple qilinmagan dastur birinchi ishga tushganda Apple serveriga murojaat qiladi va internetsiz Mac'da bloklanadi ([manba](https://nektony.com/how-to/remove-non-notarized-apps-mac)) — oflayn dastur uchun bu majburiy. macOS Sequoia'dan boshlab imzolanmagan dasturni Control-click bilan ochish imkoniyati olib tashlangan ([manba](https://eclecticlight.co/2024/08/10/gatekeeper-and-notarization-in-sequoia/)).
- Hardened runtime: ichki barcha bajariladigan fayllar (Python engine, ffmpeg, llama-server, whisper.cpp) ham alohida imzolanadi.
- **Windows:** NSIS yoki MSI, kod imzolash sertifikati bilan; imzosiz o'rnatuvchi har yuklashda SmartScreen ogohlantirishini chiqaradi ([manba](https://r-pkg.thecoatlessprofessor.com/shinyelectron/articles/code-signing.html)).
- Tauri sidecar fayllari `nom-<target-triple>` ko'rinishida bo'lishi shart ([Tauri hujjati](https://v2.tauri.app/develop/sidecar/)); NSIS qayta o'rnatishda eski sidecar qolib ketish holati qayd etilgan ([issue #15134](https://github.com/tauri-apps/tauri/issues/15134)) — CI har buildda sidecar'ni toza yig'adi va xeshini tekshiradi.

**Model katalogi — dastur kerakli modellarni o'zi yuklab oladi**

Dastur modellarsiz o'rnatiladi. Birinchi ishga tushishda apparat testi o'tkaziladi (RAM, VRAM, GPU turi, protsessor, bo'sh disk). So'ng dastur katalogdan shu kompyuterga mos **to'liq to'plamni** — ASR, alignment, diarizatsiya, ko'rish modellari va LLM — o'zi tanlaydi va yuklab oladi. Foydalanuvchi faqat "Boshlash" tugmasini bosadi; xohlasa, to'plamni ko'rib, o'zgartirishi mumkin.

- **Katalog** — dastur ichidagi, Ed25519 bilan imzolangan JSON. Har bir model uchun: id, vazifa (asr / llm / align / diarization / vision), versiya, hajm, sha256, minimal RAM va VRAM, platformalar, backend (whisper.cpp, faster-whisper, llama.cpp, ONNX Runtime), litsenziya, yuklash manzillari (asosiy + zaxira) va R0 baholash natijalari.
- **Avtomatik tanlov qoidasi:** har bir vazifa uchun apparat darajasiga (2-bo'lim) sig'adigan va R0'da eng yaxshi natija bergan model tanlanadi. Belgilar: "Tavsiya etiladi"; "Ishlaydi, lekin sekin"; "Mos emas" — sabab bilan bloklanadi (masalan, "8 GB VRAM kerak, sizda 4 GB").
- **Majburiylik:** ASR to'plamisiz dastur ishlamaydi, shuning uchun u yuklab bo'linmaguncha import tugmasi faol bo'lmaydi. LLM ham standart to'plamga kiradi; faqat kompyuterga hech bir katalog LLM'i sig'masa yoki yuklash muvaffaqiyatsiz bo'lsa, highlight vaqtincha Lite rejimda ishlaydi (7-bo'lim).
- **Yuklash:** fonda, ketma-ket (avval ASR — dastur tezroq ishga tayyor bo'lsin), to'xtasa davom etadi, oldindan bo'sh disk tekshiriladi, tugagach sha256 va 30 soniyalik o'z-o'zini sinash.
- **Yangilanish:** yangi katalog dastur yangilanishi bilan yoki imzolangan fayl orqali keladi. Katalogda yaxshiroq model chiqsa, dastur taklif qiladi, foydalanuvchi rozi bo'lsa yuklaydi; eski model yangisi sinovdan o'tguncha o'chirilmaydi.
- **Internetsiz kompyuter:** boshqa kompyuterda yuklangan to'plam "Eksport" tugmasi bilan `.lzpack` paketiga (modellar + manifest + imzo) o'raladi va USB orqali import qilinadi.
- **Model menejeri:** o'rnatilganlar, har vazifa uchun standart model, yangilash, o'chirish, sinov. Modellar foydalanuvchi ma'lumotlari papkasida, `Models/<vazifa>/` ichida saqlanadi.

**Katalogdan tashqari modellar (ilg'or sozlama, standart holatda yashirin)**

- URL yoki fayldan qo'shish va `Models/<vazifa>/` papkasini avtomatik skanerlash.
- Faqat format sarlavhasi tekshirilgan model fayllari qabul qilinadi (LLM uchun GGUF); bajariladigan fayl, skript yoki arxiv ichidagi kod hech qachon ishga tushirilmaydi.
- Qo'shilgan model namunaviy transkriptda sinaladi; natijasidan qat'i nazar "Katalogdan tashqari — sifat kafolatlanmaydi" belgisi qo'yiladi.

**Yangilash.** Onlayn avto-yangilash ixtiyoriy va standart holatda o'chiq. Oflayn yo'l: imzolangan yangilanish fayli dasturga tashlanadi.

**Litsenziyalash (tijorat versiya bo'lsa).** Server talab qilmaydigan oflayn kalit: Ed25519 bilan imzolangan JSON (egasi, tarif, muddat, qurilmalar soni). Tariflar, sinov muddati va narx — ANIQLANSIN.

**Mualliflik ko'rsatmalari.** "Haqida → Litsenziyalar" oynasida barcha komponentlar ro'yxati. CC-BY modellar (masalan, pyannote community-1) muallifni ko'rsatishni talab qiladi. O'z fine-tune'ingizda ISSAI/TUIT Uzbek Speech Corpus ishlatilsa, tijorat mahsulotiga ISSAI belgilagan maxsus bayonot qo'shilishi shart ([ISSAI](https://issai.nu.edu.kz/uzbek-asr/)).

## 14. Nofunksional talablar

Har bir talab tekshirish usuli bilan birga yozilgan; raqamli maqsadlar R0 benchmarkidan keyin tasdiqlanadi yoki tuzatiladi.

| ID | Talab | Qanday tekshiriladi |
| --- | --- | --- |
| NFR-01 Oflayn | Ishlash vaqtida birorta tarmoq so'rovi yo'q (yangilash va yuklab olish o'chiq holatda) | CI'da tarmoqsiz muhitda to'liq pipeline + chiquvchi ulanishlar monitori |
| NFR-02 Maxfiylik | Telemetriya yo'q; loglarda transkript matni yo'q; diagnostika paketi faqat foydalanuvchi bosganda yaratiladi | Kod ko'rigi + log tarkibi testi |
| NFR-03 Tezlik | Daraja bo'yicha maqsadlar 2-bo'limda | Har relizda benchmark to'plami, natija jadvali |
| NFR-04 Javob berish | UI hech qachon qotmaydi; klip tanlanganda preview ≤ 1 s da boshlanadi (maqsad) | Avtomatik UI testlari, profilirovka |
| NFR-05 Ishonchlilik | Har o'zgarish avtosaqlanadi; qulashdan keyin ish oxirgi bosqichdan davom etadi | Jarayonni majburan to'xtatish testlari |
| NFR-06 Uzun video | 4 soatgacha video xotira to'lmasdan qayta ishlanadi (maqsad) | Oqimli (streaming) ishlov; 4 soatlik test fayli |
| NFR-07 Resurslar | Model yuklashdan oldin bo'sh RAM/VRAM tekshiriladi, yetmasa kichikroq modelga o'tiladi; "jim rejim" (kam oqim, kam qizish) | Cheklangan xotirali VM testlari |
| NFR-08 Xavfsizlik | Engine faqat 127.0.0.1 da, tasodifiy port va sessiya tokeni bilan; FFmpeg shell'siz argumentlar massivi bilan chaqiriladi; model paketlari imzosi tekshiriladi | Xavfsizlik ko'rigi, fuzz testlari |
| NFR-09 LLM chiqishi | LLM natijasi faqat ma'lumot: JSON sxemadan o'tmagan javob rad etiladi; transkript ichidagi "buyruq" hech qanday amal bajartirmaydi | Prompt-injection test to'plami |
| NFR-10 Lokalizatsiya | 4 interfeys tili, barcha matn i18n fayllarida | Tarjima to'liqligi testi |
| NFR-11 Qulaylik | To'liq klaviatura bilan boshqarish, kontrast, masshtablash | Qo'lda accessibility tekshiruvi |
| NFR-12 Diagnostika | Aylanadigan log fayllar; "Diagnostika paketi" tugmasi (versiyalar, apparat, oxirgi xatolar) | Qo'lda tekshiruv |

## 15. Sifat o'lchovlari, testlar va qabul mezonlari

Sifat o'z "oltin" test to'plamlarimizda o'lchanadi; birinchi o'lchov (baseline) R0'da olinadi, keyingi har reliz undan yomonlashmasligi shart.

**Oltin to'plamlar**

| To'plam | Tarkibi | Nimani o'lchaydi |
| --- | --- | --- |
| UzPodcast-Eval | 3–5 soat audio + qo'lda transkript | WER, CER, ismlar aniqligi, sukutdagi "o'ylab topish" |
| Align-Eval | 30 daqiqa, so'z chegaralari qo'lda belgilangan | So'z vaqti xatosi (median, p95) |
| UzHighlight-Eval | 10 epizod, 3 mutaxassis belgilagan highlightlar | precision@5, topish ulushi, chegara xatosi, sarlavha bahosi |
| Reframe-Eval | 10 video, har soniyada aktiv spiker belgilangan | Aktiv spiker kadrda bo'lgan vaqt ulushi, keraksiz kamera harakatlari soni |
| Render-Eval | Uslub va layout kombinatsiyalari | Kadr snapshotlari (SSIM), ASS fayl snapshotlari |

**Mutlaq talablar (har relizda 100%)**

- Hech bir klip so'z o'rtasida boshlanmaydi yoki tugamaydi.
- LLM javoblarining 100% JSON sxemadan o'tadi (grammatika bilan cheklangan dekodlash).
- Oflayn rejimda 0 ta tarmoq so'rovi.
- Eksport qilingan fayl 1080×1920, ovoz va video sinxron (ffprobe tekshiruvi).
- Imlo: transliteratsiya jadval testlari 100% o'tadi.

**Nisbiy talablar:** WER, highlight precision@5 va aktiv spiker ulushi oldingi relizdan yomonlashsa, reliz to'xtatiladi (chegara qiymatlari baseline'dan keyin belgilanadi — ANIQLANSIN).

**Test darajalari**

1. Unit: normalizator, transliteratsiya (jadvalli testlar), chegara tekislash, kamera yo'li, ASS generatori.
2. Integratsiya: 5 daqiqalik fixture video bo'yicha to'liq pipeline.
3. E2E UI: Tauri WebDriver orqali asosiy oqim (import → klip → eksport).
4. Platforma matritsasi: macOS arm64, Windows x64 (CPU), Windows + NVIDIA (o'z runner).
5. Toza o'rnatish: internetsiz yangi VM'da o'rnatuvchi + model paketi.
6. Chidamlilik: 4 soatlik video, ketma-ket 20 epizod.
7. Inson bahosi: oyiga bir marta SMM paneli eski va yangi versiya kliplarini ko'r-ko'rona solishtiradi.

## 16. Litsenziyalar va huquqiy jihatlar

Tijorat sotuvga chiqishdan oldin quyidagi ro'yxat yurist tomonidan tekshiriladi; jadval texnik tanlov uchun yo'naltiruvchi, yuridik xulosa emas.

| Komponent | Litsenziya | Holat |
| --- | --- | --- |
| FFmpeg (GPL qismlarisiz) | LGPL 2.1+ | Ruxsat; dinamik bog'lanadi, manba va qayta bog'lash imkoni ta'minlanadi |
| libx264 / libx265 | GPL | **Chiqarilgan** |
| whisper.cpp | MIT ([manba](https://hexdocs.pm/whisper_cpp/whisper_cpp.epub)) | Ruxsat |
| pyannote community-1 | CC-BY-4.0 | Ruxsat, muallif ko'rsatiladi |
| MediaPipe BlazeFace | Apache-2.0 | Ruxsat |
| LR-ASD | MIT | Ruxsat |
| Qwen3.5, Gemma 4 | Apache-2.0 | Ruxsat |
| BuzzASR/uzbek | MIT | Ruxsat |
| rubaiSTT v2 | Apache-2.0 | Ruxsat |
| piyola-v2 | CC-BY-4.0 | Ruxsat, muallif ko'rsatiladi |
| Omnilingual ASR | Apache-2.0 (model), CC-BY-4.0 (korpus) | Ruxsat |
| Meta MMS forced aligner | CC-BY-NC-4.0 | **Chiqarilgan** (notijorat) |
| SCRFD vaznlari | Notijorat | **Chiqarilgan** |
| YOLOv8-Face | AGPL-3.0 | **Chiqarilgan** |
| ISSAI USC korpusi | CC-BY-4.0 + majburiy bayonot | Fine-tune'da ishlatilsa bayonot qo'shiladi |
| Abduqayum, NeuronAI, alloma modellari | ANIQLANSIN | Litsenziya aniqlanmaguncha faqat R0 sinovida |

**H.264 patentlari.** FFmpeg dekoderlari LGPL bo'lsa ham, tijorat ishlatishda patent to'lovlari masalasi chiqishi mumkinligi qayd etilgan ([OpenMPF](https://openmpfgithubio.readthedocs.io/en/latest/docs/License-And-Distribution/)). Shu sababli kodlashda operatsion tizim va GPU enkoderlariga ustuvorlik beriladi; yakuniy xulosa — yuristda.

**Kontent huquqi.** Foydalanuvchi faqat o'ziga tegishli yoki ruxsat olingan videolarni qayta ishlashi foydalanish shartlarida yoziladi. Ixtiyoriy YouTube yuklab olish plagini (v1.0 dan keyin) alohida ogohlantirish bilan keladi.

## 17. Yo'l xaritasi: 0 dan Pro gacha

Ish R0 tadqiqotidan boshlanadi: model tanlovi o'z ma'lumotlaringizda o'lchanmaguncha UI yozish boshlanmaydi. Muddatlar jamoa tarkibiga bog'liq taxmin (19-bo'lim).

&#91;embedded content: yo'l xaritasi · 6 bosqich, 5 darvoza\]

Har darvoza o'lchanadigan natija bilan yopiladi; o'tmasa, bosqich uzaytiriladi, keyingisi boshlanmaydi.

**Jamoa rollari (minimal):** ML muhandisi (ASR, alignment, LLM baholash), Python backend (engine, pipeline, FFmpeg), frontend (Tauri + React), QA / reliz muhandisi (CI, imzolash, o'rnatuvchilar), SMM ekspert (highlight baholash, uslublar) va qisman lingvist (transkripsiya yo'riqnomasi, imlo qoidalari).

**Gemini TZ'sidagi "keyingi qadamlar"ga javob:** Python pipeline (M1), face tracking va 9:16 crop (M3), animatsiyali o'zbekcha subtitr (M1 da oddiy, M3 da to'liq).

## 18. Xavflar va ularni kamaytirish

Eng katta xavf — spontan, shevali podkast nutqida ASR xatosi: hatto eng yaxshi ochiq o'zbekcha model ham shunday audioda \~26% WER ko'rsatgan ([piyola-v2](https://huggingface.co/idrock/piyola-v2)). Shuning uchun R0 aynan shu xavfni birinchi o'lchaydi.

| Xavf | Ta'siri | Kamaytirish choralari |
| --- | --- | --- |
| Spontan va shevali nutqda ASR xatosi yuqori | Noto'g'ri subtitr, yomon highlight | R0 model tanlovi; lug'at; tuzatishlardan o'rganish; o'z fine-tune (Pro) |
| Rus/ingliz so'zlari aralash nutq | So'zlar buzilib yoziladi | Lug'at, LLM post-tuzatish, alohida o'lchov |
| Kichik lokal LLM o'zbekchani yomon tushunadi | Highlightlar sayoz | Gibrid ball (signal + LLM), Pro darajada katta model, inson tasdig'i, vaznlarni o'rganish |
| O'zbekcha tijoriy alignment modeli yo'q | So'z vaqtlari noaniq | TDT davomiyliklari yoki Whisper DTW zaxirasi; USC (CC-BY) ustida o'z CTC modelini o'qitish |
| Windows apparat xilma-xilligi | Ishga tushmaslik, sekinlik | Bir necha backend, avto-aniqlash, CPU zaxirasi, drayver tekshiruvi |
| PyInstaller + PyTorch hajmi va mo'rtligi | Katta o'rnatuvchi, xatolar | Iloji boricha native runtime (llama.cpp, whisper.cpp, ONNX Runtime); PyTorch faqat kerakli joyda; ONNX eksport R0'da sinaladi |
| Alifbo islohoti sanasi noma'lum | Subtitr eskirib qoladi | Uch imlo rejimi, qoidalar konfiguratsiyada |
| Litsenziya noaniqliklari (NVENC, H.264, ba'zi modellar) | Huquqiy xavf | 1.0 dan oldin yurist ko'rigi; noaniq modellar mahsulotga kirmaydi |
| Instagram talablari o'zgarishi | Noto'g'ri eksport | Limitlar konfiguratsiya faylida, har relizda tekshiruv |
| Noutbukda qizish va batareya | Foydalanuvchi noroziligi | "Jim rejim", tahlilni rejalashtirish, quvvat ulanganini tekshirish |

## 19. Ochiq savollar — ANIQLANSIN

Quyidagilar javobsiz qolsa, tegishli qism R0 tugashi bilan to'xtab qoladi.

- [ ] Mahsulot tijorat uchun sotiladimi yoki faqat ichki foydalanishgami? (litsenziya tanloviga ta'sir qiladi)
- [ ] Yakuniy mahsulot nomi ("Lahza Studio" — ishchi nom)
- [ ] Tariflar, sinov muddati va narx
- [ ] Test to'plami uchun qaysi podkastlar olinadi va qo'lda transkripsiyani kim bajaradi
- [ ] Highlight'larni belgilaydigan 3 nafar SMM mutaxassisi
- [ ] Alifbo qonunining kuchga kirish sanasi va yangi imlo qoidalarining rasmiy matni
- [ ] FFmpeg yig'masi, NVENC va H.264 patentlari bo'yicha yurist xulosasi
- [ ] Litsenziyasi aniq bo'lmagan modellar: Abduqayum/whisper-uzbek-medium-callcenter, NeuronAI-2B, alloma-8B
- [ ] Omnilingual ASR o'zbek tilini qo'llashi va uning WER natijasi
- [ ] Standart ovoz balandligi (LUFS) maqsadi
- [ ] Reliz paytidagi Instagram davomiylik limiti
- [ ] Model paketlari hajmi va disk talabi
- [ ] Dastur bilan yetkaziladigan shriftlar ro'yxati
- [ ] Jamoa tarkibi va byudjet (17-bo'limdagi bosqich muddatlariga ta'sir qiladi)

* [ ] Katalog modellari qayerda joylashtiriladi (Hugging Face, o'z serveri yoki CDN) va zaxira manzil

## Manbalar

**ASR va alignment**

- [BuzzASR/uzbek — model kartasi](https://huggingface.co/BuzzASR/uzbek)
- [idrock/piyola-v2 — model kartasi](https://huggingface.co/idrock/piyola-v2)
- [Abduqayum/whisper-uzbek-medium-callcenter](https://friendli.ai/models/Abduqayum/whisper-uzbek-medium-callcenter)
- [islomov/rubaistt\_v2\_medium](https://huggingface.co/islomov/rubaistt_v2_medium/blob/main/README.md)
- [BlueRaccoon/whisper-small-uz (Whisper FLEURS natijasi)](https://huggingface.co/BlueRaccoon/whisper-small-uz/blob/main/README.md)
- [Meta Omnilingual ASR — e'lon](https://ai.meta.com/blog/omnilingual-asr-advancing-automatic-speech-recognition/) va [model kartasi](https://huggingface.co/ziywang50/omniASR-LLM-300M)
- [ISSAI Uzbek Speech Corpus](https://issai.nu.edu.kz/uzbek-asr/)
- [MMS forced aligner (Core ML, litsenziya izohi)](https://huggingface.co/chordai/mms-fa-aligner-coreml)
- [WhisperX: tilga alignment modeli yo'qligi xatosi](https://github.com/mahmoudashraf97/whisper-diarization/issues/21)
- [CTranslate2 va Apple Silicon](https://pyvideotrans.com/blog/ctranslate2-whisper)
- [whisper.cpp — apparat qo'llovi](https://www.sourcepulse.org/projects/2125572)

**Diarizatsiya va ko'rish**

- [pyannote speaker-diarization-community-1](https://huggingface.co/pyannote-community/speaker-diarization-community-1)
- [Pyannote Community-1 Core ML](https://huggingface.co/aufklarer/Pyannote-Community-1-CoreML)
- [MediaPipe Face ONNX — litsenziya taqqoslashi](https://huggingface.co/Heliosoph/mediapipe-face-onnx)
- [DeepTalk-ASD (LR-ASD ONNX)](https://pypi.org/project/deeptalk-asd/) va [LR-ASD](https://github.com/airmeet/LR-ASD)

**LLM**

- [Qwen3.5 kichik modellari](https://rits.shanghai.nyu.edu/ai/qwen-3-5-small-models-9b-parameters-that-beat-120b) va [xotira talablari](https://artificialanalysis.ai/articles/qwen3-5-small-models)
- [Qwen3 tillar ro'yxati](https://dev.to/projedefteri/qwen3-hybrid-thinking-and-superior-performance-in-119-languages-proje-defteri-56d2)
- [Gemma 4 e'loni](https://www.bernama.com/en/news.php?id=2540584) va [ekotizim qo'llovi](https://aiworld.eu/story/google-has-released-gemma-4)
- [NeuronAI-2B](https://huggingface.co/NeuronUz/NeuronAI-2B), [alloma-8B-Instruct](https://featherless.ai/models/uzlm/alloma-8B-Instruct), [UzLiB benchmark](https://github.com/tahrirchi/uzlib)

**Video, platforma, huquq**

- [FFmpeg LICENSE](https://code.ffmpeg.org/Traneptora/FFmpeg/src/commit/c8b50ff8f9b3c102765e8b8902db82e9ebf7332c/LICENSE.md) va [eski tahriri](https://ffmpeg.org/doxygen/3.4/md_LICENSE.html)
- [OpenMPF — H.264 va litsenziyalar](https://openmpfgithubio.readthedocs.io/en/latest/docs/License-And-Distribution/)
- [Tauri 2 sidecar](https://v2.tauri.app/develop/sidecar/) va [NSIS sidecar muammosi](https://github.com/tauri-apps/tauri/issues/15134)
- [Notarizatsiya va staple](https://nektony.com/how-to/remove-non-notarized-apps-mac), [Sequoia Gatekeeper](https://eclecticlight.co/2024/08/10/gatekeeper-and-notarization-in-sequoia/), [kod imzolash](https://r-pkg.thecoatlessprofessor.com/shinyelectron/articles/code-signing.html)
- Instagram Reels: [Hopper (Meta xavfsiz zonasi)](https://www.hopperhq.com/blog/instagram-reel-size/), [Argil](https://argil.ai/blog/instagram-reel-size-e350f), [Moda](https://moda.app/resources/sizes/instagram-reel)

**O'zbek imlosi**

- [Oʻ — Unicode U+02BB](https://en.wikipedia.org/wiki/O%CA%BB)
- [gov.uz — Senat yangi alifboni ma'qulladi (2026-09-10)](https://gov.uz/oz/cirns/news/view/217333)
- [kun.uz — qonun loyihasi, "ng" chiqarilishi](https://kun.uz/news/2026/07/07/ozbekistonda-alifbo-islohoti-boyicha-qonun-qabul-qilindi-4cf07b)
- [spot.uz — Senat muhokamasi](https://www.spot.uz/oz/2026/09/10/uzbek-alphabet/)
