# Lahza Studio 0.2.3

- **Sana:** 2026-10-26 15:52 +05
- **Git commit:** `ce4bc2fec42b` (0.2.1: hook oldinga, kirill subtitr, navbat, YouTube import, litsenziyalar, versiyalar) + commit qilinmagan o'zgarishlar (working tree toza emas)
- **Platforma:** macOS 27.0.1, arm64
- **Oldingi versiya:** 0.2.2

## O'zgarishlar

- **Yangi — AV1 o'qish:** bundled FFmpeg dav1d 1.5.4 (BSD-2, statik) bilan yig'iladi, LGPL qoidasi saqlanadi (`--disable-gpl`). `codec_check` AV1 ni endi `ffmpeg -decoders` bo'yicha tekshiradi; dekoder bo'lmasa avvalgidek `unsupported_codec` (`scripts/setup_local_render.py`, `third_party/runtimes.toml`, `media/codec_check.py`).
- **Tuzatish — navbat xatolari:** engine yiqilgan vazifalarga barqaror `error_code` beradi (15 ta kod: fayl topilmadi, disk to'la, model yo'q, ffmpeg, tarmoq, bekor qilindi …); navbat paneli va vazifa qatorlari ularni 4 tilda ko'rsatadi, xom matn "Batafsil" ichida (`core/errors.py`, `lib/error-codes.ts`).
- **Tuzatish — siyrak transkript:** ASR oynasi 30 s → 10 s (jim joyda kesiladi); subtitr kartochkasi ko'pi bilan 6 s, so'z vaqtlari bo'lmasa harf soniga proporsional (`asr/base.py`, `subtitle/layout.py`). Siyraklik metrikasi (`transcript_density`) logga yoziladi.
- **Yaxshilash — ASR aniqligi:** VAD padding 30 → 200 ms, min sukunat 100 → 400 ms; `temperature=0`, `beam_size=5`; past ovozli audio kuchaytiriladi; Whisper matnni timestamp'siz dekodlaydi, so'z vaqtlari CTC aligner'dan. FLEURS uz (83 fayl) WER: base 53.1% → 19.8%, small → 15.4%; ASR ~2× tezroq.
- **Yangi — CTC aligner standart:** Omnilingual CTC 300M int8 (Apache-2.0, 328 MB) birinchi ochilishda yuklanadi; pauzalar 63/65, so'z chegarasi median 28–46 ms. Aligner bo'lmasa eski Whisper vaqtlari rejimi avtomatik. Yuklash hajmi ~3 GB. Eski loyihalar bir marta qayta tahlil qilinadi (ASR/align kesh versiyalari).
- **Yangi — Transkripsiya sifati (Tez/Aniq):** Sozlamalar → O'rnatilgan modellar. Tez — base (standart, birinchi ochilishda yuklanadigan yagona ASR); Aniq — small (~2.5× sekin, ~240 MB), hozircha `.lzpack` faylidan o'rnatiladi (internet manzili `LAHZA_ASR_ACCURATE_PACK_URL` sozlanganda). Eski tahlillar majburan qayta hisoblanmaydi (`models/asr_quality.py`, `/v1/asr-quality`).
- **Yangi — ASR benchmark:** `make asr-eval` (FLEURS uz test, CC-BY-4.0; WER/CER/RTF, ablyatsiya bayroqlari) — `eval/YORIQNOMA.md`.

## Testlar

| Tekshiruv | Natija |
|---|---|
| `make test-engine` | 970 passed, 9 skipped (46 s) |
| `make test-ui` | 105 passed, 0 failed (1 s) |
| `make typecheck` | ok (2 s) |
| `make lint` | ok (0 s) |
| `make check-licenses` | ok (0 s) |

## Binar

- `make build-local`: muvaffaqiyatli (1.2 daqiqa)
- `Lahza Studio.app`: 214.9 MB - shu papkada, ikki marta bosib ochiladi (ad-hoc imzo, notarizatsiyasiz - faqat lokal sinov; `codesign --verify --deep --strict`: ok)
- `LahzaStudio-0.2.3-macos-arm64.zip`: 137.0 MB - o'sha `.app` ning `ditto` arxivi (boshqa Mac'ga ko'chirish uchun; ochish: `ditto -x -k <zip> /Applications`)
- Xeshlar: `SHA256SUMS` (zip va `.app/Contents/MacOS/*`)
- Birinchi ochishda Gatekeeper to'xtatsa: o'ng tugma -> Open.
- Binar git'ga kirmaydi (`.gitignore`).
