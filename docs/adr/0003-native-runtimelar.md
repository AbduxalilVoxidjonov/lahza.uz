# ADR-0003: Inference uchun native runtime'lar

* Holat: Qabul qilindi
* Sana: 2026-10-14
* TZ bo'limi: 3, 5, 7

## Kontekst
CTranslate2 (faster-whisper) Apple Silicon GPU'ni (Metal) qo'llamaydi. PyTorch'ni sidecar ichiga qo'shish o'rnatuvchini juda kattalashtiradi va mo'rt qiladi.

## Qaror
* ASR: macOS va Windows AMD/Intel — whisper.cpp (Metal, Core ML, Vulkan); Windows + NVIDIA — faster-whisper (CUDA).
* LLM: llama.cpp `llama-server` (Metal, CUDA, Vulkan), GGUF Q4_K_M; dastur ichida yetkaziladi, faqat highlight bosqichida ishga tushadi.
* Ko'rish va CTC: ONNX Runtime (Mac'da Core ML, Windows'da CUDA/DirectML provayderlari).
* PyTorch faqat zarur joyda (pyannote) va R0'da Core ML/ONNX portlari bilan almashtirish ko'rib chiqiladi.

## Oqibatlar
* Modellar bir nechta formatga o'giriladi (GGML, CTranslate2, ONNX) — katalogda `backend` maydoni.
* Runtime versiyalari `third_party/runtimes.toml` da mahkamlanadi.
