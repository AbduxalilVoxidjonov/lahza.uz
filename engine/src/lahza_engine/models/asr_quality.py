"""Transkripsiya sifati: "Tez" (NavAI base, standart) yoki "Aniq" (NavAI small, ixtiyoriy).

* Birinchi ishga tushirish setup'i (models/setup.py) faqat base ni o'rnatadi - bu modul uni
  o'zgartirmaydi.
* "Aniq" = `custom:navai-whisper-small-uzbek` (FLEURS uz WER 15.4%, RTF 0.182; base: 19.8%,
  0.068). O'rnatish mavjud `.lzpack` yo'li orqali: pinned paket (sha256 + hajm) yuklanadi
  (`models.downloader.download`, davom ettirish/disk tekshiruvi bilan) yoki foydalanuvchi
  tanlagan lokal `.lzpack` fayli, so'ng `models.lzpack.import_pack`. Har ikki yo'lda
  o'rnatilgan `model.bin` ning sha256 i mustaqil konversiya xeshiga solishtiriladi.
* Yuklash manzili rasmiy hostingga joylanmagan: `LAHZA_ASR_ACCURATE_PACK_URL` (https, bir
  nechta bo'lsa vergul/bo'shliq bilan) sozlangandagina tarmoqdan yuklash taklif qilinadi.
* Tanlov = `store.set_default(Task.ASR, ...)`. ASR model ID tahlil kesh kalitida
  (core/analyze.py `StageDef("asr", model_id=...)`, montage/raw_asr.py identity) - yangi
  tahlillar tanlangan modelni ishlatadi, eski natijalar majburan qayta hisoblanmaydi.
"""
from __future__ import annotations

import os
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any, Literal

from lahza_engine.core.errors import MODEL_MISSING, CodedError
from lahza_engine.core.runner import Cancelled
from lahza_engine.models import local_bootstrap
from lahza_engine.models.catalog import Task
from lahza_engine.models.downloader import download, sha256_file
from lahza_engine.models.store import InstalledModel, ModelStore

Mode = Literal["fast", "accurate"]

FAST_MODEL_ID = local_bootstrap.MODEL_ID
ACCURATE_MODEL_ID = "custom:navai-whisper-small-uzbek"
# build/local-asr-compare/navai-small-uzbek-silero.lzpack (docs/local-models.md).
ACCURATE_PACK_SHA256 = "e51e73392bcc3ba27046c46be53213194b4c583b22ed2bd668c86640706a12df"
ACCURATE_PACK_SIZE = 251_966_951
# navai-uz/whisper-small-uzbek 4b432caf..., CTranslate2 4.8.3 int8 konversiyasi.
ACCURATE_WEIGHTS_SHA256 = "e52f815d49b7c7c02d597f746c123a9b1be2dde6b1d4004017e9ec964a8aef3a"
PACK_URL_ENV = "LAHZA_ASR_ACCURATE_PACK_URL"
DOWNLOAD_FRACTION = 0.8  # umumiy progressning yuklashga ajratilgan qismi

Progress = Callable[[str, float], None]


def pack_urls() -> list[str]:
    raw = os.environ.get(PACK_URL_ENV, "")
    return [u for u in re.split(r"[\s,]+", raw) if u.startswith("https://")]


def _usable(model: InstalledModel | None) -> bool:
    if model is None or model.task != Task.ASR:
        return False
    root = Path(model.path)
    return (root / "model.bin").is_file()


def installed(store: ModelStore, mode: Mode) -> InstalledModel | None:
    model = store.get(FAST_MODEL_ID if mode == "fast" else ACCURATE_MODEL_ID)
    return model if _usable(model) else None


def current_mode(store: ModelStore) -> str:
    model = store.default_for(Task.ASR)
    if model is None:
        return "none"
    if model.id == ACCURATE_MODEL_ID:
        return "accurate"
    if model.id == FAST_MODEL_ID:
        return "fast"
    return "custom"


def status(store: ModelStore) -> dict[str, Any]:
    default = store.default_for(Task.ASR)
    accurate = installed(store, "accurate") is not None
    return {
        "mode": current_mode(store),
        "current_model_id": default.id if default else None,
        "fast": {"model_id": FAST_MODEL_ID, "installed": installed(store, "fast") is not None},
        "accurate": {"model_id": ACCURATE_MODEL_ID, "installed": accurate,
                     "download_bytes": 0 if accurate else ACCURATE_PACK_SIZE,
                     "download_available": bool(pack_urls())},
    }


def select(store: ModelStore, mode: Mode) -> InstalledModel:
    """O'rnatilgan modelni standart ASR qiladi; o'rnatilmagan bo'lsa - `model_missing`."""
    model = installed(store, mode)
    if model is None:
        raise CodedError(MODEL_MISSING, f"ASR modeli o'rnatilmagan: {mode}", mode=mode)
    store.set_default(Task.ASR, model.id)
    return model


def install_accurate(
    store: ModelStore,
    *,
    consent: bool = False,
    pack_path: Path | None = None,
    progress: Progress | None = None,
    is_cancelled: Callable[[], bool] = lambda: False,
) -> InstalledModel:
    """small ni o'rnatadi (yuklab yoki lokal paketdan) va standart ASR qiladi."""
    from lahza_engine.models import lzpack

    def report(stage: str, fraction: float) -> None:
        if is_cancelled():
            raise Cancelled()
        if progress:
            progress(stage, fraction)

    existing = installed(store, "accurate")
    if existing is not None:
        store.set_default(Task.ASR, existing.id)
        report("verify", 1.0)
        return existing
    downloaded: Path | None = None
    if pack_path is None:
        if not consent:
            raise ValueError("Yuklash uchun foydalanuvchi roziligi kerak")
        urls = pack_urls()
        if not urls:
            raise RuntimeError("Aniq rejim paketi uchun yuklash manzili sozlanmagan. "
                               ".lzpack faylini tanlab import qiling.")
        downloaded = store.root / ".downloads" / "navai-whisper-small-uzbek.lzpack"
        report("download", 0.0)
        download(urls, downloaded, ACCURATE_PACK_SHA256, ACCURATE_PACK_SIZE,
                 progress=lambda have, total: report(
                     "download", DOWNLOAD_FRACTION * (have / total if total else 0.0)))
        pack_path = downloaded
        start = DOWNLOAD_FRACTION
    else:
        start = 0.0
    previous_vad = store.default_for(Task.VAD)
    try:
        result = lzpack.import_pack(
            store, pack_path,
            progress=lambda f: report("import-pack", start + (1 - start) * 0.95 * f),
            is_cancelled=is_cancelled)
    except lzpack.PackError:
        if is_cancelled():
            raise Cancelled() from None
        raise
    if ACCURATE_MODEL_ID not in result.get("imported", []):
        raise ValueError("Paketda aniq rejim modeli (NavAI small) yo'q")
    model = store.get(ACCURATE_MODEL_ID)
    if model is None or not _usable(model):
        raise ValueError("Aniq rejim modeli fayllari topilmadi")
    report("verify", start + (1 - start) * 0.97)
    if sha256_file(Path(model.path) / "model.bin") != ACCURATE_WEIGHTS_SHA256:
        raise ValueError("Aniq rejim modeli sha256 mos emas")
    # Paket o'z VAD ini ham olib keladi; ishlayotgan standart VAD almashtirilmaydi.
    if previous_vad is not None:
        store.set_default(Task.VAD, previous_vad.id)
    store.set_default(Task.ASR, model.id)
    if downloaded is not None:
        downloaded.unlink(missing_ok=True)
    report("verify", 1.0)
    return model
