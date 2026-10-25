"""Render: libass aniqlash, logotip, loudnorm, fayl nomi shabloni, platforma limitlari,
sahna kesimlari, bitta kadrli preview va eksport (subtitrsiz rejimda haqiqiy FFmpeg bilan)."""

import json
import subprocess
from pathlib import Path

import pytest
from conftest import requires_ffmpeg

from lahza_engine.config import RenderConfig, Settings
from lahza_engine.core import export as ex
from lahza_engine.db import store as db
from lahza_engine.media.scenes import parse_scene_times
from lahza_engine.reframe.planner import CropKey, Keyframe, LayoutSegment
from lahza_engine.render import capabilities, graph
from lahza_engine.render.capabilities import LibassMissing, has_filter
from lahza_engine.render.encoders import EncoderChoice
from lahza_engine.render.graph import RenderJob, build_graph, logo_overlay_xy
from lahza_engine.render.limits import check_limits, source_quality_warning
from lahza_engine.subtitle.ass import build_ass
from lahza_engine.subtitle.style import StyleTemplate
from lahza_engine.timeline import Timeline
from lahza_engine.types import Clip, Layout, Sentence, Transcript, Word

ENC = EncoderChoice("mpeg4", ("-c:v", "mpeg4", "-q:v", "5", "-pix_fmt", "yuv420p"), False)


def _job(tmp_path: Path, **kw) -> RenderJob:
    base = dict(src=tmp_path / "v.mp4", out=tmp_path / "o.mp4", workdir=tmp_path / "w", src_w=1920,
                src_h=1080, fps=25.0, timeline=Timeline(10_000, 14_000),
                layouts=[LayoutSegment(0, 4_000, Layout.FOCUS, keys=[CropKey(0, 0.4, cut=True)])],
                encoder=ENC)
    base.update(kw)
    return RenderJob(**base)


# --- graf (matn) --------------------------------------------------------------------------------


def test_graph_snapshot_subs_logo_loudnorm(tmp_path) -> None:
    job = _job(tmp_path, ass_text="[Script Info]", fonts_dir=tmp_path, logo=tmp_path / "logo.png",
               logo_position="bottom_left", logo_opacity=0.5,
               cfg=RenderConfig(loudnorm_target_lufs=-14.0))
    g, files, seek = build_graph(job)
    lines = g.split(";\n")
    assert lines[-4:] == [
        "[1:v]scale=194:-1,format=rgba,colorchannelmixer=aa=0.500[logo]",
        "[vs][logo]overlay=x=64:y=H-h-672:eof_action=repeat:format=auto[vl]",
        "[vl]format=yuv420p[vout]",
        "[ac]loudnorm=I=-14:TP=-1.5:LRA=11,afade=t=in:d=0.150,afade=t=out:st=3.850:d=0.150,"
        "aresample=48000[aout]",
    ]
    assert "[vc]ass=subs.ass:fontsdir=fonts[vs]" in lines
    assert "logo.png" not in g and "movie" not in g  # fayl yo'li grafga kirmaydi
    assert files["subs.ass"] == "[Script Info]" and seek == pytest.approx(9.0)


def test_logo_is_extra_input_not_in_graph(tmp_path) -> None:
    job = _job(tmp_path, logo=tmp_path / "logo.png")
    cmd = graph.build_command(job, "ffmpeg")
    i = cmd.index(str((tmp_path / "logo.png").resolve()))
    assert cmd[i - 1] == "-i" and cmd.count("-i") == 2
    assert "logo" not in (tmp_path / "w" / "graph.txt").read_text().replace("[logo]", "")


def test_logo_positions() -> None:
    from lahza_engine.config import SubtitleSafeZone

    z = SubtitleSafeZone()
    assert logo_overlay_xy("top_right", z, 1080, 1920) == ("W-w-64", "268")
    assert logo_overlay_xy("top_left", z, 1080, 1920) == ("64", "268")
    with pytest.raises(ValueError):
        logo_overlay_xy("markaz", z, 1080, 1920)


def test_video_only_graph_has_no_audio(tmp_path) -> None:
    g, _, _ = build_graph(_job(tmp_path, video_only=True))
    assert "[0:a]" not in g and "concat=n=1:v=1:a=0[vc]" in g and "[aout]" not in g


def test_zoom_and_cy_used_in_crop_and_cmd(tmp_path) -> None:
    lay = LayoutSegment(0, 4_000, Layout.MANUAL,
                        keys=[CropKey(0, 0.5, 0.5, 2.0, cut=True), CropKey(2_000, 0.6, 0.3, 1.0)])
    g, files, _ = build_graph(_job(tmp_path, layouts=[lay]))
    assert "crop@c0=w=302:h=540:x=808:y=270" in g
    assert files["p0.cmd"].splitlines()[-1].startswith("2.000 crop@c0 x 1000, crop@c0 y 54;")


# --- libass ----------------------------------------------------------------------------------


def test_has_filter_parses_ffmpeg_filters(monkeypatch) -> None:
    out = (" T.. = Timeline support\n ------\n TS ass               V->V       Render ASS.\n"
           " .. scdet             V->V       Detect\n ... color             |->V       Provide\n")

    class R:
        stdout = out

    capabilities.list_filters.cache_clear()
    monkeypatch.setattr(capabilities, "run", lambda *a, **k: R())
    assert has_filter("/fake/ffmpeg", "ass") and has_filter("/fake/ffmpeg", "color")
    assert not has_filter("/fake/ffmpeg", "Timeline")
    capabilities.list_filters.cache_clear()


def test_render_raises_libass_missing_with_uzbek_message(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(graph, "has_filter", lambda ff, name: False)
    monkeypatch.setattr(graph, "find_tool", lambda name: Path("/fake/ffmpeg"))
    with pytest.raises(LibassMissing, match="libass'siz"):
        graph.render(_job(tmp_path, ass_text="x"))


# --- fayl nomi va limitlar ----------------------------------------------------------------------


def test_filename_template() -> None:
    assert ex.render_filename(ex.DEFAULT_FILENAME_TEMPLATE, "Test Shou", "12-son", 3,
                              "Pul haqida!") == "test-shou_12-son_03_pul-haqida"
    assert ex.render_filename("{nn} - {sarlavha}", "a", "b", 1, "") == "01 - klip"
    assert "/" not in ex.render_filename("../{shou}/x", "s", "e", 1, "t")
    with pytest.raises(ValueError, match="noma'lum maydon"):
        ex.render_filename("{shou}_{sana}", "a", "b", 1, "c")


def test_platform_limits() -> None:
    assert check_limits(60_000, 1080, 1920) == []
    w = check_limits(60_000, 540, 960, file_bytes=5 * 2**30)
    assert any("1080x1920" in x for x in w)
    assert not any("GB" in x for x in w)  # no unverified Instagram file size limit
    lim = {"x": {"max_duration_s": 90, "width": 1080, "height": 1920, "aspect": "9:16"}}
    assert "uzun" in check_limits(95_000, 1080, 1920, platform="x", limits=lim)[0]
    assert "nisbati" in check_limits(10_000, 1080, 1080, platform="x", limits=lim)[0]
    with pytest.raises(ValueError, match="Unknown target platform"):
        check_limits(10_000, 1, 1, platform="yoq")
    assert "1.78" in source_quality_warning(1920, 1080)
    assert source_quality_warning(3840, 2160) is None
    assert source_quality_warning(1920, 1080, uses_crop=False) is None


def test_parse_scene_times() -> None:
    err = ("[Parsed_scdet_1 @ 0x1] lavfi.scd.score: 21.7, lavfi.scd.time: 2\n"
           "[Parsed_scdet_1 @ 0x1] lavfi.scd.score: 30, lavfi.scd.time: 4.52\n")
    assert parse_scene_times(err, True) == [2.0, 4.52]
    assert parse_scene_times("n: 0 pts: 25600 pts_time:2.04   duration: 1", False) == [2.04]


# --- haqiqiy FFmpeg (subtitrsiz) -----------------------------------------------------------------


@pytest.fixture(scope="module")
def media(tmp_path_factory) -> dict:
    d = tmp_path_factory.mktemp("m3")
    v = d / "kesim.mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "testsrc2=size=1280x720:rate=25:duration=4",
         "-f", "lavfi", "-i", "color=c=red:size=1280x720:rate=25:duration=4",
         "-f", "lavfi", "-i", "sine=frequency=330:sample_rate=48000:duration=8",
         "-filter_complex", "[0:v][1:v]concat=n=2:v=1:a=0[v]", "-map", "[v]", "-map", "2:a",
         "-c:v", "mpeg4", "-q:v", "5", "-c:a", "aac", str(v)], check=True)
    logo = d / "logo.png"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "color=c=blue:s=200x100",
                    "-frames:v", "1", str(logo)], check=True)
    return {"video": v, "logo": logo, "dir": d}


def _probe(p: Path) -> dict:
    r = subprocess.run(["ffprobe", "-v", "error", "-print_format", "json", "-show_streams",
                        "-show_format", str(p)], capture_output=True, text=True, check=True)
    return json.loads(r.stdout)


@requires_ffmpeg
@pytest.mark.ffmpeg
def test_scene_cut_detected(media) -> None:
    from lahza_engine.media.scenes import detect_scene_cuts

    cuts = detect_scene_cuts(media["video"], 1_000, 7_000)
    assert len(cuts) == 1 and abs(cuts[0] - 4_000) <= 80
    assert detect_scene_cuts(media["video"], 0, 3_000) == []


@requires_ffmpeg
@pytest.mark.ffmpeg
def test_render_without_subs_with_logo_and_loudnorm(media, tmp_path) -> None:
    job = RenderJob(src=media["video"], out=tmp_path / "o.mp4", workdir=tmp_path / "w", src_w=1280,
                    src_h=720, fps=25.0, timeline=Timeline(1_000, 4_000, cuts=[(2_000, 2_500)]),
                    layouts=[LayoutSegment(0, 1_500, Layout.FOCUS, keys=[CropKey(0, 0.3, cut=True)]),
                             LayoutSegment(1_500, 2_500, Layout.FIT_BLUR)],
                    encoder=ENC, cfg=RenderConfig(loudnorm_target_lufs=-14.0),
                    ass_text=build_ass([Word(text="salom", start_ms=1_000, end_ms=1_500)],
                                       Timeline(1_000, 4_000, cuts=[(2_000, 2_500)]),
                                       StyleTemplate()),
                    logo=media["logo"])
    if not has_filter("ffmpeg", "ass"):
        with pytest.raises(LibassMissing):
            graph.render(job)
    graph.render(job, timeout_s=120, allow_no_subs=True)
    info = _probe(job.out)
    v = next(s for s in info["streams"] if s["codec_type"] == "video")
    a = next(s for s in info["streams"] if s["codec_type"] == "audio")
    assert (v["width"], v["height"]) == (1080, 1920) and a["sample_rate"] == "48000"
    assert float(info["format"]["duration"]) == pytest.approx(2.5, abs=0.2)


def _project(tmp_path: Path, video: Path, speaker: str | None = None):
    conn = db.open_project(tmp_path / "ep.lahza")
    with conn:
        conn.execute("INSERT INTO media(id, path, hash, duration_ms, fps, width, height, "
                     "audio_channels) VALUES ('m1', ?, 'h', 8000, 25, 1280, 720, 1)", (str(video),))
    texts = ["ee", "bugun", "pul", "haqida", "gaplashamiz", "ahmoq", "gap", "yo'q"]
    words = [Word(text=t, start_ms=500 + i * 600, end_ms=1_000 + i * 600, speaker=speaker)
             for i, t in enumerate(texts)]
    db.save_transcript(conn, "m1", Transcript(sentences=[
        Sentence(id=0, start_ms=500, end_ms=words[-1].end_ms, words=words)]))
    clip = Clip(id="c1", media_id="m1", start_ms=500, end_ms=5_500, start_sentence_id=0,
                end_sentence_id=0, title="Pul haqida", caption="Izoh", hashtags=["#pul"])
    db.save_clips(conn, [clip])
    return conn, clip


@requires_ffmpeg
@pytest.mark.ffmpeg
def test_export_clip_manual_keyframes_vtt_warnings(media, tmp_path) -> None:
    conn, clip = _project(tmp_path, media["video"])
    with conn:
        conn.executemany(
            "INSERT INTO reframe_keyframes(clip_id, t_ms, layout, cx, cy, zoom, lane, source) "
            "VALUES ('c1', ?, ?, ?, 0.5, 1.0, ?, 'qolda')",
            [(0, "manual", 0.2, "a"), (2_000, "split", 0.3, "a"), (2_000, "split", 0.7, "b"),
             (4_000, "fit_blur", None, "a")])
    style = StyleTemplate(remove_fillers=True, mask_profanity=True, profanity_words=["ahmoq"],
                          logo_path=str(tmp_path / "yoq.png"))
    settings = Settings(data_dir=tmp_path / "data")
    out = ex.export_clip(conn, "m1", clip, tmp_path / "eksport", tmp_path / "work", settings, ENC,
                         style, show_name="Shou", episode="1", index=2,
                         filename_template="{nn}_{sarlavha}", allow_no_subs=True)
    assert out.video.name == "02_pul-haqida.mp4" and out.vtt and out.vtt.name == "02_pul-haqida.vtt"
    vtt = out.vtt.read_text(encoding="utf-8")
    assert vtt.startswith("WEBVTT") and "a****" in vtt and "ee " not in vtt
    assert any("Logotip" in w for w in out.warnings)
    assert any("4K" in w for w in out.warnings)
    if not has_filter("ffmpeg", "ass"):
        assert any("libass" in w for w in out.warnings)
    v = next(s for s in _probe(out.video)["streams"] if s["codec_type"] == "video")
    assert (v["width"], v["height"]) == (1080, 1920)
    # qo'lda yozuv bor - avto qatorlar yozilmaydi
    n = conn.execute("SELECT COUNT(*) FROM reframe_keyframes WHERE source='avto'").fetchone()[0]
    assert n == 0
    assert ex.load_keyframes(conn, "c1", "qolda")[1] == Keyframe(2_000, Layout.SPLIT, 0.3, 0.5)


class _OneFace:
    def detect(self, frame):
        from lahza_engine.reframe.faces import Box

        return [Box(0.6, 0.3, 0.1, 0.15)]


@requires_ffmpeg
@pytest.mark.ffmpeg
def test_preview_frame_and_auto_keyframes_saved(media, tmp_path) -> None:
    conn, clip = _project(tmp_path, media["video"])
    settings = Settings(data_dir=tmp_path / "data")
    out = ex.render_preview_frame(conn, "m1", clip, 1_200, StyleTemplate(logo_path=str(media["logo"])),
                                  settings, tmp_path / "p.jpg", detector=_OneFace())
    v = next(s for s in _probe(out)["streams"] if s["codec_type"] == "video")
    assert (v["width"], v["height"]) == (1080, 1920)
    rows = ex.load_keyframes(conn, "c1", "avto")
    assert rows and rows[0].layout is Layout.FOCUS and abs(rows[0].cx - 0.65) < 0.01
    # sahna kesimi (manba 4 s -> chiqish 3.5 s) dan keyin kamera yo'li qayta boshlangan
    segs, src = ex.resolve_layouts(conn, media["video"], clip, Timeline(500, 5_500), None, settings,
                                   1280, 720, use_auto_cache=True)
    assert src == "avto" and segs[0].layout is Layout.FOCUS
    # ikkinchi preview keshdan (detektorsiz ham focus)
    ex.render_preview_frame(conn, "m1", clip, 4_900, StyleTemplate(), settings, tmp_path / "p2.jpg")
    assert (tmp_path / "p2.jpg").stat().st_size > 0


@requires_ffmpeg
@pytest.mark.ffmpeg
def test_observations_mark_scene_and_text_cuts(media, tmp_path) -> None:
    clip = Clip(id="c", media_id="m", start_ms=1_000, end_ms=7_000, start_sentence_id=0,
                end_sentence_id=0, cuts=[(2_000, 2_600)])
    tl = Timeline(1_000, 7_000, clip.cuts)
    words = [Word(text="a", start_ms=1_000, end_ms=3_000, speaker="A"),
             Word(text="b", start_ms=2_800, end_ms=5_000, speaker="B")]
    obs = ex.observations_for_clip(media["video"], clip, tl, _OneFace(), Settings(), 1280, 720,
                                   scene_cuts=[4_000], words=words)
    cut_ts = [o.t_ms for o in obs if o.shot_cut]
    assert len(cut_ts) == 2
    assert abs(cut_ts[0] - 1_000) <= 200 and abs(cut_ts[1] - 2_400) <= 200
    assert any(o.overlap_speech for o in obs) and {o.speaker for o in obs} >= {"A", "B"}
