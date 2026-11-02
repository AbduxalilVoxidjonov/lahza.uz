# AI montaj yo'l xaritasi — 2026-10-24

Foydalanuvchi yuborgan texnik reja Lahza'ning mavjud Tauri/React + Python engine
arxitekturasiga moslashtirildi. Quyidagi bosqichlar to'liq mahsulot tayyor degani emas.
Mavjud ASR, renderer, model menejeri va shablon tizimi qaytadan yozilmaydi.

## 1. Erkin promptdan tekshiriladigan montaj rejasiga

Birinchi amaliy bosqich: lokal GGUF model → qat'iy JSON reja → deterministik
executor → tahrirlanadigan draft → preview → qo'llash → undo.

* `editing_agent/model.py`: har amalning alohida, majburiy argumentlari bor;
  noma'lum maydonlar va vaqt o'rniga float/bool qiymatlar rad etiladi.
* `editing_agent/planner.py`: mavjud lokal `llama-server`dan foydalanadi.
  Kontekstga video yoki fayl yo'llari emas, chegaralangan timeline tavsifi kiradi.
* `editing_agent/executor.py`: asl timeline'ni o'zgartirmaydi. Barcha amallar
  nusxada tekshiriladi; bittasi yaroqsiz bo'lsa qisman qo'llanmaydi.
* Rejaning `base_revision` qiymati engine'da timeline va tanlovdan hosil qilinadi.
  Model xeshni hisoblamaydi. Draft yoki tanlov o'zgarsa eski reja 409 bilan rad etiladi.
* Birinchi amallar: profil/format, caption yoqish va o'lchami, vaqtli caption,
  tekshirilgan rang preseti, klip ichidagi stop-kadr. Split, ripple/delete-silence
  agentga hali berilmaydi; ularning vaqt va FX semantikasi keyingi bosqich.
* Interfeysda lokal buyruq parseri va AI yordamchi alohida. Model bo'lmasa
  parserdan foydalanish mumkin; parser javobi LLM inferensi deb ko'rsatilmaydi.

Qabul mezonlari: autentifikatsiya, buzilgan JSON/amalni rad etish, atomiklik,
eskirgan javobdan himoya, bitta undo, haqiqiy lokal model va haqiqiy render sinovi.
Model bajara olmaydigan talablar `unresolved` sifatida qaytadi.

## 2. Uzluksiz playback

Hozir montaj preview'i kadrli. Keyingi alohida ish — timeline'dan keshli preview
media yaratish va ovoz bilan ijro; seek, pause, trim va effektlardan keyingi kesh
yangilanishini tekshirish. Audio clock, ring buffer va hardware decoding bilan
native playback keyingi o'lchanadigan bosqich bo'ladi. 1–2 soniya bufer yoki
ProRes/DNxHR formati benchmark qilmasdan majburiy tanlov deb belgilanmaydi.

## 3. O'zbekcha ASR va alignment

Mavjud NavAI/faster-whisper, CTC aligner va lug'at mexanizmlari saqlanadi.
Avval qo'lda tekshirilgan, turli sheva/shovqinni qamragan etalon to'plam bilan
WER va so'z vaqti xatosi o'lchanadi. Fine-tuning uchun dataset, foydalanish huquqi,
train/validation ajratilishi va GPU budjeti kerak. WhisperX alignment vositalari
ASR modelini fine-tune qilishning o'rnini bosmaydi. "Xatosiz montaj" kafolati berilmaydi.

## 4. Chidamlilik va muharrir

Ketma-ket 30/60/120 daqiqali sinovlar, ko'p kesimli render, xotira maksimumi,
bekor qilish va loyihani qayta ochish tekshiriladi. So'ng 4K/60 stress to'plami.
Interfeys uchun caption tahriri, hotkey, split/ripple va eskirgan reja bo'yicha
E2E sinovlar kerak. Hozirgi unit testlari to'liq desktop click-through o'rnini bosmaydi.

## 5. Tarqatish va kengaytmalar

Windows NSIS va macOS CI mavjud, lekin amaliy installer sinovi, tegishli
sertifikatlar va notarizatsiya hali reliz darvozasi. macOS 12+/Universal Binary
faqat barcha native kutubxonalar va modellar shu targetlarda tekshirilgach va'da qilinadi.
Hozirgi lokal yig'ma Apple Silicon macOS 27+.

OFX — mustaqil host implementatsiyasi, moslik va litsenziya sinovini talab qiladigan
keyingi yo'nalish. "OFX qo'shilsa barcha professional plagin ishlaydi" deb olinmaydi.
Hozirgi LUT, FFmpeg effektlari va data-only skill'lar ishlashda davom etadi.

## Namunaviy matndan tuzatilgan joylar

* Downloader namunasida resume SHA256 faqat yangi bo'laklardan hisoblangan va
  server Range'ni e'tiborsiz qoldirishi hisobga olinmagan. Mavjud downloader ishlatiladi.
* Umumiy `args` JSON sxemasi o'rniga tool bo'yicha qat'iy union; refusal ham
  shu shartnomada ifodalanadi. GBNFning o'zi semantik validatsiyani bajarmaydi.
* Python engine chiqarib tashlanmaydi; `llama-server` alohida lokal jarayon.
* Modelning til sifati va RAM sarfi jadvaldagi taxmin bilan tasdiqlanmaydi.
  Sinov modeli rasmiy Qwen3-4B Q4_K_M; tanlov va o'rnatish [AI yordamchi](local-ai-editing.md)da.
