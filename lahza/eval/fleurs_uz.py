"""FLEURS uz_uz `test` (Google, CC-BY-4.0) asosida takrorlanuvchi ASR test to'plami.

Tarkib (build/asr-eval/fleurs-uz/, git'ga kirmaydi):
* short/<id>.wav + <id>.txt - 80 ta alohida gap (~10-20 s, har biri o'z VAD -> plan_chunks yo'lida);
* long/long-<n>.wav + .txt - 3 ta ~2.5 daq yaxlit audio: 12 tadan boshqa gaplar sukunat bilan
  ulangan (uzun fayl, VAD bo'laklash va chunk chegaralari muammolarini ko'rsatadi);
* manifest.json - manba revision'i, tanlangan fayllar, sha256.

Tanlov deterministik: arxivning birinchi 260 ta wav'i (oqimda, ~520 MB arxivning bir qismi),
TSV tartibida, raqamsiz (etalon raqam->so'z normallashtirish R0 vazifasi) va har jumla ID'sidan
bittadan. Yuklangan fayllar faqat o'qiladi (ffmpeg / tarfile) - hech narsa ishga tushirilmaydi.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import tarfile
import urllib.request
import wave
from pathlib import Path

import numpy as np

REVISION = "70bb2e84b976b7e960aa89f1c648e09c59f894dd"  # google/fleurs, 2026-10-26 dagi main
BASE_URL = f"https://huggingface.co/datasets/google/fleurs/resolve/{REVISION}/data/uz_uz"
LICENSE = "CC-BY-4.0 (Google FLEURS, https://huggingface.co/datasets/google/fleurs)"
STREAM_LIMIT = 260
N_SHORT = 80
N_LONG = 3
PER_LONG = 12
# Gaplar orasidagi sukunat (s) - aylanma; 2.5 s VAD'ni ham, birlashtirishni ham sinaydi.
GAPS_S = (0.6, 1.2, 0.4, 2.5, 0.8, 1.5)
SR = 16_000


def _sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def download(dl: Path) -> None:
    dl.mkdir(parents=True, exist_ok=True)
    tsv = dl / "test.tsv"
    if not tsv.exists():
        urllib.request.urlretrieve(f"{BASE_URL}/test.tsv", tsv)  # noqa: S310 - qat'iy https URL
    wav_dir = dl / "wav"
    if wav_dir.exists() and len(list(wav_dir.glob("*.wav"))) >= STREAM_LIMIT:
        return
    wav_dir.mkdir(exist_ok=True)
    n = 0
    with urllib.request.urlopen(f"{BASE_URL}/audio/test.tar.gz") as resp, \
            tarfile.open(fileobj=resp, mode="r|gz") as tf:  # noqa: S310
        for m in tf:
            name = os.path.basename(m.name)
            if not m.isfile() or not name.endswith(".wav") or name.startswith("."):
                continue
            src = tf.extractfile(m)
            if src is None:
                continue
            (wav_dir / name).write_bytes(src.read())
            n += 1
            if n >= STREAM_LIMIT:
                break


def _write_wav(path: Path, pcm: np.ndarray) -> None:
    s16 = (np.clip(pcm, -1.0, 1.0) * 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(s16.tobytes())


def build(root: Path) -> Path:
    """root = build/asr-eval. Natija: root/fleurs-uz (manifest.json mavjud bo'lsa - tayyor)."""
    from lahza_engine.media.probe import extract_wav, read_wav_mono

    out = root / "fleurs-uz"
    if (out / "manifest.json").exists():
        return out
    dl = root / "download"
    download(dl)
    have = {p.name for p in (dl / "wav").glob("*.wav")}
    rows = [line.rstrip("\n").split("\t") for line in (dl / "test.tsv").read_text(encoding="utf-8").splitlines()]
    seen: set[str] = set()
    picked: list[list[str]] = []
    for r in rows:
        if r[1] in have and r[0] not in seen and not re.search(r"\d", r[2]):
            seen.add(r[0])
            picked.append(r)
    need = N_SHORT + N_LONG * PER_LONG
    if len(picked) < need:
        raise SystemExit(f"FLEURS: {len(picked)} ta gap topildi, {need} kerak")
    (out / "short").mkdir(parents=True, exist_ok=True)
    (out / "long").mkdir(parents=True, exist_ok=True)
    manifest: dict = {"source": "google/fleurs uz_uz test", "revision": REVISION, "license": LICENSE,
                      "short": [], "long": []}
    for r in picked[:N_SHORT]:
        stem = f"fleurs-{r[0]}"
        wav = out / "short" / f"{stem}.wav"
        extract_wav(dl / "wav" / r[1], wav)  # engine ingest bilan bir xil: 16 kHz mono s16
        (out / "short" / f"{stem}.txt").write_text(r[2] + "\n", encoding="utf-8")
        manifest["short"].append({"id": stem, "fleurs_id": r[0], "file": r[1], "gender": r[6],
                                  "sha256": _sha256(wav)})
    rest = picked[N_SHORT:need]
    for k in range(N_LONG):
        group = rest[k * PER_LONG:(k + 1) * PER_LONG]
        parts: list[np.ndarray] = []
        texts: list[str] = []
        for i, r in enumerate(group):
            tmp = out / "long" / "_tmp.wav"
            extract_wav(dl / "wav" / r[1], tmp)
            pcm, _ = read_wav_mono(tmp)
            tmp.unlink()
            parts.append(np.asarray(pcm, dtype=np.float32))
            parts.append(np.zeros(int(GAPS_S[i % len(GAPS_S)] * SR), dtype=np.float32))
            texts.append(r[2])
        stem = f"long-{k + 1}"
        wav = out / "long" / f"{stem}.wav"
        pcm = np.concatenate(parts)
        _write_wav(wav, pcm)
        (out / "long" / f"{stem}.txt").write_text("\n".join(texts) + "\n", encoding="utf-8")
        manifest["long"].append({"id": stem, "fleurs_ids": [r[0] for r in group],
                                 "files": [r[1] for r in group], "duration_s": round(len(pcm) / SR, 2),
                                 "sha256": _sha256(wav)})
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return out
