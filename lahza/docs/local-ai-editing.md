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

## Windows CPU (o'lchov 2026-10-28)

Mashina: Intel Core i7-13620H (6P+4E yadro, 16 oqim), 16 GB RAM, Intel UHD iGPU
(NVIDIA yo'q), Windows 11. **Batareyada**, "Balanced" quvvat sxemasi — tarmoqqa
ulanganda raqamlar yaxshiroq bo'lishi mumkin, bu tekshirilmadi. Runtime: ilova bilan
keladigan llama.cpp b11669 CPU yig'masi (`llama-server.exe`, Clang 20, ggml-cpu
variantlari DLL sifatida). Model: yuqoridagi Qwen3-4B Q4_K_M.

Flaglar engine bilan bir xil (`core/llama_server.py`): `-c 16384 -ngl 999 --parallel 1`
(montaj rejasi); highlight — `-c 16384 --parallel 2` (2×8192 slot), `--reasoning-budget`
yo'q, so'rovda `enable_thinking=false`, `max_tokens=1536`, DRY 0.8. `-t` berilmaydi:
llama.cpp 10 oqim tanlaydi. Sinov uchun `-t 6` (faqat P-yadrolar) sekinroq chiqdi:
50 / 5.4 tok/s.

| O'lchov | Natija |
|---|---|
| Sovuq yuklash (`/health` 200 gacha), 3 marta | 7.4 / 6.9 / 5.4 s, median 6.9 s |
| RSS, `-c 16384` (bo'sh / cho'qqi) | ~6.3–6.4 GB / 7.0 GB |
| Prompt qayta ishlash, 3091 token, 3 marta | 66.7 / 67.9 / 66.2 tok/s, median 66.7 |
| Generatsiya, 3k kontekstdan keyin 256 token | 6.7 / 6.5 / 6.4 tok/s, median 6.5 |
| Qisqa kontekst (319 token prompt, 128 token) | 80.6 / 10.0 tok/s, 1 marta |
| AI montaj rejasi, `planner.plan` to'liq (server ishga tushishi bilan), 7 so'rov | 36.0–43.0 s, median 37.0 s |
| — shundan: server yuklash / prompt (~1890 token, ~73 tok/s) / javob (27–74 token, ~8 tok/s) | 4.3–5.7 / ~26 / 3–9 s |
| LLM highlight, 30.6 daq transkript (136 gap, 5 oyna) | 1023 s (~17 daq): yuklash 7 s + map 1014 s |

Montaj rejasi (3 klipli 24 s timeline, captionlar yoqilgan, 72 px): beshala o'zbekcha
promptda reja to'g'ri chiqdi. "Ranglarni iliqroq qil" (3 marta) → `set_color: warm`;
"Subtitrlarni kattaroq qil va 2-klipda 1 soniya stop-kadr qo'y" → `set_captions 80 px`
+ `freeze_clip clip2, 1000 ms` (stop-kadr joyi promptda yo'q, model 1000 ms ni o'zi
tanlagan); "Reels formatiga o'tkaz" → `instagram_reels`; "Subtitrlarni o'chir" →
`enabled: false`; "Videoni oq-qora qil va 3-soniyada 2 soniya 'Salom' yozuvi" →
`set_color: bw` + `add_caption 3000–5000 ms`. Besh prompt umumiy aniqlik o'lchovi emas.

LLM highlight bu safar bo'sh emas: 20 nomzod, yakuniy 10 klip. Lekin sifat past:
ballar har oynada mexanik 9/8/7/6 kamayadi, `turi` faqat `kulgili`/`savol_javob`
(mavzuga mos bo'lmagan "kulgili"), sarlavhalar takrorlanadi ("Yil boshida ishga
kirish" ×4), nomzodlar bir-biriga yopishib ketadi (127–130, 128–131), ikkita yakuniy
klip vaqt bo'yicha qisman ustma-ust (415–461 va 446–498 s). Har oyna 1009–1310 chiqish
tokeni yozadi; 2 slot parallel ishlaganda bir slot tezligi 2.8–5.8 tok/s ga tushadi.

Xulosa:

* Montaj rejasi — interaktiv chegarada: ~37 s kutish, 90 s client timeout'iga zaxira bor.
  Vaqtning ~70% i ~1.9k tokenli system prompt; har so'rovda server qayta yuklanadi
  (~5 s). Prompt keshli doimiy server yoki qisqaroq prompt eng katta yutuq beradi.
  Sekinroq CPU'da 90 s chegarasi xavfli bo'lishi mumkin (o'lchanmadi).
* Issiq server o'lchovi (shu kompyuter, rozetkada, 5 buyruq x 2): birinchi so'rov **~33 s**
  (yuklash + 1889 token), keyingilari **13–19 s** (1276 token keshdan, ~620 token kontekst +
  so'rov qayta hisoblanadi); 10/10 reja to'g'ri. llama-server RSS cho'qqisi 5.8 GB.
  Kontekst 16k → 12k (eng yomon holat ~10k token): 16k da issiq server 16 GB'li noutbukda
  RAM yetmay qolardi. Sinab rad etilganlar: q8_0 KV + flash attention (0.8 GB tejaydi, lekin
  CPU'da prompt 1.5x sekin); "context, request" tartibi (issiq so'rov 5–7 s, lekin
  "subtitr + 2-klipda stop-kadr" buyrug'ida `freeze_clip` har safar tushib qoldi, 8/10).
* Montaj rejasi issiq serverdan
  foydalanadi (`core/llama_server.py` `WarmLlamaServer`): birinchi so'rovda ishga tushadi,
  oxirgi so'rovdan `LAHZA_LLM_IDLE_S` (standart 300 s, `0` — o'chiq) keyin to'xtaydi,
  model fayli o'zgarsa yoki jarayon o'lsa qayta ishga tushadi, engine to'xtashida
  (lifespan, majburiy chiqish) yopiladi; Windows'da Job Object orqali engine bilan birga
  o'ladi. So'rovda `cache_prompt: true`, system prompt + misollar har doim bir xil prefiks
  (nonce yo'q), shuning uchun ikkinchi so'rovdan faqat kontekst va so'rov hisoblanadi.
  Bo'sh turgan issiq server highlight `LlamaServer` so'rasa darhol bo'shaydi; `--cache-ram 256`.
* LLM highlight bu CPU'da amaliy emas: 30 daq video uchun ~17 daq (≈ 10 daq video uchun
  ~5.5 daq, Mac'dagi 43 s ga qarshi), sifat ham Lite'dan yaxshiroqligi isbotlanmagan.
  Windows CPU'da Lite standarti to'g'ri.
* O'lchanmadi: tarmoq quvvatida, iGPU (Vulkan/SYCL) bilan, boshqa kvantlash/kontekst
  o'lchamlarida. Skriptlar va xom JSON'lar repoga kirmagan (sessiya scratch papkasi).

Testlar va haqiqiy inferens artefaktlari `build/local-llm/`da saqlanadi; ular
Git'ga kirmaydi. Bu holat uzluksiz playback, ASR fine-tuning yoki to'liq desktop
click-through sinovi bajarilganini bildirmaydi.
