# Model katalogi

Katalog — dastur qaysi modelni qaysi kompyuterga yuklashini belgilaydigan imzolangan JSON (ADR-0002). Fayl: `catalog/catalog.json`, sxema: `engine/src/lahza_engine/models/catalog.py`.

## Yozuv tuzilmasi

```json
{
  "id": "asr-piyola-v2",
  "task": "asr",
  "name": "piyola-v2 (Parakeet TDT 0.6B, o'zbekcha)",
  "version": "r0",
  "backend": "nemo-onnx",
  "files": [{"path": "model.onnx", "urls": ["https://...", "https://zaxira/..."], "sha256": "…", "size_bytes": 123}],
  "platforms": ["darwin-arm64", "win32-x86_64"],
  "tiers": ["lite", "standard", "pro"],
  "min_ram_gb": null,
  "min_vram_gb": null,
  "license": "CC-BY-4.0",
  "source_url": "https://huggingface.co/idrock/piyola-v2",
  "attribution": "…",
  "status": "candidate",
  "eval": {"score": 0.0, "wer_uzpodcast": 0.0},
  "notes": "…"
}
```

| Maydon | Qoida |
| --- | --- |
| `task` | `asr`, `align`, `vad`, `diarization`, `vision`, `llm` |
| `backend` | `whisper.cpp`, `faster-whisper`, `nemo-onnx`, `llama.cpp`, `onnxruntime`, `pyannote`, `silero`, `ctc-aligner` |
| `status` | `candidate` — baholanmagan, o'rnatilmaydi; `approved` — R0'dan o'tgan; `deprecated` — yangi o'rnatishga taklif qilinmaydi |
| `approved` uchun | har faylda `sha256`, `size_bytes` va kamida bitta URL majburiy (validator rad etadi) |
| `eval.score` | Shu vazifa ichida tanlov tartibi (yuqorisi afzal) |

## Hozirgi holat

Katalogda faqat `candidate` yozuvlar: TZ'da sanalgan modellar, manbasi va litsenziyasi bilan. URL va sha256 bo'sh — ular R0'da model formatga o'girilib, o'lchanib, joylashtirilgandan keyin to'ldiriladi. Shu sababli onboarding hozir "R0 bosqichida" xabarini ko'rsatadi.

## Avtomatik tanlov algoritmi (`select_bundle`)

1. Apparat aniqlanadi va daraja hisoblanadi (`models/hardware.py`, TZ 2-bo'lim jadvali).
2. Har vazifa uchun `approved` yozuvlar olinadi.
3. Har biri uchun moslik: platforma → RAM → VRAM (Apple Silicon'da umumiy xotira) → disk joyi. Mos kelmagani sabab bilan chiqariladi ("8 GB VRAM kerak, sizda 4 GB").
4. Daraja `tiers` ichida bo'lganlar afzal; ular ichida `eval.score` eng yuqorisi.
5. Natija: har vazifa uchun bitta yozuv yoki `null` va sabab. LLM `null` bo'lsa — Lite rejim.

## Imzolash

```bash
python scripts/catalog_keygen.py            # bir marta: kalitlar juftligi (maxfiy kalit repoga KIRMAYDI)
python scripts/catalog_sign.py catalog/catalog.json --key <maxfiy.key>
```

* Imzo: Ed25519, kanonik JSON (`signature` maydonisiz, kalitlar saralangan, bo'shliqsiz, UTF-8).
* Ochiq kalit ilovaga build vaqtida `LAHZA_CATALOG_PUBKEY` muhit o'zgaruvchisi orqali kiritiladi (`engine.rs`: `option_env!`).
* Imzo yaroqsiz bo'lsa engine katalogni rad etadi; `LAHZA_DEV=1` bo'lsagina imzosiz katalog qabul qilinadi.

## Yangi modelni qo'shish jarayoni

1. `candidate` yozuv: manba, litsenziya (aniq bo'lmasa `ANIQLANSIN` — mahsulotga kirmaydi).
2. Formatga o'girish (GGML / CTranslate2 / ONNX / GGUF) va o'z serverga yoki ruxsat etilgan hostingga joylash (TZ 19-bo'lim: qayerda — ochiq savol).
3. `eval/` skriptlari bilan oltin to'plamlarda o'lchash; natija `eval/results/<model_id>.json`.
4. `python scripts/catalog_add_file.py <id> <fayl> --url <URL>` — sha256 va hajm avtomatik yoziladi.
5. `status: approved`, `eval.score`, `tiers`, `min_*_gb` to'ldiriladi; katalog qayta imzolanadi; PR ko'rib chiqiladi.

## Katalogdan tashqari modellar

Yashirin ilg'or sozlama: `Models/llm/*.gguf` papkasiga fayl tashlash + "Qayta skanerlash". Faqat GGUF sarlavhali fayllar qabul qilinadi, bajariladigan fayllar rad etiladi, belgisi "sifat kafolatlanmaydi" (`models/store.py`).

## Oflayn ko'chirish (.lzpack)

Internetli kompyuterda yuklangan modellar `Models/` papkasi + `installed.json` manifest + imzo sifatida `.lzpack` ga o'raladi va USB orqali import qilinadi (M2-APP-9).
