"""YouTube havolasidan import (YT-1, ADR-0010): havola validatsiyasi, alohida jarayondagi yuklovchi
(soxta `yt_dlp` moduli bilan - HAQIQIY TARMOQ YO'Q), bekor qilish, davom ettirish, API xatolari va
yuklangandan keyin epizod yaratilishi."""

from __future__ import annotations

import json
import queue
import sys
import textwrap
import threading
import time
from pathlib import Path
from typing import Any

import pytest
from _api_helpers import make_client, wait_job

from lahza_engine.api import routes_youtube
from lahza_engine.core.jobs import Job
from lahza_engine.core.runner import Cancelled
from lahza_engine.media import youtube

FAKE_YTDLP = textwrap.dedent('''
    """Testlar uchun soxta yt_dlp: tarmoqqa chiqmaydi, xatti-harakati video ID'siga bog'liq."""
    import json
    import os
    import time
    from pathlib import Path

    __version__ = "2099.01.01"


    class DownloadError(Exception):
        pass


    class YoutubeDL:
        def __init__(self, params):
            self.params = params
            self.out = Path(params["outtmpl"]["default"]).parent if "outtmpl" in params else None

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def _hook(self, **d):
            for h in self.params.get("progress_hooks", []):
                h(d)

        def extract_info(self, url, download=False):
            if "v=" not in url:
                return self._listing(url)
            vid = url.split("v=", 1)[1]
            self.out.mkdir(parents=True, exist_ok=True)
            keep = {k: v for k, v in self.params.items() if k not in ("progress_hooks", "logger")}
            (self.out / "params.json").write_text(json.dumps({"url": url, **keep}))
            if vid.startswith("private"):
                raise DownloadError(f"ERROR: [youtube] {vid}: Private video. Sign in if you've been granted access")
            if vid.startswith("agegate"):
                raise DownloadError("ERROR: Sign in to confirm your age. This video may be inappropriate for some users.")
            if vid.startswith("netfail"):
                raise DownloadError("ERROR: Unable to download webpage: <urlopen error [Errno 8] nodename nor servname provided>")
            if vid.startswith("jsfail"):
                self.params["logger"].warning("n challenge solving failed: no supported JavaScript runtime")
                raise DownloadError("ERROR: Requested format is not available")
            if vid.startswith("crash"):
                os._exit(3)
            if vid.startswith("chap"):
                return {"id": vid, "title": "Boblar bilan", "duration": 600, "_type": "video",
                        "description": "Tavsif matni", "uploader": "Kanal",
                        "chapters": [{"start_time": 0, "end_time": 120, "title": "Kirish"},
                                     {"start_time": 120.5, "end_time": 600, "title": "Asosiy qism"},
                                     {"start_time": "x", "title": "buzuq"}]}
            return {"id": vid, "title": "Sarlavha/1: test", "duration": 12, "_type": "video"}

        def _listing(self, url):
            # Soxta playlist/kanal: `extract_flat` parametri va havola faylga yoziladi.
            Path(os.environ["LAHZA_FAKE_YT_LOG"]).write_text(json.dumps({"url": url, **{
                k: v for k, v in self.params.items() if k != "logger"}}))
            if "PLprivate" in url:
                raise DownloadError("ERROR: [youtube:tab] PLprivate: This playlist is private")
            if "PLslow" in url:
                time.sleep(30)
            n = 60 if ("PLbig" in url or "/@" in url) else 4
            entries = [{"_type": "url", "ie_key": "Youtube", "id": f"vid{i:08d}",
                        "url": f"https://www.youtube.com/watch?v=vid{i:08d}", "title": f"Video {i}",
                        "duration": 60 + i,
                        "thumbnails": [{"url": "https://evil.example/x.jpg"},
                                       {"url": f"https://i.ytimg.com/vi/vid{i:08d}/hq.jpg"}]}
                       for i in range(n)]
            if n == 4:
                entries[1].update(title="[Private video]", duration=None)
                entries[2].update(url="https://www.youtube.com/shorts/vid00000002")
                entries[3].update(live_status="is_upcoming")
                entries.append({"_type": "url", "id": "UCxxxxxxxxxxxxxxxxxxxxxx", "url": "https://www.youtube.com/channel/x"})
                entries.append(dict(entries[0]))  # takror
            return {"_type": "playlist", "id": "PL", "title": "Mening playlistim",
                    "entries": iter(entries[:self.params.get("playlistend") or None])}

        def process_ie_result(self, info, download=True):
            vid = info["id"]
            part = self.out / f"{vid}.mp4.part"
            final = self.out / f"{vid}.mp4"
            resumed = part.stat().st_size if part.exists() and self.params.get("continuedl") else 0
            (self.out / "resumed.txt").write_text(str(resumed))
            if vid.startswith("slow"):
                with part.open("ab") as f:
                    f.write(b"x" * 10)
                while True:
                    self._hook(status="downloading", filename=str(final), downloaded_bytes=10,
                               total_bytes=1000, speed=5.0, eta=200)
                    time.sleep(0.05)
            if vid.startswith("flaky") and not resumed:
                part.write_bytes(b"x" * 500)
                self._hook(status="downloading", filename=str(final), downloaded_bytes=500, total_bytes=1000)
                raise DownloadError("ERROR: Connection reset by peer")
            self._hook(status="downloading", filename=str(final), downloaded_bytes=250,
                       total_bytes=1000, speed=1000.0, eta=1)
            final.write_bytes(b"\\x00" * 1000)
            part.unlink(missing_ok=True)
            self._hook(status="finished", filename=str(final), downloaded_bytes=1000, total_bytes=1000)
            return {**info, "requested_downloads": [{"filepath": str(final)}]}
''')


@pytest.fixture
def fake_ytdlp(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "fake-components"
    (root / "yt_dlp").mkdir(parents=True)
    (root / "yt_dlp" / "__init__.py").write_text(FAKE_YTDLP, encoding="utf-8")
    (root / "yt_dlp" / "version.py").write_text("__version__ = '2099.01.01'\n", encoding="utf-8")
    monkeypatch.setenv("LAHZA_YTDLP_PATH", str(root))
    # Kompyuterdagi haqiqiy deno/node versiyasi testga ta'sir qilmasin (JS tekshiruvi alohida testda).
    monkeypatch.setattr(youtube, "js_runtimes", lambda _d: [])
    return root


# ---- havola validatsiyasi --------------------------------------------------------------------
VID = "dQw4w9WgXcQ"


@pytest.mark.parametrize("url", [
    f"https://www.youtube.com/watch?v={VID}",
    f"https://youtube.com/watch?v={VID}&list=PL123&t=42s",
    f"http://m.youtube.com/watch?feature=share&v={VID}",
    f"https://youtu.be/{VID}?si=abc",
    f"youtu.be/{VID}",
    f"https://www.youtube.com/shorts/{VID}",
    f"  https://www.youtube.com/live/{VID}  ",
    f"HTTPS://WWW.YOUTUBE.COM/watch?v={VID}",
])
def test_parse_video_id_accepts_youtube_links(url: str) -> None:
    assert youtube.parse_video_id(url) == VID
    assert youtube.canonical_url(VID) == f"https://www.youtube.com/watch?v={VID}"


@pytest.mark.parametrize("url", [
    "", "   ",
    f"https://vimeo.com/watch?v={VID}",
    f"https://youtube.com.evil.com/watch?v={VID}",
    f"https://evilyoutube.com/watch?v={VID}",
    f"https://www.youtube.com/watch?v={VID}x",
    "https://www.youtube.com/watch?v=short",
    "https://www.youtube.com/playlist?list=PL1234567890",
    "https://www.youtube.com/@kanal",
    "https://www.youtube.com/channel/UC1234567890",
    f"https://www.youtube.com/watch?v={VID}&v=aaaaaaaaaaa",
    f"ftp://youtube.com/watch?v={VID}",
    f"javascript://youtu.be/{VID}",
    f"https://user:pw@youtu.be/{VID}",
    f"https://youtu.be:8080/{VID}",
    f"https://youtu.be/{VID}/extra",
    "file:///etc/passwd",
])
def test_parse_video_id_rejects_other_links(url: str) -> None:
    with pytest.raises(youtube.InvalidUrl):
        youtube.parse_video_id(url)


@pytest.mark.parametrize(("text", "code"), [
    ("ERROR: [youtube] x: Private video. Sign in if you've been granted access", "private"),
    ("ERROR: Sign in to confirm your age", "age_restricted"),
    ("ERROR: Sign in to confirm you're not a bot. Use --cookies", "login_required"),
    ("<urlopen error [Errno -3] Temporary failure in name resolution>", "network"),
    ("WARNING: n challenge solving failed\nERROR: Requested format is not available", "js_runtime"),
    ("ERROR: Requested format is not available", "format_unavailable"),
    ("ERROR: Video unavailable. This video has been removed", "unavailable"),
    ("ERROR: This live event will begin in a few moments", "live"),
    ("ERROR: something odd", "unknown"),
    ("ModuleNotFoundError: No module named 'xml.etree'", "incompatible"),
])
def test_classify_error(text: str, code: str) -> None:
    got, msg = youtube.classify_error(text)
    assert got == code
    assert msg


def test_build_params_mp4_1080_no_remote_components() -> None:
    p = youtube.build_params(Path("/tmp/x"), "/opt/ffmpeg", ("deno", "/opt/deno"))
    assert "height<=1080" in p["format"] and "+ba" in p["format"]
    assert p["merge_output_format"] == "mp4"
    assert p["continuedl"] is True and p["noplaylist"] is True
    assert p["remote_components"] == []
    assert p["ffmpeg_location"] == "/opt/ffmpeg"
    assert p["js_runtimes"] == {"deno": {"path": "/opt/deno"}}
    single = youtube.build_params(Path("/tmp/x"), None, None)
    assert "+" not in single["format"] and "ffmpeg_location" not in single


# ---- alohida jarayondagi yuklovchi -----------------------------------------------------------
def test_download_success_in_child_process(tmp_path: Path, fake_ytdlp: Path) -> None:
    out = tmp_path / "dl" / "okokokokok1"
    seen: list[float] = []
    infos: list[dict[str, Any]] = []
    res = youtube.download("https://youtu.be/okokokokok1", out, cancel=threading.Event(),
                           on_progress=lambda f, _d: seen.append(f), on_info=infos.append)
    assert res.path == out / "okokokokok1.mp4" and res.path.is_file()
    assert res.title == "Sarlavha/1: test" and not res.reused
    assert infos and infos[0]["title"] == "Sarlavha/1: test"
    assert seen[-1] == 1.0 and seen == sorted(seen)
    params = json.loads((out / "params.json").read_text())
    # Bolaga faqat kanonik havola va chiqish papkasi beriladi.
    assert params["url"] == "https://www.youtube.com/watch?v=okokokokok1"
    assert params["outtmpl"]["default"].startswith(str(out))
    assert params["remote_components"] == [] and params["continuedl"] is True
    # Engine jarayoni yt_dlp'ni import qilmaydi (soxta modul faqat bolada yuklanadi).
    assert "yt_dlp" not in sys.modules or getattr(sys.modules["yt_dlp"], "__version__", "") != "2099.01.01"

    # Qayta import - tarmoqsiz: tayyor fayl qayta ishlatiladi, bola jarayon ishga tushmaydi.
    def boom(*_a: Any) -> None:
        raise AssertionError("bola jarayon ishga tushmasligi kerak")

    again = youtube.download("https://www.youtube.com/watch?v=okokokokok1", out,
                             cancel=threading.Event(), target=boom)
    assert again.reused and again.path == res.path


@pytest.mark.parametrize(("vid", "code"), [
    ("private0000", "private"),
    ("agegate0000", "age_restricted"),
    ("netfail0000", "network"),
    ("jsfail00000", "js_runtime"),
    ("crash000000", "crashed"),
])
def test_download_errors_are_explained(tmp_path: Path, fake_ytdlp: Path, vid: str, code: str) -> None:
    with pytest.raises(youtube.YoutubeError) as ei:
        youtube.download(f"https://youtu.be/{vid}", tmp_path / vid, cancel=threading.Event())
    assert ei.value.code == code
    assert str(ei.value) == youtube.MESSAGES[code]


def _download_in_thread(url: str, out: Path, cancel: threading.Event, **kw: Any) -> dict[str, Any]:
    box: dict[str, Any] = {}

    def run() -> None:
        try:
            box["res"] = youtube.download(url, out, cancel=cancel, **kw)
        except BaseException as e:  # noqa: BLE001
            box["err"] = e

    t = threading.Thread(target=run)
    t.start()
    box["thread"] = t
    return box


def _wait_for(pred, timeout: float = 30.0) -> None:  # type: ignore[no-untyped-def]
    end = time.time() + timeout
    while time.time() < end:
        if pred():
            return
        time.sleep(0.05)
    raise TimeoutError


def test_cancel_kills_process_and_removes_partial_files(tmp_path: Path, fake_ytdlp: Path) -> None:
    out = tmp_path / "slowslow000"
    cancel = threading.Event()
    box = _download_in_thread("https://youtu.be/slowslow000", out, cancel)
    _wait_for(lambda: (out / "slowslow000.mp4.part").exists())
    cancel.set()
    box["thread"].join(15)
    assert not box["thread"].is_alive()
    assert isinstance(box.get("err"), Cancelled)
    assert not out.exists()


def test_cancel_on_shutdown_keeps_partial_files(tmp_path: Path, fake_ytdlp: Path) -> None:
    out = tmp_path / "slowslow001"
    cancel = threading.Event()
    box = _download_in_thread("https://youtu.be/slowslow001", out, cancel, keep_partial=lambda: True)
    _wait_for(lambda: (out / "slowslow001.mp4.part").exists())
    cancel.set()
    box["thread"].join(15)
    assert isinstance(box.get("err"), Cancelled)
    assert (out / "slowslow001.mp4.part").exists()


def test_interrupted_download_resumes(tmp_path: Path, fake_ytdlp: Path) -> None:
    out = tmp_path / "flaky000000"
    with pytest.raises(youtube.YoutubeError) as ei:
        youtube.download("https://youtu.be/flaky000000", out, cancel=threading.Event())
    assert ei.value.code == "network"
    assert (out / "flaky000000.mp4.part").stat().st_size == 500  # xatoda qisman fayl saqlanadi
    res = youtube.download("https://youtu.be/flaky000000", out, cancel=threading.Event())
    assert res.path.is_file()
    assert (out / "resumed.txt").read_text() == "500"


def _yt_fmt(fid: str, vcodec: str, acodec: str, ext: str, height: int | None = None) -> dict[str, Any]:
    return {"format_id": fid, "vcodec": vcodec, "acodec": acodec, "ext": ext, "height": height,
            "url": f"https://example.invalid/{fid}", "protocol": "https", "tbr": 1}


# YouTube'ning odatiy 1080p ro'yxati: AV1 (399) "eng yaxshi", lekin LGPL FFmpeg'da dav1d yo'q.
YT_FORMATS = [
    _yt_fmt("18", "avc1.42001E", "mp4a.40.2", "mp4", 360), _yt_fmt("140", "none", "mp4a.40.2", "m4a"),
    _yt_fmt("251", "none", "opus", "webm"), _yt_fmt("137", "avc1.640028", "none", "mp4", 1080),
    _yt_fmt("248", "vp9", "none", "webm", 1080), _yt_fmt("399", "av01.0.08M.08", "none", "mp4", 1080),
    _yt_fmt("401", "av01.0.12M.08", "none", "mp4", 2160),
]


@pytest.mark.parametrize(("drop", "want_merge", "want_single"), [
    ((), "137+140", "18"),        # H.264 bor - AV1 o'rniga shu (jonli sinov: AV1 render'da yiqildi)
    (("137",), "248+140", "18"),  # H.264 1080p yo'q - VP9 (360p progressiv emas)
])
def test_format_prefers_decodable_codecs(drop: tuple[str, ...], want_merge: str, want_single: str) -> None:
    """Haqiqiy yt-dlp format tanlovchisi (tarmoqsiz, soxta format ro'yxati bilan)."""
    yt_dlp = pytest.importorskip("yt_dlp")
    formats = [f for f in YT_FORMATS if f["format_id"] not in drop]
    for spec, want in ((youtube.FORMAT_MERGE, want_merge), (youtube.FORMAT_SINGLE, want_single)):
        with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True}) as ydl:
            sel = ydl.build_format_selector(spec)
            got = list(sel({"formats": formats, "has_merged_format": True, "incomplete_formats": False}))
        assert got and got[0]["format_id"] == want
        assert "av01" not in str(got[0].get("vcodec"))


def test_stale_marker_from_old_version_is_redownloaded(tmp_path: Path, fake_ytdlp: Path) -> None:
    """0.2.1 belgisi (versiyasiz, AV1 fayl) qayta ishlatilmaydi: papka tozalanib qayta yuklanadi."""
    out = tmp_path / "okokokokok2"
    out.mkdir()
    old = out / "okokokokok2.mp4"
    old.write_bytes(b"av1")
    (out / youtube.DONE_MARKER).write_text(json.dumps(
        {"id": "okokokokok2", "path": str(old), "title": "eski", "duration": 12}), encoding="utf-8")
    res = youtube.download("https://youtu.be/okokokokok2", out, cancel=threading.Event())
    assert not res.reused and res.path.read_bytes() == b"\x00" * 1000
    marker = json.loads((out / youtube.DONE_MARKER).read_text("utf-8"))
    assert marker["v"] == youtube.MARKER_VERSION
    again = youtube.download("https://youtu.be/okokokokok2", out, cancel=threading.Event())
    assert again.reused


def test_download_without_ytdlp(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(youtube, "find_ytdlp", lambda _p: None)
    with pytest.raises(youtube.YoutubeError) as ei:
        youtube.download("https://youtu.be/okokokokok1", tmp_path / "x", cancel=threading.Event())
    assert ei.value.code == "not_installed"


def test_child_reports_missing_ytdlp(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setitem(sys.modules, "yt_dlp", None)  # import -> ImportError
    monkeypatch.setattr(sys, "path", list(sys.path))
    q: queue.Queue = queue.Queue()
    youtube.child_main("https://www.youtube.com/watch?v=okokokokok1", str(tmp_path), {}, [], q)
    kind, data = q.get_nowait()
    assert kind == "error" and data["code"] == "not_installed"


def _broken_pkg(root: Path, init: str) -> Path:
    (root / "yt_dlp").mkdir(parents=True)
    (root / "yt_dlp" / "__init__.py").write_text(textwrap.dedent(init), encoding="utf-8")
    return root


def test_child_reports_incompatible_when_dependency_missing(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """yt-dlp bor, lekin u import qiladigan modul (muzlatilgan ilovada yo'q stdlib) topilmadi."""
    root = _broken_pkg(tmp_path / "comp", "import lahza_yoq_modul_xyz\n")
    monkeypatch.delitem(sys.modules, "yt_dlp", raising=False)
    monkeypatch.setattr(sys, "path", list(sys.path))
    q: queue.Queue = queue.Queue()
    youtube.child_main("https://www.youtube.com/watch?v=okokokokok1", str(tmp_path), {}, [str(root)], q)
    kind, data = q.get_nowait()
    assert kind == "error" and data["code"] == "incompatible", data
    assert data["module"] == "lahza_yoq_modul_xyz" and "lahza_yoq_modul_xyz" in data["message"]
    assert data["message"].startswith(youtube.MESSAGES["incompatible"])


def test_child_reports_incompatible_on_lazy_import(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    root = _broken_pkg(tmp_path / "comp", """
        class YoutubeDL:
            def __init__(self, params):
                pass

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def extract_info(self, url, download=False):
                import lahza_yoq_extractor_xyz  # noqa: F401
    """)
    monkeypatch.delitem(sys.modules, "yt_dlp", raising=False)
    monkeypatch.setattr(sys, "path", list(sys.path))
    q: queue.Queue = queue.Queue()
    youtube.child_main("https://www.youtube.com/watch?v=okokokokok1", str(tmp_path), {}, [str(root)], q)
    kind, data = q.get_nowait()
    assert kind == "error" and data["code"] == "incompatible" and data["module"] == "lahza_yoq_extractor_xyz"
    sys.modules.pop("yt_dlp", None)


def test_status_reports_components(tmp_path: Path, fake_ytdlp: Path) -> None:
    st = youtube.status(tmp_path)
    assert st["installed"] is True and st["version"] == "2099.01.01"
    assert set(st) == {"installed", "version", "ejs", "js_runtime", "ffmpeg", "ytdlp_source",
                       "js_runtime_version", "js_runtime_source", "js_runtime_outdated"}
    # LAHZA_YTDLP_PATH (Components/ emas) - tizimdagi komponent.
    assert st["ytdlp_source"] == "system"


# ---- API ------------------------------------------------------------------------------------
def _project(c) -> str:  # type: ignore[no-untyped-def]
    return c.post("/v1/projects", json={"name": "Shou"}).json()["id"]


def _stub_analysis(monkeypatch: pytest.MonkeyPatch, calls: list[dict[str, Any]]) -> None:
    def fake_submit(s, eid, show_id, pdir, src, focus, num_speakers, force_lite, **meta):  # type: ignore[no-untyped-def]
        calls.append({"eid": eid, "src": src, "focus": focus, "force_lite": force_lite, **meta})
        return s.jobs.submit("analyze", lambda job: {"episode_id": eid}, episode_id=eid, **meta)

    monkeypatch.setattr(routes_youtube, "submit_analysis", fake_submit)


def test_api_enabled_by_default_can_be_disabled_and_consent_required(tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
                                                      fake_ytdlp: Path) -> None:
    c, _st = make_client(tmp_path, monkeypatch)
    pid = _project(c)
    body = {"project_id": pid, "url": "https://youtu.be/okokokokok1", "consent": True}
    assert c.get("/v1/settings/youtube-import").json()["enabled"] is True  # standart yoqilgan
    c.put("/v1/settings/youtube-import", json={"enabled": False})
    r = c.post("/v1/media:import-url", json=body)
    assert r.status_code == 403

    r = c.put("/v1/settings/youtube-import", json={"enabled": True})
    assert r.status_code == 200 and r.json()["enabled"] is True and r.json()["installed"] is True
    assert c.get("/v1/settings/youtube-import").json()["enabled"] is True

    assert c.post("/v1/media:import-url", json={**body, "consent": False}).status_code == 400
    assert c.post("/v1/media:import-url", json={k: v for k, v in body.items() if k != "consent"}).status_code == 400
    r = c.post("/v1/media:import-url", json={**body, "url": "https://vimeo.com/123"})
    assert r.status_code == 400 and "havola" in r.json()["detail"]
    assert c.post("/v1/media:import-url", json={**body, "project_id": "yoq"}).status_code == 404
    assert c.post("/v1/media:import-url", json={**body, "num_speakers": 0}).status_code == 400

    monkeypatch.setattr(routes_youtube.youtube, "find_ytdlp", lambda _p: None)
    r = c.post("/v1/media:import-url", json=body)
    assert r.status_code == 409 and "o'rnatilmagan" in r.json()["detail"]

    c.put("/v1/settings/youtube-import", json={"enabled": False})
    assert c.post("/v1/media:import-url", json=body).status_code == 403


def test_api_download_creates_episode_and_starts_analysis(tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
                                                         fake_ytdlp: Path) -> None:
    c, st = make_client(tmp_path, monkeypatch)
    pid = _project(c)
    calls: list[dict[str, Any]] = []
    _stub_analysis(monkeypatch, calls)
    c.put("/v1/settings/youtube-import", json={"enabled": True})
    r = c.post("/v1/media:import-url", json={"project_id": pid, "url": "https://www.youtube.com/watch?v=okokokokok1&list=PL1",
                                             "consent": True, "focus": "iqtisod", "force_lite": True})
    assert r.status_code == 200, r.text
    job = r.json()["job"]
    assert job["kind"] == "download" and job["meta"]["video_id"] == "okokokokok1"
    done: Job = wait_job(st, job["id"], timeout=60)
    assert done.status == "done", done.error
    eid = done.result["episode_id"]
    row = st.episode_row(eid)
    assert row["show_id"] == pid and row["title"] == "Sarlavha_1_ test"  # papka nomiga yaroqli
    assert Path(row["project_dir"]).is_dir()
    assert done.result["path"].endswith("okokokokok1.mp4") and Path(done.result["path"]).is_file()
    assert Path(done.result["path"]).is_relative_to(st.settings.data_dir / "Imports" / "youtube")
    assert calls and calls[0]["eid"] == eid and calls[0]["focus"] == "iqtisod" and calls[0]["force_lite"] is True
    assert calls[0]["source_url"] == "https://www.youtube.com/watch?v=okokokokok1"
    assert done.meta["episode_id"] == eid and done.meta["title"] == "Sarlavha/1: test"
    assert wait_job(st, done.result["analysis_job_id"]).status == "done"


def test_api_download_error_and_cancel(tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
                                       fake_ytdlp: Path) -> None:
    c, st = make_client(tmp_path, monkeypatch)
    pid = _project(c)
    calls: list[dict[str, Any]] = []
    _stub_analysis(monkeypatch, calls)
    c.put("/v1/settings/youtube-import", json={"enabled": True})

    r = c.post("/v1/media:import-url", json={"project_id": pid, "url": "https://youtu.be/private0000", "consent": True})
    failed = wait_job(st, r.json()["job"]["id"], timeout=60)
    assert failed.status == "failed" and failed.meta["error_code"] == "private"
    assert failed.error == youtube.MESSAGES["private"]

    r = c.post("/v1/media:import-url", json={"project_id": pid, "url": "https://youtu.be/slowslow002", "consent": True})
    jid = r.json()["job"]["id"]
    part = st.settings.data_dir / "Imports" / "youtube" / "slowslow002" / "slowslow002.mp4.part"
    _wait_for(lambda: part.exists())
    # Bir video ikki marta parallel yuklanmaydi.
    dup = c.post("/v1/media:import-url", json={"project_id": pid, "url": "https://youtu.be/slowslow002", "consent": True})
    assert dup.status_code == 409
    assert c.post(f"/v1/jobs/{jid}:cancel").status_code == 200
    cancelled = wait_job(st, jid, timeout=30)
    assert cancelled.status == "cancelled"
    assert not part.parent.exists()
    assert not calls  # epizod yaratilmadi, tahlil boshlanmadi
    assert c.get(f"/v1/projects/{pid}/episodes").json() == []


def test_api_import_blocked_while_components_install(tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
                                                      fake_ytdlp: Path) -> None:
    """Komponentlar almashtirilayotganda yangi yuklash boshlanmaydi (aralash eski/yangi modullar)."""
    c, st = make_client(tmp_path, monkeypatch)
    pid = _project(c)
    _stub_analysis(monkeypatch, [])
    gate = threading.Event()
    inst = st.jobs.submit("install", lambda job: gate.wait(10) and {}, op="youtube-components")
    body = {"project_id": pid, "url": "https://youtu.be/okokokokok1", "consent": True}
    r = c.post("/v1/media:import-url", json=body)
    assert r.status_code == 409 and r.json()["detail"] == routes_youtube.BUSY_INSTALLING
    gate.set()
    assert wait_job(st, inst.id).status == "done"
    r = c.post("/v1/media:import-url", json=body)
    assert r.status_code == 200, r.text
    assert wait_job(st, r.json()["job"]["id"], timeout=60).status == "done"


def test_file_import_unchanged(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """YouTube funksiyasi o'chiq bo'lsa ham oddiy fayl importi avvalgidek ishlaydi."""
    c, _st = make_client(tmp_path, monkeypatch)
    pid = _project(c)
    assert c.post("/v1/media:import", json={"project_id": pid, "path": str(tmp_path / "yoq.mp4")}).status_code == 400
