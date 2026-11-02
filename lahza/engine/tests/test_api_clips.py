from pathlib import Path

import pytest
from _api_helpers import make_client, seed_episode, wait_job

import lahza_engine.core.export as export_mod
from lahza_engine.db import store as db
from lahza_engine.types import Clip, ClipSource


def _manual(c, eid, a=2, b=4, title=None):
    return c.post(f"/v1/episodes/{eid}/clips",
                  json={"start_sentence_id": a, "end_sentence_id": b, "title": title})


def test_manual_clip_snapped(tmp_path: Path, monkeypatch) -> None:
    c, st = make_client(tmp_path, monkeypatch)
    _, eid, pdir = seed_episode(st, tmp_path)
    r = _manual(c, eid, title="Mening klipim")
    assert r.status_code == 200
    clip = r.json()
    tr = db.load_transcript(db.open_project(pdir), eid)
    s2, s4 = tr.sentences[2], tr.sentences[4]
    assert clip["source"] == "qolda" and clip["status"] == "nomzod" and clip["title"] == "Mening klipim"
    assert clip["start_sentence_id"] == 2 and clip["end_sentence_id"] == 4
    # pre/post roll: gap ichidagi pauzaga, lekin qo'shni gapga kirmaydi
    assert tr.sentences[1].end_ms < clip["start_ms"] <= s2.start_ms
    assert s4.end_ms <= clip["end_ms"] < tr.sentences[5].start_ms
    row = db.open_project(pdir).execute("SELECT user_edited FROM clips WHERE id = ?",
                                        (clip["id"],)).fetchone()
    assert row[0] == 1
    assert _manual(c, eid, 4, 2).status_code == 400
    assert _manual(c, eid, 0, 99).status_code == 404
    auto_title = _manual(c, eid, 6, 6).json()["title"]
    assert auto_title.startswith("so'z6_0")


def test_cuts_validation_and_snap(tmp_path: Path, monkeypatch) -> None:
    c, st = make_client(tmp_path, monkeypatch)
    _, eid, pdir = seed_episode(st, tmp_path)
    clip = _manual(c, eid).json()
    words = [w for s in db.load_transcript(db.open_project(pdir), eid).sentences for w in s.words]
    w1, w2, w3 = words[2 * 12 + 1], words[2 * 12 + 2], words[2 * 12 + 5]
    url = f"/v1/episodes/{eid}/clips/{clip['id']}/cuts"
    mid1 = (w1.start_ms + w1.end_ms) // 2
    mid2 = (w2.start_ms + w2.end_ms) // 2
    r = c.put(url, json={"cuts": [[w3.start_ms, w3.end_ms], [mid1, mid2], [w2.start_ms, w2.end_ms]]})
    assert r.status_code == 200
    assert r.json()["cuts"] == [[w1.start_ms, w2.end_ms], [w3.start_ms, w3.end_ms]]
    assert db.get_clip(db.open_project(pdir), eid, clip["id"]).cuts == [
        (w1.start_ms, w2.end_ms), (w3.start_ms, w3.end_ms)]
    assert c.put(url, json={"cuts": [[clip["start_ms"] - 10, clip["start_ms"] + 100]]}).status_code == 400
    assert c.put(url, json={"cuts": [[w2.end_ms, w2.start_ms]]}).status_code == 400
    assert c.put(url, json={"cuts": [[clip["start_ms"], clip["end_ms"]]]}).status_code == 400
    assert c.put(url, json={"cuts": []}).json()["cuts"] == []
    assert c.put(f"/v1/episodes/{eid}/clips/yoq/cuts", json={"cuts": []}).status_code == 404


def test_keyframes_roundtrip(tmp_path: Path, monkeypatch) -> None:
    c, st = make_client(tmp_path, monkeypatch)
    _, eid, _ = seed_episode(st, tmp_path)
    clip = _manual(c, eid).json()
    url = f"/v1/episodes/{eid}/clips/{clip['id']}/keyframes"
    assert c.get(url).json() == []
    kfs = [{"t_ms": 0, "layout": "focus", "cx": 0.4, "cy": 0.3, "zoom": 1.2, "lane": "a"},
           {"t_ms": 1500, "layout": "fit_blur", "source": "avto"}]
    assert c.put(url, json={"keyframes": kfs}).json() == {"ok": True}
    got = c.get(url).json()
    assert [k["t_ms"] for k in got] == [0, 1500] and {k["source"] for k in got} == {"qolda"}
    assert got[0]["cx"] == 0.4 and got[1]["zoom"] == 1.0
    assert c.put(url, json={"keyframes": [{"t_ms": 10**8, "layout": "focus"}]}).status_code == 400
    assert c.put(url, json={"keyframes": [{"t_ms": 0, "layout": "xato"}]}).status_code == 422
    dup = [{"t_ms": 5, "layout": "focus"}, {"t_ms": 5, "layout": "split"}]
    assert c.put(url, json={"keyframes": dup}).status_code == 400


def test_similar_non_overlapping(tmp_path: Path, monkeypatch) -> None:
    c, st = make_client(tmp_path, monkeypatch)
    _, eid, pdir = seed_episode(st, tmp_path, n=60)
    clip = _manual(c, eid, 2, 6).json()
    r = c.post(f"/v1/episodes/{eid}/clips/{clip['id']}:similar")
    assert r.status_code == 200
    found = r.json()
    assert 1 <= len(found) <= 3
    spans = [(clip["start_ms"], clip["end_ms"])] + [(x["start_ms"], x["end_ms"]) for x in found]
    for i, (a, b) in enumerate(spans):
        for a2, b2 in spans[i + 1:]:
            assert b <= a2 or b2 <= a
    assert all(x["source"] == "ai_lite" and x["status"] == "nomzod" for x in found)
    ids = {x.id for x in db.load_clips(db.open_project(pdir), eid)}
    assert {x["id"] for x in found} <= ids


def test_preview(tmp_path: Path, monkeypatch) -> None:
    c, st = make_client(tmp_path, monkeypatch)
    _, eid, _ = seed_episode(st, tmp_path)
    clip = _manual(c, eid).json()
    url = f"/v1/episodes/{eid}/clips/{clip['id']}:preview"
    seen = {}

    def fake(conn, media_id, clip, t_out_ms, style, settings, out_jpg, detector=None):
        seen.update(t=t_out_ms, ortho=style.orthography.value)
        out_jpg.write_bytes(b"\xff\xd8\xff\xe0fakejpeg")
        return out_jpg

    monkeypatch.setattr(export_mod, "render_preview_frame", fake, raising=False)
    r = c.post(url, json={"t_ms": 10**9, "orthography": "ascii"})
    assert r.status_code == 200 and r.headers["content-type"] == "image/jpeg"
    assert r.content.startswith(b"\xff\xd8")
    assert seen["t"] == clip["end_ms"] - clip["start_ms"] - 1 and seen["ortho"] == "ascii"
    monkeypatch.delattr(export_mod, "render_preview_frame")
    assert c.post(url, json={"t_ms": 0}).status_code == 501


@pytest.fixture()
def fake_export(monkeypatch):
    from lahza_engine.render.encoders import EncoderChoice

    calls: list[dict] = []
    state = {"fail": False, "libass": True}
    monkeypatch.setattr("lahza_engine.render.capabilities.has_filter",
                        lambda ff, name: state["libass"])

    def export_clip(conn, media_id, clip, out_dir, workdir, settings, encoder, style, detector=None,
                    fonts_dir=None, show_name="lahza", episode="ep", index=1, layouts=None,
                    filename_template="{shou}_{epizod}_{nn}_{sarlavha}", allow_no_subs=False,
                    platform="instagram_reels"):
        calls.append({"clip": clip.id, "show": show_name, "episode": episode, "index": index,
                      "tpl": filename_template, "ortho": style.orthography.value,
                      "no_subs": allow_no_subs})
        if state["fail"]:
            raise RuntimeError("render yiqildi")
        out_dir.mkdir(parents=True, exist_ok=True)
        v = out_dir / f"{index:02d}.mp4"
        v.write_bytes(b"x")
        return export_mod.ExportResult(v, out_dir / "a.srt", out_dir / "a.txt", None,
                                       vtt=out_dir / "a.vtt", warnings=["ogohlantirish"])

    monkeypatch.setattr(export_mod, "export_clip", export_clip)
    monkeypatch.setattr("lahza_engine.media.tools.find_tool", lambda name: Path("/bin/ffmpeg"))
    monkeypatch.setattr("lahza_engine.render.encoders.choose_encoder",
                        lambda *a, **k: EncoderChoice("libx264", (), False))

    class _Hw:
        def best_gpu(self):
            return None

    monkeypatch.setattr("lahza_engine.models.hardware.detect", lambda *a: _Hw())
    return calls, state


def test_export_records_and_retry(tmp_path: Path, monkeypatch, fake_export) -> None:
    calls, state = fake_export
    c, st = make_client(tmp_path, monkeypatch)
    _, eid, pdir = seed_episode(st, tmp_path, show_name="Biznes")
    conn = db.open_project(pdir)
    db.save_clips(conn, [Clip(id="k1", media_id=eid, start_ms=0, end_ms=5000, start_sentence_id=0,
                              end_sentence_id=0, title="Birinchi", source=ClipSource.AI_LITE)],
                  replace_ai=False)
    clip = _manual(c, eid, 3, 5, title="Ikkinchi").json()
    out = tmp_path / "out"
    r = c.post(f"/v1/episodes/{eid}/clips/{clip['id']}:export",
               json={"out_dir": str(out), "orthography": "new", "filename_template": "{nn}_{sarlavha}"})
    job = wait_job(st, r.json()["id"])
    assert job.status == "done", job.error
    assert calls[-1] == {"clip": clip["id"], "show": "Biznes", "episode": "Birinchi epizod", "index": 2,
                         "tpl": "{nn}_{sarlavha}", "ortho": "new", "no_subs": False}
    assert job.result["vtt"].endswith("a.vtt") and job.result["warnings"] == ["ogohlantirish"]
    row = conn.execute("SELECT * FROM exports WHERE job_id = ?", (job.id,)).fetchone()
    assert row["status"] == "done" and row["path"].endswith("02.mp4") and row["finished_at"]

    state["fail"] = True
    failed = wait_job(st, c.post(f"/v1/episodes/{eid}/clips/k1:export",
                                 json={"out_dir": str(out)}).json()["id"])
    assert failed.status == "failed"
    row = conn.execute("SELECT * FROM exports WHERE job_id = ?", (failed.id,)).fetchone()
    assert row["status"] == "failed" and "RuntimeError" in row["error"]

    lst = c.get("/v1/exports").json()
    assert [x["job"]["id"] for x in lst] == [failed.id, job.id]
    assert lst[0]["clip_id"] == "k1" and lst[0]["title"] == "Birinchi" and lst[0]["episode_id"] == eid

    assert c.post(f"/v1/jobs/{job.id}:retry").status_code == 409  # done -> qayta emas
    state["fail"] = False
    r = c.post(f"/v1/jobs/{failed.id}:retry")
    assert r.status_code == 200 and r.json()["meta"]["retry_of"] == failed.id
    assert wait_job(st, r.json()["id"]).status == "done"
    assert calls[-1]["index"] == 1
    assert c.post("/v1/jobs/yoq:retry").status_code == 404

    # libass yo'q: subtitrsiz ruxsatsiz -> 422, ruxsat bilan -> vazifa
    state["libass"] = False
    r = c.post(f"/v1/episodes/{eid}/clips/k1:export", json={"out_dir": str(out)})
    assert r.status_code == 422 and "libass" in r.json()["detail"]
    r = c.post(f"/v1/episodes/{eid}/clips/k1:export", json={"out_dir": str(out), "allow_no_subs": True})
    assert wait_job(st, r.json()["id"]).status == "done" and calls[-1]["no_subs"] is True
    assert c.post(f"/v1/episodes/{eid}/clips/yoq:export", json={"out_dir": str(out)}).status_code == 404


def test_export_workers_env(monkeypatch) -> None:
    from lahza_engine.core.events import EventBus
    from lahza_engine.core.jobs import JobManager

    monkeypatch.setenv("LAHZA_EXPORT_WORKERS", "3")
    assert JobManager(EventBus()).export_workers == 3
    monkeypatch.setenv("LAHZA_EXPORT_WORKERS", "xato")
    assert JobManager(EventBus()).export_workers == 2
    assert JobManager(EventBus(), export_workers=1).export_workers == 1
