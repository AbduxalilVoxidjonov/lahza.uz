# Local Uzbek ASR: experimental, not quality approved

The original generic SYSTRAN Whisper base passed synthetic English but failed the real Uzbek
sample. Do not describe that English check as Uzbek quality evidence. Bootstrap now installs
**NavAI Uzbek base**, an actual Uzbek fine-tune. The local registry currently selects the
better **NavAI Uzbek small int8** conversion; an offline `.lzpack` is available for that model.
Both improve recognizability but still make substantial errors. Reliable Uzbek transcription
has **not** been established. No labeled reference was available, so no local WER is reported.
No catalog entries were approved or modified. All installations remain `source="custom"`,
`verified=False`, `self_test_ok=None`.

## Desktop API choice

`lahza_engine.models.local_bootstrap.bootstrap` keeps this exact public signature:

```python
def bootstrap(store: ModelStore, *, consent: bool = False,
              progress: ProgressFn | None = None) -> InstalledModel: ...
```

It downloads `custom:navai-whisper-base-uzbek`, **148,506,445 bytes**, and selects it as ASR default.
Suggested UI label: **NavAI Uzbek base — experimental**. This is not the old generic base.
It requires only existing inference dependencies, not Torch or Transformers. Call in a worker;
`ProgressFn = Callable[[int, int | None], None]` reports aggregate bytes. Callback exceptions,
including cancellation, propagate. Registration follows a successful local CPU load. Serialize
bootstrap jobs per store. Cancellation is cooperative at progress callbacks, not instantaneous
while waiting for HTTP or model loading. Partial downloads remain for retry.

```sh
engine/.venv/bin/python -m pip install -e 'engine[desktop]'
engine/.venv/bin/python -m pip install --no-deps -r engine/requirements-desktop-nodeps.txt
engine/.venv/bin/python scripts/bootstrap_local_models.py --download --consent --with-vad
```

Both `--download` and `--consent` are required before network or store creation. Optional
`--models-dir PATH` overrides `Settings().models_dir`, which normally honors `LAHZA_DATA_DIR`.
`--with-vad` also installs official Silero ONNX. From a desktop job, call
`bootstrap_vad(store, consent=True, progress=callback)` separately (same signature and return
type); ASR and VAD report separate progress totals. VAD's model progress excludes its 1 KB license.
Calling base bootstrap again intentionally selects base, replacing the current small default.

PyAV is not used (ADR-0015): audio is decoded by the LGPL FFmpeg into a 16 kHz mono float32
array (`lahza_engine.media.pcm`) and faster-whisper is imported through `asr/fw_compat.py`.
This task installed dependencies into engine/.venv, and conversion dependencies only into
build/asr-convert-venv. No runtime setup scripts, API files, or UI files were edited.

## Offline small model import

Ready artifact: `build/local-asr-compare/navai-small-uzbek-silero.lzpack`.
Size: **251,966,951 bytes**. SHA-256:
`e51e73392bcc3ba27046c46be53213194b4c583b22ed2bd668c86640706a12df`.
It contains small int8, Silero ONNX, licenses, notices, and provenance; no Python or executable.
It is an unsigned local custom pack, not an approved signed catalog distribution.
Import verifies each file's manifest SHA-256 and size. Installations enforcing a pack signing
key require a correctly signed pack; this artifact does not bypass that policy.

```python
from pathlib import Path
from lahza_engine.config import Settings
from lahza_engine.models.catalog import Task
from lahza_engine.models.lzpack import import_pack
from lahza_engine.models.store import ModelStore

store = ModelStore(Settings().models_dir)
import_pack(store, Path("build/local-asr-compare/navai-small-uzbek-silero.lzpack"))
# Existing import preserves an existing default; explicitly select imported models.
store.set_default(Task.ASR, "custom:navai-whisper-small-uzbek")
store.set_default(Task.VAD, "custom:silero-v5.1.2")
# Invalidate cached services; then use a fresh analysis cache.
```

The default store is `/Users/me/Library/Application Support/Lahza Studio/Models` on this Mac.
Physical folders `asr/navai-whisper-base-uzbek`, `asr/navai-whisper-small-uzbek`, and
`vad/silero-v5.1.2` contain no Windows-invalid colons. Registry IDs may contain colons.

## Pinned provenance and independent conversion

[NavAI base](https://huggingface.co/navai-uz/whisper-base-uzbek) and
[small](https://huggingface.co/navai-uz/whisper-small-uzbek) are Apache-2.0 Uzbek fine-tunes.
Their model card claims 753 hours of human-transcribed training data and reports benchmark
WERs; those are author claims, not Lahza measurements. LICENSE and NOTICE are retained,
including training-corpus attribution. The upstream OpenAI model/tokenizer is MIT.

Base official source revision: `377a0da45851aeec93fe9883dc39492c38858533`.
Original safetensors: 290,403,936 bytes, SHA-256
`c1209e5d6215fa5021e336a523bae6c77bdb7049efdf00db8b5bd7abdb3ad0b8`.
The initially suggested `07fdc4db...` README revision was not used; actual downloaded source
revision is pinned above.

Download-only base uses [Mavlyudabegim's CT2 conversion](https://huggingface.co/Mavlyudabegim/navai-base-uzbek-ct2),
revision `44ca86c6da92fd9eecaf09e25655d222cdc6cde9`. The repository has no model card;
we did not trust its name alone: its `model.bin` **exactly matches** our independent FP16
conversion of the official pinned NavAI base weights, SHA-256
`cb5d527b50c63d80c82d6608d2da8713d4ce21e391b0da4402bf7659f2685699`.
Bootstrap hard-pins that hash. It fetches the stock multilingual tokenizer from
`Systran/faster-whisper-base` revision `ebe41f70d5b6dfa9166e2c581c45c9c0cfc57b66`.
We compared tokenizer vocabulary IDs: all shared tokens match NavAI's generated tokenizer;
NavAI additionally includes the standard timestamp tokens. Both tokenizers produced the same
base transcript on this sample. The stock tokenizer is bundled, avoiding runtime downloads.

Small official source revision: `4b432caf21c2752bca3384b5df1d41cf0da2801d`.
Original safetensors: **966,995,080 bytes**, SHA-256
`3662e1baf3a9bc9a3b3df9bb75060c99708f8c461df19e0e3acd80ae6814411e`.
Converted int8 `model.bin`: **244,612,629 bytes**, SHA-256
`e52f815d49b7c7c02d597f746c123a9b1be2dde6b1d4004017e9ec964a8aef3a`.

Conversion environment commands actually run:

```sh
engine/.venv/bin/python -m venv build/asr-convert-venv
build/asr-convert-venv/bin/python -m pip install 'ctranslate2==4.8.3' 'transformers>=4.46,<5' torch safetensors
```

Resolved versions: CTranslate2 4.8.3, Transformers 4.57.6, Torch 2.14.1. Only the converter
venv has Torch/Transformers. Source files were downloaded via public HF metadata + resolve URLs
with httpx, using exact revisions and `models.downloader.download`; each original file's size,
Git blob ID or LFS SHA-256 was checked before registration. Metadata and source files remain in
`build/local-asr-compare/navai-{base,small}-source/`.

Conversion commands, with offline mode set, used the [official TransformersConverter](https://opennmt.net/CTranslate2/guides/transformers.html):

```sh
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 build/asr-convert-venv/bin/python - <<'PY'
from pathlib import Path
from transformers import WhisperTokenizerFast
from ctranslate2.converters import TransformersConverter
src = Path('build/local-asr-compare/navai-small-source')
WhisperTokenizerFast.from_pretrained(str(src), local_files_only=True).backend_tokenizer.save(str(src / 'tokenizer.json'))
TransformersConverter(str(src), copy_files=['tokenizer.json', 'preprocessor_config.json'], load_as_float16=True).convert('build/local-asr-compare/navai-small-ct2', quantization='int8')
PY
```

For the independent base comparison we converted `navai-base-source` with quantization
`float16` to `navai-base-fp16`. All output file hashes and original source hashes are in each
installed model's `provenance.json`; small's provenance is included in the pack.
The source downloads for each chosen model stay below 2 GB. BuzzASR Uzbek's original weights
(3,087,130,976 bytes) and rubaiSTT medium's (3,055,544,304 bytes) exceeded the budget and were
not downloaded. A third-party quantized rubai GGML option exists, but whisper.cpp was not
installed; Homebrew's available formula adds other runtimes, so we did not expand setup here.

Silero is official [snakers4/silero-vad](https://github.com/snakers4/silero-vad), v5.1.2 commit
`6478567951ae5c9979ad7b234185b5515f4be7a1`. ONNX size: **2,327,524 bytes**, SHA-256
`2623a2953f6ff3d2c1e61740c6cdb7168133479b267dfef114a4a3cc5bdd788f`.
The model and MIT license are hash pinned. It uses existing ONNX Runtime CPU, no Torch.

## Real Uzbek comparison and VAD diagnosis

Source: `build/local-smoke/source/nauuJZeQb0I-60-210.mp4` (150 seconds).
All speech processing remained local; no user audio was uploaded.

```sh
ffmpeg -hide_banner -loglevel error -y -i build/local-smoke/source/nauuJZeQb0I-60-210.mp4 -t 30 -ac 1 -ar 16000 build/local-asr-compare/uzbek-30s.wav
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 engine/.venv/bin/python build/local-asr-compare/compare.py
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 engine/.venv/bin/python build/local-asr-compare/compare_chunks.py
HF_HUB_OFFLINE=1 engine/.venv/bin/python build/local-asr-compare/compare_decoding.py
```

Comparison scripts/results are retained in build/local-asr-compare. They block
`socket.socket.connect`, use CPU int8, language `uz`, and local-only model directories.

| Model | Direct 30-second result | Decode time |
| --- | --- | --- |
| Generic SYSTRAN base | Garbled multilingual fragments; unsuitable here | 12.690 s |
| NavAI Uzbek base | 42 words; recognizable project discussion, substantial errors | 2.436 s |
| NavAI Uzbek small int8 | 65 words; more recovered Uzbek phrases, still substantial errors | 6.605 s |

Installed small through `build_services`: **65 words**, **7.311 s** including load, saved to
`installed-small-result.json`. Example output (not a reference transcript):

> iqtibos loyihasida juda koʻp mutafakkirlarni tadbirkorlikni marketologlarni oʻtmishday oʻtgan psixologlarni

The tail contains malformed phrases such as “debimiz mashhur qizimiz”; recognizability does
not establish accuracy. Turning off timestamp tokens did not resolve these errors and was
not made a backend default. Both models were also decoded using the exact first pipeline
chunk boundaries: energy 0–29.840 s, Silero 0–27.750 s. Small remained more recognizable,
but Silero's first-chunk output ended in repeated letter words; this is a remaining failure.

Cached energy VAD coverage: **129.12/150 s (86.08%)**, **27.93/30 s (93.1%)**. After padding and
merging, six ASR chunks cover nearly all the recording:
`[0,29840], [29980,58730], [58750,87890], [88030,116540], [116740,142100], [142360,150200]`.
Thus VAD was not discarding most of this sample. Silero found **92.585%** full-recording speech
coverage. It is a better speech-aware default, but did not solve ASR errors on its own.
`silero-vad.json` and `chunk-comparison.json` retain the measured boundaries and transcripts.

## Backend changes and verification

FasterWhisperBackend explicitly uses standard compression/log-probability/no-speech thresholds
2.4 / -1.0 / 0.6, word timestamps, no previous-text conditioning, and `local_files_only=True`.
These thresholds trigger standard decoding fallback; they do not guarantee hallucination-free
output. Tokens without a real letter or number are rejected after normalization. Unicode
modifier apostrophes such as `ʻ` are rejected even though `str.isalnum()` returns True for them;
words such as `oʻzbek` and `gʻoya` remain. Unrelated TypeError failures are no longer retried
as though they were an unsupported hotwords argument.

```sh
engine/.venv/bin/python -m pytest engine/tests/test_local_bootstrap.py engine/tests/test_asr_faster_whisper.py engine/tests/test_models.py engine/tests/test_ml_services.py engine/tests/test_ml_vad.py engine/tests/test_local_bootstrap_api.py engine/tests/test_api_models.py
engine/.venv/bin/python -m ruff check engine/src/lahza_engine/models/local_bootstrap.py engine/src/lahza_engine/asr/faster_whisper_backend.py engine/tests/test_local_bootstrap.py engine/tests/test_asr_faster_whisper.py
engine/.venv/bin/python -m pip check
```

Results: **45 passed**, plus **11 lzpack tests passed**; Ruff passed, no broken dependency requirements.
A clean temporary-store import of the real pack loaded small + Silero through `build_services`
and returned the same **65 words in 8.711 s** with socket connections blocked; see
`build/local-asr-compare/pack-import-result.json`. Coverage includes
consent/cancellation, custom registration, revision/budget/hash/load failures, aggregate
progress, VAD registration, punctuation hallucination rejection, preserved Uzbek words,
local-only loading, and the existing PM-owned API tests. The 150-second analyze/export rerun
belongs to PM and is not claimed here. Use a fresh episode/cache and invalidate services:
old cached ASR/VAD output does not reflect the new model or filtering.
