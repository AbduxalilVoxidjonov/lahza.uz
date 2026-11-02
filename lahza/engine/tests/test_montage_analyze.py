"""Manba tahlili (montage/analyze.py): sof o'lchovlar, transkript bilan to'ldirish va sintetik video."""

from __future__ import annotations

import subprocess
import threading
from pathlib import Path

import numpy as np
import pytest
from conftest import make_sentences, requires_ffmpeg

from lahza_engine.highlight.signals import SentenceSignals, SignalReport
from lahza_engine.montage import analyze as an
from lahza_engine.montage.analyze import (
    AnalysisCancelled,
    Shot,
    SourceAnalysis,
    analyze_file,
    enrich_with_transcript,
    laplacian_var,
    shots_from_cuts,
)
from lahza_engine.montage.model import MediaRef
from lahza_engine.types import Clip, Sentence, Word


def test_laplacian_sharp_vs_flat() -> None:
    rng = np.random.default_rng(0)
    noisy = rng.integers(0, 255, (60, 80)).astype(np.float32)
    flat = np.full((60, 80), 128, dtype=np.float32)
    assert laplacian_var(noisy) > 1000 > laplacian_var(flat) == 0.0
    assert an.sharpness_norm(laplacian_var(noisy)) > 0.9 and an.sharpness_norm(0.0) == 0.0
    assert an.exposure_norm(128) == 1.0 and an.exposure_norm(5) < 0.2
    assert an.motion_pref(0.03) > an.motion_pref(0.0) and an.motion_pref(0.3) < 0.1
    good = an.shot_score(0.9, 1.0, 0.6, 0.04, 3000)
    blurry_dark = an.shot_score(0.1, 0.1, 0.6, 0.04, 3000)
    assert 0 <= blurry_dark < good <= 1


def test_shots_from_cuts() -> None:
    assert shots_from_cuts([], 5000) == [(0, 5000)]
    assert shots_from_cuts([2000, 4000], 6000) == [(0, 2000), (2000, 4000), (4000, 6000)]
    # Juda qisqa (chaqnash) shot oldingisiga qo'shiladi.
    assert shots_from_cuts([2000, 2100, 4000], 6000) == [(0, 2100), (2100, 4000), (4000, 6000)]
    assert shots_from_cuts([100, 3000], 6000) == [(0, 3000), (3000, 6000)]


def test_roundtrip_dict() -> None:
    m = MediaRef(id="x", path="/a.mp4", duration_ms=1000, width=10, height=10, fps=25)
    sa = SourceAnalysis(media=m, shots=[Shot(0, 1000, 0.5)], sentences=make_sentences(1),
                        speech=[(0, 900)], curve=[0.1, 0.2])
    back = SourceAnalysis.from_dict(sa.to_dict())
    assert back == sa


def test_enrich_with_transcript() -> None:
    sents = make_sentences(6)
    sents[1] = sents[1].model_copy(update={"words": [*sents[1].words[:-1],
                                                     Word(text="nega?", start_ms=sents[1].words[-1].start_ms,
                                                          end_ms=sents[1].end_ms)]})
    sents[3] = sents[3].model_copy(update={"words": [Word(text="2026", start_ms=sents[3].start_ms,
                                                          end_ms=sents[3].start_ms + 300),
                                                     *sents[3].words[1:]]})
    sents = [s.model_copy(update={"speaker": "A" if i < 4 else "B"}) for i, s in enumerate(sents)]
    m = MediaRef(id="ep", path="/ep.mp4", duration_ms=sents[-1].end_ms + 500, width=1920, height=1080, fps=25)
    sa = SourceAnalysis(media=m, shots=[Shot(0, m.duration_ms)])
    clip = Clip(id="c1", media_id="ep", start_ms=sents[2].start_ms, end_ms=sents[4].end_ms, start_sentence_id=2,
                end_sentence_id=4, title="Zo'r joy", score=82.0)
    signals = SignalReport(sentences=[SentenceSignals(sentence_id=5, loudness_z=3, peak_z=3)])
    out = enrich_with_transcript(sa, sents, [clip], signals)
    assert out is not sa and not sa.sentences
    assert out.sentences == sents
    assert out.highlights[0].clip_id == "c1" and out.highlights[0].score == 0.82
    assert out.highlights[0].title == "Zo'r joy"
    assert sents[1].start_ms in out.emphasis_ms  # savol
    assert sents[3].start_ms in out.emphasis_ms  # raqamli so'z
    assert sents[5].start_ms in out.emphasis_ms  # kuchli signal
    assert sents[0].start_ms not in out.emphasis_ms
    assert out.speaker_changes_ms == [sents[4].start_ms]
    assert out.speech == [(s.start_ms, s.end_ms) for s in sents]


def test_enrich_hook_sentence_is_emphasis() -> None:
    sents = make_sentences(3)
    m = MediaRef(id="ep", path="/ep.mp4", duration_ms=30_000, width=1, height=1, fps=25)
    clip = Clip(id="c", media_id="ep", start_ms=0, end_ms=10_000, start_sentence_id=0, end_sentence_id=1,
                hook_sentence_id=1)
    out = enrich_with_transcript(SourceAnalysis(media=m), sents, [clip])
    assert out.emphasis_ms == [sents[1].start_ms]
    assert isinstance(out.sentences[0], Sentence)


# --- sintetik video (ffmpeg) -----------------------------------------------------------------


@pytest.fixture(scope="module")
def two_scene_video(tmp_path_factory: pytest.TempPathFactory) -> Path:
    if not an.find_tool:  # pragma: no cover
        pytest.skip("ffmpeg yo'q")
    out = tmp_path_factory.mktemp("an") / "ikki_sahna.mp4"
    cmd = [
        "ffmpeg", "-y", "-v", "error",
        "-f", "lavfi", "-i", "testsrc2=size=320x240:rate=25:duration=3",
        "-f", "lavfi", "-i", "color=c=0x2050C0:size=320x240:rate=25:duration=3",
        "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=16000:duration=6",
        "-filter_complex", "[0:v][1:v]concat=n=2:v=1:a=0[v]",
        "-map", "[v]", "-map", "2:a", "-c:v", "mpeg4", "-q:v", "4", "-c:a", "aac", "-shortest", str(out),
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        pytest.skip("sintetik videoni yaratib bo'lmadi")
    return out


@requires_ffmpeg
def test_analyze_two_scenes_and_cache(two_scene_video: Path, tmp_path: Path,
                                      monkeypatch: pytest.MonkeyPatch) -> None:
    progress: list[float] = []
    sa = analyze_file(two_scene_video, "v1", tmp_path / "cache", None, on_progress=progress.append)
    assert sa.media.id == "v1" and sa.media.has_audio and abs(sa.media.duration_ms - 6000) < 200
    assert len(sa.shots) == 2, sa.shots
    assert abs(sa.shots[0].end_ms - 3000) <= 120
    assert sa.shots[0].start_ms == 0 and sa.shots[-1].end_ms == sa.media.duration_ms
    # testsrc2 - keskin naqsh va harakat; bir rangli kadr - xira (laplasian 0) va harakatsiz.
    assert sa.shots[0].sharpness > sa.shots[1].sharpness
    assert sa.shots[0].motion > sa.shots[1].motion
    assert sa.shots[0].score > sa.shots[1].score
    assert all(0 <= s.score <= 1 and s.energy > 0.3 for s in sa.shots)
    assert sa.curve and all(0 <= x <= 1 for x in sa.curve)
    assert progress and progress[-1] == 1.0
    files = list((tmp_path / "cache").glob("analysis-*.json"))
    assert len(files) == 1

    # Ikkinchi chaqiruv - keshdan (ffmpeg chaqirilmaydi), boshqa media id bilan.
    def boom(*a, **k):  # type: ignore[no-untyped-def]
        raise AssertionError("kesh ishlatilmadi")

    monkeypatch.setattr("lahza_engine.media.scenes.detect_scene_cuts", boom)
    sa2 = analyze_file(two_scene_video, "boshqa", tmp_path / "cache", None)
    assert sa2.media.id == "boshqa" and sa2.shots == sa.shots


@requires_ffmpeg
def test_analyze_cancel(two_scene_video: Path, tmp_path: Path) -> None:
    ev = threading.Event()
    ev.set()
    with pytest.raises(AnalysisCancelled):
        analyze_file(two_scene_video, "v1", tmp_path / "c2", None, cancel=ev)
    assert not list((tmp_path / "c2").glob("analysis-*.json"))


@requires_ffmpeg
def test_probe_media_audio_only(tmp_path: Path) -> None:
    wav = tmp_path / "m.wav"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "sine=frequency=300:duration=2", str(wav)],
                   check=True, capture_output=True, timeout=30)
    info = an.probe_media(wav)
    assert info.has_audio and not info.has_video and abs(info.duration_ms - 2000) < 100


@requires_ffmpeg
def test_planner_real_music_probe(tmp_path: Path) -> None:
    from lahza_engine.montage.planner import MontageOverrides, plan_montage
    from lahza_engine.templates.store import get_builtin

    wav = tmp_path / "music.wav"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "sine=frequency=300:duration=30", str(wav)],
                   check=True, capture_output=True, timeout=30)
    m = MediaRef(id="a", path="/a.mp4", duration_ms=40_000, width=1920, height=1080, fps=25)
    sa = SourceAnalysis(media=m, shots=[Shot(i * 4000, (i + 1) * 4000, 0.5 + i / 100) for i in range(10)])
    tl = plan_montage(get_builtin("uz.lahza.tpl.event-rhythm"), [sa], MontageOverrides(music_path=str(wav)), None)
    assert tl.media["music"].duration_ms > 29_000 and tl.media["music"].hash
