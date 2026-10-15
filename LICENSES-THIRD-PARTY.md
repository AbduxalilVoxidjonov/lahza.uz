# Uchinchi tomon litsenziyalari

Bu ro'yxat ilovaning "Haqida → Litsenziyalar" oynasida ko'rsatiladi. Tijorat relizidan oldin yurist tomonidan tekshiriladi (TZ 16-bo'lim); jadval texnik yo'naltiruvchi, yuridik xulosa emas.

## Ilovaga kiradigan dasturiy ta'minot

Qo'lda yuritiladigan umumiy jadval (native runtime'lar va Rust qismi). Python va npm paketlarining
aniq versiyalari quyidagi avtomatik jadvallarda.

| Komponent | Litsenziya | Izoh |
| --- | --- | --- |
| Tauri 2, tauri-plugin-shell, tauri-plugin-dialog | MIT / Apache-2.0 | Rust crate'lari (`app/src-tauri/Cargo.lock`) |
| serde, serde_json, uuid, tokio | MIT / Apache-2.0 | Rust; tranzitiv crate'lar ro'yxati `cargo about` bilan generatsiya qilinadi (ANIQLANSIN, M2) |
| React, React Router, TanStack Query, Zustand | MIT | npm jadvaliga qarang |
| FastAPI, Starlette, Uvicorn, Pydantic, httpx | MIT / BSD-3-Clause | Python jadvaliga qarang |
| NumPy | BSD-3-Clause (+ 0BSD, MIT, Zlib, CC0-1.0 qismlar) | |
| cryptography | Apache-2.0 / BSD-3-Clause | |
| psutil | BSD-3-Clause | |
| ONNX Runtime (`onnxruntime`) | MIT | Silero VAD (`engine[onnx]`) |
| fontTools (`fonttools`) | MIT | Shriftlar (`engine[fonts]`) |
| CPython (sidecar ichida) | PSF-2.0 | PyInstaller sidecar'ga Python interpretatorini qo'shadi |
| PyInstaller bootloader | GPL-2.0-or-later, bootloader istisnosi bilan | Istisno yig'ilgan dasturni istalgan litsenziyada tarqatishga ruxsat beradi; faqat build vositasi |
| FFmpeg (GPL qismlarisiz yig'ma) | LGPL-2.1+ | Dinamik bog'lanadi; manba kodi va qayta bog'lash imkoni ta'minlanadi |
| libass | ISC | FFmpeg ichida (`--enable-libass`) |
| FreeType | FTL yoki GPL-2.0 (tanlov) | libass bog'liqligi; FTL tanlanadi |
| HarfBuzz | MIT ("Old MIT") | libass bog'liqligi |
| FriBiDi | LGPL-2.1+ | libass bog'liqligi; dinamik bog'lanadi |
| whisper.cpp, llama.cpp (ggml) | MIT | |

### Python paketlari (sidecar)

Avtomatik: `engine/.venv/bin/python scripts/gen_licenses.py`. Qo'lda tahrirlamang.

<!-- gen_licenses:python:start -->
Python 3.12 muhitidan, `lahza-engine` + ekstralar: onnx, fonts. 27 paket.

| Paket | Versiya | Litsenziya | Kim tortgan |
| --- | --- | --- | --- |
| annotated-doc | 0.0.5 | MIT | fastapi |
| annotated-types | 0.8.0 | MIT | pydantic |
| anyio | 4.15.1 | MIT | httpx |
| certifi | 2026.7.22 | MPL-2.0 | httpx |
| cffi | 2.1.1 | MIT-0 | cryptography |
| click | 8.5.0 | BSD-3-Clause | uvicorn |
| cryptography | 50.0.2 | Apache-2.0 OR BSD-3-Clause | to'g'ridan |
| fastapi | 0.143.2 | MIT | to'g'ridan |
| flatbuffers | 25.12.19 | Apache-2.0 | onnxruntime |
| fonttools | 4.67.0 | MIT | to'g'ridan |
| h11 | 0.16.0 | MIT | uvicorn |
| httpcore | 1.0.9 | BSD-3-Clause | httpx |
| httpx | 0.28.1 | BSD-3-Clause | to'g'ridan |
| idna | 3.20 | BSD-3-Clause | httpx |
| numpy | 2.5.4 | BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0 | to'g'ridan |
| onnxruntime | 1.31.0 | MIT | to'g'ridan |
| opentelemetry-api | 1.45.1 | Apache-2.0 | fastapi |
| packaging | 26.3 | Apache-2.0 OR BSD-2-Clause | onnxruntime |
| protobuf | 7.36.2 | BSD-3-Clause | onnxruntime |
| psutil | 7.2.2 | BSD-3-Clause | to'g'ridan |
| pycparser | 3.11 | BSD-3-Clause | cffi |
| pydantic | 2.14.1 | MIT | to'g'ridan |
| pydantic_core | 2.50.1 | MIT | pydantic |
| starlette | 1.8.0 | BSD-3-Clause | fastapi |
| typing-inspection | 0.4.4 | MIT | pydantic |
| typing_extensions | 4.16.0 | PSF-2.0 | pydantic |
| uvicorn | 0.54.0 | BSD-3-Clause | to'g'ridan |
<!-- gen_licenses:python:end -->

### npm paketlari (UI)

Avtomatik: `engine/.venv/bin/python scripts/gen_licenses.py`. Faqat production bog'liqliklar
(Vite, TypeScript, `@tauri-apps/cli` kabi build vositalari ilovaga kirmaydi).

<!-- gen_licenses:npm:start -->
`app/package-lock.json` production bog'liqliklari. 12 paket.

| Paket | Versiya | Litsenziya |
| --- | --- | --- |
| @tanstack/query-core | 5.104.2 | MIT |
| @tanstack/react-query | 5.104.2 | MIT |
| @tauri-apps/api | 2.12.3 | Apache-2.0 OR MIT |
| @tauri-apps/plugin-dialog | 2.8.2 | MIT OR Apache-2.0 |
| cookie | 1.1.1 | MIT |
| react | 19.3.0 | MIT |
| react-dom | 19.3.0 | MIT |
| react-router | 7.18.4 | MIT |
| react-router-dom | 7.18.4 | MIT |
| scheduler | 0.28.0 | MIT |
| set-cookie-parser | 2.7.2 | MIT |
| zustand | 5.0.15 | MIT |
<!-- gen_licenses:npm:end -->

## Modellar (katalogdan yuklanadi)

| Model | Litsenziya | Muallifni ko'rsatish |
| --- | --- | --- |
| pyannote speaker-diarization-community-1 | CC-BY-4.0 | **Majburiy:** "pyannote speaker-diarization-community-1 (CC-BY-4.0)" |
| idrock/piyola-v2 | CC-BY-4.0 | **Majburiy:** "idrock/piyola-v2, asosi nvidia/parakeet-tdt-0.6b-v2 (CC-BY-4.0)" |
| BuzzASR/uzbek | MIT | |
| islomov/rubaistt_v2_medium | Apache-2.0 | |
| Meta Omnilingual ASR | Apache-2.0 (model), CC-BY-4.0 (korpus) | |
| Silero VAD | MIT | |
| MediaPipe BlazeFace | Apache-2.0 | |
| LR-ASD | MIT | |
| Qwen3.5, Gemma 4 | Apache-2.0 | |

O'z fine-tune'ingizda ISSAI/TUIT Uzbek Speech Corpus ishlatilsa, mahsulotga ISSAI belgilagan bayonot qo'shiladi:
"Our product uses ISSAI and TUIT Uzbek Speech Corpus (https://doi.org/10.48342/drss-8q87), which is available under a Creative Commons Attribution 4.0 International License."

## Ishlatilmaydi

| Komponent | Sabab |
| --- | --- |
| libx264, libx265 | GPL |
| Meta MMS forced aligner | CC-BY-NC-4.0 (notijorat) |
| InsightFace SCRFD vaznlari | Notijorat |
| YOLOv8-Face | AGPL-3.0 |

Litsenziyasi aniqlanmagan modellar (Abduqayum/whisper-uzbek-medium-callcenter, NeuronAI-2B, alloma-8B) aniqlanmaguncha faqat R0 sinovida ishlatiladi va mahsulotga kirmaydi.
