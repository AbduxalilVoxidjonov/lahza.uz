# Lahza Studio 0.2.5

- **Sana:** 2026-10-29 20:37 +05
- **Git commit:** `9a64be5fec9b` (Ilova yopilishi: qayta ishga tushirish kill bilan poygalashmaydi) + commit qilinmagan o'zgarishlar (working tree toza emas)
- **Platforma:** macOS 27.0.1, arm64
- **Oldingi versiya:** 0.2.4

## O'zgarishlar

- **Tuzatish — ilova yopilishida yetim engine:** engine qulab, qayta ishga tushirish kutayotgan paytda ilova yopilsa, yangi engine yopilgandan keyin ko'tarilib qolishi mumkin edi; endi kutishdan keyin va spawn'dan so'ng `kill` holati tekshiriladi (`app/src-tauri/src/engine.rs`). Windows'da 30 marta oddiy yopish, 9 marta AI montaj/issiq llama-server paytida yopish va 3 marta majburiy o'ldirish sinaldi — hech qaysida jarayon qolmadi.
- **Tuzatish — Windows desktop: engine ishga tushmasdi.** `--watch-stdin` (Tauri doim beradi) Windows'da sinxron stdin pipe'ni bloklab o'qirdi va meros handle'li bola jarayonlar (ffmpeg, subprocess) CRT ishga tushishida osilib qolardi; endi `PeekNamedPipe` bilan so'raladi (`core/lifecycle.py`).
- **Yangi — Windows MSVC relizi adminsiz:** xwin (MSVC CRT/SDK) + rust-lld + clang-cl, `+crt-static` - `lahza-studio.exe` VC++ runtime'ga bog'lanmaydi; NSIS per-user o'rnatuvchi WebView2 offline o'rnatuvchisi bilan (`tauri.conf.json`). `scripts/stage_windows_dlls.py` har exe/dll importini tekshiradi va yetishmagan VC++ runtime DLL'larini `resources/bin` ga qo'yadi.
- **Yangi — Windows uchun LGPL FFmpeg 7.1.1:** `scripts/build_runtimes.ps1 -FFmpegOnly` portativ MSYS2 (UCRT64) bilan dav1d 1.5.4 (statik), libass, Media Foundation/AMF/VPL; GPL DLL darvozasi, litsenziya matnlari `bin/licenses/local-render/`. 455 MB GPL sinov yig'masi o'rniga 37.6 MB.
- **Litsenziyalar:** Windows komponentlari (VC++ runtime, cuDNN, Intel/LLVM OpenMP, MinGW runtime) va so'rov bilan yuklanadigan yt-dlp/yt-dlp-ejs (meriyah, astring)/Deno uchun alohida bo'limlar; GPL tekshiruvi GCC runtime istisnosini to'g'ri taniydi.

- **O'zgarish — YouTube importi standart yoqilgan** (egasi qarori, ADR-0010); har importda rozilik saqlanadi.
- **Yangi — komponent yangilanishi ilova relizisiz:** Sozlamalarda "Yangilanishni tekshirish" — PyPI/GitHub'dagi oxirgi yt-dlp, yt-dlp-ejs (yt-dlp talab qilgan versiya) va Deno 2.x, e'lon qilingan sha256 bilan; YouTube yuklash yiqilsa import kartasida shu tugmaga havola.
- **Yangi — YouTube komponentlari ilovaning o'zidan:** Sozlamalar (va import kartasi)dagi tugma yt-dlp, yt-dlp-ejs va Deno'ni bir marta yuklaydi — mahkamlangan versiya, sha256 tekshiruvi, atomik joylash (`media/youtube_components.py`, `/v1/settings/youtube-import:install-components`). Desktop ilovada YouTube importi endi `make setup-youtube`siz ishlaydi; yt-dlp sidecar'ga kirmaydi (ADR-0010).
- **Tuzatish — Windows:** Claude montaj `claude.cmd` bilan ishlaydi (`--system-prompt-file`); sidecar yangi VC++ runtime'ni o'zi olib keladi (eski `msvcp140` onnxruntime/ctranslate2'ni qulatardi); llama-server/whisper-cli statik CRT bilan yig'iladi.
- **Tuzatish — Windows lokal sinov:** ASR GPU yo'q yoki CUDA ishga tushmasa CPU'ga o'tadi (Lite daraja ishlaydi); 16 GB RAM "unsupported" deb ko'rsatilmaydi (o'rnatilgan fizik RAM o'qiladi); LUT/SRT/MOGRT importi (`os.O_NONBLOCK`) va `C:\` yo'llari (`.lahzaskill`) tuzatildi; o'rnatish vazifasi holati jurnal va lease'dan keyin ko'rinadi.
- **Yaxshilash — AI montaj tezligi:** issiq llama-server (birinchi so'rovda ko'tariladi, `LAHZA_LLM_IDLE_S` = 300 s bo'sh tursa yopiladi, Windows'da Job Object bilan engine bilan birga o'ladi) va prompt keshi; kontekst 16k → 12k. i7-13620H CPU: birinchi buyruq ~33 s, keyingilari 13-19 s (avval ~37 s), 10/10 to'g'ri reja. Qwen3-4B Windows CPU o'lchovi: `docs/local-ai-editing.md`.
- **Tuzatish — YouTube komponentlari:** o'rnatish va YouTube yuklash bir vaqtda ishlamaydi (409); xatoda eski nusxa saqlanadi; yangi `incompatible` xato kodi (4 tilda); pre-release versiyalar rad etiladi; o'rnatish progressida hajm ("3.0 MB / 44.0 MB").

- YouTube: playlist va kanal havolalari — videolar ro'yxati (ko'pi bilan 50), tanlanganlari partiyaviy navbatga qo'shiladi (`POST /v1/media:resolve-url`).
- Partiyaviy navbat YouTube havolalarini qabul qiladi: har element yuklanadi, import va tahlil qilinadi; bekor qilish va qayta urinish ishlaydi.
- YouTube metama'lumoti: video sarlavhasi epizod nomi bo'ladi, tavsif va boblar saqlanadi; epizod sahifasida boblar ro'yxati va manba havolasi.
- Lite highlight YouTube boblarini kichik signal sifatida hisobga oladi (bob boshida boshlangan klipga bonus).
- JS runtime versiyasi tekshiriladi (Deno 2.3+, Node 22+): eski runtime haqida aniq xabar, ilovaning o'z Deno'si afzal.
- Sozlamalar: tizimdagi yt-dlp/Deno ishlatilayotgani versiyasi bilan ko'rsatiladi.
- Dasturchi muhiti: `make dev-engine` ilova papkasidagi FFmpeg va llama-server'ni topadi (`LAHZA_BIN_DIR`).

## Testlar

| Tekshiruv | Natija |
|---|---|
| `make test-engine` | 1351 passed, 13 skipped, 2 deselected (227 s) |
| `make test-ui` | 129 passed, 0 failed (1 s) |
| `make typecheck` | ok (2 s) |
| `make lint` | ok (0 s) |
| `make check-licenses` | ok (0 s) |

## Binar

- `make build-local`: muvaffaqiyatli (1.1 daqiqa)
- `Lahza Studio.app`: 188.5 MB - shu papkada, ikki marta bosib ochiladi (ad-hoc imzo, notarizatsiyasiz - faqat lokal sinov; `codesign --verify --deep --strict`: ok)
- `LahzaStudio-0.2.5-macos-arm64.zip`: 110.7 MB - o'sha `.app` ning `ditto` arxivi (boshqa Mac'ga ko'chirish uchun; ochish: `ditto -x -k <zip> /Applications`)
- Xeshlar: `SHA256SUMS` (zip va `.app/Contents/MacOS/*`)
- Birinchi ochishda Gatekeeper to'xtatsa: o'ng tugma -> Open.
- Binar git'ga kirmaydi (`.gitignore`).
