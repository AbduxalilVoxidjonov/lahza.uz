"""Montaj renderi (MontageTimeline -> FFmpeg), montaj hisoboti (`_edl.json`), matn qatlami (ASS).

Haqiqiy ffmpeg bilan, libass'siz rejimda (allow_no_subs=True): sintetik manbalar - 1920x1080
(ovozli), 1080x1920 (mono ovoz, boshqa chastota), 1280x720 (ovozsiz); o'tishlar, harakat, freeze,
rang, musiqa + ducking, intro karta; chiqish 9:16, 1:1, 16:9.
"""

import json
import subprocess
import threading
from pathlib import Path

import numpy as np
import pytest
from conftest import HAS_FFMPEG, has_libass, make_words, requires_ffmpeg

from lahza_engine.config import Settings
from lahza_engine.core.runner import Cancelled
from lahza_engine.fx.registry import GPL_FILTERS, IO_FILTERS, check_graph, graph_filters
from lahza_engine.montage.model import (
    Brand,
    Captions,
    Crop,
    Format,
    FxRef,
    MediaRef,
    MontageTimeline,
    MusicItem,
    TextItem,
    TransitionRef,
    VideoItem,
)
from lahza_engine.montage.report import edl_report
from lahza_engine.reframe.faces import Box
from lahza_engine.render import montage_render as mr
from lahza_engine.render.capabilities import LibassMissing
from lahza_engine.render.encoders import EncoderChoice
from lahza_engine.subtitle.ass import build_montage_ass
from lahza_engine.subtitle.style import StyleTemplate

ENC = EncoderChoice("mpeg4", ("-c:v", "mpeg4", "-q:v", "5", "-pix_fmt", "yuv420p"), False)


def _ff(*args: str) -> None:
    subprocess.run(["ffmpeg", "-v", "error", "-y", *args], check=True)


@pytest.fixture(scope="module")
def media(tmp_path_factory) -> dict[str, MediaRef]:
    d = tmp_path_factory.mktemp("msrc")
    if not HAS_FFMPEG:
        pytest.skip("ffmpeg yo'q")
    try:
        _ff("-f", "lavfi", "-i", "testsrc2=s=1920x1080:r=25:d=5", "-f", "lavfi", "-i",
            "sine=f=440:r=48000:d=5", "-c:v", "mpeg4", "-q:v", "5", "-c:a", "aac", "-shortest",
            str(d / "a.mp4"))
        _ff("-f", "lavfi", "-i", "testsrc2=s=1080x1920:r=30:d=5", "-f", "lavfi", "-i",
            "sine=f=660:r=44100:d=5", "-c:v", "mpeg4", "-q:v", "5", "-c:a", "aac", "-ac", "1",
            "-shortest", str(d / "b.mp4"))
        _ff("-f", "lavfi", "-i", "testsrc2=s=1280x720:r=30:d=5", "-c:v", "mpeg4", "-q:v", "5",
            str(d / "c.mp4"))
        _ff("-f", "lavfi", "-i", "sine=f=220:r=44100:d=12", "-c:a", "aac", str(d / "m.m4a"))
    except (OSError, subprocess.CalledProcessError):
        pytest.skip("ffmpeg yo'q yoki sintetik manba yaratib bo'lmadi")
    return {
        "a": MediaRef(id="a", path=str(d / "a.mp4"), hash="ha", duration_ms=5000, width=1920,
                      height=1080, fps=25),
        "b": MediaRef(id="b", path=str(d / "b.mp4"), hash="hb", duration_ms=5000, width=1080,
                      height=1920, fps=30),
        "c": MediaRef(id="c", path=str(d / "c.mp4"), duration_ms=5000, width=1280, height=720,
                      fps=30, has_audio=False),
        "music": MediaRef(id="music", path=str(d / "m.m4a"), duration_ms=12000, width=0,
                          height=0, fps=0),
    }


def _rich_tl(media: dict[str, MediaRef], aspect: str = "9:16", **kw) -> MontageTimeline:
    base = dict(
        format=Format.for_aspect(aspect),
        media=media,
        video=[
            VideoItem(id="v1", media="a", src_in_ms=500, src_out_ms=2300, reason="hook",
                      fx=[FxRef(plugin="uz.lahza.motion.punch-in", at_ms=1000, dur_ms=350)]),
            VideoItem(id="v2", media="b", src_in_ms=1000, src_out_ms=2800,
                      transition_in=TransitionRef(plugin="uz.lahza.tr.dissolve", dur_ms=400),
                      fx=[FxRef(plugin="uz.lahza.speed.freeze", at_ms=600, params={"dur_ms": 400})]),
            VideoItem(id="v3", media="c", src_in_ms=0, src_out_ms=1500, reframe="center",
                      transition_in=TransitionRef(plugin="uz.lahza.tr.cut", dur_ms=200),
                      fx=[FxRef(plugin="uz.lahza.motion.pan", params={"yonalish": "chapga"})]),
            VideoItem(id="v4", media="a", src_in_ms=2500, src_out_ms=4300, speed=1.5,
                      crop=Crop(cx=0.3, cy=0.5, zoom=1.2),
                      transition_in=TransitionRef(plugin="uz.lahza.tr.fadeblack", dur_ms=300),
                      fx=[FxRef(plugin="uz.lahza.motion.shake"),
                          FxRef(plugin="uz.lahza.motion.push-in", at_ms=0)]),
        ],
        music=[MusicItem(media="music", gain_db=-12, duck=True)],
        color=FxRef(plugin="uz.lahza.color.warm"),
        text=[TextItem(id="intro", start_ms=0, end_ms=1000, text="Intro", kind="card",
                       background="#203040")],
    )
    base.update(kw)
    return MontageTimeline(**base)


def _probe(path: Path) -> dict:
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                        "stream=codec_type,width,height,duration,sample_aspect_ratio,start_time",
                        "-of", "json", str(path)], capture_output=True, text=True, check=True)
    out = {}
    for s in json.loads(r.stdout)["streams"]:
        out[s["codec_type"]] = s
    return out


def _rgb(jpg: Path, w: int, h: int) -> np.ndarray:
    r = subprocess.run(["ffmpeg", "-v", "error", "-i", str(jpg), "-s", f"{w}x{h}", "-f", "rawvideo",
                        "-pix_fmt", "rgb24", "-"], capture_output=True, check=True)
    return np.frombuffer(r.stdout, np.uint8).reshape(h, w, 3).astype(np.float32)


# --- Model yordamchilari, segmentlar, hisobot ---------------------------------------------------


def test_offsets_and_segments(media) -> None:
    tl = _rich_tl(media)
    segs = mr.plan_segments(tl)
    fps = tl.format.fps
    starts = tl.item_starts()
    for sg, st in zip(segs, starts, strict=True):
        assert sg.start_f == round(st * fps / 1000)
    assert segs[1].xfade == "dissolve" and segs[1].overlap_f == 12
    # Kesim: model 200 ms ustma-ust hisoblagan - oldingi element shu joyda tugaydi.
    assert segs[2].xfade is None and segs[1].end_f == segs[2].start_f
    assert segs[3].xfade == "fadeblack"
    assert segs[-1].end_f == round((starts[-1] + tl.video[-1].out_duration_ms) * fps / 1000)
    outro = _rich_tl(media, text=[TextItem(id="o", start_ms=6000, end_ms=8000, text="CTA",
                                            kind="card")])
    assert outro.duration_ms == 8000  # video tugagach karta oralig'i


def test_edl_report_content(media) -> None:
    tl = _rich_tl(media)
    r = edl_report(tl)
    assert r["haqiqiy_kadr"] is True and r["generativ"] is False
    assert r["duration_ms"] == tl.duration_ms
    assert [i["id"] for i in r["items"]] == ["v1", "v2", "v3", "v4"]
    v1 = r["items"][0]
    assert v1["media"]["path"] == media["a"].path and v1["media"]["hash"] == "ha"
    assert (v1["src_in_ms"], v1["src_out_ms"], v1["out_start_ms"]) == (500, 2300, 0)
    assert v1["fx"][0]["plugin"] == "uz.lahza.motion.punch-in" and v1["fx"][0]["params"]["zoom"] == 1.25
    assert v1["reason"] == "hook"
    assert r["items"][1]["transition_in"] == {"plugin": "uz.lahza.tr.dissolve", "dur_ms": 400}
    assert r["color"]["plugin"] == "uz.lahza.color.warm"
    assert {s["id"] for s in r["sources"]} == {"a", "b", "c"}
    assert r["music"][0]["duck"] is True
    json.dumps(r)


def test_montage_ass_text_layer() -> None:
    items = [TextItem(id="a", start_ms=0, end_ms=2000, text="Salom\nDunyo {x}", kind="card"),
             TextItem(id="b", start_ms=3000, end_ms=5000, text="Obuna bo'ling", kind="cta",
                      position="lower", animation="slide_up"),
             TextItem(id="c", start_ms=500, end_ms=1500, text="Ali Valiyev", kind="lower_third",
                      animation="pop")]
    doc = build_montage_ass(items, make_words("bir ikki uch"), StyleTemplate(), width=1080,
                            height=1920)
    assert sum(ln.startswith("Style: ") for ln in doc.splitlines()) == 4  # Default+Card+Cta+Lower
    assert "Salom\\NDunyo (x)" in doc  # yangi qator va { } ekranlangan
    assert "\\move(540," in doc and "\\fscx120" in doc
    assert doc.index("Style: Card") < doc.index("[Events]")
    late = build_montage_ass(items, [], StyleTemplate(), offset_ms=2500)
    assert "Salom" not in late and "Obuna" in late


# --- Graf (oq ro'yxat, yo'llar grafga kirmaydi) ------------------------------------------------


def test_graphs_whitelisted_and_no_user_paths(media, tmp_path) -> None:
    lut = tmp_path / "my look.cube"
    lut.write_text("LUT_3D_SIZE 2\n" + "0 0 0\n1 0 0\n0 1 0\n1 1 0\n0 0 1\n1 0 1\n0 1 1\n1 1 1\n")
    items = []
    trs = ["uz.lahza.tr.fade", "uz.lahza.tr.wipeleft", "uz.lahza.tr.slideup",
           "uz.lahza.tr.zoomin", "uz.lahza.tr.smoothleft", "uz.lahza.tr.circleopen"]
    colors = ["uz.lahza.color.cool", "uz.lahza.color.bw", "uz.lahza.color.vivid",
              "uz.lahza.color.film"]
    motions = ["uz.lahza.motion.zoom-out", "uz.lahza.motion.pan", "uz.lahza.motion.shake",
               "uz.lahza.motion.punch-in"]
    for i in range(6):
        items.append(VideoItem(
            id=f"x{i}", media="abc"[i % 3], src_in_ms=0, src_out_ms=1500,
            reframe=["auto", "fit_blur", "center"][i % 3],
            transition_in=TransitionRef(plugin=trs[i], dur_ms=300) if i else None,
            fx=[FxRef(plugin=motions[i % 4]), FxRef(plugin=colors[i % 4]),
                FxRef(plugin="uz.lahza.audio.fade"),
                FxRef(plugin="uz.lahza.speed.freeze", at_ms=200)]))
    tl = _rich_tl(media, video=items, color=FxRef(plugin="uz.lahza.color.lut",
                                                  params={"file": str(lut)}),
                  brand=Brand(logo_path=str(tmp_path / "logo.png")),
                  audio={"loudnorm_lufs": -14})
    settings = Settings()
    names: set[str] = set()
    segs = mr.plan_segments(tl)
    for sg in segs:
        ig = mr.build_item_graph(tl, sg.item, tmp_path / sg.item.id, settings, n_frames=sg.n_frames)
        g = ";\n".join(ig.chains)
        names |= check_graph(g)
        assert media["a"].path not in g
    color = mr._global_color(tl, tmp_path, [])
    assert color == "lut3d=file=lut0.cube" and (tmp_path / "lut0.cube").is_file()
    g = mr.build_compose_graph(tl, segs, settings, ass=True, fonts=True, color=color,
                               music_inputs=[6], logo_idx=7)
    names |= check_graph(g)
    for p in (str(lut), media["music"].path, "logo.png"):
        assert p not in g
    assert not names & (GPL_FILTERS | IO_FILTERS)
    assert {"xfade", "acrossfade", "zoompan", "sidechaincompress", "loudnorm", "lut3d",
            "colorbalance", "hue", "curves", "drawbox", "ass", "overlay", "tpad"} <= names
    assert "eq" not in graph_filters(g)
    assert "transition=circleopen" in g and "[6:a]" in g and "[7:v]" in g


def test_libass_missing(media, tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(mr, "has_filter", lambda ffmpeg, name: False)
    monkeypatch.setattr(mr, "find_tool", lambda name: Path("ffmpeg"))
    tl = _rich_tl(media)
    with pytest.raises(LibassMissing):
        mr.render_montage(tl, tmp_path / "o.mp4", tmp_path / "w", ENC, Settings())
    assert not (tmp_path / "w").exists()  # hech narsa boshlanmagan


# --- Haqiqiy ffmpeg ---------------------------------------------------------------------------


@requires_ffmpeg
def test_render_rich_9x16(media, tmp_path) -> None:
    tl = _rich_tl(media)
    ticks: list[float] = []
    res = mr.render_montage(tl, tmp_path / "out" / "montaj.mp4", tmp_path / "w", ENC, Settings(),
                            allow_no_subs=True, on_progress=ticks.append)
    assert res.video.is_file() and not (tmp_path / "w").exists()
    p = _probe(res.video)
    v, a = p["video"], p["audio"]
    assert (v["width"], v["height"]) == (1080, 1920)
    assert v.get("sample_aspect_ratio", "1:1") in ("1:1", "N/A")
    frame = 1 / tl.format.fps
    want = tl.duration_ms / 1000
    assert abs(float(v["duration"]) - want) <= frame + 1e-3
    assert abs(float(a["duration"]) - float(v["duration"])) <= frame + 1e-3  # A/V bir xil
    assert ticks and ticks[-1] == 1.0 and ticks == sorted(ticks)
    # Hisobot
    assert res.edl == tmp_path / "out" / "montaj_edl.json"
    edl = json.loads(res.edl.read_text(encoding="utf-8"))
    assert edl["haqiqiy_kadr"] is True and edl["render"]["video"] == "montaj.mp4"
    assert len(edl["items"]) == 4 and edl["items"][2]["media"]["path"] == media["c"].path
    if not has_libass():
        assert any("libass" in w for w in res.warnings)
        assert edl["render"]["text_drawn"] is False
    assert res.srt is None


@requires_ffmpeg
@pytest.mark.parametrize("aspect,size", [("1:1", (1080, 1080)), ("16:9", (1920, 1080))])
def test_render_other_aspects(media, tmp_path, aspect, size) -> None:
    lut = tmp_path / "id.cube"
    lut.write_text("LUT_3D_SIZE 2\n0 0 0\n1 0 0\n0 1 0\n1 1 0\n0 0 1\n1 0 1\n0 1 1\n1 1 1\n")
    tl = MontageTimeline(
        format=Format.for_aspect(aspect), media=media,
        video=[VideoItem(id="a1", media="b", src_in_ms=0, src_out_ms=1500),
               VideoItem(id="a2", media="a", src_in_ms=1000, src_out_ms=2500, reframe="focus",
                         transition_in=TransitionRef(plugin="uz.lahza.tr.fade", dur_ms=500),
                         fx=[FxRef(plugin="uz.lahza.motion.zoom-out")])],
        color=FxRef(plugin="uz.lahza.color.lut", params={"file": str(lut)}))
    res = mr.render_montage(tl, tmp_path / "o.mp4", tmp_path / "w", ENC, Settings())
    p = _probe(res.video)
    assert (p["video"]["width"], p["video"]["height"]) == size
    assert abs(float(p["video"]["duration"]) - tl.duration_ms / 1000) <= 1 / 30 + 1e-3
    assert abs(float(p["audio"]["duration"]) - float(p["video"]["duration"])) <= 1 / 30 + 1e-3


def _mean_volume(path: Path, start: float, end: float) -> float:
    r = subprocess.run(["ffmpeg", "-v", "info", "-hide_banner", "-i", str(path), "-af",
                        f"atrim={start}:{end},volumedetect", "-f", "null", "-"],
                       capture_output=True, text=True)
    for line in r.stderr.splitlines():
        if "mean_volume" in line:
            return float(line.split("mean_volume:")[1].split()[0])
    return -999.0


@requires_ffmpeg
def test_silence_for_source_without_audio_and_card_color(media, tmp_path) -> None:
    tl = MontageTimeline(
        format=Format(aspect="9:16", w=540, h=960), media=media,
        video=[VideoItem(id="s1", media="a", src_in_ms=0, src_out_ms=1500),
               VideoItem(id="s2", media="c", src_in_ms=0, src_out_ms=1500, volume_db=6)],
        text=[TextItem(id="o", start_ms=3000, end_ms=4000, text="", kind="card",
                       background="#FF0000")],
        audio={"fade_ms": 0})
    res = mr.render_montage(tl, tmp_path / "o.mp4", tmp_path / "w", ENC, Settings(),
                            allow_no_subs=True)
    assert _mean_volume(res.video, 0.2, 1.3) > -40  # ovozli manba
    assert _mean_volume(res.video, 1.7, 2.8) < -80  # ovozsiz manba -> sukut
    assert abs(float(_probe(res.video)["video"]["duration"]) - 4.0) <= 1 / 30 + 1e-3
    # Outro karta (videodan keyin) - rangli fon.
    jpg = tmp_path / "card.jpg"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", "3.5", "-i", str(res.video),
                    "-frames:v", "1", str(jpg)], check=True)
    px = _rgb(jpg, 16, 16).mean(axis=(0, 1))
    assert px[0] > 180 and px[1] < 60 and px[2] < 60


@requires_ffmpeg
def test_frame_preview_matches_export(media, tmp_path) -> None:
    tl = _rich_tl(media, music=[])
    s = Settings()
    # Intro karta oralig'i: karta foni.
    card = mr.render_montage_frame(tl, 300, tmp_path / "c.jpg", s)
    px = _rgb(card, 9, 16).mean(axis=(0, 1))
    assert abs(px[0] - 0x20) < 20 and abs(px[2] - 0x40) < 20
    # Element ichida: preview = eksport kadri (NFR-M2, yumshoq chegara).
    t_ms = 1250  # v1 ichida, punch-in faol, karta va o'tishdan tashqarida  # v1 ichida, punch-in faol (o'tishdan oldin)
    prev = mr.render_montage_frame(tl, t_ms, tmp_path / "p.jpg", s)
    assert prev.is_file()
    res = mr.render_montage(tl, tmp_path / "o.mp4", tmp_path / "w", ENC, s, allow_no_subs=True)
    exp = tmp_path / "e.jpg"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t_ms / 1000 + 0.01:.3f}", "-i",
                    str(res.video), "-frames:v", "1", str(exp)], check=True)
    diff = np.abs(_rgb(prev, 108, 192) - _rgb(exp, 108, 192)).mean()
    assert diff < 8, diff
    # Freeze ichidagi va 16:9 dagi kadrlar ham xatosiz.
    starts = tl.item_starts()
    mr.render_montage_frame(tl, starts[1] + 800, tmp_path / "f.jpg", s)
    mr.render_montage_frame(tl.model_copy(update={"format": Format.for_aspect("16:9")}), 99_999,
                            tmp_path / "end.jpg", s)
    assert _rgb(tmp_path / "end.jpg", 16, 9).shape == (9, 16, 3)


@requires_ffmpeg
def test_captions_srt_and_detector_plan(media, tmp_path) -> None:
    class OneFace:
        def detect(self, frame):
            return [Box(0.6, 0.3, 0.15, 0.3)]

    words = make_words("salom dunyo bu sinov", start_ms=100)
    tl = MontageTimeline(
        format=Format(aspect="9:16", w=540, h=960), media=media,
        video=[VideoItem(id="d1", media="a", src_in_ms=0, src_out_ms=1500, reframe="auto")],
        captions=Captions(enabled=True, words=words))
    if not has_libass():
        with pytest.raises(LibassMissing):
            mr.render_montage(tl, tmp_path / "o.mp4", tmp_path / "w", ENC, Settings())
    res = mr.render_montage(tl, tmp_path / "o.mp4", tmp_path / "w", ENC, Settings(),
                            detector=OneFace(), allow_no_subs=True)
    assert res.srt is not None and "salom" in res.srt.read_text(encoding="utf-8")
    assert (_probe(res.video)["video"]["width"]) == 540
    mr.render_montage_frame(tl, 700, tmp_path / "p.jpg", Settings(), detector=OneFace())


@requires_ffmpeg
def test_cancel_kills_ffmpeg(media, tmp_path) -> None:
    tl = _rich_tl(media)
    ev = threading.Event()
    ev.set()
    with pytest.raises(Cancelled):
        mr.render_montage(tl, tmp_path / "o.mp4", tmp_path / "w", ENC, Settings(),
                          allow_no_subs=True, cancel=ev)
    ev2 = threading.Event()
    with pytest.raises(Cancelled):
        mr.render_montage(tl, tmp_path / "o2.mp4", tmp_path / "w2", ENC, Settings(),
                          allow_no_subs=True, cancel=ev2, on_progress=lambda x: ev2.set())
    assert not (tmp_path / "o2.mp4").exists()


@requires_ffmpeg
def test_frame_preview_last_ms_of_item(media, tmp_path) -> None:
    """Regressiya: element oxirgi ms'idagi preview (30 fps manba) - trim boshi yuqoriga yaxlitlanib
    yagona kadr tushib qolardi va ffmpeg "Nothing was written" bilan 500 qaytarardi."""
    tl = MontageTimeline(format=Format.for_aspect("9:16"), media=media,
                         video=[VideoItem(id="v1", media="b", src_in_ms=0, src_out_ms=3000)])
    for t in (2999, 2990, 2967, tl.duration_ms - 1):
        out = mr.render_montage_frame(tl, t, tmp_path / f"f{t}.jpg", Settings())
        assert out.is_file() and out.stat().st_size > 0, t
