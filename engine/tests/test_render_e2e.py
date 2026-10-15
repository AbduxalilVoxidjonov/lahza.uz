"""Haqiqiy FFmpeg bilan render va to'liq pipeline (soxta ASR bilan) sinovi."""

import json
import subprocess
from pathlib import Path

import pytest
from conftest import requires_ffmpeg, requires_libass

from lahza_engine.config import RenderConfig, Settings
from lahza_engine.core.analyze import analyze
from lahza_engine.core.export import export_clip
from lahza_engine.core.runner import StageContext
from lahza_engine.core.services import Services
from lahza_engine.db import store as db
from lahza_engine.media.probe import fast_hash, probe
from lahza_engine.reframe.planner import CropKey, LayoutSegment
from lahza_engine.render.encoders import choose_encoder
from lahza_engine.render.graph import RenderJob, build_graph, render
from lahza_engine.subtitle.ass import build_ass
from lahza_engine.subtitle.style import StyleTemplate
from lahza_engine.timeline import Timeline
from lahza_engine.types import Layout, Word

pytestmark = [requires_ffmpeg, pytest.mark.ffmpeg]


@pytest.fixture(scope="module")
def video(tmp_path_factory) -> Path:
    p = tmp_path_factory.mktemp("v") / "podkast.mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "testsrc2=size=1920x1080:rate=25:duration=95",
         "-f", "lavfi", "-i",
         # nutqqa o'xshash: 2.6 s ovoz, 0.4 s sukut (energiya VAD uchun)
         "aevalsrc=0.5*sin(2*PI*330*t)*lt(mod(t\\,3)\\,2.6):s=48000:d=95",
         "-c:v", "mpeg4", "-q:v", "5", "-c:a", "aac", "-shortest", str(p)],
        check=True,
    )
    return p


def _out_info(p: Path) -> dict:
    r = subprocess.run(["ffprobe", "-v", "error", "-print_format", "json", "-show_streams",
                        "-show_format", str(p)], capture_output=True, text=True, check=True)
    return json.loads(r.stdout)


def _encoder():
    return choose_encoder("ffmpeg", None, 4000, platform="linux", allow_dev_fallback=True)


@requires_libass
@pytest.mark.libass
def test_render_all_layouts_with_cuts_and_subtitles(video: Path, tmp_path: Path) -> None:
    tl = Timeline(10_000, 22_000, cuts=[(14_000, 15_000)])  # 11 s natija
    layouts = [
        LayoutSegment(0, 4_000, Layout.FOCUS,
                      keys=[CropKey(0, 0.3, cut=True), CropKey(2_000, 0.5), CropKey(3_000, 0.8, cut=True)]),
        LayoutSegment(4_000, 8_000, Layout.SPLIT, keys=[CropKey(0, 0.25, cut=True)],
                      keys_b=[CropKey(0, 0.75, cut=True)]),
        LayoutSegment(8_000, tl.duration_ms, Layout.FIT_BLUR),
    ]
    words = [Word(text=t, start_ms=10_000 + i * 700, end_ms=10_000 + i * 700 + 600)
             for i, t in enumerate(["o'zbek", "tilida", "subtitr", "sinovi", "bu", "yerda", "yaxshi", "ko'rinadi"])]
    ass = build_ass(words, tl, StyleTemplate())
    job = RenderJob(src=video, out=tmp_path / "out.mp4", workdir=tmp_path / "w", src_w=1920,
                    src_h=1080, fps=25.0, timeline=tl, layouts=layouts, encoder=_encoder(),
                    cfg=RenderConfig(), ass_text=ass)
    graph, files, seek = build_graph(job)
    assert seek == pytest.approx(9.0)
    assert "p0.cmd" in files and "subs.ass" in files and "vstack" in graph and "gblur" in graph
    render(job, timeout_s=300)
    info = _out_info(job.out)
    v = next(s for s in info["streams"] if s["codec_type"] == "video")
    a = next(s for s in info["streams"] if s["codec_type"] == "audio")
    assert (v["width"], v["height"]) == (1080, 1920)
    assert a["sample_rate"] == "48000"
    assert float(info["format"]["duration"]) == pytest.approx(11.0, abs=0.25)


class FakeAsr:
    """Haqiqiy model o'rniga: bo'lak vaqtiga mos so'zlar qaytaradi."""

    model_id = "fake-asr"

    def transcribe_chunk(self, wav, offset_ms, opts):
        info = probe_duration(wav)
        out, t = [], 0
        k = 0
        while t + 400 <= info:
            text = f"so'z{(offset_ms + t) // 1000}" + ("." if k % 12 == 11 else "")
            out.append(Word(text=text, start_ms=offset_ms + t, end_ms=offset_ms + t + 350))
            t += 450
            k += 1
        return out


def probe_duration(wav: Path) -> int:
    import wave

    with wave.open(str(wav)) as w:
        return int(w.getnframes() * 1000 / w.getframerate())


@requires_libass  # eksport subtitrni ASS orqali yoqib yozadi
@pytest.mark.libass
def test_full_pipeline_lite_then_export(video: Path, tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path / "data")
    pdir = tmp_path / "ep.lahza"
    conn = db.open_project(pdir)
    svc = Services(asr=FakeAsr(), asr_model_id="fake-asr")
    ctx = StageContext("m1", fast_hash(video), pdir, conn,
                       services={"src": str(video), "svc": svc, "force_lite": True})
    res = analyze(ctx, settings)
    assert res["highlight"]["mode"] == "lite"
    assert probe(video).width == 1920
    clips = db.load_clips(conn, "m1")
    assert clips, "Lite rejim kamida bitta klip topishi kerak"
    clip = clips[0]
    assert settings.highlight.min_clip_ms * 0.8 <= clip.duration_ms <= settings.highlight.max_clip_ms
    out = export_clip(conn, "m1", clip, tmp_path / "eksport", pdir / "work", settings, _encoder(),
                      StyleTemplate(), detector=None, show_name="Test shou", episode="12-son")
    assert out.video.exists() and out.srt.exists() and out.caption.exists()
    assert out.video.name.startswith("test-shou_12-son_01_")
    v = next(s for s in _out_info(out.video)["streams"] if s["codec_type"] == "video")
    assert (v["width"], v["height"]) == (1080, 1920)
    # Ikkinchi tahlil keshdan: ASR qayta chaqirilmaydi.
    svc.asr = None
    analyze(StageContext("m1", fast_hash(video), pdir, conn,
                         services={"src": str(video), "svc": svc, "force_lite": True}), settings)
