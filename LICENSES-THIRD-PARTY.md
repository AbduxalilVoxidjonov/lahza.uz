# Uchinchi tomon litsenziyalari

Bu ro'yxat ilovaning "Sozlamalar → Litsenziyalar" oynasida ko'rsatiladi (ma'lumot: `app/src/generated/licenses.json`, ilova bundle'iga kiradi, oflayn). Tijorat relizidan oldin yurist tomonidan tekshiriladi (TZ 16-bo'lim); jadval texnik yo'naltiruvchi, yuridik xulosa emas.

## Ilovaga kiradigan dasturiy ta'minot

Qo'lda yuritiladigan umumiy jadval (native runtime'lar va Rust qismi). Python va npm paketlarining
aniq versiyalari quyidagi avtomatik jadvallarda.

| Komponent | Litsenziya | Izoh |
| --- | --- | --- |
| Tauri 2, tauri-plugin-shell, tauri-plugin-dialog | MIT / Apache-2.0 | Rust crate'lari (`app/src-tauri/Cargo.lock`) |
| serde, serde_json, uuid, tokio | MIT / Apache-2.0 | Rust; tranzitiv crate'lar quyidagi avtomatik jadvalda (`Cargo.lock`) |
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
| faster-whisper, CTranslate2, tokenizers | MIT / MIT / Apache-2.0 | ASR (`engine[desktop]`); faster-whisper `--no-deps` bilan o'rnatiladi |
| PyAV (`av`) | — (to'plamga **kirmaydi**) | PyPI g'ildiraklari GPL libx264/libx265 bilan yig'ilgan FFmpeg olib keladi. Sidecar'dan chiqarilgan, ASR audio'si yuqoridagi LGPL FFmpeg bilan dekod qilinadi ([ADR-0015](docs/adr/0015-pyavsiz-asr-dekod.md)) |

Barcha avtomatik bo'limlar: `make licenses` (`engine/.venv/bin/python scripts/gen_licenses.py`), tekshiruv:
`make check-licenses`. Belgilar orasini qo'lda tahrirlamang. Generator sidecar'ning Python/native
qismida GPL komponent (masalan `av`, `libx264`, `libx265`) topsa xato bilan to'xtaydi (ADR-0015).

### Python paketlari (sidecar)

<!-- gen_licenses:python:start -->
`lahza-engine` + ekstralar: desktop, onnx, fonts; CPython va PyInstaller bootloader. 42 komponent.

| Paket | Versiya | Litsenziya | Kim tortgan |
| --- | --- | --- | --- |
| annotated-doc | 0.0.5 | MIT | fastapi |
| annotated-types | 0.8.0 | MIT | pydantic |
| anyio | 4.15.1 | MIT | httpx |
| certifi | 2026.7.22 | MPL-2.0 | httpx |
| cffi | 2.1.1 | MIT-0 | cryptography |
| click | 8.5.0 | BSD-3-Clause | uvicorn |
| cryptography | 50.0.2 | Apache-2.0 OR BSD-3-Clause | to'g'ridan |
| ctranslate2 | 4.8.3 | MIT | to'g'ridan |
| fastapi | 0.143.2 | MIT | to'g'ridan |
| faster-whisper | 1.2.1 | MIT | to'g'ridan (--no-deps) |
| filelock | 4.2.4 | MIT | huggingface_hub |
| flatbuffers | 25.12.19 | Apache-2.0 | onnxruntime |
| fonttools | 4.67.0 | MIT | to'g'ridan |
| fsspec | 2026.9.0 | BSD-3-Clause | huggingface_hub |
| h11 | 0.16.0 | MIT | uvicorn |
| hf-xet | 1.7.0 | Apache-2.0 | huggingface_hub |
| httpcore | 1.0.9 | BSD-3-Clause | httpx |
| httpcore2 | 2.16.0 | BSD-3-Clause | httpx2 |
| httpx | 0.28.1 | BSD-3-Clause | to'g'ridan |
| httpx2 | 2.16.0 | BSD-3-Clause | huggingface_hub |
| huggingface_hub | 2.3.0 | Apache-2.0 | to'g'ridan |
| idna | 3.20 | BSD-3-Clause | httpx |
| numpy | 2.5.4 | BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0 | to'g'ridan |
| onnxruntime | 1.31.0 | MIT | to'g'ridan |
| opentelemetry-api | 1.45.1 | Apache-2.0 | fastapi |
| packaging | 26.3 | Apache-2.0 OR BSD-2-Clause | huggingface_hub |
| protobuf | 7.36.2 | BSD-3-Clause | onnxruntime |
| psutil | 7.2.2 | BSD-3-Clause | to'g'ridan |
| pycparser | 3.11 | BSD-3-Clause | cffi |
| pydantic | 2.14.1 | MIT | to'g'ridan |
| pydantic_core | 2.50.1 | MIT | pydantic |
| PyYAML | 6.0.3 | MIT | ctranslate2 |
| starlette | 1.8.0 | BSD-3-Clause | fastapi |
| tokenizers | 0.23.3 | Apache-2.0 | to'g'ridan |
| tqdm | 4.70.1 | MPL-2.0 AND MIT | to'g'ridan |
| truststore | 0.10.5 | MIT | httpx2 |
| typing-inspection | 0.4.4 | MIT | pydantic |
| typing_extensions | 4.16.0 | PSF-2.0 | pydantic |
| uvicorn | 0.54.0 | BSD-3-Clause | to'g'ridan |
| websockets | 17.2 | BSD-3-Clause | to'g'ridan |
| CPython | 3.12.14 | PSF-2.0 | sidecar ichida (PyInstaller) |
| PyInstaller bootloader | 6.22.3 | GPL-2.0-or-later WITH Bootloader-exception | build vositasi (bootloader sidecar ichida) |
<!-- gen_licenses:python:end -->

### Python g'ildiraklaridagi native kutubxonalar

<!-- gen_licenses:python-native:start -->
Python g'ildiraklariga biriktirilgan native kutubxonalar: 1 ta. Litsenziya fayl nomi bo'yicha ("nom jadvali"), yuridik tekshiruvda tasdiqlanadi. **GPL** belgisi - ADR-0004 ga zid: generator bunday holatda yiqiladi (ADR-0015).

| Kutubxona | Fayl | Litsenziya | Manba | Xavf |
| --- | --- | --- | --- | --- |
| ctranslate2 | libctranslate2.4.8.3.dylib | MIT | ctranslate2 4.8.3 g'ildiragi |  |
<!-- gen_licenses:python-native:end -->

### npm paketlari (UI)

Faqat production bog'liqliklar (Vite, TypeScript, `@tauri-apps/cli` kabi build vositalari ilovaga kirmaydi).

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

### Rust crate'lari (Tauri qobig'i)

<!-- gen_licenses:rust:start -->
`app/src-tauri/Cargo.lock`: 430 crate (build vaqtidagilari ham, xavfsiz tomonga). 251 tasining litsenziyasi lokal cargo registry `Cargo.toml` idan; 179 tasi lokal registry'da yo'q (asosan Windows/Linux/Android crate'lari) - `ANIQLANSIN`, shu platformadagi build muhitida to'ldiriladi.

<details><summary>Crate'lar ro'yxati</summary>

| Crate | Versiya | Litsenziya |
| --- | --- | --- |
| adler2 | 2.0.1 | 0BSD OR MIT OR Apache-2.0 |
| aho-corasick | 1.1.5 | Unlicense OR MIT |
| alloc-no-stdlib | 3.0.0 | BSD-3-Clause |
| alloc-stdlib | 0.3.0 | BSD-3-Clause |
| android_system_properties | 0.1.6 | ANIQLANSIN |
| anyhow | 1.0.104 | MIT OR Apache-2.0 |
| atk | 0.18.2 | ANIQLANSIN |
| atk-sys | 0.18.2 | ANIQLANSIN |
| atomic-waker | 1.1.2 | ANIQLANSIN |
| autocfg | 1.5.1 | Apache-2.0 OR MIT |
| base64 | 0.21.7 | MIT OR Apache-2.0 |
| base64 | 0.22.1 | ANIQLANSIN |
| base64 | 0.23.1 | MIT OR Apache-2.0 |
| bit-set | 0.8.0 | Apache-2.0 OR MIT |
| bit-vec | 0.8.0 | Apache-2.0 OR MIT |
| bitflags | 1.3.2 | MIT/Apache-2.0 |
| bitflags | 2.13.2 | MIT OR Apache-2.0 |
| block-buffer | 0.10.4 | MIT OR Apache-2.0 |
| block2 | 0.6.2 | MIT |
| brotli | 9.0.0 | BSD-3-Clause AND MIT |
| brotli-decompressor | 6.0.1 | BSD-3-Clause/MIT |
| bs58 | 0.5.1 | MIT/Apache-2.0 |
| bumpalo | 3.20.3 | ANIQLANSIN |
| bytemuck | 1.25.2 | ANIQLANSIN |
| byteorder | 1.5.0 | Unlicense OR MIT |
| bytes | 1.12.1 | MIT |
| cairo-rs | 0.18.5 | ANIQLANSIN |
| cairo-sys-rs | 0.18.2 | ANIQLANSIN |
| camino | 1.2.6 | MIT OR Apache-2.0 |
| cargo-platform | 0.1.9 | MIT OR Apache-2.0 |
| cargo_metadata | 0.19.2 | MIT |
| cargo_toml | 1.0.1 | Apache-2.0 OR MIT |
| cc | 1.8.0 | MIT OR Apache-2.0 |
| cesu8 | 1.1.0 | ANIQLANSIN |
| cfb | 0.14.0 | MIT |
| cfg-expr | 0.15.8 | ANIQLANSIN |
| cfg-if | 1.0.5 | MIT OR Apache-2.0 |
| chrono | 0.4.45 | MIT OR Apache-2.0 |
| combine | 4.6.8 | ANIQLANSIN |
| cookie | 0.18.2 | MIT OR Apache-2.0 |
| core-foundation | 0.10.1 | MIT OR Apache-2.0 |
| core-foundation-sys | 0.8.7 | MIT OR Apache-2.0 |
| core-graphics | 0.25.0 | MIT OR Apache-2.0 |
| core-graphics-types | 0.2.0 | MIT OR Apache-2.0 |
| core_detect | 1.0.0 | ANIQLANSIN |
| cpufeatures | 0.2.17 | MIT OR Apache-2.0 |
| crc32fast | 1.5.2 | MIT OR Apache-2.0 |
| crossbeam-channel | 0.5.17 | MIT OR Apache-2.0 |
| crossbeam-utils | 0.8.23 | MIT OR Apache-2.0 |
| crypto-common | 0.1.7 | MIT OR Apache-2.0 |
| cssparser | 0.37.0 | MPL-2.0 |
| cssparser-macros | 0.7.1 | MPL-2.0 |
| ctor | 1.0.13 | Apache-2.0 OR MIT |
| darling | 0.24.1 | MIT |
| darling_core | 0.24.1 | MIT |
| darling_macro | 0.24.1 | MIT |
| dbus | 0.9.12 | ANIQLANSIN |
| defmt | 1.1.1 | MIT OR Apache-2.0 |
| defmt-macros | 1.1.1 | MIT OR Apache-2.0 |
| defmt-parser | 1.0.0 | MIT OR Apache-2.0 |
| deranged | 0.5.9 | MIT OR Apache-2.0 |
| derive_more | 2.1.1 | MIT |
| derive_more-impl | 2.1.1 | MIT |
| digest | 0.10.7 | MIT OR Apache-2.0 |
| dirs | 7.0.0 | MIT OR Apache-2.0 |
| dirs-sys | 0.5.0 | MIT OR Apache-2.0 |
| dispatch2 | 0.3.1 | Zlib OR Apache-2.0 OR MIT |
| displaydoc | 0.2.7 | MIT OR Apache-2.0 |
| dlopen2 | 0.8.2 | ANIQLANSIN |
| dlopen2_derive | 0.4.3 | ANIQLANSIN |
| dom_query | 0.28.0 | MIT |
| dpi | 0.1.2 | Apache-2.0 AND MIT |
| dtoa | 1.0.11 | MIT OR Apache-2.0 |
| dtoa-short | 0.3.5 | MPL-2.0 |
| dunce | 1.0.5 | CC0-1.0 OR MIT-0 OR Apache-2.0 |
| dyn-clone | 1.0.20 | MIT OR Apache-2.0 |
| embed-resource | 3.0.12 | MIT |
| embed_plist | 1.2.2 | MIT OR Apache-2.0 |
| encoding_rs | 0.8.42 | (Apache-2.0 OR MIT) AND BSD-3-Clause |
| equivalent | 1.0.3 | Apache-2.0 OR MIT |
| erased-serde | 0.4.10 | MIT OR Apache-2.0 |
| fastrand | 2.5.0 | Apache-2.0 OR MIT |
| fdeflate | 0.3.7 | MIT OR Apache-2.0 |
| field-offset | 0.3.6 | ANIQLANSIN |
| find-msvc-tools | 0.1.14 | MIT OR Apache-2.0 |
| flate2 | 1.1.10 | MIT OR Apache-2.0 |
| fnv | 1.0.7 | Apache-2.0 / MIT |
| foldhash | 0.2.0 | Zlib |
| foreign-types | 0.5.0 | MIT/Apache-2.0 |
| foreign-types-macros | 0.2.4 | MIT/Apache-2.0 |
| foreign-types-shared | 0.3.1 | MIT/Apache-2.0 |
| form_urlencoded | 1.2.2 | MIT OR Apache-2.0 |
| futures-channel | 0.3.34 | ANIQLANSIN |
| futures-core | 0.3.34 | ANIQLANSIN |
| futures-executor | 0.3.34 | ANIQLANSIN |
| futures-io | 0.3.34 | ANIQLANSIN |
| futures-macro | 0.3.34 | ANIQLANSIN |
| futures-sink | 0.3.34 | ANIQLANSIN |
| futures-task | 0.3.34 | ANIQLANSIN |
| futures-util | 0.3.34 | ANIQLANSIN |
| gdk | 0.18.2 | ANIQLANSIN |
| gdk-pixbuf | 0.18.5 | ANIQLANSIN |
| gdk-pixbuf-sys | 0.18.0 | ANIQLANSIN |
| gdk-sys | 0.18.2 | ANIQLANSIN |
| gdkwayland-sys | 0.18.2 | ANIQLANSIN |
| gdkx11 | 0.18.2 | ANIQLANSIN |
| gdkx11-sys | 0.18.2 | ANIQLANSIN |
| generic-array | 0.14.7 | MIT |
| getrandom | 0.3.4 | MIT OR Apache-2.0 |
| getrandom | 0.4.3 | MIT OR Apache-2.0 |
| gio | 0.18.4 | ANIQLANSIN |
| gio-sys | 0.18.1 | ANIQLANSIN |
| glib | 0.18.5 | ANIQLANSIN |
| glib-macros | 0.18.5 | ANIQLANSIN |
| glib-sys | 0.18.1 | ANIQLANSIN |
| glob | 0.3.4 | MIT OR Apache-2.0 |
| gobject-sys | 0.18.0 | ANIQLANSIN |
| gtk | 0.18.2 | ANIQLANSIN |
| gtk-sys | 0.18.2 | ANIQLANSIN |
| gtk3-macros | 0.18.2 | ANIQLANSIN |
| hashbrown | 0.12.3 | MIT OR Apache-2.0 |
| hashbrown | 0.17.1 | MIT OR Apache-2.0 |
| heck | 0.4.1 | ANIQLANSIN |
| heck | 0.5.0 | MIT OR Apache-2.0 |
| hex | 0.4.3 | MIT OR Apache-2.0 |
| html5ever | 0.39.0 | MIT OR Apache-2.0 |
| http | 1.5.0 | MIT OR Apache-2.0 |
| http-body | 1.1.0 | ANIQLANSIN |
| http-body-util | 0.1.5 | ANIQLANSIN |
| httparse | 1.10.1 | ANIQLANSIN |
| hyper | 1.12.0 | ANIQLANSIN |
| hyper-util | 0.1.21 | ANIQLANSIN |
| iana-time-zone | 0.1.65 | MIT OR Apache-2.0 |
| iana-time-zone-haiku | 0.1.2 | ANIQLANSIN |
| ico | 0.5.0 | MIT |
| icu_collections | 2.3.0 | Unicode-3.0 |
| icu_locale_core | 2.3.0 | Unicode-3.0 |
| icu_normalizer | 2.3.0 | Unicode-3.0 |
| icu_normalizer_data | 2.3.0 | Unicode-3.0 |
| icu_properties | 2.3.0 | Unicode-3.0 |
| icu_properties_data | 2.3.0 | Unicode-3.0 |
| icu_provider | 2.3.1 | Unicode-3.0 |
| ident_case | 1.0.1 | MIT/Apache-2.0 |
| idna | 1.1.0 | MIT OR Apache-2.0 |
| idna_adapter | 1.2.2 | Apache-2.0 OR MIT |
| indexmap | 1.9.3 | Apache-2.0 OR MIT |
| indexmap | 2.14.2 | Apache-2.0 OR MIT |
| infer | 0.22.0 | MIT |
| ipnet | 2.12.2 | ANIQLANSIN |
| is-docker | 0.2.0 | ANIQLANSIN |
| is-wsl | 0.4.0 | ANIQLANSIN |
| itoa | 1.0.18 | MIT OR Apache-2.0 |
| javascriptcore-rs | 1.1.2 | ANIQLANSIN |
| javascriptcore-rs-sys | 1.1.1 | ANIQLANSIN |
| jiff | 0.2.38 | Unlicense OR MIT |
| jiff-core | 0.1.1 | Unlicense OR MIT |
| jiff-static | 0.2.38 | ANIQLANSIN |
| jiff-tzdb | 0.1.9 | ANIQLANSIN |
| jiff-tzdb-platform | 0.1.3 | ANIQLANSIN |
| jni | 0.21.1 | ANIQLANSIN |
| jni-sys | 0.3.1 | ANIQLANSIN |
| jni-sys | 0.4.1 | ANIQLANSIN |
| jni-sys-macros | 0.4.1 | ANIQLANSIN |
| js-sys | 0.3.106 | ANIQLANSIN |
| json-patch | 4.2.0 | MIT/Apache-2.0 |
| jsonptr | 0.7.1 | MIT OR Apache-2.0 |
| keyboard-types | 0.8.3 | MIT OR Apache-2.0 |
| libappindicator | 0.9.0 | ANIQLANSIN |
| libappindicator-sys | 0.9.0 | ANIQLANSIN |
| libc | 0.2.190 | MIT OR Apache-2.0 |
| libdbus-sys | 0.2.7 | ANIQLANSIN |
| libloading | 0.7.4 | ANIQLANSIN |
| libredox | 0.1.25 | ANIQLANSIN |
| litemap | 0.8.3 | Unicode-3.0 |
| lock_api | 0.4.14 | MIT OR Apache-2.0 |
| log | 0.4.34 | MIT OR Apache-2.0 |
| markup5ever | 0.39.0 | MIT OR Apache-2.0 |
| memchr | 2.8.3 | Unlicense OR MIT |
| memoffset | 0.9.1 | ANIQLANSIN |
| mime | 0.3.17 | MIT OR Apache-2.0 |
| miniz_oxide | 0.8.9 | MIT OR Zlib OR Apache-2.0 |
| miniz_oxide | 0.9.1 | MIT OR Zlib OR Apache-2.0 |
| mio | 1.2.4 | MIT |
| muda | 0.20.0 | Apache-2.0 OR MIT |
| multiversion_no_op | 1.0.0 | Apache-2.0 OR MIT |
| ndk | 0.9.0 | ANIQLANSIN |
| ndk-context | 0.1.1 | ANIQLANSIN |
| ndk-sys | 0.6.0+11769913 | ANIQLANSIN |
| new_debug_unreachable | 1.0.6 | MIT |
| num-conv | 0.2.2 | MIT OR Apache-2.0 |
| num-traits | 0.2.19 | MIT OR Apache-2.0 |
| num_enum | 0.7.6 | ANIQLANSIN |
| num_enum_derive | 0.7.6 | ANIQLANSIN |
| objc2 | 0.6.5 | MIT |
| objc2-app-kit | 0.3.2 | Zlib OR Apache-2.0 OR MIT |
| objc2-cloud-kit | 0.3.2 | ANIQLANSIN |
| objc2-core-data | 0.3.2 | ANIQLANSIN |
| objc2-core-foundation | 0.3.2 | Zlib OR Apache-2.0 OR MIT |
| objc2-core-graphics | 0.3.2 | Zlib OR Apache-2.0 OR MIT |
| objc2-core-image | 0.3.2 | ANIQLANSIN |
| objc2-core-location | 0.3.2 | ANIQLANSIN |
| objc2-core-text | 0.3.2 | ANIQLANSIN |
| objc2-encode | 4.1.0 | MIT |
| objc2-exception-helper | 0.1.1 | Zlib OR Apache-2.0 OR MIT |
| objc2-foundation | 0.3.2 | MIT |
| objc2-io-surface | 0.3.2 | Zlib OR Apache-2.0 OR MIT |
| objc2-quartz-core | 0.3.2 | Zlib OR Apache-2.0 OR MIT |
| objc2-ui-kit | 0.3.2 | ANIQLANSIN |
| objc2-user-notifications | 0.3.2 | ANIQLANSIN |
| objc2-web-kit | 0.3.2 | Zlib OR Apache-2.0 OR MIT |
| once_cell | 1.21.4 | MIT OR Apache-2.0 |
| open | 5.4.4 | MIT |
| option-ext | 0.2.0 | MPL-2.0 |
| os_pipe | 1.2.3 | MIT |
| pango | 0.18.3 | ANIQLANSIN |
| pango-sys | 0.18.0 | ANIQLANSIN |
| parking_lot | 0.12.5 | MIT OR Apache-2.0 |
| parking_lot_core | 0.9.12 | MIT OR Apache-2.0 |
| percent-encoding | 2.3.2 | MIT OR Apache-2.0 |
| phf | 0.13.1 | MIT |
| phf_codegen | 0.13.1 | MIT |
| phf_generator | 0.13.1 | MIT |
| phf_macros | 0.13.1 | MIT |
| phf_shared | 0.13.1 | MIT |
| pin-project-lite | 0.2.17 | Apache-2.0 OR MIT |
| pkg-config | 0.3.34 | ANIQLANSIN |
| plist | 1.10.1 | MIT |
| png | 0.17.16 | MIT OR Apache-2.0 |
| png | 0.18.1 | MIT OR Apache-2.0 |
| portable-atomic | 1.15.0 | ANIQLANSIN |
| portable-atomic-util | 0.2.8 | ANIQLANSIN |
| potential_utf | 0.1.6 | Unicode-3.0 |
| powerfmt | 0.2.1 | MIT OR Apache-2.0 |
| precomputed-hash | 0.1.1 | MIT |
| proc-macro-crate | 1.3.1 | ANIQLANSIN |
| proc-macro-crate | 2.0.2 | ANIQLANSIN |
| proc-macro-crate | 3.5.0 | ANIQLANSIN |
| proc-macro-error | 1.0.4 | ANIQLANSIN |
| proc-macro-error-attr | 1.0.4 | ANIQLANSIN |
| proc-macro2 | 1.0.107 | MIT OR Apache-2.0 |
| quick-xml | 0.42.0 | MIT |
| quote | 1.0.47 | MIT OR Apache-2.0 |
| r-efi | 5.3.0 | ANIQLANSIN |
| r-efi | 6.0.0 | ANIQLANSIN |
| raw-window-handle | 0.6.2 | MIT OR Apache-2.0 OR Zlib |
| redox_syscall | 0.5.18 | ANIQLANSIN |
| redox_users | 0.5.3 | ANIQLANSIN |
| ref-cast | 1.0.27 | MIT OR Apache-2.0 |
| ref-cast-impl | 1.0.27 | MIT OR Apache-2.0 |
| regex | 1.13.1 | MIT OR Apache-2.0 |
| regex-automata | 0.4.18 | MIT OR Apache-2.0 |
| regex-syntax | 0.8.11 | MIT OR Apache-2.0 |
| reqwest | 0.13.5 | ANIQLANSIN |
| rfd | 0.16.0 | MIT |
| rustc-hash | 2.1.3 | Apache-2.0 OR MIT |
| rustc_version | 0.4.1 | MIT OR Apache-2.0 |
| rustversion | 1.0.23 | MIT OR Apache-2.0 |
| same-file | 1.0.6 | Unlicense/MIT |
| schemars | 0.8.22 | MIT |
| schemars | 0.9.0 | MIT |
| schemars | 1.2.3 | MIT |
| schemars_derive | 0.8.22 | MIT |
| scopeguard | 1.2.0 | MIT OR Apache-2.0 |
| selectors | 0.38.0 | MPL-2.0 |
| semver | 1.0.28 | MIT OR Apache-2.0 |
| serde | 1.0.229 | MIT OR Apache-2.0 |
| serde-untagged | 0.1.9 | MIT OR Apache-2.0 |
| serde_core | 1.0.229 | MIT OR Apache-2.0 |
| serde_derive | 1.0.229 | MIT OR Apache-2.0 |
| serde_derive_internals | 0.29.1 | MIT OR Apache-2.0 |
| serde_json | 1.0.154 | MIT OR Apache-2.0 |
| serde_repr | 0.1.21 | MIT OR Apache-2.0 |
| serde_spanned | 0.6.9 | ANIQLANSIN |
| serde_spanned | 1.1.2 | MIT OR Apache-2.0 |
| serde_with | 3.24.0 | MIT OR Apache-2.0 |
| serde_with_macros | 3.24.0 | MIT OR Apache-2.0 |
| serialize-to-javascript | 0.1.2 | MIT OR Apache-2.0 |
| serialize-to-javascript-impl | 0.1.2 | MIT OR Apache-2.0 |
| servo_arc | 0.4.3 | MIT OR Apache-2.0 |
| sha2 | 0.10.9 | MIT OR Apache-2.0 |
| shared_child | 1.1.2 | MIT |
| shlex | 2.0.1 | MIT OR Apache-2.0 |
| simd-adler32 | 0.3.10 | MIT |
| simdutf8 | 0.1.5 | MIT OR Apache-2.0 |
| siphasher | 1.0.4 | MIT OR Apache-2.0 |
| slab | 0.4.12 | ANIQLANSIN |
| smallvec | 1.16.3 | MIT OR Apache-2.0 |
| socket2 | 0.6.5 | MIT OR Apache-2.0 |
| softbuffer | 0.4.8 | ANIQLANSIN |
| soup3 | 0.5.0 | ANIQLANSIN |
| soup3-sys | 0.5.0 | ANIQLANSIN |
| stable_deref_trait | 1.2.1 | MIT OR Apache-2.0 |
| string_cache | 0.9.0 | MIT OR Apache-2.0 |
| string_cache_codegen | 0.6.1 | MIT OR Apache-2.0 |
| strsim | 0.11.1 | MIT |
| swift-rs | 1.0.9 | MIT OR Apache-2.0 |
| syn | 1.0.109 | ANIQLANSIN |
| syn | 2.0.119 | MIT OR Apache-2.0 |
| syn | 3.0.9 | MIT OR Apache-2.0 |
| sync_wrapper | 1.0.2 | ANIQLANSIN |
| synstructure | 0.14.0 | MIT |
| system-deps | 6.2.2 | ANIQLANSIN |
| tao | 0.37.1 | Apache-2.0 |
| tao-macros | 0.1.4 | ANIQLANSIN |
| target-lexicon | 0.12.16 | ANIQLANSIN |
| tauri | 2.12.3 | Apache-2.0 OR MIT |
| tauri-build | 2.7.2 | Apache-2.0 OR MIT |
| tauri-codegen | 2.7.2 | Apache-2.0 OR MIT |
| tauri-macros | 2.7.2 | Apache-2.0 OR MIT |
| tauri-plugin | 2.7.1 | Apache-2.0 OR MIT |
| tauri-plugin-dialog | 2.8.2 | Apache-2.0 OR MIT |
| tauri-plugin-fs | 2.7.0 | Apache-2.0 OR MIT |
| tauri-plugin-shell | 2.5.0 | Apache-2.0 OR MIT |
| tauri-runtime | 2.12.1 | Apache-2.0 OR MIT |
| tauri-runtime-wry | 2.12.1 | Apache-2.0 OR MIT |
| tauri-utils | 2.10.1 | Apache-2.0 OR MIT |
| tauri-winres | 0.3.6 | MIT |
| tendril | 0.5.1 | MIT OR Apache-2.0 |
| thiserror | 1.0.69 | ANIQLANSIN |
| thiserror | 2.0.21 | MIT OR Apache-2.0 |
| thiserror-impl | 1.0.69 | ANIQLANSIN |
| thiserror-impl | 2.0.21 | MIT OR Apache-2.0 |
| time | 0.3.55 | MIT OR Apache-2.0 |
| time-core | 0.1.9 | MIT OR Apache-2.0 |
| time-macros | 0.2.32 | MIT OR Apache-2.0 |
| tinystr | 0.8.4 | Unicode-3.0 |
| tinyvec | 1.13.3 | Zlib OR Apache-2.0 OR MIT |
| tokio | 1.53.3 | MIT |
| tokio-util | 0.7.20 | ANIQLANSIN |
| toml | 0.8.2 | ANIQLANSIN |
| toml | 1.1.8+spec-1.1.0 | MIT OR Apache-2.0 |
| toml_datetime | 0.6.3 | ANIQLANSIN |
| toml_datetime | 1.1.2+spec-1.1.0 | MIT OR Apache-2.0 |
| toml_edit | 0.19.15 | ANIQLANSIN |
| toml_edit | 0.20.2 | ANIQLANSIN |
| toml_edit | 0.25.17+spec-1.1.0 | ANIQLANSIN |
| toml_parser | 1.1.5+spec-1.1.0 | MIT OR Apache-2.0 |
| toml_writer | 1.1.3+spec-1.1.0 | MIT OR Apache-2.0 |
| tower | 0.5.3 | ANIQLANSIN |
| tower-http | 0.6.11 | ANIQLANSIN |
| tower-layer | 0.3.3 | ANIQLANSIN |
| tower-service | 0.3.3 | ANIQLANSIN |
| tracing | 0.1.44 | ANIQLANSIN |
| tracing-core | 0.1.36 | ANIQLANSIN |
| tray-icon | 0.25.1 | MIT OR Apache-2.0 |
| try-lock | 0.2.5 | ANIQLANSIN |
| typeid | 1.0.3 | MIT OR Apache-2.0 |
| typenum | 1.20.1 | MIT OR Apache-2.0 |
| unicode-ident | 1.0.27 | (MIT OR Apache-2.0) AND Unicode-3.0 |
| unicode-segmentation | 1.13.3 | ANIQLANSIN |
| url | 2.5.8 | MIT OR Apache-2.0 |
| urlpattern | 0.6.0 | MIT |
| utf8_iter | 1.0.4 | Apache-2.0 OR MIT |
| uuid | 1.28.0 | Apache-2.0 OR MIT |
| version-compare | 0.2.1 | ANIQLANSIN |
| version_check | 0.9.5 | MIT/Apache-2.0 |
| vswhom | 0.1.0 | ANIQLANSIN |
| vswhom-sys | 0.1.3 | ANIQLANSIN |
| walkdir | 2.5.0 | Unlicense/MIT |
| want | 0.3.2 | ANIQLANSIN |
| wasi | 0.11.1+wasi-snapshot-preview1 | ANIQLANSIN |
| wasip2 | 1.0.4+wasi-0.2.12 | ANIQLANSIN |
| wasm-bindgen | 0.2.129 | ANIQLANSIN |
| wasm-bindgen-futures | 0.4.79 | ANIQLANSIN |
| wasm-bindgen-macro | 0.2.129 | ANIQLANSIN |
| wasm-bindgen-macro-support | 0.2.129 | ANIQLANSIN |
| wasm-bindgen-shared | 0.2.129 | ANIQLANSIN |
| wasm-streams | 0.5.0 | ANIQLANSIN |
| web-sys | 0.3.106 | ANIQLANSIN |
| web-time | 1.1.0 | MIT OR Apache-2.0 |
| web_atoms | 0.2.6 | MIT OR Apache-2.0 |
| webkit2gtk | 2.0.2 | ANIQLANSIN |
| webkit2gtk-sys | 2.0.2 | ANIQLANSIN |
| webview2-com | 0.39.1 | ANIQLANSIN |
| webview2-com-macros | 0.8.1 | ANIQLANSIN |
| webview2-com-sys | 0.39.1 | ANIQLANSIN |
| winapi | 0.3.9 | ANIQLANSIN |
| winapi-i686-pc-windows-gnu | 0.4.0 | ANIQLANSIN |
| winapi-util | 0.1.11 | ANIQLANSIN |
| winapi-x86_64-pc-windows-gnu | 0.4.0 | ANIQLANSIN |
| window-vibrancy | 0.8.1 | Apache-2.0 OR MIT |
| windows | 0.62.2 | ANIQLANSIN |
| windows-collections | 0.3.2 | ANIQLANSIN |
| windows-core | 0.62.2 | ANIQLANSIN |
| windows-future | 0.3.2 | ANIQLANSIN |
| windows-implement | 0.60.2 | ANIQLANSIN |
| windows-interface | 0.59.3 | ANIQLANSIN |
| windows-link | 0.2.1 | ANIQLANSIN |
| windows-numerics | 0.3.1 | ANIQLANSIN |
| windows-result | 0.4.1 | ANIQLANSIN |
| windows-strings | 0.5.1 | ANIQLANSIN |
| windows-sys | 0.45.0 | ANIQLANSIN |
| windows-sys | 0.60.2 | ANIQLANSIN |
| windows-sys | 0.61.2 | ANIQLANSIN |
| windows-targets | 0.42.2 | ANIQLANSIN |
| windows-targets | 0.53.5 | ANIQLANSIN |
| windows-threading | 0.2.1 | ANIQLANSIN |
| windows-version | 0.1.7 | ANIQLANSIN |
| windows_aarch64_gnullvm | 0.42.2 | ANIQLANSIN |
| windows_aarch64_gnullvm | 0.53.1 | ANIQLANSIN |
| windows_aarch64_msvc | 0.42.2 | ANIQLANSIN |
| windows_aarch64_msvc | 0.53.1 | ANIQLANSIN |
| windows_i686_gnu | 0.42.2 | ANIQLANSIN |
| windows_i686_gnu | 0.53.1 | ANIQLANSIN |
| windows_i686_gnullvm | 0.53.1 | ANIQLANSIN |
| windows_i686_msvc | 0.42.2 | ANIQLANSIN |
| windows_i686_msvc | 0.53.1 | ANIQLANSIN |
| windows_x86_64_gnu | 0.42.2 | ANIQLANSIN |
| windows_x86_64_gnu | 0.53.1 | ANIQLANSIN |
| windows_x86_64_gnullvm | 0.42.2 | ANIQLANSIN |
| windows_x86_64_gnullvm | 0.53.1 | ANIQLANSIN |
| windows_x86_64_msvc | 0.42.2 | ANIQLANSIN |
| windows_x86_64_msvc | 0.53.1 | ANIQLANSIN |
| winnow | 0.5.40 | ANIQLANSIN |
| winnow | 1.0.4 | MIT |
| winreg | 0.56.0 | ANIQLANSIN |
| wit-bindgen | 0.57.1 | ANIQLANSIN |
| writeable | 0.6.4 | Unicode-3.0 |
| wry | 0.57.0 | Apache-2.0 OR MIT |
| x11 | 2.21.0 | ANIQLANSIN |
| x11-dl | 2.21.0 | ANIQLANSIN |
| yoke | 0.8.3 | Unicode-3.0 |
| yoke-derive | 0.8.4 | Unicode-3.0 |
| zerofrom | 0.1.8 | Unicode-3.0 |
| zerofrom-derive | 0.1.8 | Unicode-3.0 |
| zerotrie | 0.2.5 | Unicode-3.0 |
| zerovec | 0.11.8 | Unicode-3.0 |
| zerovec-derive | 0.11.6 | Unicode-3.0 |
| zlib-rs | 0.6.8 | Zlib |
| zmij | 1.0.23 | MIT |

</details>
<!-- gen_licenses:rust:end -->

### Native runtime'lar

`third_party/runtimes.toml`, lokal alfa pinlari va staging qilingan `bin/licenses/` dan.

<!-- gen_licenses:runtimes:start -->
| Komponent | Versiya | Litsenziya | Izoh |
| --- | --- | --- | --- |
| FFmpeg | 7.1.1 | LGPL-2.1-or-later | GPL/nonfree/version3 o'chiq, dinamik bog'lanadi (ADR-0004). runtimes.toml ref bo'sh (ANIQLANSIN, R0-RT-1). Reliz bayroqlari: --enable-shared --disable-static --disable-doc --disable-debug --enable-libass --enable-libfreetype --enable-libharfbuzz --enable-libfribidi --enable-libdav1d |
| dav1d | 1.5.4 | BSD-2-Clause | AV1 dasturiy dekoderi. Statik yig'iladi va FFmpeg ichiga bog'lanadi (alohida dylib yo'q); BSD-2 shartiga ko'ra COPYING matni `bin/licenses/local-render/dav1d.COPYING` da. SHA-256 686616b7c69eb88d44459391ab25cac13b6647a3b288835c5784e71c1514a5c5. |
| llama.cpp (ggml) | b11669 | MIT | llama-server va libggml/libllama dylib'lari. runtimes.toml ref bo'sh (ANIQLANSIN, R0-RT-1). |
| whisper.cpp (ggml) | ANIQLANSIN | MIT | runtimes.toml ref bo'sh (ANIQLANSIN, R0-RT-1). Lokal alfa paketiga kirmaydi (ASR: faster-whisper). LICENSE matni lokal yo'q. |
| brotli | 1.2.1 | MIT | Dinamik bog'lanadi (bin/lib). |
| freetype | 2.15.0 | FTL | Dinamik bog'lanadi (bin/lib). FTL yoki GPL-2.0 tanlovi: FTL tanlanadi. |
| fribidi | 1.0.17 | GPL-2.0-or-later AND LGPL-2.1-or-later | Dinamik bog'lanadi (bin/lib). Kutubxona LGPL-2.1-or-later; GPL-2.0 qismi faqat CLI vositasiga tegishli. |
| gettext | 1.0 | GPL-3.0-or-later AND LGPL-2.1-or-later | Dinamik bog'lanadi (bin/lib). Faqat libintl (LGPL-2.1-or-later) ko'chiriladi; GPL-3.0 qismi (gettext vositalari) ilovaga kirmaydi. |
| glib | 2.90.1 | LGPL-2.1-or-later | Dinamik bog'lanadi (bin/lib). LICENSE fayli bottle'da yo'q. |
| graphite2 | 1.3.15 | MIT OR MPL-2.0 OR LGPL-2.1-or-later OR GPL-2.0-or-later | Dinamik bog'lanadi (bin/lib). Ko'p litsenziyali: MIT tanlanadi. |
| harfbuzz | 15.0.0 | MIT | Dinamik bog'lanadi (bin/lib). |
| libass | 0.17.5 | ISC | Dinamik bog'lanadi (bin/lib). |
| libpng | 1.6.59 | libpng-2.0 | Dinamik bog'lanadi (bin/lib). |
| libunibreak | 8.0 | Zlib | Dinamik bog'lanadi (bin/lib). LICENSE fayli bottle'da yo'q. |
| pcre2 | 10.49 | BSD-3-Clause | Dinamik bog'lanadi (bin/lib). |
<!-- gen_licenses:runtimes:end -->

### Shriftlar

<!-- gen_licenses:fonts:start -->
| Shrift | Manba commit | Litsenziya | Mualliflik |
| --- | --- | --- | --- |
| Inter | e7db6ca603fd | OFL-1.1 | Copyright 2020 The Inter Project Authors (https://github.com/rsms/inter). |
<!-- gen_licenses:fonts:end -->

### LGPL talablari va manba taklifi

<!-- gen_licenses:lgpl:start -->
Ilovadagi LGPL komponentlari (FFmpeg, FriBiDi, GLib, gettext/libintl va boshqalar) quyidagi shartlarda
tarqatiladi (LGPL-2.1 6-bo'lim; yuridik xulosa R0-LEG-1 da):

1. **Dinamik bog'lanish.** FFmpeg `--enable-shared --disable-static` bilan yig'iladi; kutubxonalar
   ilova paketida alohida `.dylib`/`.dll` fayllar sifatida turadi (`bin/`, `bin/lib/`) va
   `@loader_path` orqali yuklanadi. Foydalanuvchi ularni mos ABI'li o'z yig'masi bilan almashtira oladi.
2. **GPL/nonfree qismlarsiz.** `--enable-gpl`, `--enable-nonfree`, `--enable-version3` yo'q, libx264/libx265
   qo'shilmaydi (ADR-0004; `scripts/setup_local_render.py` buni tekshiradi). Konfiguratsiya qatori
   `bin/licenses/local-render/manifest.json` da ilova bilan birga beriladi.
3. **Litsenziya matnlari.** LGPL-2.1 to'liq matni va FFmpeg `LICENSE.md` ilova ichida (`bin/licenses/`) va
   "Sozlamalar -> Litsenziyalar" oynasida.
4. **Teskari muhandislik.** EULA LGPL kutubxonalarini o'zgartirish uchun zarur bo'lgan teskari muhandislik
   va disk raskadrovkani taqiqlamaydi.
5. **Manba taklifi** (ilovada ham ko'rsatiladi):

> Lahza Studio tarkibidagi LGPL litsenziyali komponentlarning (FFmpeg 7.1.1 va ro'yxatdagi boshqa LGPL
> kutubxonalar) aynan shu relizda ishlatilgan to'liq manba kodini, yig'ish skriptlari va konfiguratsiya
> bayroqlari bilan birga, mahsulot tarqatilgan kundan boshlab kamida 3 yil davomida har qanday uchinchi
> shaxsga tarqatish xarajatidan oshmaydigan haq evaziga taqdim etamiz. So'rov manzili: ANIQLANSIN
> (rasmiy aloqa e-pochtasi relizdan oldin belgilanadi). FFmpeg manbasi: https://ffmpeg.org/releases/ffmpeg-7.1.1.tar.xz (SHA-256 733984395e0dbbe5c046abda2dc49a5544e7e0e1e2366bba849222ae9e3a03b1).
<!-- gen_licenses:lgpl:end -->

## Modellar (katalogdan yuklanadi)

### Katalog yozuvlari (avtomatik)

<!-- gen_licenses:models:start -->
`catalog/catalog.json`: 12 yozuv.

| Model | Katalog ID | Litsenziya | Muallifni ko'rsatish |
| --- | --- | --- | --- |
| BuzzASR Uzbek (Whisper large-v3 fine-tune) | asr-buzzasr-uzbek (asr, holat: candidate) | MIT |  |
| Gemma 4 26B A4B (GGUF Q4_K_M) | llm-gemma4-26b-a4b-q4 (llm, holat: candidate) | Apache-2.0 |  |
| MediaPipe BlazeFace + LR-ASD | vision-blazeface-lrasd (vision, holat: candidate) | Apache-2.0 (BlazeFace), MIT (LR-ASD) |  |
| Meta Omnilingual ASR - CTC 300M v2 (int8 ONNX) | align-omnilingual-ctc (align, holat: candidate) | Apache-2.0 |  |
| NeuronAI-2B (o'zbekcha, Qwen3.5-2B asosida) | llm-neuronai-2b (llm, holat: candidate) | ANIQLANSIN |  |
| piyola-v2 (Parakeet TDT 0.6B, o'zbekcha) | asr-piyola-v2 (asr, holat: candidate) | CC-BY-4.0 | **Majburiy:** "idrock/piyola-v2 (CC-BY-4.0), asosi nvidia/parakeet-tdt-0.6b-v2" |
| pyannote speaker-diarization-community-1 | diarization-pyannote-community-1 (diarization, holat: candidate) | CC-BY-4.0 | **Majburiy:** "pyannote speaker-diarization-community-1 (CC-BY-4.0)" |
| Qwen3.5 4B (GGUF Q4_K_M) | llm-qwen3.5-4b-q4 (llm, holat: candidate) | Apache-2.0 |  |
| Qwen3.5 9B (GGUF Q4_K_M) | llm-qwen3.5-9b-q4 (llm, holat: candidate) | Apache-2.0 |  |
| rubaiSTT v2 medium | asr-rubaistt-v2-medium (asr, holat: candidate) | Apache-2.0 |  |
| Silero VAD | vad-silero (vad, holat: candidate) | MIT |  |
| whisper-uzbek-medium-callcenter | asr-whisper-uzbek-medium-callcenter (asr, holat: candidate) | ANIQLANSIN |  |
<!-- gen_licenses:models:end -->

### Model oilalari (qo'lda)

| Model | Litsenziya | Muallifni ko'rsatish |
| --- | --- | --- |
| pyannote speaker-diarization-community-1 | CC-BY-4.0 | **Majburiy:** "pyannote speaker-diarization-community-1 (CC-BY-4.0)" |
| idrock/piyola-v2 | CC-BY-4.0 | **Majburiy:** "idrock/piyola-v2, asosi nvidia/parakeet-tdt-0.6b-v2 (CC-BY-4.0)" |
| BuzzASR/uzbek | MIT | |
| islomov/rubaistt_v2_medium | Apache-2.0 | |
| Meta Omnilingual ASR (CTC 300M v2 — standart so'z tekislagich; ONNX int8: OpenVoiceOS/omnilingual-asr-ctc-300m-onnx) | Apache-2.0 (model), CC-BY-4.0 (korpus) | |
| Silero VAD | MIT | |
| MediaPipe BlazeFace | Apache-2.0 | |
| LR-ASD | MIT | |
| Qwen3.5, Gemma 4 | Apache-2.0 | |

O'z fine-tune'ingizda ISSAI/TUIT Uzbek Speech Corpus ishlatilsa, mahsulotga ISSAI belgilagan bayonot qo'shiladi:
"Our product uses ISSAI and TUIT Uzbek Speech Corpus (https://doi.org/10.48342/drss-8q87), which is available under a Creative Commons Attribution 4.0 International License."

## Ixtiyoriy komponentlar (qo'lda; ilovaga qo'shilmaydi)

YouTube havolasidan import (YT-1, [ADR-0010](docs/adr/0010-youtube-havola-import.md)) — standart o'chiq, yurist xulosasidan oldin relizga kirmaydi. Komponentlar o'rnatuvchiga kirmaydi: katalogdan (keyinchalik) yoki dasturchi muhitida `make setup-youtube` bilan olinadi.

| Komponent | Litsenziya | Izoh |
| --- | --- | --- |
| yt-dlp (PyPI paketi) | Unlicense | Python kutubxonasi sifatida, alohida jarayonda. Rasmiy PyInstaller exe'lari GPLv3+ kod o'z ichiga oladi — ular **ishlatilmaydi** |
| yt-dlp-ejs (PyPI paketi) | Unlicense (ANIQLANSIN: ichidagi JS bog'liqliklar) | YouTube JS challenge yechimi; internetdan avtomatik olinmaydi (`remote_components = []`) |
| Deno | MIT | JavaScript runtime (>= 2.3), yt-dlp-ejs uchun |

## Ishlatilmaydi

| Komponent | Sabab |
| --- | --- |
| libx264, libx265 | GPL |
| Meta MMS forced aligner | CC-BY-NC-4.0 (notijorat) |
| InsightFace SCRFD vaznlari | Notijorat |
| YOLOv8-Face | AGPL-3.0 |

Litsenziyasi aniqlanmagan modellar (Abduqayum/whisper-uzbek-medium-callcenter, NeuronAI-2B, alloma-8B) aniqlanmaguncha faqat R0 sinovida ishlatiladi va mahsulotga kirmaydi.

## ANIQLANSIN ro'yxati (avtomatik)

<!-- gen_licenses:unresolved:start -->
Jami 182 ta yozuvda `ANIQLANSIN` bor.

| Turi | Komponent | Versiya | Litsenziya |
| --- | --- | --- | --- |
| runtime | whisper.cpp (ggml) | ANIQLANSIN | MIT |
| model | NeuronAI-2B (o'zbekcha, Qwen3.5-2B asosida) | r0 | ANIQLANSIN |
| model | whisper-uzbek-medium-callcenter | r0 | ANIQLANSIN |

Rust (179 crate, lokal registry'da yo'q): android_system_properties, atk, atk-sys, atomic-waker, base64, bumpalo, bytemuck, cairo-rs, cairo-sys-rs, cesu8, cfg-expr, combine, core_detect, dbus, dlopen2, dlopen2_derive, field-offset, futures-channel, futures-core, futures-executor, futures-io, futures-macro, futures-sink, futures-task, futures-util, gdk, gdk-pixbuf, gdk-pixbuf-sys, gdk-sys, gdkwayland-sys, gdkx11, gdkx11-sys, gio, gio-sys, glib, glib-macros, glib-sys, gobject-sys, gtk, gtk-sys, gtk3-macros, heck, http-body, http-body-util, httparse, hyper, hyper-util, iana-time-zone-haiku, ipnet, is-docker, is-wsl, javascriptcore-rs, javascriptcore-rs-sys, jiff-static, jiff-tzdb, jiff-tzdb-platform, jni, jni-sys, jni-sys-macros, js-sys, libappindicator, libappindicator-sys, libdbus-sys, libloading, libredox, memoffset, ndk, ndk-context, ndk-sys, num_enum, num_enum_derive, objc2-cloud-kit, objc2-core-data, objc2-core-image, objc2-core-location, objc2-core-text, objc2-ui-kit, objc2-user-notifications, pango, pango-sys, pkg-config, portable-atomic, portable-atomic-util, proc-macro-crate, proc-macro-error, proc-macro-error-attr, r-efi, redox_syscall, redox_users, reqwest, serde_spanned, slab, softbuffer, soup3, soup3-sys, syn, sync_wrapper, system-deps, tao-macros, target-lexicon, thiserror, thiserror-impl, tokio-util, toml, toml_datetime, toml_edit, tower, tower-http, tower-layer, tower-service, tracing, tracing-core, try-lock, unicode-segmentation, version-compare, vswhom, vswhom-sys, want, wasi, wasip2, wasm-bindgen, wasm-bindgen-futures, wasm-bindgen-macro, wasm-bindgen-macro-support, wasm-bindgen-shared, wasm-streams, web-sys, webkit2gtk, webkit2gtk-sys, webview2-com, webview2-com-macros, webview2-com-sys, winapi, winapi-i686-pc-windows-gnu, winapi-util, winapi-x86_64-pc-windows-gnu, windows, windows-collections, windows-core, windows-future, windows-implement, windows-interface, windows-link, windows-numerics, windows-result, windows-strings, windows-sys, windows-targets, windows-threading, windows-version, windows_aarch64_gnullvm, windows_aarch64_msvc, windows_i686_gnu, windows_i686_gnullvm, windows_i686_msvc, windows_x86_64_gnu, windows_x86_64_gnullvm, windows_x86_64_msvc, winnow, winreg, wit-bindgen, x11, x11-dl.
<!-- gen_licenses:unresolved:end -->
