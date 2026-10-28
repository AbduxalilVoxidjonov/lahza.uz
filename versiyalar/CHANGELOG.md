# O'zgarishlar tarixi

Eng yangisi tepada. Keyingi reliz o'zgarishlari `## [Kelgusi]` bo'limiga yoziladi —
`make release-local V=x.y.z` ularni versiya sarlavhasiga o'tkazadi.

## [Kelgusi]

- **Tuzatish — Windows desktop: engine ishga tushmasdi.** `--watch-stdin` (Tauri doim beradi) Windows'da sinxron stdin pipe'ni bloklab o'qirdi va meros handle'li bola jarayonlar (ffmpeg, subprocess) CRT ishga tushishida osilib qolardi; endi `PeekNamedPipe` bilan so'raladi (`core/lifecycle.py`).
- **Yangi — Windows MSVC relizi adminsiz:** xwin (MSVC CRT/SDK) + rust-lld + clang-cl, `+crt-static` - `lahza-studio.exe` VC++ runtime'ga bog'lanmaydi; NSIS per-user o'rnatuvchi WebView2 offline o'rnatuvchisi bilan (`tauri.conf.json`). `scripts/stage_windows_dlls.py` har exe/dll importini tekshiradi va yetishmagan VC++ runtime DLL'larini `resources/bin` ga qo'yadi.
- **Yangi — Windows uchun LGPL FFmpeg 7.1.1:** `scripts/build_runtimes.ps1 -FFmpegOnly` portativ MSYS2 (UCRT64) bilan dav1d 1.5.4 (statik), libass, Media Foundation/AMF/VPL; GPL DLL darvozasi, litsenziya matnlari `bin/licenses/local-render/`. 455 MB GPL sinov yig'masi o'rniga 37.6 MB.
- **Litsenziyalar:** Windows komponentlari (VC++ runtime, cuDNN, Intel/LLVM OpenMP, MinGW runtime) va so'rov bilan yuklanadigan yt-dlp/yt-dlp-ejs (meriyah, astring)/Deno uchun alohida bo'limlar; GPL tekshiruvi GCC runtime istisnosini to'g'ri taniydi.

- **O'zgarish — YouTube importi standart yoqilgan** (egasi qarori, ADR-0010); har importda rozilik saqlanadi.
- **Yangi — komponent yangilanishi ilova relizisiz:** Sozlamalarda "Yangilanishni tekshirish" — PyPI/GitHub'dagi oxirgi yt-dlp, yt-dlp-ejs (yt-dlp talab qilgan versiya) va Deno 2.x, e'lon qilingan sha256 bilan; YouTube yuklash yiqilsa import kartasida shu tugmaga havola.
- **Yangi — YouTube komponentlari ilovaning o'zidan:** Sozlamalar (va import kartasi)dagi tugma yt-dlp, yt-dlp-ejs va Deno'ni bir marta yuklaydi — mahkamlangan versiya, sha256 tekshiruvi, atomik joylash (`media/youtube_components.py`, `/v1/settings/youtube-import:install-components`). Desktop ilovada YouTube importi endi `make setup-youtube`siz ishlaydi; yt-dlp sidecar'ga kirmaydi (ADR-0010).
- **Tuzatish — Windows:** Claude montaj `claude.cmd` bilan ishlaydi (`--system-prompt-file`); sidecar yangi VC++ runtime'ni o'zi olib keladi (eski `msvcp140` onnxruntime/ctranslate2'ni qulatardi); llama-server/whisper-cli statik CRT bilan yig'iladi.

## [0.2.4] — 2026-10-26

- **Yangi — Claude montaj (standart o'chiq):** foydalanuvchi kompyuteridagi Claude Code/Desktop topiladi; montaj panelida Lokal/Claude reja tanlovi, Lahza MCP serveri (`lahza-engine mcp`, 13 tool) Claude'ga bir tugma bilan ulanadi. Claude'ga faqat timeline tavsifi va transkript matni boradi (`claude_bridge/`, `/v1/claude/*`, docs/15-claude-montaj.md).
- **Yaxshilash — LLM highlight tezligi:** 10 daqiqalik videoda 498 s → 43 s (M3-PERF-2).
- **Yaxshilash — xotira:** WAV oqimli o'qiladi; 4 soatlik podkastda RSS 2242 → 210 MB (V1-1).
- **Yangi — aktiv spiker:** LR-ASD ONNX backend + diarizatsiya, eksportda kadr gapirayotgan odamga yo'naltiriladi (R0-VIS-2, M3-RF-1).
- **Yangi — mustaqil Lahza Engine servisi:** macOS LaunchAgent / Windows Task Scheduler; Studio va Adobe plaginlari bitta engine'ni discovery orqali topadi (ADB-7).
- **Yangi — shaxsiy lug'at va ball vaznlari:** real natijalardan o'rganadi (PRO-1, PRO-6).
- **Yangi — oflayn litsenziya kaliti:** Ed25519, standart holatda o'chiq (V1-3, ADR-0016).
- **Litsenziya — ASR PyAV'siz:** dekod LGPL FFmpeg orqali, GPL libx264/libx265 li `av` sidecar'dan chiqarildi (ADR-0015).
- **Yaxshilash — import kartasi:** fayl va YouTube havolasi bitta sahifada.
- **Sifat:** chidamlilik testlari, tezlik benchmarki, platforma limitlari (V1-1, M3-PERF-1, V1-6); navbat `shutdown()` dagi poyga holati tuzatildi.

Tafsilotlar: [`0.2.4/NOTES.md`](0.2.4/NOTES.md)

## [0.2.3] — 2026-10-26

- **Yangi — AV1 o'qish:** bundled FFmpeg dav1d 1.5.4 (BSD-2, statik) bilan yig'iladi, LGPL qoidasi saqlanadi (`--disable-gpl`). `codec_check` AV1 ni endi `ffmpeg -decoders` bo'yicha tekshiradi; dekoder bo'lmasa avvalgidek `unsupported_codec` (`scripts/setup_local_render.py`, `third_party/runtimes.toml`, `media/codec_check.py`).
- **Tuzatish — navbat xatolari:** engine yiqilgan vazifalarga barqaror `error_code` beradi (15 ta kod: fayl topilmadi, disk to'la, model yo'q, ffmpeg, tarmoq, bekor qilindi …); navbat paneli va vazifa qatorlari ularni 4 tilda ko'rsatadi, xom matn "Batafsil" ichida (`core/errors.py`, `lib/error-codes.ts`).
- **Tuzatish — siyrak transkript:** ASR oynasi 30 s → 10 s (jim joyda kesiladi); subtitr kartochkasi ko'pi bilan 6 s, so'z vaqtlari bo'lmasa harf soniga proporsional (`asr/base.py`, `subtitle/layout.py`). Siyraklik metrikasi (`transcript_density`) logga yoziladi.
- **Yaxshilash — ASR aniqligi:** VAD padding 30 → 200 ms, min sukunat 100 → 400 ms; `temperature=0`, `beam_size=5`; past ovozli audio kuchaytiriladi; Whisper matnni timestamp'siz dekodlaydi, so'z vaqtlari CTC aligner'dan. FLEURS uz (83 fayl) WER: base 53.1% → 19.8%, small → 15.4%; ASR ~2× tezroq.
- **Yangi — CTC aligner standart:** Omnilingual CTC 300M int8 (Apache-2.0, 328 MB) birinchi ochilishda yuklanadi; pauzalar 63/65, so'z chegarasi median 28–46 ms. Aligner bo'lmasa eski Whisper vaqtlari rejimi avtomatik. Yuklash hajmi ~3 GB. Eski loyihalar bir marta qayta tahlil qilinadi (ASR/align kesh versiyalari).
- **Yangi — Transkripsiya sifati (Tez/Aniq):** Sozlamalar → O'rnatilgan modellar. Tez — base (standart, birinchi ochilishda yuklanadigan yagona ASR); Aniq — small (~2.5× sekin, ~240 MB), hozircha `.lzpack` faylidan o'rnatiladi (internet manzili `LAHZA_ASR_ACCURATE_PACK_URL` sozlanganda). Eski tahlillar majburan qayta hisoblanmaydi (`models/asr_quality.py`, `/v1/asr-quality`).
- **Yangi — ASR benchmark:** `make asr-eval` (FLEURS uz test, CC-BY-4.0; WER/CER/RTF, ablyatsiya bayroqlari) — `eval/YORIQNOMA.md`.

Tafsilotlar: [`0.2.3/NOTES.md`](0.2.3/NOTES.md)

## [0.2.2] — 2026-10-26

- **Tuzatish — YouTube import eksporti:** yt-dlp AV1 formatni tanlardi, bundled LGPL FFmpeg esa AV1'ni dekodlay olmaydi → eksport 69 kodi bilan yiqilardi. Endi avc1 (H.264) → vp9 tartibida tanlanadi; 0.2.1 da yuklangan AV1 nusxalar bir marta avtomatik qayta yuklanadi (`media/youtube.py`, `MARKER_VERSION = 2`). Jonli sinov: https://youtu.be/prxGMABkASI — yuklash, tahlil, lotin/kirill eksport, hook.
- **Tuzatish — dekodlanmaydigan kodek:** import paytida birinchi kadr dekodlab tekshiriladi; AV1 fayllar epizod yaratilishidan oldin tushunarli `unsupported_codec` xatosi bilan rad etiladi (4 tilda), render ham xom ffmpeg logi o'rniga shu kodni qaytaradi (`media/codec_check.py`).
- **Tuzatish — chala MP4:** muvaffaqiyatsiz render eksport papkasida buzuq fayl qoldirmaydi (`render/graph.py`).
- **Tuzatish — hook subtitri:** subtitr kartochkalari hook prefiksi oxirida majburan bo'linadi (SRT, VTT, ASS, host caption) — hook matni klip boshidagi matn bilan bitta kartochkaga qo'shilmaydi (`subtitle/layout.py`, `subtitle/ass.py`).

Tafsilotlar: [`0.2.2/NOTES.md`](0.2.2/NOTES.md)

## [0.2.1] — 2026-10-26

- **Tuzatish — yetim `lahza-engine serve` jarayonlari:** ilova yopilgandan keyin engine endi qolmaydi. Sabab: Tauri faqat PyInstaller bootloader'ini SIGKILL qilardi (Python bolasi yetim qolardi) va `/v1/events` WebSocket handler'i uzilishni sezmay SIGTERM'dagi to'xtashni abadiy to'sardi. Endi: jarayon guruhiga SIGTERM → 2,5 s → SIGKILL (`engine.rs`), engine'da tez to'xtash + majburiy `os._exit` + bola jarayonlarni o'ldirish, ota jarayon watchdog'i (`--parent-pid`, `--watch-stdin`; `core/lifecycle.py`). Batafsil: `docs/01-arxitektura.md` "Engine hayot sikli".

Tafsilotlar: [`0.2.1/NOTES.md`](0.2.1/NOTES.md)

## [0.2.0] — 2026-10-26

- **PRO-3 — hook oldinga:** klipning eng kuchli 2–4 soniyalik jumlasi klip boshiga qo'yiladi (`highlight/hook_front.py`, keshdagi signallar, ~0,5 ms/klip). Hostplan va montaj manbasi hook'ni hali hisobga olmaydi.
- **PRO-4 — kirill subtitr:** lug'atli lotin → kirill transliteratsiya (`text/translit.py`, `text/data/cyrillic.json`), uslub sozlamasida yozuv tanlovi. Qolgani: lug'atni tilshunos ko'rib chiqishi.
- **PRO-5 — partiyaviy tahlil navbati:** bir nechta epizod navbatda (`core/batch.py`, `/v1/queue` API, `lahza batch` CLI, UI navbat paneli).
- **YT-1 — YouTube havolasidan import:** `media/youtube.py`, ixtiyoriy `make setup-youtube`; standart holatda **o'chiq** — yurist xulosasi kutilmoqda (ADR-0010).
- **V1-5 — litsenziyalar oynasi:** "Sozlamalar → Litsenziyalar", `make licenses` / `make check-licenses` (`LICENSES-THIRD-PARTY.md` + `app/src/generated/licenses.json`, oflayn). Qolgani: ANIQLANSIN yozuvlari (asosan Windows crate'lari).
- **Reliz:** `versiyalar/` papkasi, `make bump-version`, `make release-local` (`scripts/release_local.py`).

Tafsilotlar: [`0.2.0/NOTES.md`](0.2.0/NOTES.md)

## [0.1.0] — 2026-10-16 … 2026-10-25

Tarixiy yozuv (binarsiz; versiya raqami bu davrda o'zgarmagan). Tafsilotlar: [`0.1.0/NOTES.md`](0.1.0/NOTES.md)

- `2aa5587` (2026-10-25) — Lokal alfa: AI montaj yordamchisi (lokal Qwen3 GGUF), stikerlar, `.lahzaskill` retseptlari, Mac `.app`.
- `d7ba061` (2026-10-23) — ADB-1..6: Premiere Pro (UXP) va After Effects (CEP) plaginlari.
- `6e96fa5` (2026-10-20) — RCP-1, MNT-1..3, FX-1..5, TL-1..3: video shablonlar va avtomatik montaj.
- `b8e8b1c` (2026-10-16) — R0-ORG-3: boshlang'ich holat — M1/M2/M3 kod darajasida.
