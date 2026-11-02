"""Eksportda aktiv spiker (M3-RF-1 ulanishi): ASD backend + diarizatsiya -> reframe rejasi.

Kadrlar (iter_frames), audio va ASD backend soxta: ffmpeg/onnxruntime kerak emas (oxirgi test
bundan mustasno - klip oralig'i audiosini ffmpeg bilan dekodlash).
"""

from __future__ import annotations

import json
import wave
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from conftest import requires_ffmpeg

from lahza_engine.config import Settings
from lahza_engine.core import export as ex
from lahza_engine.core import services as services_mod
from lahza_engine.db import store as db
from lahza_engine.diarize.assign import Turn
from lahza_engine.media import frames as frames_mod
from lahza_engine.models.catalog import Task
from lahza_engine.reframe.faces import Box, FaceTracker
from lahza_engine.reframe.planner import Observation, plan
from lahza_engine.timeline import clip_timeline
from lahza_engine.types import Clip, ClipHook, Layout, Sentence, Transcript, Word

W, H = 160, 90
LEFT = Box(0.05, 0.25, 0.30, 0.45)  # katta yuz, cx = 0.20
RIGHT = Box(0.70, 0.35, 0.15, 0.22)  # kichik yuz, cx = 0.775


def _region(frame: np.ndarray, b: Box, value: int) -> None:
    frame[int(b.y * H):int((b.y + b.h) * H), int(b.x * W):int((b.x + b.w) * W)] = value


def _fake_frames(speaking):
    """iter_frames o'rniga: kadrda gapirayotgan yuz (speaking(t) -> Box) oq, qolgani qora."""

    def fake(src, start_ms, end_ms, fps=5.0, width=640, src_w=1920, src_h=1080):  # noqa: ARG001
        i = 0
        while True:
            t = start_ms + int(i * 1000 / fps)
            if t >= end_ms:
                return
            f = np.zeros((H, W, 3), np.uint8)
            b = speaking(t)
            if b is not None:
                _region(f, b, 255)
            yield t, f
            i += 1

    return fake


class TwoFaces:
    def detect(self, frame):  # noqa: ANN001, ANN201
        return [LEFT, RIGHT]


class FakeAsd:
    """Yorug' yuz kesimi - gapiryapti (0.9), qorong'i - jim (0.05)."""

    def __init__(self) -> None:
        self.calls = 0
        self.max_len = 0

    def score(self, faces: np.ndarray, mfcc: np.ndarray) -> np.ndarray:
        self.calls += 1
        self.max_len = max(self.max_len, len(faces))
        assert faces.shape[1:] == (112, 112) and mfcc.shape[1] == 13
        return np.where(faces.mean(axis=(1, 2)) > 20, 0.9, 0.05).astype(np.float32)


@pytest.fixture
def fake_audio(monkeypatch):
    seen: list[tuple] = []

    def clip_audio(path, start_ms, end_ms):  # noqa: ANN001, ANN202
        seen.append((path, start_ms, end_ms))
        return np.zeros(16 * (end_ms - start_ms), np.float32)

    monkeypatch.setattr(ex, "_clip_audio", clip_audio)
    return seen


def _clip(start: int = 0, end: int = 6_000, **kw) -> Clip:
    return Clip(id="c1", media_id="m1", start_ms=start, end_ms=end, start_sentence_id=0,
                end_sentence_id=0, **kw)


def _focus_cx(segs, t_ms: int) -> float | None:
    seg = next(s for s in segs if s.start_ms <= t_ms < s.end_ms)
    if seg.layout is not Layout.FOCUS:
        return None
    rel = t_ms - seg.start_ms
    keys = [k for k in seg.keys if k.t_ms <= rel] or seg.keys[:1]
    return keys[-1].cx


# --- ASD bilan: to'g'ri yuzga yo'naltirish ----------------------------------------------------


def test_asd_points_camera_at_small_speaking_face(monkeypatch, fake_audio) -> None:
    monkeypatch.setattr(frames_mod, "iter_frames", _fake_frames(lambda t: RIGHT))
    clip = _clip()
    asd = FakeAsd()
    segs = ex.build_layout_plan(Path("v.mp4"), clip, clip_timeline(clip), TwoFaces(), Settings(),
                                1280, 720, detect_scenes=False, asd=asd, turns=[], overlaps=[],
                                audio_path=Path("a.wav"))
    assert all(s.layout is Layout.FOCUS for s in segs)
    assert abs(_focus_cx(segs, 3_000) - RIGHT.cx) < 0.02
    assert fake_audio == [(Path("a.wav"), 0, 6_000)]  # faqat klip oralig'i
    assert asd.calls and asd.max_len <= 250  # bo'laklarda baholanadi
    # ASD'siz - eng katta (jim) yuz
    base = ex.build_layout_plan(Path("v.mp4"), clip, clip_timeline(clip), TwoFaces(), Settings(),
                                1280, 720, detect_scenes=False)
    assert abs(_focus_cx(base, 3_000) - LEFT.cx) < 0.02


def test_asd_with_diarization_follows_speaker_change(monkeypatch, fake_audio) -> None:
    monkeypatch.setattr(frames_mod, "iter_frames",
                        _fake_frames(lambda t: RIGHT if t < 13_000 else LEFT))
    clip = _clip(10_000, 16_000)
    turns = [Turn(10_000, 13_000, "SPEAKER_00"), Turn(13_000, 16_000, "SPEAKER_01")]
    obs = ex.observations_for_clip(Path("v.mp4"), clip, clip_timeline(clip), TwoFaces(),
                                   Settings(), 1280, 720, asd=FakeAsd(), turns=turns,
                                   overlaps=[(15_500, 15_700)])
    assert obs[0].t_ms == 0 and obs[-1].t_ms < 6_000  # chiqish vaqtida
    assert all(len(o.track_ids) == 2 and len(set(o.track_ids)) == 2 for o in obs)
    assert len({tuple(o.track_ids) for o in obs}) == 1  # treker ID lari barqaror
    assert {o.speaker for o in obs} == {"SPEAKER_00", "SPEAKER_01"}  # manba vaqtidagi turn'lar
    assert any(o.overlap_speech for o in obs)
    early = [o for o in obs if o.t_ms < 2_500]
    late = [o for o in obs if 4_500 <= o.t_ms < 5_400]
    assert all(o.faces[o.active_index] == RIGHT for o in early)
    assert all(o.faces[o.active_index] == LEFT for o in late)
    rid = early[0].track_ids[1]
    assert early[5].asd_scores[rid] == pytest.approx(0.9)
    segs = plan(obs, 6_000, Settings().reframe)
    assert abs(_focus_cx(segs, 1_000) - RIGHT.cx) < 0.02
    assert abs(_focus_cx(segs, 5_000) - LEFT.cx) < 0.02


def test_asd_without_audio_falls_back_to_largest(monkeypatch) -> None:
    monkeypatch.setattr(frames_mod, "iter_frames", _fake_frames(lambda t: RIGHT))
    monkeypatch.setattr(ex, "_clip_audio", lambda *a: None)
    clip = _clip()
    asd = FakeAsd()
    obs = ex.observations_for_clip(Path("v.mp4"), clip, clip_timeline(clip), TwoFaces(),
                                   Settings(), 1280, 720, asd=asd)
    assert asd.calls == 0 and not any(o.asd_scores for o in obs)
    assert all(o.faces[o.active_index] == LEFT and not o.wide for o in obs)


# --- Model yo'q: reja bit-darajada avvalgidek --------------------------------------------------


def _legacy_observations(src, clip, timeline, detector, settings, src_w, src_h, scene_cuts=None,
                         words=None):
    """ASD ulanishidan oldingi `observations_for_clip` (8224d0c) - o'zgarishsiz nusxa."""
    tracker = FaceTracker()
    obs: list[Observation] = []
    cuts = sorted(scene_cuts or [])
    bounds = timeline.boundaries_out()
    spk_words = [w for w in (words or []) if w.speaker]
    prev_src = prev_out = None
    for t_src, frame in frames_mod.iter_frames(src, clip.start_ms, clip.end_ms,
                                               settings.reframe.analysis_fps,
                                               src_w=src_w, src_h=src_h):
        t_out = timeline.to_out(t_src)
        if t_out is None:
            continue
        shot_cut = prev_src is not None and (
            any(prev_src < c <= t_src for c in cuts)
            or any(prev_out is not None and prev_out < b <= t_out for b in bounds)
        )
        prev_src, prev_out = t_src, t_out
        boxes = detector.detect(frame)
        tracker.update(t_out, boxes)
        active = None
        if boxes:
            active = max(range(len(boxes)), key=lambda i: boxes[i].w * boxes[i].h)
        speaker, overlap = ex._speech_at(spk_words, t_src) if spk_words else (None, False)
        obs.append(Observation(t_out, boxes, active, shot_cut=shot_cut, overlap_speech=overlap,
                               speaker=speaker))
    return ex._with_hook_prefix(obs, timeline)


class VaryingFaces:
    """Yuzlar soni va o'lchami vaqt bo'yicha o'zgaradi (kadr yorug'ligi orqali)."""

    def __init__(self) -> None:
        self.n = 0

    def detect(self, frame):  # noqa: ANN001, ANN201
        self.n += 1
        k = self.n % 7
        if k == 0:
            return []
        if k < 3:
            return [Box(0.1 + 0.01 * k, 0.3, 0.2, 0.3)]
        return [Box(0.1, 0.3, 0.2 + 0.02 * k, 0.3), Box(0.6, 0.3, 0.25, 0.32)]


@pytest.mark.parametrize("kw", [
    {},
    {"cuts": [(2_000, 2_600)]},
    {"hook": ClipHook(start_ms=4_000, end_ms=5_000), "cuts": [(1_000, 1_400)]},
])
def test_no_asd_plan_is_bit_identical(monkeypatch, kw) -> None:
    monkeypatch.setattr(frames_mod, "iter_frames", _fake_frames(lambda t: None))
    clip = _clip(1_000, 9_000, **kw)
    tl = clip_timeline(clip)
    words = [Word(text="a", start_ms=1_000, end_ms=3_000, speaker="A"),
             Word(text="b", start_ms=2_800, end_ms=6_000, speaker="B"),
             Word(text="c", start_ms=6_000, end_ms=9_000, speaker="A")]
    s = Settings()
    legacy = plan(_legacy_observations(Path("v"), clip, tl, VaryingFaces(), s, 1280, 720,
                                       scene_cuts=[5_000], words=words), tl.duration_ms, s.reframe)
    new_obs = ex.observations_for_clip(Path("v"), clip, tl, VaryingFaces(), s, 1280, 720,
                                       scene_cuts=[5_000], words=words)
    old_obs = _legacy_observations(Path("v"), clip, tl, VaryingFaces(), s, 1280, 720,
                                   scene_cuts=[5_000], words=words)
    # kuzatuvlar faqat track_ids bilan farq qiladi
    assert [o.__dict__ | {"track_ids": []} for o in new_obs] == [o.__dict__ for o in old_obs]
    assert all(len(o.track_ids) == len(o.faces) for o in new_obs)
    # model yo'q (asd=None): diarizatsiya berilsa ham reja aynan avvalgidek
    turns = [Turn(1_000, 5_000, "SPEAKER_00"), Turn(5_000, 9_000, "SPEAKER_01")]
    monkeypatch.setattr(ex, "_clip_audio", lambda *a: pytest.fail("audio o'qilmasligi kerak"))
    got = ex.build_layout_plan(Path("v"), clip, tl, VaryingFaces(), s, 1280, 720, words=words,
                               detect_scenes=False, asd=None, turns=turns,
                               overlaps=[(3_000, 3_500)])
    legacy_ns = plan(_legacy_observations(Path("v"), clip, tl, VaryingFaces(), s, 1280, 720,
                                          words=words), tl.duration_ms, s.reframe)
    assert repr(got) == repr(legacy_ns)
    assert legacy  # parametrlangan holatlar bo'sh emas


# --- Diarizatsiya va audio manbai ---------------------------------------------------------------


def _project(tmp_path: Path, diarize: dict | None, wav: Path | None):
    conn = db.open_project(tmp_path / "ep.lahza")
    with conn:
        conn.execute("INSERT INTO media(id, path, hash, duration_ms, fps, width, height, "
                     "audio_channels) VALUES ('m1', ?, 'h', 20000, 25, 1280, 720, 1)",
                     (str(tmp_path / "v.mp4"),))
        for stage, data in (("diarize", diarize), ("ingest", {"wav": str(wav)} if wav else None)):
            if data is None:
                continue
            p = tmp_path / f"{stage}.json"
            p.write_text(json.dumps(data), encoding="utf-8")
            conn.execute("INSERT INTO stage_runs(media_id, stage, version, param_hash, cache_key,"
                         " status, result_path) VALUES ('m1', ?, 1, 'p', 'k', 'done', ?)",
                         (stage, str(p)))
    return conn


def test_load_diarization_from_stage_cache(tmp_path) -> None:
    wav = tmp_path / "audio.wav"
    wav.write_bytes(b"RIFF")
    conn = _project(tmp_path, {"turns": [{"start_ms": 0, "end_ms": 900, "speaker": "SPEAKER_00"}],
                               "overlaps": [[400, 600]], "method": "pyannote"}, wav)
    assert ex.load_diarization(conn, "m1") == ([Turn(0, 900, "SPEAKER_00")], [(400, 600)], wav)
    # lite / diarizatsiyasiz tahlil
    conn2 = _project(tmp_path / "b", {"turns": [], "overlaps": [], "method": "none"}, None)
    assert ex.load_diarization(conn2, "m1") == ([], [], None)
    conn3 = _project(tmp_path / "c", None, None)
    assert ex.load_diarization(conn3, "m1") == ([], [], None)


def test_resolve_layouts_uses_episode_diarization(monkeypatch, tmp_path, fake_audio) -> None:
    import lahza_engine.media.scenes as scenes

    monkeypatch.setattr(scenes, "detect_scene_cuts", lambda *a, **k: [])
    monkeypatch.setattr(frames_mod, "iter_frames",
                        _fake_frames(lambda t: RIGHT if t < 13_000 else LEFT))
    wav = tmp_path / "audio.wav"
    wav.write_bytes(b"RIFF")
    conn = _project(tmp_path, {"turns": [{"start_ms": 10_000, "end_ms": 13_000, "speaker": "S0"},
                                         {"start_ms": 13_000, "end_ms": 16_000, "speaker": "S1"}],
                               "overlaps": []}, wav)
    clip = _clip(10_000, 16_000)
    w = Word(text="gap", start_ms=10_000, end_ms=16_000)
    db.save_transcript(conn, "m1", Transcript(sentences=[
        Sentence(id=0, start_ms=10_000, end_ms=16_000, words=[w])]))
    db.save_clips(conn, [clip])
    captured: dict = {}
    real = ex.observations_for_clip

    def spy(*a, **k):  # noqa: ANN002, ANN003, ANN202
        captured.update(k)
        return real(*a, **k)

    monkeypatch.setattr(ex, "observations_for_clip", spy)
    segs, source = ex.resolve_layouts(conn, tmp_path / "v.mp4", clip, clip_timeline(clip),
                                      TwoFaces(), Settings(), 1280, 720, asd=FakeAsd())
    assert source == "avto"
    assert [t.speaker for t in captured["turns"]] == ["S0", "S1"]
    assert fake_audio == [(wav, 10_000, 16_000)]  # ingest WAV'idan, faqat klip oralig'i
    assert abs(_focus_cx(segs, 1_000) - RIGHT.cx) < 0.02
    assert abs(_focus_cx(segs, 5_000) - LEFT.cx) < 0.02
    # model yo'q - diarizatsiya o'qilmaydi, eng katta yuz
    monkeypatch.setattr(ex, "load_diarization", lambda *a: pytest.fail("o'qilmasligi kerak"))
    segs2, _ = ex.resolve_layouts(conn, tmp_path / "v.mp4", clip, clip_timeline(clip),
                                  TwoFaces(), Settings(), 1280, 720, asd=None)
    assert abs(_focus_cx(segs2, 1_000) - LEFT.cx) < 0.02


# --- Services: ASD lazy, bir marta --------------------------------------------------------------


class FakeStore:
    def __init__(self, vision: Path | None) -> None:
        self.vision = vision

    def default_for(self, task: Task):  # noqa: ANN201
        if task is Task.VISION and self.vision is not None:
            return SimpleNamespace(id="vision-1", path=str(self.vision))
        return None


def test_services_asd_lazy_once(monkeypatch, tmp_path) -> None:
    import lahza_engine.reframe.asd as asd_mod

    calls: list[Path] = []

    def from_dir(cls, root):  # noqa: ANN001, ANN202
        calls.append(root)
        return ("asd", root.name)

    monkeypatch.setattr(asd_mod.LrAsdOnnx, "from_dir", classmethod(from_dir))
    (tmp_path / "vision").mkdir()
    (tmp_path / "vision" / "asd.onnx").write_bytes(b"x")
    s = services_mod.build_services(FakeStore(tmp_path / "vision"))
    assert calls == []  # build_services ASD'ni yuklamaydi
    assert s.asd_backend() == ("asd", "vision")
    assert s.asd_backend() == ("asd", "vision") and len(calls) == 1


def test_services_asd_missing_is_none(tmp_path) -> None:
    (tmp_path / "vision").mkdir()
    (tmp_path / "vision" / "blazeface.onnx").write_bytes(b"x")
    assert services_mod.build_services(FakeStore(tmp_path / "vision")).asd_backend() is None
    assert services_mod.build_services(FakeStore(None)).asd_backend() is None
    assert services_mod.Services().asd_backend() is None


# --- Klip oralig'i audiosi (haqiqiy ffmpeg) -----------------------------------------------------


@requires_ffmpeg
@pytest.mark.ffmpeg
def test_clip_audio_decodes_only_range(tmp_path) -> None:
    sr = 16_000
    pcm = (np.arange(3 * sr) // sr * 8_000 + 1_000).astype("<i2")  # har soniya - boshqa daraja
    wav = tmp_path / "a.wav"
    with wave.open(str(wav), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm.tobytes())
    got = ex._clip_audio(wav, 1_000, 2_000)
    assert got is not None and abs(len(got) - sr) <= 32
    assert np.median(got) == pytest.approx(9_000, abs=2)  # int16 shkalasi, 2-soniya
    assert ex._clip_audio(tmp_path / "yoq.wav", 0, 1_000) is None
