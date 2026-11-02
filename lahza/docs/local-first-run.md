# Desktop: birinchi ochish va tekshiruv

Foydalanuvchi to‘liq `.app` paketini ochadi. Python, pip, Node, Cargo yoki Homebrew
foydalanuvchiga kerak emas. Ular faqat dasturni manbadan yig‘uvchi dasturchiga kerak.
FFmpeg (libass bilan), FFprobe, llama-server va native kutubxonalar ilova ichida;
ASR/VAD Python inference kutubxonalari frozen engine ichida bo‘ladi.

Birinchi ishga tushishda UI `GET /v1/setup` orqali lokal tayyorlikni tekshiradi va
`POST /v1/setup:start` (`{"consent":true}`) bilan kerakli modellarni o‘rnatadi.
GET hech narsa yuklamaydi. Holat: `ready`, `components`, `job`; har komponentda
`id`, `ready`, `required`, `download_bytes`, `detail` bor. Jarayon standart
`GET /v1/jobs/{id}` orqali kuzatiladi. Takroriy start faol ishni takrorlamaydi;
tayyor modellar tekshiriladi va qayta yuklanmaydi.

Taxminiy birinchi yuklama (decimal MB/GB):

| Komponent | Yuklama | Vazifa |
| --- | ---: | --- |
| NavAI Uzbek Whisper base, CTranslate2 | 149 MB atrofida | Nutqni matnga aylantirish |
| Silero VAD v5.1.2 | 2.33 MB | Nutq oralig‘ini topish |
| Qwen3 4B Q4_K_M | 2,497,280,256 bayt, 2.50 GB | Matnli montaj ko‘rsatmalarini tushunish |

Jami taxminan 2.65 GB, model metadata va litsenziyalari bilan biroz ko‘proq.
Diskda ilova va eksportlardan tashqari kamida 4 GB bo‘sh joy qoldiring. Yuklash
uchun internet kerak; tayyor modellar bilan tahrir, transkripsiya va eksport lokal
ishlaydi. Model fayllari foydalanuvchi profilida saqlanadi, `.app` ichiga yozilmaydi:
macOS `~/Library/Application Support/Lahza Studio/Models`, Windows
`%LOCALAPPDATA%/Lahza Studio/Models`.

Xatoda UI qayta urinishni taklif qiladi; tugagan fayllar qayta tekshiriladi,
qisman yuklangan fayllarni davom ettirish downloader imkoniyatlariga bog‘liq.
Standart `POST /v1/jobs/{id}:cancel` yuklashni bekor qiladi; keyingi urinish
sog‘lom tugagan modellarni qayta ishlatadi. Ilova yopilib qolsa eski ish tayyor
hisoblanmaydi: qayta urinish kerakligi ko‘rsatiladi. Internet bo‘lmasa yuklash
xatosidan keyin ulanishni tiklab qayta urining yoki sozlashni keyinroq davom ettiring.
Runtime yetishmasa model yuklash uni tuzatmaydi: to‘liq desktop paketini qayta
olish kerak. Ilova paketida yetishmayotgan runtime endi release buildni to‘xtatadi;
yetishmayotgan inference backend esa sidecar buildni to‘xtatadi.

## Dasturchi uchun takrorlash

Apple Silicon lokal yig‘ma: `docs/local-desktop.md` dagi ad-hoc imzolash jarayoni.
Bu lokal FFmpeg kutubxonalari sabab macOS 27 talab qiladi. macOS 14 va Windows
to‘liq native paketlari shu kompyuterda tekshirilmagan. Ad-hoc imzo notarizatsiya
emas; ommaviy tarqatish uchun release imzolash jarayoni alohida bajariladi.

```sh
cargo check --manifest-path app/src-tauri/Cargo.toml
LAHZA_TEST_RUNTIME="$PWD/app/src-tauri/resources/bin" \
  engine/.venv/bin/python -m pytest engine/tests/test_desktop_packaging.py
engine/.venv/bin/python scripts/smoke_desktop.py \
  --video build/local-smoke/source/nauuJZeQb0I-60-210.mp4 \
  --out build/first-run-verification/new-smoke
```

Smoke yangi, izolyatsiyalangan profil yaratadi; tanlangan mavjud model fayllarini
shu profilning `Models` papkasiga hardlink qiladi (boshqa diskda nusxalaydi).
Registry yo‘llari ham yangi boshqariladigan papkani ko‘rsatadi: planner tashqi
model yo‘llarini rad etadi. Asl registry o‘zgarmaydi. Yangi profil
nomini bering; mavjud dalillar papkasi ustiga yozilmaydi. `--setup-vad` ASR va LLM
sog‘lom bo‘lib, faqat VAD yetishmagandagina download boshlaydi. Bu 2.5 GB modelni
qayta yuklamasdan haqiqiy downloader/API yo‘lini tekshirish uchun.
`--binary .../Contents/MacOS/lahza-engine --resources .../Contents/Resources`
yangi paketning frozen API yo‘lini tekshiradi.
`--raw` epizod importini chetlab, beginner oqimidagi `kind=file` manbani
`captions=true` bilan yuboradi; caption so‘zlari, epizodlar soni nol bo‘lishi,
MP4 audio/video va bo‘sh bo‘lmagan SRTni tekshiradi.
`--offline` tayyor setupni talab qiladi va upstream HTTP/HTTPS so‘rovlarini
ishlamaydigan lokal proxyga yo‘naltiradi; localhost API ishlashda davom etadi.
Bu operatsion tizim firewalli bilan to‘liq tarmoq uzilishi sinovi emas.

## Amalda tekshirilganlar

2026-10-25, Apple Silicon/macOS lokal muhit:

- `cargo check` o‘tdi.
- Packaging testlari frozen sidecar, katalog va bundled FFmpeg bilan: 16/16 o‘tdi;
  yakuniy raw-fix paket logi `build/first-run-verification/packaging-final-raw.log`.
  Dastlab katalog endpointi 500 qaytardi: test PATHi macOSning
  `/usr/sbin/sysctl` buyrug‘ini yashirgan edi. Standart system PATH
  (`/usr/bin:/bin:/usr/sbin:/sbin`) bilan qayta sinov o‘tdi; Homebrew/Python yo‘q.
- FFmpeg sinovi system-only PATH bilan, Homebrew dyliblarini yuklamasdan ASS chizdi.
- Izolyatsiyalangan source API: loyiha yaratish → video import → real ASR →
  epizoddan montaj → 1080×1920 H.264/AAC MP4 va 3 ta vaqtli SRT cue. Xato ogohlantirishi yo‘q.
- Eksport kadri ko‘zdan kechirildi: subtitrlar videoda ko‘rinadi.
- Dalillar `build/first-run-verification/desktop-source-import-smoke/` ichida.
- Haqiqiy `/v1/setup:start` bilan faqat VAD yuklandi (2,327,524 bayt ONNX va
  litsenziya); keyingi GET barcha komponentlar uchun `ready=true` qaytardi.
  Takroriy POST yangi download o‘rniga ayni tugagan jobni qaytardi. Ichki model
  hardlinklari bilan takrorlangan dalillar
  `build/first-run-verification/setup-managed-source/report.json` ichida.
- Tayyor profilda upstream HTTP/HTTPS proxy bloklangan holda setup start
  `installed=[]`, `ready=true` qaytardi; import/ASR/montaj va MP4/SRT eksport o‘tdi.
  A/V davomiylik farqi 0.067 soniya. Dalillar
  `build/first-run-verification/desktop-offline-source/report.json` ichida.
- Yakuniy raw-fix `.app` qayta yig‘ildi (198.00 MiB), ad-hoc imzolandi va
  `codesign --verify --deep --strict --verbose=2` o‘tdi. 268 ta build manbasi
  xeshlari o‘zgarmaganligi tekshirildi. Build logi `tauri-final-raw-build.log`;
  to‘liq binary SHA256 va source snapshot xeshlari `package-final-status.json`da.
- Raw-fixdan oldingi paket ichidagi frozen engine: tayyor setup, haqiqiy ASR, Qwen
  o‘zbekcha promptidan 80 px caption rejasi, preview, saqlash va H.264/AAC MP4/SRT
  eksport ishladi. Upstream HTTP/HTTPS proxy bloklangan edi. Dalillar
  `build/first-run-verification/desktop-frozen-offline-ai/report.json` ichida;
  subtitr ko‘rinishi `desktop-frozen-preview.jpg` da tekshirildi.
- Frozen engine orqali haqiqiy VAD yuklash va takroriy start ham o‘tdi:
  `build/first-run-verification/desktop-frozen-vad/report.json`.
- Raw-fixdan oldingi, bir xil frontendli paket live desktop tekshiruvida ochildi, native macOS fayl
  dialogida video tanlandi va format bosqichiga avtomatik o‘tildi. Live browser
  tekshiruvida o‘zbekcha AI reja → ko‘rib chiqish → qo‘llash → saqlash → eksport o‘tdi.
  Yakuniy raw-fix paket GUI’sini qayta ochish Mac qulflangani sabab tekshirilmadi.
  Yakuniy paketning engine/API/render yo‘li quyidagi frozen smoke bilan tekshirildi.
- Yakuniy paketda to‘g‘ridan-to‘g‘ri `kind=file`, `captions=true`, epizod importsiz
  smoke o‘tdi: 0 epizod, 15 ta caption so‘zi, 3 ta SRT cue, 1080×1920 H.264/AAC
  MP4, A/V farqi 0.067 soniya. Upstream HTTP/HTTPS proxy bloklangan edi.
  Dalillar `build/first-run-verification/raw-frozen-final/report.json`, ko‘zdan
  kechirilgan kadr `raw-frozen-final-preview.jpg`. Eksport warnings ro‘yxati bo‘sh.
- Live birinchi ochish: VAD yetishmagan izolyatsiyalangan profilga kirish bilan
  tugmasiz download boshlandi; 2.3 MB va progress ko‘rindi. 63%da Stop bosilgach
  journal `cancelled` bo‘ldi va avtomatik takrorlash to‘xtadi. Retry bilan yakunda
  `done`, `ready=true` bo‘ldi. Profil: `ui-auto-vad-data`; screenshot:
  `build/first-run-verification/automatic-setup-progress.png`.

Qolgan diagnostik cheklov: frozen ASR+AI smoke engine tugatilganda
`multiprocessing/resource_tracker.py` 1 ta semaphore shutdown vaqtida tozalanganini
ogohlantirdi. Jarayon exit 0, MP4/SRT va barcha packaging testlari muvaffaqiyatli;
bu warning alohida lifecycle kuzatuvi sifatida saqlangan (`desktop-frozen-offline-ai/engine.log`).

Oddiy `kind=file` uchun dastlab aniqlangan subtitr bo‘shligi tuzatildi:
o‘rnatilgan ASR raw videoni lokal transkripsiya qiladi; alohida epizod importi
kerak emas. ASR matn sifati bu smoke bilan baholanmagan va tanilgan matnda
xatolar bo‘lishi mumkin. macOS va Windowsning barcha versiyalarida sinov o‘tkazilmagan.
