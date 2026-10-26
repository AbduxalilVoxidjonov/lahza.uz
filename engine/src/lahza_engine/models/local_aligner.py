"""Pinned CTC forced-aligner installer (Omnilingual ASR CTC 300M v2, int8 ONNX, Apache-2.0).

So'z vaqtlarini aniqlash (TZ 6-bo'lim) uchun standart akustik model. Fayllar qat'iy reviziya va
sha256 bilan yuklanadi; tarmoqsiz qayta tekshiriladi (`verify_installation`). Torch kerak emas.
"""
from __future__ import annotations

import json
from pathlib import Path

from lahza_engine.models.catalog import Task
from lahza_engine.models.downloader import ProgressFn, download, sha256_file
from lahza_engine.models.store import InstalledModel, ModelStore

REPO = "OpenVoiceOS/omnilingual-asr-ctc-300m-onnx"
REVISION = "bc55e1de19af8a907b0a010d06fc4637a2d5bf0c"
UPSTREAM = "facebook/omniASR-CTC-300M"
BASE_URL = f"https://huggingface.co/{REPO}/resolve/{REVISION}"
MODEL_ID = "custom:omniasr-ctc-300m-v2-int8"
MODEL_FOLDER = "omniasr-ctc-300m-v2-int8"
LICENSE = "Apache-2.0"
# (fayl, hajm, sha256) - reviziyadan mustaqil hisoblangan; model sha256 HF LFS bilan mos.
FILES: tuple[tuple[str, int, str], ...] = (
    ("model.int8.onnx", 328094283, "38a6cc569d46eb382f27d85b3208b883e834ff281b2057a606ec79e4ae501545"),
    ("tokens.txt", 90630, "7d99997ef207ff14c2cfe825f2aa037528ea250113cc3c6392bfe49326884ba6"),
    ("LICENSE", 581, "a70a523bafbb595c2844104feb313d204904dac91c3d186c05f22a10a71c7a94"),
    ("README.md", 6296, "da9da66361beabb49ddf208fa5901551a8ca7239cd49ef827f9344b2467b1f8d"),
)
MODEL_SIZE = sum(size for _, size, _ in FILES)
# `align.ctc_onnx.CtcAligner.from_dir` sozlamalari: blank `<s>`=0, so'z ajratgich - bo'shliq
# ("|" lug'atda oddiy belgi), 20 ms kadr. end_pad_ms: 150 s o'zbekcha nutqda energiya/sukunat
# chegaralari bilan o'lchangan (oxirlar ~70 ms erta chiqadi); 15 s bo'lak - aniqlik 30 s bilan
# bir xil, eng yuqori xotira ~2 GB o'rniga ~1.4 GB (150 s audio, M-seriya Mac).
ALIGNER_CONFIG = {"vocab": "tokens.txt", "blank": 0, "separator": " ", "apostrophe": "'",
                  "frame_ms": 20, "max_chunk_ms": 15000, "end_pad_ms": 60, "normalize": True}


def verify_installation(target: Path) -> None:
    """Tarmoqsiz: barcha qat'iy fayllar hajmi va sha256, sozlama va provenance."""
    for name, size, digest in FILES:
        path = target / name
        if not path.is_file() or path.stat().st_size != size or sha256_file(path) != digest:
            raise ValueError(f"aligner fayli mos emas: {name}")
    conf = json.loads((target / "aligner.json").read_text(encoding="utf-8"))
    if conf != ALIGNER_CONFIG:
        raise ValueError("aligner.json mos emas")
    source = json.loads((target / "provenance.json").read_text(encoding="utf-8"))
    if source.get("repository") != REPO or source.get("revision") != REVISION:
        raise ValueError("aligner provenance mos emas")


def _register(store: ModelStore, target: Path) -> InstalledModel:
    model = InstalledModel(id=MODEL_ID, task=Task.ALIGN, version=REVISION, path=str(target),
                           source="custom", verified=False)
    store.register([model])
    return model


def install_model(store: ModelStore, *, consent: bool = False,
                  progress: ProgressFn | None = None) -> InstalledModel:
    if not consent:
        raise ValueError("Model installation requires consent=true")
    target = store.model_dir(Task.ALIGN, MODEL_FOLDER).resolve()
    try:
        verify_installation(target)
    except (OSError, ValueError, KeyError, TypeError):
        pass  # yo'q yoki buzilgan: qayta yuklanadi (download qisman fayldan davom etadi)
    else:
        if progress:
            progress(MODEL_SIZE, MODEL_SIZE)
        return _register(store, target)
    done = 0
    records = []
    for name, size, digest in FILES:
        url = f"{BASE_URL}/{name}"

        def report(have: int, _total: int | None, base: int = done) -> None:
            if progress:
                progress(base + have, MODEL_SIZE)

        download([url], target / name, digest, size, progress=report)
        done += size
        records.append({"path": name, "url": url, "size_bytes": size, "sha256": digest})
    config = target / "aligner.json"
    config.write_text(json.dumps(ALIGNER_CONFIG, indent=2) + "\n", encoding="utf-8")
    records.append({"path": config.name, "sha256": sha256_file(config)})
    provenance = {"repository": REPO, "revision": REVISION, "upstream_model": UPSTREAM,
                  "upstream_variant": "omniASR_CTC_300M_v2 (dynamic int8 ONNX)",
                  "license": LICENSE, "source_url": f"https://huggingface.co/{REPO}",
                  "catalog_approved": False, "files": records}
    temporary = target / "provenance.tmp"
    temporary.write_text(json.dumps(provenance, indent=2) + "\n", encoding="utf-8")
    temporary.replace(target / "provenance.json")
    verify_installation(target)
    if progress:
        progress(MODEL_SIZE, MODEL_SIZE)
    return _register(store, target)
