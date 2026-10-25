"""Offline raw-video captions using the same ASR chunks/word grouping as episode import."""
from __future__ import annotations

import hashlib
import json
import logging
import tempfile
import threading
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

from lahza_engine.asr.base import AsrOptions, dedupe_overlaps, plan_chunks
from lahza_engine.core.runner import Cancelled
from lahza_engine.core.services import Services
from lahza_engine.media.probe import extract_wav, fast_hash, read_wav_mono
from lahza_engine.media.tools import find_tool, run
from lahza_engine.models.catalog import Task
from lahza_engine.models.store import InstalledModel, ModelStore
from lahza_engine.text.orthography import normalize
from lahza_engine.text.sentences import build_sentences
from lahza_engine.types import Sentence
from lahza_engine.vad.energy import energy_vad

if TYPE_CHECKING:
    from lahza_engine.montage.analyze import SourceAnalysis

log = logging.getLogger(__name__)
CACHE_VERSION = 1


def _identity(model: InstalledModel | None) -> dict | None:
    if model is None:
        return None
    root = Path(model.path)
    files = [root] if root.is_file() else sorted(p for p in root.rglob("*") if p.is_file())
    return {"model": model.model_dump(mode="json"), "files": [
        (str(p.resolve()), p.stat().st_size, p.stat().st_mtime_ns, p.stat().st_ctime_ns)
        for p in files]}


def transcribe_source(
    source: SourceAnalysis, store: ModelStore, services: Callable[[], Services],
    cache_dir: Path, cancel: threading.Event, on_progress: Callable[[float], None] | None = None,
) -> SourceAnalysis:
    """Missing/unusable ASR keeps basic montage; planner reports missing caption data.

    Cache contains only complete transcripts and is independent of template/captions toggle.
    No registry, episode, or visual-analysis cache is modified here.
    """
    def check() -> None:
        if cancel.is_set():
            raise Cancelled()

    def progress(fraction: float) -> None:
        check()
        if on_progress:
            on_progress(fraction)

    check()
    if not source.media.has_audio:
        return source
    model = store.default_for(Task.ASR)
    if model is None or model.task != Task.ASR:
        return source
    from lahza_engine.montage.analyze import enrich_with_transcript

    try:
        identity = {"version": CACHE_VERSION,
                    "source": source.media.hash or fast_hash(source.media.path),
                    "asr": _identity(model), "vad": _identity(store.default_for(Task.VAD))}
        key = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
        cached = cache_dir / f"raw-asr-{key}.json"
        check()
        if cached.is_file():
            try:
                data = json.loads(cached.read_text(encoding="utf-8"))
                sentences = [Sentence.model_validate(s) for s in data["sentences"]]
                if data["key"] == key:
                    progress(1)
                    return enrich_with_transcript(source, sentences)
            except (OSError, ValueError, KeyError, TypeError):
                pass  # interrupted/corrupt cache is never treated as a transcript
        svc = services()
        check()
        if svc.asr is None:
            return source
        actual_id = svc.asr_model_id or getattr(svc.asr, "model_id", None)
        if actual_id != model.id:
            raise RuntimeError("ASR services/default mismatch")
        with tempfile.TemporaryDirectory(prefix="lahza-raw-asr-") as directory:
            work = Path(directory)
            wav = extract_wav(source.media.path, work / "audio.wav")
            progress(.1)
            pcm, rate = read_wav_mono(wav)
            check()
            try:
                speech = svc.vad(pcm, rate) if svc.vad is not None else energy_vad(pcm, rate)
            except Exception:
                check()
                speech = energy_vad(pcm, rate)
            check()
            chunks = plan_chunks(speech)
            duration = min(source.media.duration_ms, round(len(pcm) * 1000 / rate))
            words = []
            ffmpeg = find_tool("ffmpeg")
            for index, (start, end) in enumerate(chunks):
                check()
                end = min(end, duration)
                if end <= start:
                    continue
                piece = work / "chunk.wav"
                result = run([ffmpeg, "-y", "-v", "error", "-ss", f"{start / 1000:.3f}",
                              "-t", f"{(end - start) / 1000:.3f}", "-i", wav, "-c", "copy", piece])
                check()
                if result.returncode:
                    raise RuntimeError("ASR audio chunk extraction failed")
                words.extend(svc.asr.transcribe_chunk(piece, start, AsrOptions()))
                progress(.1 + .85 * (index + 1) / max(1, len(chunks)))
            words = [w.model_copy(update={"text": normalize(w.text)}) for w in dedupe_overlaps(words)
                     if 0 <= w.start_ms < w.end_ms <= duration]
            sentences = build_sentences(words)
        check()
        enriched = enrich_with_transcript(source, sentences)
        cache_dir.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=cache_dir,
                                         suffix=".tmp", delete=False) as stream:
            temporary = Path(stream.name)
            try:
                json.dump({"key": key, "sentences": [s.model_dump(mode="json") for s in sentences]}, stream,
                          ensure_ascii=False)
                stream.flush()
                check()
                stream.close()
                temporary.replace(cached)
            finally:
                temporary.unlink(missing_ok=True)
        progress(1)
        return enriched
    except Cancelled:
        raise
    except Exception as exc:
        check()
        log.warning("Raw ASR unavailable: %s", type(exc).__name__)
        return source
