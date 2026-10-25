# Lokal AI montaj yordamchisi

Bu [yo'l xaritasi](14-agentic-roadmap.md)ning birinchi amaliy bosqichi. Mavjud
lokal buyruq parseri yoniga haqiqiy GGUF model bilan rejalash qo'shilgan. U hali
erkin topshiriqlarning barchasini bajaradigan yoki xatosiz o'zbekcha tushunadigan
muharrir emas. Model taklifi qo'llashdan oldin tekshirilishi kerak.

## O'rnatish va ishlatish

Apple Silicon lokal yig'masida:

```sh
make setup-local-llm  # rasmiy model (~2.50 GB) va runtime (~12 MB) yuklanadi
make build-local
```

Mavjud LLM standarti almashtirilmaydi. Boshqa model tanlangan bo'lsa, model
menejerida yangi modelni standart qiling yoki quyidagidan foydalaning:

```sh
engine/.venv/bin/python scripts/setup_local_llm.py --model --consent --set-default
```

Skript parametrsiz faqat rejani chiqaradi; tarmoq amali yo'q. Model bo'lmasa
AI rejimida aniq sabab ko'rinadi; lokal buyruqlar rejimi ishlashda davom etadi.
Runtime o'rnatish skripti hozir macOS arm64 uchun, Windows o'rnatish sinovi qolgan.

Montaj oynasidagi rejimdan **AI yordamchi**ni tanlang, prompt yozing va reja
tuzing. O'zgarishlar ro'yxatini tekshiring, so'ng qo'llang. Draft yangilanadi;
avtomatik saqlash bajarilmaydi. Saqlash va eksport odatdagi boshqaruvlar orqali.
Natijani bitta undo bilan qaytarish mumkin.

## Hozirgi amallar

* `set_format`: Reels, Shorts yoki keng YouTube preseti; davomiylik kesilmaydi,
  foydalanuvchi tanlagan audio sample rate saqlanadi.
* `set_captions`: mavjud ASR captionlarini ko'rsatish/yashirish, mutlaq shrift o'lchami.
* `add_caption`: aniq boshlanish/tugash bilan oddiy matn qatlami.
* `set_color`: warm/cool/film/vivid/bw presetlari.
* `freeze_clip`: klipning chiqish vaqtiga nisbatan 100–5000 ms stop-kadr;
  ovoz va timeline davomiyligi uzaymaydi.

Agent split, ripple/delete-silence, fayl/skript, model yoki skill o'rnatish,
internetdan media qidirish amallarini bajarmaydi. Qo'llanmaydigan talablar
`unresolved` sabab bilan qaytadi. Takroriy yoki zid sozlamali rejalar rad etiladi.

## Ishlash tartibi

`GET /v1/editing-agent/status` modelni xotiraga yuklamasdan mavjudligini tekshiradi.
`POST /v1/editing-agent:plan` body: `{prompt,timeline,selected_video_id}`.
Javob: `{plan,changes,warnings,model_id}`. `plan` sxemasi `lahza.edit-plan/1`.
`POST /v1/editing-agent:preview` body: `{timeline,plan,selected_video_id}`;
javob yangi timeline va o'zgarishlar ro'yxati. Bu endpoint bazaga yozmaydi.

Modelga yuboriladigan tavsifda fayl yo'llari yoki video yo'q: format, caption
holati, klip ID/chiqish vaqtlari va chegaralangan transkript bor. Butun tavsif
uchun hajm chegarasi qo'llanadi. Inferens faqat loopback'dagi `llama-server`ga
so'rov qiladi; model yuklash faqat foydalanuvchi boshlaydigan setup amali.

Har tool uchun alohida qat'iy argument sxemasi, butun son ms, media chegaralari,
plugin parametrlari va profil tekshiruvlari ishlaydi. Reja engine'da hisoblangan
timeline+tanlov xeshiga bog'lanadi. Eskirgan reja — 409; noto'g'ri reja — 422;
model/runtime yo'q — 503. Executor nusxada ishlaydi, qisman qo'llamaydi.

## Sinov modeli va kelib chiqishi

* Rasmiy [Qwen3-4B-GGUF](https://huggingface.co/Qwen/Qwen3-4B-GGUF), Apache-2.0.
* Revision: `bc640142c66e1fdd12af0bd68f40445458f3869b`.
* `Qwen3-4B-Q4_K_M.gguf`, 2,497,280,256 bytes.
* SHA256: `7485fe6f11af29433bc51cab58009521f205840f5b4ae3a32fa7f92e8534fdf5`.
* [llama.cpp b11669](https://github.com/ggml-org/llama.cpp/releases/tag/b11669), MIT,
  macOS arm64 arxivi xeshi skriptda mahkamlangan.

Model vaznlari `.app`ga kirmaydi, foydalanuvchining Models papkasida turadi.
Xesh va pinlangan LICENSE/README tekshiriladi; registry'da baribir `custom`,
`verified=false`: bu ishlab chiqarish katalogida tasdiqlangan model emas.

## Aniqlik chegarasi

Haqiqiy sinovdagi dastlabki model taklifi `iliqroq` o'rniga `vivid` tanlagan va
caption amallarini takrorlagan. Tool tavsiflari va misollar ko'rinadigan promptga
qo'shildi, takroriy sozlamalar executor'da bloklandi. Alohida sinovda inglizcha
`Enable captions` to'g'ri, o'zbekcha `Subtitrlarni yoq` esa noto'g'ri `false`
qaytargan. `yoq`/`yo'q` farqi promptda izohlangan, ammo bu umumiy til aniqligi
kafolati emas. JSON sxemasidan o'tishi foydalanuvchi maqsadini to'g'ri tushunganini
isbotlamaydi. Reja va preview'ni ko'rish hamda qo'lda tuzatish zarur.

Qayta sinovda erkin o'zbekcha promptdan ("Reels formati, subtitr 80 piksel, iliqroq
rang, 7-soniyadan 1 soniya stop-kadr, boshqasini o'zgartirma") to'rtala buyruq
to'g'ri chiqdi: `set_format`, `set_captions`, `set_color: warm`, `freeze_clip`.
Reja 7.03 soniyada tuzildi; undan 12 soniyali 1080×1920 MP4/SRT eksport qilindi
(`build/local-llm/real-report.json`). Bitta muvaffaqiyatli prompt umumiy aniqlik
o'lchovi emas.

## Highlight uchun hali yaroqsiz

Xuddi shu Qwen3-4B Q4_K_M bilan LLM highlight sinovi (`highlight/llm.py`,
haqiqiy transkriptning 21 gapi, 2 nomzod so'raldi) 91.68 soniyada sxemaga mos,
lekin **bo'sh** javob qaytardi: `{"nomzodlar": []}`, yaroqli nomzod — 0
(`build/local-llm/highlight-report.json`). Shuning uchun highlight standart holatda
Lite rejimda qoladi; bu model montaj buyruqlari uchun ishlatiladi, highlight
uchun emas. Kattaroq model, boshqa prompt yoki o'zbekcha prompt R0 baholashida
(UzHighlight-Eval) solishtiriladi.

Testlar va haqiqiy inferens artefaktlari `build/local-llm/`da saqlanadi; ular
Git'ga kirmaydi. Bu holat uzluksiz playback, ASR fine-tuning yoki to'liq desktop
click-through sinovi bajarilganini bildirmaydi.
