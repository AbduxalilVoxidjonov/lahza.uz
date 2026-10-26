"""Dekodlanmaydigan video kodeki (AV1 va h.k.): import rad etiladi, render aniq xato kodi beradi.

AV1 faqat ishlatilayotgan ffmpeg'da libdav1d (yoki libaom-av1) bo'lsa qabul qilinadi."""

from __future__ import annotations

import json
import shutil
import subprocess
import time
from pathlib import Path
from types import SimpleNamespace

import pytest
from _api_helpers import make_client
from conftest import requires_ffmpeg

from lahza_engine.core.events import EventBus
from lahza_engine.core.jobs import JobManager
from lahza_engine.media import codec_check
from lahza_engine.media.codec_check import (
    UNSUPPORTED_CODEC,
    UnsupportedCodec,
    check_decodable,
    codec_supported,
    decoder_failure_codec,
    parse_decoders,
)

# Jonli sinovdagi haqiqiy log (bundled LGPL ffmpeg 7.1.1, dav1d'siz).
AV1_LOG = """\
[av1 @ 0x7b74c2ca80] Your platform doesn't support hardware accelerated AV1 decoding.
[av1 @ 0x7b74c2ca80] Failed to get pixel format.
[av1 @ 0x7b74c2ca80] Get current frame error
[vist#0:0/av1 @ 0x7b74c08600] [dec:av1 @ 0x7b74c483c0] Error submitting packet to decoder: Function not implemented
[vist#0:0/av1 @ 0x7b74c08600] [dec:av1 @ 0x7b74c483c0] Decode error rate 1 exceeds maximum 0.666667
"""
CORRUPT_H264_LOG = """\
[h264 @ 0x1] Invalid NAL unit size (1234 > 99).
[h264 @ 0x1] Error splitting the input into NAL units.
[vist#0:0/h264 @ 0x2] [dec:h264 @ 0x3] Error submitting packet to decoder: Invalid data found when processing input
"""

# `ffmpeg -decoders` chiqishidan parcha (7.1.1).
DECODERS_HEADER = """\
Decoders:
 V..... = Video
 A..... = Audio
 S..... = Subtitle
 .F.... = Frame-level multithreading
 ------
"""
DECODERS_NO_DAV1D = DECODERS_HEADER + """\
 VFS..D h264                 H.264 / AVC / MPEG-4 AVC / MPEG-4 part 10
 VFS..D hevc                 HEVC (High Efficiency Video Coding)
 V....D av1                  Alliance for Open Media AV1
"""
DECODERS_DAV1D = DECODERS_NO_DAV1D + """\
 V..... libdav1d             dav1d AV1 decoder by VideoLAN (codec av1)
"""

BUNDLED_BIN = Path(__file__).resolve().parents[2] / "app" / "src-tauri" / "resources" / "bin"


# --- log tanish -------------------------------------------------------------------------------


def test_decoder_failure_recognized_from_real_av1_log() -> None:
    assert decoder_failure_codec(AV1_LOG) == "av1"


@pytest.mark.parametrize("log, codec", [
    ("Decoder (codec av1) not found for input stream #0:0", "av1"),
    ("[vist#0:0/vp9 @ 0x1] [dec:vp9 @ 0x2] Error submitting packet to decoder: Function not implemented",
     "vp9"),
    ("[hevc @ 0x9] Failed to get pixel format.", "hevc"),
])
def test_decoder_failure_variants(log: str, codec: str) -> None:
    assert decoder_failure_codec(log) == codec


@pytest.mark.parametrize("log", [CORRUPT_H264_LOG, "", "Error opening output file out.mp4.",
                                 "[Parsed_ass_0 @ 0x1] Function not implemented"])
def test_other_errors_not_classified_as_codec(log: str) -> None:
    assert decoder_failure_codec(log) is None


def test_unsupported_codec_message_and_detail() -> None:
    e = UnsupportedCodec("av1")
    assert "AV1" in str(e) and "H.264" in str(e)
    assert isinstance(e, RuntimeError)  # mavjud `except RuntimeError` joylari buzilmaydi
    assert e.detail() == {"code": UNSUPPORTED_CODEC, "message": str(e), "codec": "av1", "label": "AV1"}


# --- check_decodable (ffprobe/ffmpeg soxtalashtirilgan) ---------------------------------------


def _fake_tools(monkeypatch, *, codec: str | None, probe_rc: int = 0, decode_rc: int = 0,
                decode_err: str = "", decoders: str = "") -> list[list[str]]:
    """`decoders` - `ffmpeg -decoders` chiqishi ("" = ro'yxat olinmadi, birinchi kadr sinovi)."""
    calls: list[list[str]] = []

    def fake_run(args, timeout=None):
        args = [str(a) for a in args]
        calls.append(args)
        if "-decoders" in args:
            return SimpleNamespace(returncode=0, stdout=decoders, stderr="")
        if Path(args[0]).name == "ffprobe":
            streams = [{"codec_name": codec}] if codec else []
            return SimpleNamespace(returncode=probe_rc, stdout=json.dumps({"streams": streams}),
                                   stderr="")
        return SimpleNamespace(returncode=decode_rc, stdout="", stderr=decode_err)

    monkeypatch.setattr(codec_check, "find_tool", lambda name: Path("/fake") / name)
    monkeypatch.setattr(codec_check, "run", fake_run)
    return calls


def test_parse_decoders_real_output() -> None:
    names = parse_decoders(DECODERS_DAV1D)
    assert {"h264", "hevc", "av1", "libdav1d"} <= names
    assert "=" not in names and "------" not in names and "Decoders:" not in names
    assert "libdav1d" not in parse_decoders(DECODERS_NO_DAV1D)
    assert parse_decoders("") == frozenset()


@pytest.mark.parametrize("listing, expected", [
    (DECODERS_DAV1D, True),
    (DECODERS_NO_DAV1D, False),  # ichki `av1` apparatsiz ishlamaydi - hisobga olinmaydi
    (DECODERS_NO_DAV1D + " V....D libaom-av1           libaom AV1 (codec av1)\n", True),
    ("", None),
])
def test_codec_supported_av1(monkeypatch, listing: str, expected) -> None:
    _fake_tools(monkeypatch, codec="av1", decoders=listing)
    assert codec_supported("av1", "/fake/ffmpeg") is expected
    assert codec_supported("h264", "/fake/ffmpeg") is True  # maxsus talab yo'q


def test_check_rejects_av1(monkeypatch, tmp_path: Path) -> None:
    # Dekoderlar ro'yxati olinmadi -> birinchi kadr sinovi xatoni ushlaydi (eski xatti-harakat).
    calls = _fake_tools(monkeypatch, codec="av1", decode_rc=69, decode_err=AV1_LOG)
    with pytest.raises(UnsupportedCodec) as ei:
        check_decodable(tmp_path / "v.mp4")
    assert ei.value.codec == "av1" and ei.value.code == UNSUPPORTED_CODEC
    decode = calls[-1]
    assert decode[decode.index("-frames:v") + 1] == "1"  # faqat birinchi kadr


def test_check_rejects_av1_without_dav1d_before_decoding(monkeypatch, tmp_path: Path) -> None:
    calls = _fake_tools(monkeypatch, codec="av1", decoders=DECODERS_NO_DAV1D)
    with pytest.raises(UnsupportedCodec) as ei:
        check_decodable(tmp_path / "v.mp4")
    assert ei.value.codec == "av1"
    assert not any("-frames:v" in c for c in calls)  # dekodlashga urinilmagan


def test_check_accepts_av1_with_dav1d(monkeypatch, tmp_path: Path) -> None:
    calls = _fake_tools(monkeypatch, codec="av1", decoders=DECODERS_DAV1D)
    assert check_decodable(tmp_path / "v.mp4") == "av1"
    assert any("-frames:v" in c for c in calls)  # baribir birinchi kadr dekodlab ko'rilgan


def test_check_av1_with_dav1d_but_decode_fails(monkeypatch, tmp_path: Path) -> None:
    _fake_tools(monkeypatch, codec="av1", decoders=DECODERS_DAV1D, decode_rc=69, decode_err=AV1_LOG)
    with pytest.raises(UnsupportedCodec):
        check_decodable(tmp_path / "v.mp4")


def test_check_accepts_decodable(monkeypatch, tmp_path: Path) -> None:
    _fake_tools(monkeypatch, codec="hevc")
    assert check_decodable(tmp_path / "v.mp4") == "hevc"


def test_check_ignores_non_codec_failures(monkeypatch, tmp_path: Path) -> None:
    # Buzuq fayl - kodek muammosi emas: import to'xtatilmaydi (xato keyingi bosqichda chiqadi).
    _fake_tools(monkeypatch, codec="h264", decode_rc=1, decode_err=CORRUPT_H264_LOG)
    assert check_decodable(tmp_path / "v.mp4") == "h264"
    # ffprobe faylni o'qiy olmadi / video yo'q - ffmpeg chaqirilmaydi.
    calls = _fake_tools(monkeypatch, codec=None, probe_rc=1)
    assert check_decodable(tmp_path / "v.mp4") is None
    assert len(calls) == 1


def test_check_non_av1_skips_decoder_listing(monkeypatch, tmp_path: Path) -> None:
    calls = _fake_tools(monkeypatch, codec="h264", decoders=DECODERS_NO_DAV1D)
    assert check_decodable(tmp_path / "v.mp4") == "h264"
    assert not any("-decoders" in c for c in calls)


# --- import: epizod yaratilishidan OLDIN rad etiladi -----------------------------------------


def test_import_rejects_unsupported_codec_before_episode(monkeypatch, tmp_path: Path) -> None:
    c, st = make_client(tmp_path, monkeypatch)
    pid = c.post("/v1/projects", json={"name": "Shou"}).json()["id"]
    src = tmp_path / "av1.mp4"
    src.write_bytes(b"\x00" * 1024)
    _fake_tools(monkeypatch, codec="av1", decode_rc=69, decode_err=AV1_LOG)
    r = c.post("/v1/media:import", json={"project_id": pid, "path": str(src)})
    assert r.status_code == 415
    detail = r.json()["detail"]
    assert detail["code"] == UNSUPPORTED_CODEC and detail["codec"] == "av1"
    assert "AV1" in detail["message"]
    assert st.lib("SELECT id FROM episodes") == []
    assert not list(st.settings.library_dir.glob("*/*.lahza"))  # papka ham yaratilmagan


def test_create_episode_raises_for_jobs(monkeypatch, tmp_path: Path) -> None:
    """YouTube/navbat oqimi: create_episode vazifa ichida - xato kodi vazifa meta'siga tushadi."""
    from lahza_engine.api.routes_episodes import create_episode

    c, st = make_client(tmp_path, monkeypatch)
    pid = c.post("/v1/projects", json={"name": "Shou"}).json()["id"]
    _fake_tools(monkeypatch, codec="av1", decode_rc=69, decode_err=AV1_LOG)
    with pytest.raises(UnsupportedCodec):
        create_episode(st, pid, tmp_path / "x.mp4", None)
    assert st.lib("SELECT id FROM episodes") == []


def test_job_manager_records_error_code() -> None:
    jm = JobManager(EventBus())

    def work(job):
        raise UnsupportedCodec("av1")

    job = jm.submit("export", work)
    for _ in range(200):
        if job.status in ("done", "failed", "cancelled"):
            break
        time.sleep(0.01)
    assert job.status == "failed"
    assert job.meta["error_code"] == UNSUPPORTED_CODEC
    assert job.meta["error_params"]["codec"] == "av1"
    assert "AV1" in (job.error or "") and "ffmpeg" not in (job.error or "")


def test_job_manager_keeps_existing_error_code() -> None:
    jm = JobManager(EventBus())

    def work(job):
        job.meta["error_code"] = "network"
        raise UnsupportedCodec("av1")

    job = jm.submit("download", work)
    for _ in range(200):
        if job.status == "failed":
            break
        time.sleep(0.01)
    assert job.meta["error_code"] == "network"


# --- render: xom ffmpeg logi o'rniga unsupported_codec ---------------------------------------


def test_render_run_maps_decoder_failure(monkeypatch, tmp_path: Path) -> None:
    from lahza_engine.render import graph

    out = tmp_path / "out" / "clip.mp4"
    job = SimpleNamespace(out=out, workdir=tmp_path)

    def fake_run(cmd, **kw):
        out.write_bytes(b"chala")
        return SimpleNamespace(returncode=69, stdout="", stderr=AV1_LOG)

    monkeypatch.setattr(subprocess, "run", fake_run)
    with pytest.raises(UnsupportedCodec) as ei:
        graph._run(["ffmpeg"], job, None)
    assert ei.value.codec == "av1"
    assert not out.exists()  # chala MP4 o'chirilgan (graph._run tuzatishi saqlangan)
    assert (tmp_path / "ffmpeg.log").read_text(encoding="utf-8") == AV1_LOG


def test_render_run_other_errors_unchanged(monkeypatch, tmp_path: Path) -> None:
    from lahza_engine.render import graph

    job = SimpleNamespace(out=tmp_path / "o.mp4", workdir=tmp_path)
    monkeypatch.setattr(subprocess, "run", lambda cmd, **kw: SimpleNamespace(
        returncode=1, stdout="", stderr="Error opening output file"))
    with pytest.raises(RuntimeError) as ei:
        graph._run(["ffmpeg"], job, None)
    assert not isinstance(ei.value, UnsupportedCodec)
    assert "render xatosi (ffmpeg 1)" in str(ei.value)


# --- haqiqiy ffmpeg ---------------------------------------------------------------------------


@requires_ffmpeg
def test_real_h264_is_decodable(tmp_path: Path) -> None:
    src = tmp_path / "h264.mp4"
    r = subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "testsrc=d=1:s=160x120:r=10",
                        "-pix_fmt", "yuv420p", "-c:v", "mpeg4", str(src)], capture_output=True)
    if r.returncode != 0:
        pytest.skip("sinov videosi yaratilmadi")
    assert check_decodable(src) == "mpeg4"


def _bundled_has_dav1d() -> bool | None:
    """True/False - bundled ffmpeg'da libdav1d bormi; bundled ffmpeg yo'q bo'lsa None."""
    ff = BUNDLED_BIN / "ffmpeg"
    if not ff.is_file() or not (BUNDLED_BIN / "ffprobe").is_file():
        return None
    r = subprocess.run([str(ff), "-hide_banner", "-decoders"], capture_output=True, text=True)
    if r.returncode != 0:
        return None
    return "libdav1d" in parse_decoders(r.stdout)


def _bundled_lacks_av1() -> bool:
    return _bundled_has_dav1d() is False


def _system_av1_encoder() -> str | None:
    if shutil.which("ffmpeg") is None:
        return None
    r = subprocess.run(["ffmpeg", "-hide_banner", "-encoders"], capture_output=True, text=True)
    return next((e for e in ("libsvtav1", "libaom-av1", "librav1e") if e in r.stdout), None)


@pytest.mark.skipif(not _bundled_lacks_av1() or _system_av1_encoder() is None,
                    reason="bundled dav1d'siz ffmpeg yoki AV1 enkoderli tizim ffmpeg'i yo'q")
def test_real_av1_rejected_by_bundled_ffmpeg(monkeypatch, tmp_path: Path) -> None:
    src = tmp_path / "av1.mp4"
    r = subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i",
                        "testsrc=d=1:s=320x240:r=10", "-pix_fmt", "yuv420p",
                        "-c:v", str(_system_av1_encoder()), str(src)], capture_output=True)
    if r.returncode != 0:
        pytest.skip("AV1 sinov videosi yaratilmadi")
    monkeypatch.setenv("LAHZA_BIN_DIR", str(BUNDLED_BIN))
    with pytest.raises(UnsupportedCodec) as ei:
        check_decodable(src)
    assert ei.value.codec == "av1"


@pytest.mark.skipif(not _bundled_has_dav1d() or _system_av1_encoder() is None,
                    reason="bundled ffmpeg'da libdav1d yoki AV1 enkoderli tizim ffmpeg'i yo'q")
def test_real_av1_decoded_by_bundled_ffmpeg_with_dav1d(monkeypatch, tmp_path: Path) -> None:
    src = tmp_path / "av1.mp4"
    r = subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i",
                        "testsrc=d=1:s=320x240:r=10", "-pix_fmt", "yuv420p",
                        "-c:v", str(_system_av1_encoder()), str(src)], capture_output=True)
    if r.returncode != 0:
        pytest.skip("AV1 sinov videosi yaratilmadi")
    monkeypatch.setenv("LAHZA_BIN_DIR", str(BUNDLED_BIN))
    assert check_decodable(src) == "av1"
