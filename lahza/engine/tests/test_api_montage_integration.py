"""Montaj API - haqiqiy PLANNER/RENDER modullari bilan (ular mavjud bo'lsa; aks holda skip)."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest
from _api_helpers import make_client, seed_episode, wait_job
from conftest import requires_ffmpeg

from lahza_engine.db import store as db
from lahza_engine.montage.model import MontageTimeline
from lahza_engine.types import Clip

BUILTIN_IDS = {"uz.lahza.tpl.podcast-hook", "uz.lahza.tpl.event-rhythm", "uz.lahza.tpl.product-promo",
               "uz.lahza.tpl.interview-clean", "uz.lahza.tpl.course-announce", "uz.lahza.tpl.daily-story"}


def test_real_fx_and_templates(tmp_path: Path, monkeypatch) -> None:
    pytest.importorskip("lahza_engine.fx.registry")
    pytest.importorskip("lahza_engine.templates.store")
    c, _ = make_client(tmp_path, monkeypatch)
    fx = c.get("/v1/fx").json()
    assert {m["id"] for m in fx} >= {"uz.lahza.tr.dissolve", "uz.lahza.motion.punch-in", "uz.lahza.color.warm"}
    assert all(m["kind"] == "transition" for m in c.get("/v1/fx?kind=transition").json())

    tpls = c.get("/v1/templates").json()
    assert {t["id"] for t in tpls if t["builtin"]} >= BUILTIN_IDS
    dup = c.post("/v1/templates/uz.lahza.tpl.podcast-hook:duplicate", json={"name": "Mening podkastim"}).json()
    assert dup["id"].startswith("user.") and not dup["builtin"]
    body = {**dup, "transition": {"plugin": "uz.lahza.tr.yoq", "dur_ms": 300}}
    r = c.put(f"/v1/templates/{dup['id']}", json=body)
    assert r.status_code == 400 and "plagin" in r.json()["detail"]
    r = c.put(f"/v1/templates/{dup['id']}", json={**dup, "intro": {"text": "{nomalum}"}})
    assert r.status_code == 400 and "o'rinbosar" in r.json()["detail"]

    out = tmp_path / "t.json"
    assert c.post(f"/v1/templates/{dup['id']}:export", json={"path": str(out)}).json() == {"ok": True}
    imp = c.post("/v1/templates:import", json={"path": str(out)}).json()
    assert imp["id"].startswith("user.") and imp["id"] != dup["id"] and imp["name"]["uz"] == "Mening podkastim"
    bad = tmp_path / "bad.json"
    bad.write_text('{"schema": "boshqa"}')
    r = c.post("/v1/templates:import", json={"path": str(bad)})
    assert r.status_code == 400 and "shablon" in r.json()["detail"]


def _real_montage(tmp_path: Path, monkeypatch):
    pytest.importorskip("lahza_engine.montage.analyze")
    pytest.importorskip("lahza_engine.montage.planner")
    pytest.importorskip("lahza_engine.templates.store")
    c, st = make_client(tmp_path, monkeypatch)
    ff = shutil.which("ffmpeg")
    vids = []
    for i, src in enumerate(("testsrc", "smptebars")):
        v = tmp_path / f"v{i}.mp4"
        subprocess.run([ff, "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i",
                        f"{src}=size=640x360:rate=25:duration=12", "-f", "lavfi", "-i",
                        "sine=frequency=440:duration=12", "-shortest", "-pix_fmt", "yuv420p", "-y", str(v)],
                       check=True)
        vids.append(v)
    # Epizod manbasi: asl fayl - haqiqiy video, klip [6400, 25600) emas, video 12 s -> [1000, 11000)
    _, eid, pdir = seed_episode(st, tmp_path, n=2)
    conn = db.open_project(pdir)
    with conn:
        conn.execute("UPDATE media SET path = ?, duration_ms = 12000 WHERE id = ?", (str(vids[1]), eid))
    db.save_clips(conn, [Clip(id="k1", media_id=eid, start_ms=1000, end_ms=11_000, start_sentence_id=0,
                              end_sentence_id=1, title="Klip", score=80.0)])
    conn.close()

    r = c.post("/v1/montages", json={
        "template_id": "uz.lahza.tpl.daily-story", "name": "Integratsiya",
        "sources": [{"kind": "file", "path": str(vids[0])}, {"kind": "clip", "episode_id": eid, "clip_id": "k1"}],
        "overrides": {"target_duration_ms": 10_000}})
    assert r.status_code == 200, r.text
    j = wait_job(st, r.json()["job"]["id"], timeout=120)
    m = c.get(f"/v1/montages/{r.json()['montage_id']}").json()
    assert j.status == "done", (j.error, m["error"])
    assert m["status"] == "ready" and m["timeline"]
    tl = MontageTimeline.model_validate(m["timeline"])
    assert tl.video and tl.duration_ms == m["duration_ms"]
    for it in tl.video:  # klip manbasidan olingan bo'laklar klip ichida (gap snap post-roll'i uchun zaxira)
        if tl.media[it.media].origin.startswith("clip:"):
            assert 1000 - 500 <= it.src_in_ms < it.src_out_ms <= 11_000 + 500

    return c, st, m


@requires_ffmpeg
def test_real_analyze_and_plan(tmp_path: Path, monkeypatch) -> None:
    c, _, m = _real_montage(tmp_path, monkeypatch)
    thumb = c.get(f"/v1/montages/{m['id']}/sources/src1/thumb?t_ms=1000")
    assert thumb.status_code == 200 and thumb.content[:2] == b"\xff\xd8"


@requires_ffmpeg
def test_real_preview_and_render(tmp_path: Path, monkeypatch) -> None:
    pytest.importorskip("lahza_engine.render.montage_render")
    c, st, m = _real_montage(tmp_path, monkeypatch)
    r = c.post(f"/v1/montages/{m['id']}:preview", json={"t_ms": 500})
    assert r.status_code == 200 and r.content[:2] == b"\xff\xd8"
    r = c.post(f"/v1/montages/{m['id']}:render", json={"out_dir": str(tmp_path / "out"), "allow_no_subs": True})
    assert r.status_code == 200, r.text
    j = wait_job(st, r.json()["id"], timeout=300)
    assert j.status == "done", j.error
    assert Path(j.result["video"]).exists() and Path(j.result["edl"]).exists()
