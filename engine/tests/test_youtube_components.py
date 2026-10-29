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
        "https://x/deno.zip": _zip({exe: b"#!/bin/sh\necho deno 2.9.8\n"}),
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
    own = youtube.js_runtimes(tmp_path)[0]
    assert own.path == base / "deno" / exe and own.bundled
    if sys.platform != "win32":  # soxta deno - shell skript; versiyasi (2.9.8) yt-dlp talabiga mos
        assert youtube.find_js_runtime(tmp_path) == ("deno", base / "deno" / exe)
    assert yc.plan(tmp_path) == [] and yc.status(tmp_path) == {
        "components_ready": True, "components_download_bytes": 0,
        "component_versions": {"yt_dlp": "1.0", "yt_dlp_ejs": "1.0", "deno": "1.0"}}
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

    def fake_install(data_dir: Path, *, consent: bool, cancel, progress, update):  # type: ignore[no-untyped-def]
        assert consent is True and update is False
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


# ---- yangilanish: PyPI/GitHub metama'lumoti (soxta javoblar) ---------------------------------
def _pypi(name: str, version: str, url: str, sha: str = "a" * 64, requires: list[str] | None = None) -> dict:
    return {"info": {"version": version, "requires_dist": requires or []},
            "urls": [{"packagetype": "sdist", "filename": f"{name}-{version}.tar.gz", "url": url + ".tar.gz",
                      "size": 10, "digests": {"sha256": sha}},
                     {"packagetype": "bdist_wheel", "filename": f"{name}-{version}-py3-none-any.whl",
                      "url": url, "size": 100, "digests": {"sha256": sha}}]}


def _upstream(ytdlp: str = "2099.1.2", ejs: str = "0.9.0", deno: str = "v2.99.0",
              wheel_host: str = "https://files.pythonhosted.org/p/", deno_url: str | None = None) -> httpx.Client:
    triple = yc._DENO_TRIPLE[(sys.platform, yc._arch())]
    routes = {
        "https://pypi.org/pypi/yt-dlp/json": _pypi("yt_dlp", ytdlp, wheel_host + "yt.whl"),
        f"https://pypi.org/pypi/yt-dlp/{ytdlp}/json": _pypi(
            "yt_dlp", ytdlp, wheel_host + "yt.whl", requires=["requests", f"yt-dlp-ejs=={ejs}; extra == 'default'"]),
        f"https://pypi.org/pypi/yt-dlp-ejs/{ejs}/json": _pypi("yt_dlp_ejs", ejs, wheel_host + "ejs.whl"),
        yc.DENO_LATEST: {"tag_name": deno, "assets": [
            {"name": f"deno-{triple}.zip", "size": 200, "digest": "sha256:" + "b" * 64,
             "browser_download_url": deno_url or f"{yc.DENO_DOWNLOAD}{deno}/deno-{triple}.zip"}]},
    }
    return httpx.Client(transport=httpx.MockTransport(
        lambda r: httpx.Response(200, json=routes[str(r.url)]) if str(r.url) in routes else httpx.Response(404)))


def test_resolve_latest_uses_upstream_hashes_and_ejs_pin() -> None:
    latest = {a.name: a for a in yc.resolve_latest(_upstream())}
    assert latest["yt-dlp"].version == "2099.1.2" and latest["yt-dlp"].url.endswith("yt.whl")
    assert latest["yt-dlp-ejs"].version == "0.9.0"  # yt-dlp requires_dist talabidan, "eng oxirgi" emas
    assert latest["deno"].version == "2.99.0" and latest["deno"].sha256 == "b" * 64
    assert all(a.size > 0 and len(a.sha256) == 64 for a in latest.values())


def test_resolve_latest_never_downgrades() -> None:
    latest = {a.name: a for a in yc.resolve_latest(_upstream(ytdlp="2020.1.1", ejs="0.0.1", deno="v2.0.0"))}
    assert latest["yt-dlp"] == yc.YTDLP and latest["yt-dlp-ejs"] == yc.EJS
    assert latest["deno"] == yc.deno_asset()


@pytest.mark.parametrize("kw,match", [
    ({"wheel_host": "https://evil.example/"}, "g'ildiragi topilmadi"),  # faqat files.pythonhosted.org
    ({"deno": "v3.0.0"}, "kutilmagan versiya"),  # faqat Deno 2.x
])
def test_resolve_latest_rejects_untrusted(kw: dict, match: str) -> None:
    with pytest.raises(yc.ComponentError, match=match):
        yc.resolve_latest(_upstream(**kw))


def test_resolve_latest_network_error_is_explained() -> None:
    client = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(503)))
    with pytest.raises(yc.ComponentError, match="yangilanish"):
        yc.resolve_latest(client)


def test_update_reinstalls_both_wheels_and_keeps_deno(tmp_path: Path, served,
                                                      monkeypatch: pytest.MonkeyPatch) -> None:
    bodies, client, calls, _e = served
    yc.install(tmp_path, consent=True, client=client)
    url = "https://x/yt_dlp2.whl"
    bodies[url] = _zip({"yt_dlp/__init__.py": b"# v2", "yt_dlp/version.py": b""})
    newer = yc.Asset("yt_dlp", "2.0", url, hashlib.sha256(bodies[url]).hexdigest(), len(bodies[url]), "test")
    assets = [newer, yc.WHEELS[1], next(iter(yc.DENO.values()))]
    assert [a.name for a in yc.plan(tmp_path, assets=assets)] == ["yt_dlp", "yt_dlp_ejs"]  # bitta papka
    assert yc.plan(tmp_path, assets=list(yc.WHEELS)) == []  # bir xil versiya - hech narsa
    calls.clear()
    monkeypatch.setattr(yc, "resolve_latest", lambda *a, **k: assets)
    out = yc.install(tmp_path, consent=True, client=client, update=True)
    assert out["component_versions"]["yt_dlp"] == "2.0" and out["components"] == ["yt_dlp", "yt_dlp_ejs"]
    assert (tmp_path / "Components" / "yt-dlp" / "yt_dlp" / "__init__.py").read_text() == "# v2"
    assert not any("deno" in c for c in calls)


def test_api_check_updates(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    c, st = make_client(tmp_path, monkeypatch)
    url = "/v1/settings/youtube-import:check-updates"
    monkeypatch.setattr(routes_youtube.youtube_components, "check_updates",
                        lambda d: {"installed": {}, "latest": {"yt-dlp": "2099"}, "update_available": True,
                                   "download_bytes": 5})
    assert c.post(url).json()["update_available"] is True

    def boom(_d):  # type: ignore[no-untyped-def]
        raise yc.ComponentError("yangilanish ma'lumotini olib bo'lmadi: offline")

    monkeypatch.setattr(routes_youtube.youtube_components, "check_updates", boom)
    r = c.post(url)
    assert r.status_code == 502 and "offline" in r.json()["detail"]
    seen: list[bool] = []

    def fake_install(data_dir, *, consent, cancel, progress, update):  # type: ignore[no-untyped-def]
        seen.append(update)
        return {"components": []}

    monkeypatch.setattr(routes_youtube.youtube_components, "install", fake_install)
    job = c.post("/v1/settings/youtube-import:install-components", json={"consent": True, "update": True}).json()
    assert wait_job(st, job["job"]["id"]).status == "done" and seen == [True]


# ---- reviewer topilmalari: pre-reliz, Deno havolasi, kesh nomi, almashtirish xavfsizligi ---------------
@pytest.mark.parametrize("version,plain", [("2026.11.1", True), ("0.8.0", True), ("2026.11.1rc1", False),
                                           ("2.10.0-rc.1", False), ("1.0.dev0", False), ("", False)])
def test_plain_version(version: str, plain: bool) -> None:
    assert yc._plain(version) is plain


def test_resolve_latest_skips_prereleases() -> None:
    pins = {"yt-dlp": yc.YTDLP, "yt-dlp-ejs": yc.EJS, "deno": yc.deno_asset()}
    # yt-dlp pre-reliz -> ikkala g'ildirak ham mahkamlangan (`_vt` rc1 ni relizdan katta deb hisoblardi).
    latest = {a.name: a for a in yc.resolve_latest(_upstream(ytdlp="2099.1.2rc1"))}
    assert latest["yt-dlp"] == pins["yt-dlp"] and latest["yt-dlp-ejs"] == pins["yt-dlp-ejs"]
    assert latest["deno"].version == "2.99.0"  # Deno o'z relizi bo'yicha alohida
    # yt-dlp oddiy, lekin u talab qilgan ejs pre-reliz -> juftlik mahkamlangani qoladi.
    latest = {a.name: a for a in yc.resolve_latest(_upstream(ejs="0.9.0rc1"))}
    assert latest["yt-dlp"] == pins["yt-dlp"] and latest["yt-dlp-ejs"] == pins["yt-dlp-ejs"]
    # Deno pre-reliz -> mahkamlangan Deno.
    latest = {a.name: a for a in yc.resolve_latest(_upstream(deno="v2.99.0-rc.1"))}
    assert latest["deno"] == pins["deno"] and latest["yt-dlp"].version == "2099.1.2"


@pytest.mark.parametrize("url", [
    f"{yc.DENO_DOWNLOAD}v2.98.0/deno-TRIPLE.zip",  # boshqa reliz
    f"{yc.DENO_DOWNLOAD}v2.99.0/../v2.98.0/deno-TRIPLE.zip",
    "https://github.com/evil/deno/releases/download/v2.99.0/deno-TRIPLE.zip",
])
def test_deno_url_must_match_tag(url: str) -> None:
    triple = yc._DENO_TRIPLE[(sys.platform, yc._arch())]
    with pytest.raises(yc.ComponentError, match="mos emas"):
        yc.resolve_latest(_upstream(deno="v2.99.0", deno_url=url.replace("TRIPLE", triple)))


def test_cache_name_is_versioned_and_safe() -> None:
    a1 = yc.Asset("deno", "2.9.8", f"{yc.DENO_DOWNLOAD}v2.9.8/deno-x.zip", "a" * 64, 1, "MIT")
    a2 = yc.Asset("deno", "2.9.9", f"{yc.DENO_DOWNLOAD}v2.9.9/deno-x.zip", "a" * 64, 1, "MIT")
    assert yc._cache_name(a1) == "deno-2.9.8-deno-x.zip" != yc._cache_name(a2)
    name = yc._cache_name(yc.Asset("x", "1", "https://h/a/..%2F..%2Fevil.whl?q=1", "a" * 64, 1, "t"))
    assert "/" not in name and "\\" not in name and not name.startswith(".")
    for bad in ("https://h/", "https://h/a/..", "https://h/a/.", "https://h/a\\..\\b"):
        with pytest.raises(yc.ComponentError, match="yaroqsiz"):
            yc._cache_name(yc.Asset("x", "1", bad, "a" * 64, 1, "t"))


def test_stale_part_of_other_version_is_not_resumed(tmp_path: Path, served, monkeypatch: pytest.MonkeyPatch) -> None:
    """Deno arxivi nomi versiyalar bo'yicha bir xil: A ning `.part` qoldig'i B havolasi bilan davom ettirilmaydi."""
    bodies, client, _c, exe = served
    old = yc.Asset("deno", "1.0", "https://x/v1/deno.zip", "c" * 64, 10_000, "MIT")
    cache = tmp_path / "Components" / ".downloads"
    cache.mkdir(parents=True)
    (cache / (yc._cache_name(old) + ".part")).write_bytes(b"\0" * 100)  # uzilgan A yuklamasi
    url = "https://x/v2/deno.zip"
    bodies[url] = _zip({exe: b"#!/bin/sh\necho deno 2.0\n"})
    new = yc.Asset("deno", "2.0", url, hashlib.sha256(bodies[url]).hexdigest(), len(bodies[url]), "MIT")
    monkeypatch.setattr(yc, "DENO", {(sys.platform, yc._arch()): new})
    out = yc.install(tmp_path, consent=True, client=client)
    assert out["component_versions"]["deno"] == "2.0"


def _dirs(tmp_path: Path) -> tuple[Path, Path]:
    final, staging = tmp_path / "yt-dlp", tmp_path / ".staging-1"
    final.mkdir()
    (final / "v.txt").write_text("old")
    staging.mkdir()
    (staging / "v.txt").write_text("new")
    return final, staging


def _deny_rename(monkeypatch: pytest.MonkeyPatch, *locked: Path) -> None:
    """Windows: ishlab turgan deno.exe yoki ochiq fayl bor papka nomini o'zgartirib bo'lmaydi."""
    real = Path.rename

    def rename(self: Path, target):  # type: ignore[no-untyped-def]
        if self in locked:
            raise PermissionError(13, "Access is denied", str(self))
        return real(self, target)

    monkeypatch.setattr(Path, "rename", rename)


def test_publish_rolls_back_when_new_cannot_be_placed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    final, staging = _dirs(tmp_path)
    _deny_rename(monkeypatch, staging)
    with pytest.raises(yc.ComponentError, match="almashtirib bo'lmadi"):
        yc._publish(staging, final)
    assert (final / "v.txt").read_text() == "old"  # eskisi joyiga qaytarildi
    assert not final.with_name("yt-dlp.old").exists()


def test_publish_locked_folder_is_clean_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    final, staging = _dirs(tmp_path)
    _deny_rename(monkeypatch, final)
    with pytest.raises(yc.ComponentError, match="ishlatilayotgan"):
        yc._publish(staging, final)
    assert (final / "v.txt").read_text() == "old" and (staging / "v.txt").exists()


def test_publish_rollback_failure_keeps_old_copy(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    final, staging = _dirs(tmp_path)
    old = final.with_name("yt-dlp.old")
    _deny_rename(monkeypatch, staging, old)
    with pytest.raises(yc.ComponentError, match="qaytarib bo'lmadi"):
        yc._publish(staging, final)
    assert (old / "v.txt").read_text() == "old"  # o'chirilmadi
    monkeypatch.undo()
    yc._publish(staging, final)  # keyingi urinish: avval eskisi tiklanadi, keyin almashtiriladi
    assert (final / "v.txt").read_text() == "new" and not old.exists()


def test_publish_error_fails_install_cleanly(tmp_path: Path, served, monkeypatch: pytest.MonkeyPatch) -> None:
    bodies, client, _c, exe = served
    yc.install(tmp_path, consent=True, client=client)
    url = "https://x/deno2.zip"
    bodies[url] = _zip({exe: b"v2"})
    newer = yc.Asset("deno", "2.0", url, hashlib.sha256(bodies[url]).hexdigest(), len(bodies[url]), "MIT")
    monkeypatch.setattr(yc, "resolve_latest", lambda *a, **k: [*yc.WHEELS, newer])
    _deny_rename(monkeypatch, tmp_path / "Components" / "deno")
    with pytest.raises(yc.ComponentError, match="ishlatilayotgan"):
        yc.install(tmp_path, consent=True, client=client, update=True)
    assert yc.installed_versions(tmp_path)["deno"] == "1.0"  # eski Deno joyida
    assert sorted(p.name for p in (tmp_path / "Components").iterdir() if not p.name.startswith(".")) == [
        "deno", "yt-dlp"]


def test_api_install_blocked_while_youtube_download_runs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    c, st = make_client(tmp_path, monkeypatch)
    gate = threading.Event()
    dl = st.jobs.submit("download", lambda job: gate.wait(10) and {}, op="youtube", video_id="okokokokok1")
    url = "/v1/settings/youtube-import:install-components"
    r = c.post(url, json={"consent": True, "update": True})
    assert r.status_code == 409 and r.json()["detail"] == routes_youtube.BUSY_DOWNLOADING
    gate.set()
    assert wait_job(st, dl.id).status == "done"

    def fake_install(data_dir, *, consent, cancel, progress, update):  # type: ignore[no-untyped-def]
        return {"components": []}

    monkeypatch.setattr(routes_youtube.youtube_components, "install", fake_install)
    job = c.post(url, json={"consent": True}).json()["job"]
    assert wait_job(st, job["id"]).status == "done"
