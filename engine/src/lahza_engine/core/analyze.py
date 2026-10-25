"""Tahlil pipeline'i: import qilingandan keyin avtomatik ishlaydigan 1-9 bosqichlar (TZ 4-bo'lim).

ingest -> vad -> asr -> normalize -> align -> diarize -> sentences -> signals -> highlight
Vizual tahlil va reframe rejasi har klip uchun (preview/eksportda) hisoblanadi - core/export.py.
"""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path
from typing import Any

from lahza_engine.asr.base import AsrOptions, dedupe_overlaps, plan_chunks
from lahza_engine.config import Settings
from lahza_engine.core.runner import StageContext, StageDef, run_stages
from lahza_engine.core.services import MissingModel, Services
from lahza_engine.db import store as db
from lahza_engine.diarize.assign import (
    DiarizationResult,
    assign_speakers,
    find_overlaps,
    normalize_labels,
)
from lahza_engine.highlight.finder import find_highlights
from lahza_engine.highlight.signals import compute_signals
from lahza_engine.media.probe import extract_wav, make_proxy, probe, read_wav_mono
from lahza_engine.media.tools import find_tool, run
from lahza_engine.text.orthography import normalize
from lahza_engine.text.punctuation import needs_restoration, restore_punctuation
from lahza_engine.text.sentences import build_sentences
from lahza_engine.types import Transcript, Word
from lahza_engine.vad.energy import energy_vad

log = logging.getLogger(__name__)


def _words(data: list[dict[str, Any]]) -> list[Word]:
    return [Word.model_validate(w) for w in data]


def _dump(words: list[Word]) -> list[dict[str, Any]]:
    return [w.model_dump(mode="json") for w in words]


def stage_ingest(ctx: StageContext) -> dict[str, Any]:
    src = Path(ctx.services["src"])
    info = probe(src)
    wav = ctx.cache_dir / "audio16k.wav"
    extract_wav(src, wav)
    proxy = ctx.cache_dir / "proxy.mp4"
    try:
        make_proxy(src, proxy)
    except Exception as e:  # noqa: BLE001 - proksi bo'lmasa ham tahlil davom etadi
        log.warning("proksi yaratilmadi: %s", e)
    with ctx.conn:
        ctx.conn.execute(
            "INSERT OR REPLACE INTO media(id, path, hash, duration_ms, fps, width, height, audio_channels)"
            " VALUES (?,?,?,?,?,?,?,?)",
            (ctx.media_id, str(src), ctx.media_hash, info.duration_ms, info.fps, info.width,
             info.height, info.audio_channels),
        )
    return {"wav": str(wav), "proxy": str(proxy) if proxy.exists() else None,
            "duration_ms": info.duration_ms, "fps": info.fps, "width": info.width,
            "height": info.height}


def stage_vad(ctx: StageContext) -> dict[str, Any]:
    pcm, sr = read_wav_mono(ctx.results["ingest"]["wav"])
    vad = ctx.services["svc"].vad
    if vad is not None:
        try:
            return {"speech": vad(pcm, sr), "method": getattr(vad, "method", "silero")}
        except Exception as e:  # noqa: BLE001 - VAD xatosi tahlilni to'xtatmaydi
            log.warning("Silero VAD xatosi, energiya VAD'iga o'tildi: %s", e)
    return {"speech": energy_vad(pcm, sr), "method": "energy"}


def stage_asr(ctx: StageContext) -> dict[str, Any]:
    svc: Services = ctx.services["svc"]
    if svc.asr is None:
        raise MissingModel("ASR modeli o'rnatilmagan - Sozlamalar > Modellar")
    wav = Path(ctx.results["ingest"]["wav"])
    chunks = plan_chunks([tuple(r) for r in ctx.results["vad"]["speech"]])
    opts = AsrOptions(hotwords=ctx.services.get("hotwords", []))
    ffmpeg = str(find_tool("ffmpeg"))
    words: list[Word] = []
    with tempfile.TemporaryDirectory() as td:
        for i, (a, b) in enumerate(chunks):
            ctx.check_cancel()
            piece = Path(td) / f"c{i}.wav"
            r = run([ffmpeg, "-y", "-v", "error", "-ss", f"{a / 1000:.3f}", "-t", f"{(b - a) / 1000:.3f}",
                     "-i", wav, "-c", "copy", piece])
            if r.returncode != 0:
                raise RuntimeError(r.stderr[-300:])
            words.extend(svc.asr.transcribe_chunk(piece, a, opts))
            ctx.services["progress"]((i + 1) / max(1, len(chunks)))
    return {"words": _dump(dedupe_overlaps(words)), "chunks": len(chunks)}


def stage_normalize(ctx: StageContext) -> dict[str, Any]:
    lex: dict[str, str] = ctx.services.get("lexicon_map", {})
    out = []
    for w in _words(ctx.results["asr"]["words"]):
        t = normalize(w.text)
        t = lex.get(t.lower(), t)
        out.append(w.model_copy(update={"text": t}))
    restored = needs_restoration(out)
    if restored:
        out = restore_punctuation(out, force=True)
    return {"words": _dump(out), "punctuation": "restored" if restored else "asr"}


def stage_align(ctx: StageContext) -> dict[str, Any]:
    # CTC aligner (TZ 6-bo'lim): bo'lmasa yoki xato bersa ASR vaqtlari saqlanadi, usul qayd etiladi.
    svc: Services = ctx.services["svc"]
    aligner = svc.aligner
    words = _words(ctx.results["normalize"]["words"])
    if aligner is None:
        return {"words": _dump(words), "method": "asr-timestamps"}
    try:
        aligned = aligner(words, Path(ctx.results["ingest"]["wav"]))
    except Exception as e:  # noqa: BLE001
        log.warning("CTC tekislash xatosi - ASR vaqtlari qoldi: %s", e)
        return {"words": _dump(words), "method": "asr-timestamps"}
    return {"words": _dump(aligned), "method": getattr(aligner, "method", "ctc")}


def stage_diarize(ctx: StageContext) -> dict[str, Any]:
    svc: Services = ctx.services["svc"]
    words = _words(ctx.results["align"]["words"])
    none = {"words": _dump(words), "turns": [], "overlaps": [], "method": "none"}
    if svc.diarizer is None:
        return none
    wav = Path(ctx.results["ingest"]["wav"])
    n = ctx.services.get("num_speakers")
    try:
        if hasattr(svc.diarizer, "diarize"):
            res: DiarizationResult = svc.diarizer.diarize(wav, n)
            turns, overlaps = res.turns, res.overlaps
        else:
            turns = normalize_labels(svc.diarizer(wav, n))
            overlaps = find_overlaps(turns)
    except Exception as e:  # noqa: BLE001 - diarizatsiyasiz davom etiladi
        log.warning("diarizatsiya xatosi - spikersiz davom etiladi: %s", e)
        return none
    return {"words": _dump(assign_speakers(words, turns)),
            "turns": [t.__dict__ for t in turns],
            "overlaps": [[a, b] for a, b in overlaps], "method": "pyannote"}


def stage_sentences(ctx: StageContext) -> dict[str, Any]:
    sentences = build_sentences(_words(ctx.results["diarize"]["words"]))
    db.save_transcript(ctx.conn, ctx.media_id, Transcript(sentences=sentences))
    return {"count": len(sentences)}


def stage_signals(ctx: StageContext) -> dict[str, Any]:
    tr = db.load_transcript(ctx.conn, ctx.media_id)
    pcm, sr = read_wav_mono(ctx.results["ingest"]["wav"])
    rep = compute_signals(tr.sentences, pcm, sr)
    return {"sentences": [s.__dict__ for s in rep.sentences]}


def stage_highlight(ctx: StageContext) -> dict[str, Any]:
    from lahza_engine.highlight.signals import SentenceSignals, SignalReport

    settings: Settings = ctx.services["settings"]
    svc: Services = ctx.services["svc"]
    tr = db.load_transcript(ctx.conn, ctx.media_id)
    rep = SignalReport([SentenceSignals(**d) for d in ctx.results["signals"]["sentences"]])
    llm_candidates = None
    mode = "lite"
    if svc.llm_model_path is not None and not ctx.services.get("force_lite"):
        from lahza_engine.core.llama_server import LlamaServer
        from lahza_engine.highlight.llm import (
            LlamaServerClient,
            propose_candidates,
        )

        with LlamaServer(svc.llm_model_path) as url:
            client = LlamaServerClient(url, svc.llm_model_id or "llm")
            try:
                llm_candidates = propose_candidates(
                    client, tr.sentences, settings.highlight, focus=ctx.services.get("focus"),
                    on_progress=ctx.services["progress"],
                )
            finally:
                client.close()
        mode = "llm"
    clips = find_highlights(ctx.media_id, tr.sentences, rep, settings.highlight, llm_candidates,
                            svc.llm_model_id)
    db.save_clips(ctx.conn, clips)
    return {"mode": mode, "clips": [c.id for c in clips]}


def analysis_stages(settings: Settings) -> list[StageDef]:
    h = settings.highlight
    return [
        # v2: WAV preserves container-time leading silence instead of resetting audio alone.
        StageDef("ingest", 2, stage_ingest, weight=1),
        StageDef("vad", 2, stage_vad, weight=1,
                 params=lambda c: {"vad": getattr(c.services["svc"].vad, "method", None)}),
        # v2: explicit decoder thresholds and punctuation-only hallucination filtering.
        StageDef("asr", 2, stage_asr, weight=10,
                 model_id=lambda c: c.services["svc"].asr_model_id,
                 params=lambda c: {"hotwords": c.services.get("hotwords", [])}),
        StageDef("normalize", 2, stage_normalize, params=lambda c: c.services.get("lexicon_map", {})),
        StageDef("align", 2, stage_align, weight=2,
                 model_id=lambda c: c.services["svc"].aligner_model_id),
        StageDef("diarize", 2, stage_diarize, weight=3,
                 params=lambda c: {"n": c.services.get("num_speakers")}),
        StageDef("sentences", 1, stage_sentences),
        StageDef("signals", 1, stage_signals),
        StageDef("highlight", 1, stage_highlight, weight=4,
                 model_id=lambda c: None if c.services.get("force_lite") else c.services["svc"].llm_model_id,
                 params=lambda c: {**h.model_dump(), "focus": c.services.get("focus")}),
    ]


def analyze(ctx: StageContext, settings: Settings) -> dict[str, dict[str, Any]]:
    ctx.services.setdefault("settings", settings)
    return run_stages(analysis_stages(settings), ctx)
