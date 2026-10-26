"""O'rnatilgan modellardan backend'larni yig'ish.

Har bir backend ixtiyoriy: yo'q bo'lsa pipeline mos zaxiraga o'tadi. Istisno - ASR: ASR modelisiz
tahlil boshlanmaydi (TZ 13-bo'lim).
"""

from __future__ import annotations

import logging
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from lahza_engine.models.catalog import Task
from lahza_engine.models.store import ModelStore

log = logging.getLogger(__name__)


class MissingModel(RuntimeError):
    pass


@dataclass
class Services:
    asr: Any | None = None
    asr_model_id: str | None = None
    vad: Any | None = None
    aligner: Any | None = None
    aligner_model_id: str | None = None
    diarizer: Any | None = None
    face_detector: Any | None = None
    llm_model_path: Path | None = None
    llm_model_id: str | None = None


def _first_file(path: Path, suffixes: tuple[str, ...]) -> Path | None:
    if path.is_file():
        return path if path.suffix in suffixes else None
    for p in sorted(path.rglob("*")):
        if p.suffix in suffixes:
            return p
    return None


def build_services(store: ModelStore) -> Services:
    s = Services()
    asr = store.default_for(Task.ASR)
    if asr is not None:
        root = Path(asr.path)
        if (root / "model.bin").exists():  # CTranslate2 format
            from lahza_engine.asr.faster_whisper_backend import (
                FasterWhisperBackend,
            )

            device = "cuda" if sys.platform == "win32" else "cpu"
            s.asr = FasterWhisperBackend(root, asr.id, device=device)
        else:
            ggml = _first_file(root, (".bin", ".gguf"))
            if ggml is not None:
                from lahza_engine.asr.whisper_cpp import WhisperCppBackend

                s.asr = WhisperCppBackend(ggml, asr.id)
        s.asr_model_id = asr.id if s.asr else None

    s.vad = _build_vad(store)
    s.aligner = _build_aligner(store)
    if s.aligner is not None:
        m = _align_model(store)
        s.aligner_model_id = m.id if m else None

    diar = store.default_for(Task.DIARIZATION)
    if diar is not None:
        try:
            from lahza_engine.diarize.assign import PyannoteDiarizer

            s.diarizer = PyannoteDiarizer(Path(diar.path))
        except Exception as e:  # noqa: BLE001
            log.warning("diarizatsiya yuklanmadi: %s", e)

    s.face_detector = _build_face_detector(store)

    llm = store.default_for(Task.LLM)
    if llm is not None:
        s.llm_model_path = _first_file(Path(llm.path), (".gguf",))
        s.llm_model_id = llm.id if s.llm_model_path else None
    return s


def _build_vad(store: ModelStore) -> Any | None:
    """Avval Silero ONNX (onnxruntime, torch'siz), keyin `silero-vad` paketi; yo'q bo'lsa None -
    stage_vad energiya VAD'iga o'tadi."""
    m = store.default_for(Task.VAD)
    if m is not None:
        onnx = _first_file(Path(m.path), (".onnx",))
        if onnx is not None:
            try:
                from lahza_engine.vad.silero_onnx import SileroOnnxVad

                return SileroOnnxVad(onnx)
            except Exception as e:  # noqa: BLE001 - ixtiyoriy
                log.warning("Silero ONNX VAD yuklanmadi: %s", e)
    try:
        from lahza_engine.vad.energy import SileroVad

        return SileroVad()
    except Exception:  # noqa: BLE001 - ixtiyoriy
        log.info("Silero VAD yo'q - energiya VAD zaxirasi ishlatiladi")
    return None


def _align_model(store: ModelStore) -> Any | None:
    """Standart ALIGN modeli; tanlanmagan bo'lsa - setup o'rnatgan qat'iy aligner (standart yoqiq)."""
    m = store.default_for(Task.ALIGN)
    if m is not None:
        return m
    from lahza_engine.models.local_aligner import MODEL_ID

    get = getattr(store, "get", None)
    m = get(MODEL_ID) if get is not None else None
    return m if m is not None and m.task == Task.ALIGN else None


def _build_aligner(store: ModelStore) -> Any | None:
    m = _align_model(store)
    if m is None:
        return None
    try:
        from lahza_engine.align.ctc_onnx import CtcAligner

        return CtcAligner.from_dir(Path(m.path))
    except Exception as e:  # noqa: BLE001 - ixtiyoriy: ASR vaqtlari qoladi
        log.warning("CTC aligner yuklanmadi: %s", e)
        return None


def _face_onnx(root: Path) -> Path | None:
    if root.is_file():
        return root if root.suffix == ".onnx" else None
    files = sorted(root.rglob("*.onnx"))
    named = [p for p in files if any(k in p.name.lower() for k in ("face", "blaze"))]
    return (named or files or [None])[0]


def _build_face_detector(store: ModelStore) -> Any | None:
    """Avval BlazeFace ONNX (Task.VISION default), keyin mediapipe, keyin None (xira fon)."""
    m = store.default_for(Task.VISION)
    if m is not None:
        onnx = _face_onnx(Path(m.path))
        if onnx is not None:
            try:
                from lahza_engine.reframe.faces import OnnxBlazeFaceDetector

                return OnnxBlazeFaceDetector(onnx)
            except Exception as e:  # noqa: BLE001
                log.warning("BlazeFace ONNX yuklanmadi: %s", e)
    try:
        from lahza_engine.reframe.faces import MediaPipeDetector

        return MediaPipeDetector()
    except Exception:  # noqa: BLE001
        log.info("yuz detektori yo'q - reframe 'xira fon' layoutiga o'tadi")
    return None
