"""YouTube import komponentlari (ADR-0010 2-band): mahkamlangan yt-dlp, yt-dlp-ejs va Deno.

Soxta HTTP transport bilan - HAQIQIY TARMOQ YO'Q. sha256/hajm tekshiruvi, atomik joylash, rozilik,
xavfli arxiv yo'llari, bekor qilish va API oqimi."""

from __future__ import annotations

import hashlib
import io
import sys
import threading
import zipfile
from pathlib import Path

import httpx
import pytest
from _api_helpers import make_client, wait_job

from lahza_engine.api import routes_youtube
from lahza_engine.core.runner import Cancelled
from lahza_engine.media import youtube
from lahza_engine.media import youtube_components as yc
from lahza_engine.models.downloader import DownloadError


def _zip(files: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for name, body in files.items():
            z.writestr(zipfile.ZipInfo(name) if "\\" not in name else _raw(name), body)
    return buf.getvalue()


def _raw(name: str) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(name)
    info.filename = name  # Windows'da ham "\" saqlansin
    return info


def _asset(name: str, url: str, body: bytes, sha: str | None = None) -> yc.Asset:
    return yc.Asset(name, "1.0", url, sha or hashlib.sha256(body).hexdigest(), len(body), "test")


@pytest.fixture
def served(monkeypatch: pytest.MonkeyPatch):
    """Komponentlarni soxta serverdan beradi; `bodies[url]` o'zgartirilsa - buzilgan fayl."""
    exe = "deno.exe" if sys.platform == "win32" else "deno"
    bodies = {
        "https://x/yt_dlp.whl": _zip({"yt_dlp/__init__.py": b"", "yt_dlp/version.py": b"__version__ = '1.0'\n",
                                      "yt_dlp-1.0.dist-info/LICENSE": b"Unlicense"}),
        "https://x/yt_dlp_ejs.whl": _zip({"yt_dlp_ejs/__init__.py": b""}),
        "https://x/deno.zip": _zip({exe: b"#!/bin/sh\necho deno 1.0\n"}),
    }
    assets = {u: _asset(u.rsplit("/", 1)[1].split(".")[0], u, b) for u, b in bodies.items()}
    wheels = (assets["https://x/yt_dlp.whl"], assets["https://x/yt_dlp_ejs.whl"])
    monkeypatch.setattr(yc, "WHEELS", wheels)
    monkeypatch.setattr(yc, "DENO", {(sys.platform, yc._arch()): assets["https://x/deno.zip"]})
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        return httpx.Response(200, content=bodies[str(request.url)])

    client = httpx.Client(transport=httpx.MockTransport(handler))
    return bodies, client, calls, exe


def test_install_places_pinned_components(tmp_path: Path, served) -> None:
    _bodies, client, calls, exe = served
    assert [a.name for a in yc.plan(tmp_path)] == ["yt_dlp", "yt_dlp_ejs", "deno"]
    seen: list[float] = []
    out = yc.install(tmp_path, consent=True, client=client, progress=lambda f, _i: seen.append(f))
    assert out["components"] == ["yt_dlp", "yt_dlp_ejs", "deno"] and out["installed"] is True
    assert seen == sorted(seen) and seen[-1] == 1.0
    base = tmp_path / "Components"
    assert youtube.find_ytdlp(youtube.component_paths(tmp_path)) == base / "yt-dlp" / "yt_dlp"
    assert youtube.find_js_runtime(tmp_path) == ("deno", base / "deno" / exe)
    assert yc.plan(tmp_path) == [] and yc.status(tmp_path) == {"components_ready": True,
                                                               "components_download_bytes": 0}
    assert not (base / ".downloads").exists()  # arxivlar o'rnatilgandan keyin o'chiriladi
    assert sorted(p.name for p in base.iterdir()) == ["deno", "yt-dlp"]  # .staging-* qolmaydi
    yc.install(tmp_path, consent=True, client=client)
    assert len(calls) == 3  # qayta chaqiruv - hech narsa yuklanmaydi


def test_consent_required(tmp_path: Path, served) -> None:
    _b, client, calls, _e = served
    with pytest.raises(yc.ComponentError, match="rozilik"):
        yc.install(tmp_path, consent=False, client=client)
    assert calls == [] and not (tmp_path / "Components").exists()


def test_checksum_mismatch_installs_nothing(tmp_path: Path, served) -> None:
    bodies, client, _c, _e = served
    bodies["https://x/yt_dlp_ejs.whl"] = _zip({"yt_dlp_ejs/__init__.py": b"tampered"})
    with pytest.raises(DownloadError):
        yc.install(tmp_path, consent=True, client=client)
    assert not (tmp_path / "Components" / "yt-dlp").exists()  # yarim o'rnatish qolmaydi
    assert youtube.component_paths(tmp_path) == []


@pytest.mark.parametrize("bad", ["../evil.py", "/abs.py", "yt_dlp\\..\\evil.py"])
def test_unsafe_archive_paths_rejected(tmp_path: Path, served, monkeypatch: pytest.MonkeyPatch, bad: str) -> None:
    bodies, client, _c, _e = served
    url = "https://x/yt_dlp.whl"
    bodies[url] = _zip({"yt_dlp/__init__.py": b"", bad: b"x"})
    wheels = (_asset("yt_dlp", url, bodies[url]), yc.WHEELS[1])
    monkeypatch.setattr(yc, "WHEELS", wheels)
    with pytest.raises(yc.ComponentError, match="xavfli"):
        yc.install(tmp_path, consent=True, client=client)
    assert not (tmp_path / "evil.py").exists() and not (tmp_path / "Components" / "yt-dlp").exists()


def test_cancel_stops_download(tmp_path: Path, served) -> None:
    _b, client, _c, _e = served
    cancel = threading.Event()
    cancel.set()
    with pytest.raises(Cancelled):
        yc.install(tmp_path, consent=True, client=client, cancel=cancel)
    assert not (tmp_path / "Components" / "yt-dlp").exists()


def test_update_replaces_old_version(tmp_path: Path, served) -> None:
    _b, client, _c, _e = served
    old = tmp_path / "Components" / "yt-dlp"
    (old / "yt_dlp").mkdir(parents=True)
    (old / "yt_dlp" / "stale.py").write_text("old")
    assert "yt_dlp" in [a.name for a in yc.plan(tmp_path)]  # versiya belgisi yo'q - yangilanadi
    yc.install(tmp_path, consent=True, client=client)
    assert not (old / "yt_dlp" / "stale.py").exists() and yc.wheels_current(tmp_path)


def test_pins_are_exact() -> None:
    for a in (*yc.WHEELS, *yc.DENO.values()):
        assert a.url.startswith("https://") and len(a.sha256) == 64 and a.size > 0
    assert yc.YTDLP.url.endswith(f"yt_dlp-{yc.YTDLP.version}-py3-none-any.whl")  # exe emas (GPL)
    assert {("win32", "x86_64"), ("darwin", "arm64")} <= set(yc.DENO)


def test_api_install_components(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    c, st = make_client(tmp_path, monkeypatch)
    view = c.get("/v1/settings/youtube-import").json()
    assert view["components_ready"] is False and view["components_download_bytes"] > 0
    assert view["install_job"] is None
    url = "/v1/settings/youtube-import:install-components"
    assert c.post(url, json={"consent": False}).status_code == 400
    gate = threading.Event()
    calls: list[Path] = []

    def fake_install(data_dir: Path, *, consent: bool, cancel, progress):  # type: ignore[no-untyped-def]
        assert consent is True
        calls.append(data_dir)
        progress(0.5, {"component": "deno"})
        gate.wait(5)
        return {"components": ["deno"]}

    monkeypatch.setattr(routes_youtube.youtube_components, "install", fake_install)
    job = c.post(url, json={"consent": True}).json()["job"]
    assert c.post(url, json={"consent": True}).status_code == 409  # bir vaqtda bittasi
    assert c.get("/v1/settings/youtube-import").json()["install_job"]["id"] == job["id"]
    gate.set()
    done = wait_job(st, job["id"])
    assert done.status == "done" and done.result == {"components": ["deno"]}
    assert calls == [st.settings.data_dir]
    assert c.get("/v1/settings/youtube-import").json()["install_job"] is None
