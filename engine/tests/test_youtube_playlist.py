"""YT-1 qoldiqlari: playlist/kanal havolalari (`/v1/media:resolve-url`), navbatdagi URL elementi,
JS runtime minimal versiyasi, metama'lumot (sarlavha, tavsif, boblar) va boblar Lite highlight'da.
Soxta `yt_dlp` moduli bilan - HAQIQIY TARMOQ YO'Q."""

from __future__ import annotations

import json
import os
import stat
import sys
import threading
from pathlib import Path
from typing import Any

import pytest
from _api_helpers import make_client, wait_job
from test_youtube_import import _wait_for, fake_ytdlp  # noqa: F401 - fikstura

from lahza_engine.api import routes_queue, routes_youtube
from lahza_engine.config import HighlightConfig
from lahza_engine.highlight import finder
from lahza_engine.highlight.signals import SentenceSignals, SignalReport
from lahza_engine.media import youtube
from lahza_engine.types import Sentence, Word

CH_ID = "UC" + "a" * 22


# ---- havola turlari ----------------------------------------------------------------------------
@pytest.mark.parametrize(("url", "kind", "canon"), [
    ("https://youtu.be/dQw4w9WgXcQ", "video", "https://www.youtube.com/watch?v=dQw4w9WgXcQ"),
    ("https://www.youtube.com/watch?v=dQw4w9WgXcQ&list=PL123", "video",
     "https://www.youtube.com/watch?v=dQw4w9WgXcQ"),
    ("https://www.youtube.com/playlist?list=PLabc_DEF-123", "playlist",
     "https://www.youtube.com/playlist?list=PLabc_DEF-123"),
    ("youtube.com/playlist?si=x&list=OLAK5uy_abc", "playlist", "https://www.youtube.com/playlist?list=OLAK5uy_abc"),
    ("https://www.youtube.com/@Kanal.uz", "channel", "https://www.youtube.com/@Kanal.uz/videos"),
    ("https://m.youtube.com/@kanal/videos", "channel", "https://www.youtube.com/@kanal/videos"),
    (f"https://www.youtube.com/channel/{CH_ID}", "channel", f"https://www.youtube.com/channel/{CH_ID}/videos"),
    ("https://www.youtube.com/c/OldName/featured", "channel", "https://www.youtube.com/c/OldName/videos"),
    ("https://www.youtube.com/user/someone", "channel", "https://www.youtube.com/user/someone/videos"),
])
def test_parse_source_url(url: str, kind: str, canon: str) -> None:
    src = youtube.parse_source_url(url)
    assert (src.kind, src.url) == (kind, canon)


@pytest.mark.parametrize("url", [
    "", "https://vimeo.com/playlist?list=PL123",
    "https://youtube.com.evil.com/playlist?list=PL123",
    "https://www.youtube.com/playlist", "https://www.youtube.com/playlist?list=a",
    "https://www.youtube.com/playlist?list=PL1&list=PL2",
    "https://www.youtube.com/playlist?list=PL<script>",
    "https://www.youtube.com/@kanal/shorts", "https://www.youtube.com/@kanal/streams",
    "https://www.youtube.com/channel/UCshort", "https://youtu.be/playlist?list=PL123",
    "https://user:pw@www.youtube.com/@kanal", "https://www.youtube.com:8080/@kanal",
    "https://www.youtube.com/feed/subscriptions", "ftp://www.youtube.com/@kanal",
    "https://www.youtube.com:99999/@kanal",
])
def test_parse_source_url_rejects(url: str) -> None:
    with pytest.raises(youtube.InvalidUrl):
        youtube.parse_source_url(url)


def test_listing_marks_and_truncates() -> None:
    entries = [{"id": f"v{i:010d}", "url": f"https://www.youtube.com/watch?v=v{i:010d}", "title": f"T{i}",
                "duration": 30} for i in range(55)]
    entries[0].update(title="[Deleted video]")
    entries[1].update(availability="subscriber_only")
    entries[2].update(live_status="is_live")
    entries[3].update(thumbnails=[{"url": "http://i.ytimg.com/a.jpg"}, {"url": "https://i.ytimg.com.evil.com/b.jpg"}])
    res = youtube.listing({"title": "PL", "entries": iter(entries)}, "playlist")
    assert res["truncated"] is True and len(res["entries"]) == youtube.MAX_ENTRIES
    assert [e["skip"] for e in res["entries"][:4]] == ["unavailable", "private", "live", None]
    assert res["entries"][3]["thumbnail_url"] is None  # http yoki boshqa domen qaytmaydi
    small = youtube.listing({"title": "PL", "entries": entries[:3], "playlist_count": 3}, "playlist")
    assert small["truncated"] is False and len(small["entries"]) == 3


# ---- resolve (alohida jarayon) -----------------------------------------------------------------
def test_resolve_playlist_in_child(tmp_path: Path, fake_ytdlp: Path, monkeypatch: pytest.MonkeyPatch) -> None:  # noqa: F811
    log = tmp_path / "resolve.json"
    monkeypatch.setenv("LAHZA_FAKE_YT_LOG", str(log))
    res = youtube.resolve("https://www.youtube.com/playlist?list=PLsmall&si=abc", data_dir=tmp_path)
    assert res["kind"] == "playlist" and res["title"] == "Mening playlistim" and res["truncated"] is False
    ids = [e["id"] for e in res["entries"]]
    assert ids == ["vid00000000", "vid00000001", "vid00000002", "vid00000003"]  # kanal bo'limi va takror tashlandi
    assert [e["skip"] for e in res["entries"]] == [None, "private", "short", "upcoming"]
    first = res["entries"][0]
    assert first["url"] == "https://www.youtube.com/watch?v=vid00000000" and first["duration_s"] == 60.0
    assert first["thumbnail_url"] == "https://i.ytimg.com/vi/vid00000000/hq.jpg"
    params = json.loads(log.read_text())
    # Bolaga faqat kanonik havola; ro'yxat "flat", 51 tagacha, remote_components bo'sh.
    assert params["url"] == "https://www.youtube.com/playlist?list=PLsmall"
    assert params["extract_flat"] == "in_playlist" and params["playlistend"] == youtube.MAX_ENTRIES + 1
    assert params["remote_components"] == []
    assert "yt_dlp" not in sys.modules or getattr(sys.modules["yt_dlp"], "__version__", "") != "2099.01.01"

    big = youtube.resolve("https://www.youtube.com/@kanal", data_dir=tmp_path)
    assert big["kind"] == "channel" and big["truncated"] is True and len(big["entries"]) == youtube.MAX_ENTRIES
    assert json.loads(log.read_text())["url"] == "https://www.youtube.com/@kanal/videos"


def test_resolve_errors_and_video_without_network(tmp_path: Path, fake_ytdlp: Path,  # noqa: F811
                                                  monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LAHZA_FAKE_YT_LOG", str(tmp_path / "log.json"))

    def boom(*_a: Any) -> None:
        raise AssertionError("video uchun bola jarayon kerak emas")

    one = youtube.resolve("https://youtu.be/okokokokok1", target=boom)
    assert one["kind"] == "video" and [e["id"] for e in one["entries"]] == ["okokokokok1"]
    with pytest.raises(youtube.YoutubeError) as e:
        youtube.resolve("https://www.youtube.com/playlist?list=PLprivate")
    assert e.value.code == "private"
    with pytest.raises(youtube.YoutubeError) as e:
        youtube.resolve("https://www.youtube.com/playlist?list=PLslow", timeout_s=1.0)
    assert e.value.code == "timeout"
    monkeypatch.setattr(youtube, "find_ytdlp", lambda _p: None)
    with pytest.raises(youtube.YoutubeError) as e:
        youtube.resolve("https://www.youtube.com/@kanal")
    assert e.value.code == "not_installed"


def _project(c) -> str:  # type: ignore[no-untyped-def]
    return c.post("/v1/projects", json={"name": "Shou"}).json()["id"]


def test_api_resolve_url(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fake_ytdlp: Path) -> None:  # noqa: F811
    monkeypatch.setenv("LAHZA_FAKE_YT_LOG", str(tmp_path / "log.json"))
    c, _st = make_client(tmp_path, monkeypatch)
    url = "https://www.youtube.com/playlist?list=PLsmall"
    assert c.post("/v1/media:resolve-url", json={"url": url}).status_code == 400  # rozilik yo'q
    r = c.post("/v1/media:resolve-url", json={"url": "https://vimeo.com/1", "consent": True})
    assert r.status_code == 400 and "havola" in r.json()["detail"]
    r = c.post("/v1/media:resolve-url", json={"url": url, "consent": True})
    assert r.status_code == 200, r.text
    assert r.json()["kind"] == "playlist" and len(r.json()["entries"]) == 4
    r = c.post("/v1/media:resolve-url", json={"url": "https://www.youtube.com/playlist?list=PLprivate", "consent": True})
    assert r.status_code == 502 and r.json()["detail"]["code"] == "private"
    assert r.json()["detail"]["message"] == youtube.MESSAGES["private"]
    c.put("/v1/settings/youtube-import", json={"enabled": False})
    assert c.post("/v1/media:resolve-url", json={"url": url, "consent": True}).status_code == 403


# ---- navbatdagi URL elementi --------------------------------------------------------------------
def _stub_queue_analysis(monkeypatch: pytest.MonkeyPatch, calls: list[dict[str, Any]],
                         gate: threading.Event | None = None) -> None:
    def fake_submit(s, eid, show_id, pdir, src, focus, num_speakers, force_lite, *, on_change=None, **meta):  # type: ignore[no-untyped-def]
        calls.append({"eid": eid, "src": src, "focus": focus, **meta})

        def work(job):  # type: ignore[no-untyped-def]
            if gate is not None:
                gate.wait(20)
            return {"episode_id": eid}

        return s.jobs.submit("analyze", work, on_change=on_change, episode_id=eid, **meta)

    monkeypatch.setattr(routes_queue, "submit_analysis", fake_submit)


def _wait_item(c, iid: str, statuses: tuple[str, ...], timeout: float = 60) -> dict[str, Any]:  # type: ignore[no-untyped-def]
    box: dict[str, Any] = {}

    def ready() -> bool:
        box["item"] = next(x for x in c.get("/v1/queue").json() if x["id"] == iid)
        return box["item"]["status"] in statuses

    try:
        _wait_for(ready, timeout)
    except TimeoutError:
        raise AssertionError(box) from None
    return box["item"]


def test_queue_url_items(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fake_ytdlp: Path) -> None:  # noqa: F811
    c, st = make_client(tmp_path, monkeypatch)
    pid = _project(c)
    calls: list[dict[str, Any]] = []
    _stub_queue_analysis(monkeypatch, calls)
    body = {"project_id": pid, "focus": "iqtisod",
            "urls": [{"url": "https://youtu.be/chapchap001", "title": "Playlistdagi nom"},
                     {"url": "https://www.youtube.com/watch?v=private0000"},
                     {"url": "https://youtu.be/chapchap001"}]}  # takror tashlanadi
    assert c.post("/v1/queue", json=body).status_code == 400  # rozilik kerak
    r = c.post("/v1/queue", json={**body, "consent": True, "urls": [{"url": "https://www.youtube.com/@kanal"}]})
    assert r.status_code == 400 and "havola" in r.json()["detail"]
    assert c.post("/v1/queue", json={"project_id": pid}).status_code == 400

    r = c.post("/v1/queue", json={**body, "consent": True})
    assert r.status_code == 200, r.text
    items = r.json()
    assert len(items) == 2 and all(x["source"] == "youtube" for x in items)
    assert items[0]["url"] == "https://www.youtube.com/watch?v=chapchap001" and items[0]["title"] == "Playlistdagi nom"
    assert items[0]["options"]["focus"] == "iqtisod"

    ok = _wait_item(c, items[0]["id"], ("done", "failed"))
    assert ok["status"] == "done", ok
    eid = ok["episode_id"]
    assert calls[0]["eid"] == eid and calls[0]["focus"] == "iqtisod"
    assert calls[0]["queue_item_id"] == items[0]["id"]
    assert calls[0]["source_url"] == "https://www.youtube.com/watch?v=chapchap001"
    # Epizod nomi - video sarlavhasi (foydalanuvchi bermagan); manba va boblar epizod papkasida.
    ep = c.get(f"/v1/episodes/{eid}").json()
    assert ep["title"] == "Boblar bilan"
    assert ep["source"]["video_id"] == "chapchap001" and ep["source"]["kind"] == "youtube"
    assert ep["source"]["chapters"] == [{"start_ms": 0, "end_ms": 120_000, "title": "Kirish"},
                                        {"start_ms": 120_500, "end_ms": 600_000, "title": "Asosiy qism"}]

    bad = _wait_item(c, items[1]["id"], ("done", "failed"))
    assert bad["status"] == "failed" and bad["error"] == youtube.MESSAGES["private"]
    assert bad["error_code"] == "private" and bad["episode_id"] is None

    # Fayl navbati kontrakti o'zgarmagan: `source` = "file", `url` = None.
    src = tmp_path / "a.mp4"
    src.write_bytes(b"\x00" * 10)
    gate = threading.Event()
    _stub_queue_analysis(monkeypatch, [], gate)
    r = c.post("/v1/queue", json={"project_id": pid, "paths": [str(src)]})
    assert r.status_code == 200 and r.json()[0]["source"] == "file" and r.json()[0]["url"] is None
    gate.set()
    st.jobs.shutdown()


def test_queue_url_cancel_and_retry(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fake_ytdlp: Path) -> None:  # noqa: F811
    c, st = make_client(tmp_path, monkeypatch)
    pid = _project(c)
    calls: list[dict[str, Any]] = []
    _stub_queue_analysis(monkeypatch, calls)
    r = c.post("/v1/queue", json={"project_id": pid, "consent": True, "urls": [{"url": "https://youtu.be/slowslow003"}]})
    iid = r.json()[0]["id"]
    part = st.settings.data_dir / "Imports" / "youtube" / "slowslow003" / "slowslow003.mp4.part"
    _wait_for(lambda: part.exists())
    running = next(x for x in c.get("/v1/queue").json() if x["id"] == iid)
    assert running["status"] == "running" and running["stage"] == "download"
    assert c.post(f"/v1/queue/{iid}:cancel").status_code == 200
    item = _wait_item(c, iid, ("cancelled",), timeout=30)
    assert item["status"] == "cancelled" and not part.parent.exists() and not calls

    # Qayta urinish: navbat oxiriga qaytadi va yana yuklashdan boshlaydi.
    r = c.post(f"/v1/queue/{iid}:retry")
    assert r.status_code == 200
    _wait_for(lambda: part.exists())
    c.post(f"/v1/queue/{iid}:cancel")
    _wait_item(c, iid, ("cancelled",), timeout=30)


def test_queue_url_requires_enabled_and_installed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
                                                 fake_ytdlp: Path) -> None:  # noqa: F811
    c, _st = make_client(tmp_path, monkeypatch)
    pid = _project(c)
    body = {"project_id": pid, "consent": True, "urls": [{"url": "https://youtu.be/okokokokok1"}]}
    c.put("/v1/settings/youtube-import", json={"enabled": False})
    assert c.post("/v1/queue", json=body).status_code == 403
    c.put("/v1/settings/youtube-import", json={"enabled": True})
    monkeypatch.setattr(routes_queue.youtube, "find_ytdlp", lambda _p: None)
    assert c.post("/v1/queue", json=body).status_code == 409


# ---- metama'lumot ---------------------------------------------------------------------------------
def test_download_keeps_metadata_and_import_url_writes_source(tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
                                                              fake_ytdlp: Path) -> None:  # noqa: F811
    out = tmp_path / "dl" / "chapchap002"
    res = youtube.download("https://youtu.be/chapchap002", out, cancel=threading.Event())
    assert res.description == "Tavsif matni" and res.uploader == "Kanal" and len(res.chapters) == 2
    again = youtube.download("https://youtu.be/chapchap002", out, cancel=threading.Event())
    assert again.reused and again.chapters == res.chapters and again.description == "Tavsif matni"

    c, st = make_client(tmp_path, monkeypatch)
    pid = _project(c)
    monkeypatch.setattr(routes_youtube, "submit_analysis",
                        lambda s, eid, *a, **k: s.jobs.submit("analyze", lambda j: {}, episode_id=eid))
    r = c.post("/v1/media:import-url", json={"project_id": pid, "url": "https://youtu.be/chapchap003",
                                             "consent": True, "title": "O'z nomim"})
    done = wait_job(st, r.json()["job"]["id"], timeout=60)
    assert done.status == "done", done.error
    eid = done.result["episode_id"]
    ep = c.get(f"/v1/episodes/{eid}").json()
    assert ep["title"] == "O'z nomim"  # foydalanuvchi nomi ustun
    assert ep["source"]["url"] == "https://www.youtube.com/watch?v=chapchap003"
    assert ep["source"]["title"] == "Boblar bilan" and ep["source"]["description"] == "Tavsif matni"
    saved = json.loads((Path(ep["project_dir"]) / "cache" / "youtube.json").read_text("utf-8"))
    assert saved["chapters"][1]["title"] == "Asosiy qism"
    assert youtube.chapter_starts(Path(ep["project_dir"])) == [0, 120_500]


def test_normalize_chapters_edge_cases() -> None:
    assert youtube.normalize_chapters(None) == []
    got = youtube.normalize_chapters([{"start_time": 30, "title": "B"}, {"start_time": 0, "title": "A"},
                                      {"start_time": -1}, "x"], duration_s=90)
    assert got == [{"start_ms": 0, "end_ms": 30_000, "title": "A"}, {"start_ms": 30_000, "end_ms": 90_000, "title": "B"}]
    assert youtube.normalize_chapters([{"start_time": 10}]) == []  # oxiri noma'lum


def test_episode_without_youtube_source(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from _api_helpers import seed_episode

    c, st = make_client(tmp_path, monkeypatch)
    _sid, eid, pdir = seed_episode(st, tmp_path)
    assert c.get(f"/v1/episodes/{eid}").json()["source"] is None
    assert youtube.chapter_starts(pdir) == []
    (pdir / "cache" / "youtube.json").write_text("{buzuq", encoding="utf-8")
    assert c.get(f"/v1/episodes/{eid}").json()["source"] is None


# ---- JS runtime minimal versiyasi ------------------------------------------------------------------
@pytest.mark.parametrize(("name", "version", "ok"), [
    ("deno", "2.3.0", True), ("deno", "2.9.8", True), ("deno", "2.2.12", False), ("deno", "1.46.3", False),
    ("node", "22.0.0", True), ("node", "20.18.1", False), ("bun", "1.2.11", True), ("bun", "1.2.10", False),
    ("bun", "1.3.14", True), ("bun", "1.4.0", False), ("deno", None, False),
])
def test_js_supported(name: str, version: str | None, ok: bool) -> None:
    assert youtube.js_supported(name, version) is ok


def _fake_exe(path: Path, out: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"#!/bin/sh\necho '{out}'\n", encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)
    return path


@pytest.mark.skipif(sys.platform == "win32", reason="shell skript bilan soxta runtime")
def test_js_runtime_version_check_prefers_bundled(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from lahza_engine.media import tools

    bin_dir = tmp_path / "bin"
    old_deno = _fake_exe(bin_dir / "deno", "deno 2.1.4 (stable, release, aarch64-apple-darwin)\nv8 13.0")
    old_node = _fake_exe(bin_dir / "node", "v20.11.0")
    system = {"deno": old_deno, "node": old_node}

    def find_tool(name: str) -> Path:
        if name in system:
            return system[name]
        raise tools.ToolNotFound(name)

    monkeypatch.setattr(tools, "find_tool", find_tool)
    data = tmp_path / "data"
    found = youtube.js_runtimes(data)
    assert [(r.name, r.version, r.supported) for r in found] == [("deno", "2.1.4", False), ("node", "20.11.0", False)]
    assert youtube.find_js_runtime(data) is None
    with pytest.raises(youtube.YoutubeError) as e:
        youtube._js_for_child(data)
    assert e.value.code == "js_outdated" and "deno 2.1.4" in str(e.value) and "2.3" in str(e.value)
    st = youtube.status(data)
    assert st["js_runtime"] is None and {"name": "deno", "version": "2.1.4"} in st["js_runtime_outdated"]

    # Ilovaning o'z (pinlangan) Deno'si afzal: tizimdagi eski deno o'tkazib yuboriladi.
    own = _fake_exe(data / "Components" / "deno" / "deno", "deno 2.9.8 (stable)")
    assert youtube.find_js_runtime(data) == ("deno", own)
    assert youtube._js_for_child(data) == ("deno", str(own))
    st = youtube.status(data)
    assert (st["js_runtime"], st["js_runtime_version"], st["js_runtime_source"]) == ("deno", "2.9.8", "components")

    # Tizimdagi yangi Deno ham yaroqli ("system").
    (data / "Components" / "deno" / "deno").unlink()
    system["deno"] = _fake_exe(tmp_path / "bin2" / "deno", "deno 2.9.6 (stable)")
    st = youtube.status(data)
    assert (st["js_runtime"], st["js_runtime_version"], st["js_runtime_source"]) == ("deno", "2.9.6", "system")
    # Runtime umuman yo'q - xato emas (yt-dlp cheklangan formatlar bilan urinadi).
    system.clear()
    assert youtube._js_for_child(data) is None


@pytest.mark.skipif(sys.platform == "win32", reason="shell skript bilan soxta runtime")
def test_download_fails_clearly_with_outdated_js(tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
                                                fake_ytdlp: Path) -> None:  # noqa: F811
    old = youtube.JsRuntime("deno", Path("/x/deno"), "2.0.0", False, False)
    monkeypatch.setattr(youtube, "js_runtimes", lambda _d: [old])

    def boom(*_a: Any) -> None:
        raise AssertionError("bola jarayon ishga tushmasligi kerak")

    with pytest.raises(youtube.YoutubeError) as e:
        youtube.download("https://youtu.be/okokokokok1", tmp_path / "o", cancel=threading.Event(), target=boom)
    assert e.value.code == "js_outdated"
    assert os.environ.get("LAHZA_YTDLP_PATH")


# ---- boblar Lite highlight'da ---------------------------------------------------------------------
def _sentences(n: int, step_ms: int = 10_000) -> list[Sentence]:
    out = []
    for i in range(n):
        start = i * step_ms
        w = Word(text=f"gap{i}", start_ms=start, end_ms=start + step_ms - 500)
        out.append(Sentence(id=i, start_ms=start, end_ms=start + step_ms - 500, words=[w]))
    return out


def test_chapters_bonus_in_lite_only() -> None:
    sents = _sentences(30)
    rep = SignalReport([SentenceSignals(sentence_id=i) for i in range(30)])
    cfg = HighlightConfig(clip_count=1, min_clip_ms=30_000, max_clip_ms=40_000)
    base = finder.find_highlights("m", sents, rep, cfg)
    with_ch = finder.find_highlights("m", sents, rep, cfg, chapters=[0, 150_000])
    assert len(base) == len(with_ch) == 1
    clip = with_ch[0]
    assert abs(clip.start_ms - 150_000) <= finder.CHAPTER_NEAR_MS
    assert clip.scores.get("chapter", 0) > 0 and "YouTube bobi" in clip.reason
    assert clip.score > base[0].score
    # Faqat 0 ms dagi bob (kirish) - ta'sir yo'q.
    only_intro = finder.find_highlights("m", sents, rep, cfg, chapters=[0])
    assert only_intro[0].start_ms == base[0].start_ms and "chapter" not in only_intro[0].scores
    # Uzoq bob - bonus yo'q; bonus yaqinlik bilan kamayadi.
    span = finder.ClipSpan(start_id=0, end_id=1, start_ms=100_000, end_ms=130_000)
    assert finder._chapter_bonus(span, [120_000]) == 0.0
    assert finder._chapter_bonus(span, [100_000]) == finder.CHAPTER_BONUS
    assert 0 < finder._chapter_bonus(span, [104_000]) < finder.CHAPTER_BONUS
