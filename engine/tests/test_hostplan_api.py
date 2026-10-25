"""Host-reja API: klip va montaj `:hostplan`, sxema, out_dir qoidalari, CORS (UXP/CEP origin'lari)."""

from __future__ import annotations

import json
import uuid
from pathlib import Path

import pytest
from _api_helpers import make_client, seed_episode
from fastapi.testclient import TestClient

from lahza_engine.api.app import create_app
from lahza_engine.config import Settings
from lahza_engine.db import store as db
from lahza_engine.hostplan.model import HostPlan
from lahza_engine.montage.model import (
    Captions,
    FxRef,
    MediaRef,
    MontageTimeline,
    MusicItem,
    TextItem,
    TransitionRef,
    VideoItem,
)
from lahza_engine.types import Clip, ClipSource, Word


def _seed_clip(st, tmp_path: Path, cuts=None, keyframes=None, hook: int | None = 1):
    _, eid, pdir = seed_episode(st, tmp_path, n=6)
    conn = db.open_project(pdir)
    sentences = db.load_transcript(conn, eid).sentences
    clip = Clip(id=uuid.uuid4().hex[:12], media_id=eid, start_ms=sentences[0].start_ms,
                end_ms=sentences[2].end_ms, start_sentence_id=0, end_sentence_id=2,
                hook_sentence_id=hook, title="Eng zo'r lahza!", source=ClipSource.MANUAL)
    db.insert_manual_clip(conn, clip)
    if cuts:
        db.set_cuts(conn, clip.id, cuts)
    if keyframes:
        db.save_manual_keyframes(conn, clip.id, keyframes)
    conn.close()
    return eid, clip, sentences, pdir


def test_schema(tmp_path, monkeypatch):
    c, _ = make_client(tmp_path, monkeypatch)
    r = c.get("/v1/hostplan/schema")
    assert r.status_code == 200
    assert r.json()["schema"] == "lahza.hostplan/1" and r.json()["engine"]


def test_clip_hostplan_fit_blur_cuts_captions(tmp_path, monkeypatch):
    c, st = make_client(tmp_path, monkeypatch)
    eid, clip, sentences, pdir = _seed_clip(st, tmp_path)
    # Ikkinchi gapning o'rtasidagi 2 so'zni kesamiz -> 2 ta video element.
    w = sentences[1].words
    cut = (w[3].start_ms, w[4].end_ms)
    r = c.put(f"/v1/episodes/{eid}/clips/{clip.id}/cuts", json={"cuts": [list(cut)]})
    assert r.status_code == 200
    out = tmp_path / "chiqish"
    r = c.post(f"/v1/episodes/{eid}/clips/{clip.id}:hostplan",
               json={"out_dir": str(out), "orthography": "ascii"})
    assert r.status_code == 200, r.text
    plan = HostPlan.model_validate(r.json())
    assert plan.source == "clip" and plan.source_id == clip.id
    assert (plan.sequence.width, plan.sequence.height) == (1080, 1920)
    cut_len = (cut[1] - cut[0]) / 1000
    assert plan.sequence.duration_s == pytest.approx((clip.end_ms - clip.start_ms) / 1000 - cut_len, abs=1e-3)
    assert len(plan.video) == 2
    a, b = plan.video
    assert a.rec_in == 0 and a.rec_out == pytest.approx(b.rec_in)
    assert a.src_out == pytest.approx(cut[0] / 1000) and b.src_in == pytest.approx(cut[1] / 1000)
    assert b.transition_in is not None and b.transition_in.kind == "cut"
    # Detektorsiz va kalit kadrsiz - xira fon; bazaga 'avto' yozilmaydi.
    assert [ly.role for ly in a.layers] == ["bg", "main"]
    conn = db.open_project(pdir)
    assert conn.execute("SELECT COUNT(*) FROM reframe_keyframes").fetchone()[0] == 0
    conn.close()
    # Subtitr: so'zlar rec vaqtida, kesilgan so'zlar yo'q, imlo ascii.
    words = [x for ln in plan.captions.lines for x in ln.words]
    texts = [x.text for x in words]
    assert w[3].text not in texts and w[4].text not in texts
    assert all("ʻ" not in t and "ʼ" not in t for t in texts) and "so'z0_0" in texts
    after = next(x for x in words if x.text == w[5].text)
    assert after.t0 == pytest.approx((w[5].start_ms - clip.start_ms) / 1000 - cut_len, abs=1e-3)
    assert all(ln.t1 > ln.t0 and len(ln.words) <= 3 for ln in plan.captions.lines)
    srt = Path(plan.captions.srt_path)
    wj = Path(plan.captions.words_path)
    assert srt.parent == out.resolve() and srt.name == "eng-zor-lahza.srt"
    assert wj.name == "eng-zor-lahza_words.json" and srt.read_text(encoding="utf-8").startswith("1\n")
    doc = json.loads(wj.read_text(encoding="utf-8"))
    assert doc["orthography"] == "ascii" and len(doc["words"]) == len(words)
    # Hook marker - 2-gap boshida (rec vaqtida); hook elementi belgilangan.
    hooks = [m for m in plan.markers if m.kind == "hook"]
    assert len(hooks) == 1
    assert hooks[0].t == pytest.approx((sentences[1].start_ms - clip.start_ms) / 1000, abs=1e-3)
    assert a.label == "hook"


def test_clip_hostplan_manual_keyframes_and_aspect(tmp_path, monkeypatch):
    c, st = make_client(tmp_path, monkeypatch)
    kfs = [{"t_ms": 0, "layout": "focus", "cx": 0.3, "cy": 0.5, "zoom": 1.0},
           {"t_ms": 2000, "layout": "focus", "cx": 0.4, "cy": 0.5, "zoom": 1.0},
           {"t_ms": 2100, "layout": "focus", "cx": 0.9, "cy": 0.5, "zoom": 1.0},
           {"t_ms": 6000, "layout": "split", "cx": 0.25, "zoom": 1.0},
           {"t_ms": 6000, "layout": "split", "cx": 0.75, "zoom": 1.0, "lane": "b"}]
    eid, clip, _, _ = _seed_clip(st, tmp_path, keyframes=kfs)
    r = c.post(f"/v1/episodes/{eid}/clips/{clip.id}:hostplan", json={"out_dir": str(tmp_path / "o")})
    assert r.status_code == 200, r.text
    plan = HostPlan.model_validate(r.json())
    first, second = plan.video[0], plan.video[1]
    assert [ly.role for ly in first.layers] == ["main"]
    keys = first.layers[0].keys
    assert keys[0].interp == "linear" and keys[1].interp == "hold"  # 2000->2100 ms keskin kesim
    assert keys[2].pos_x < keys[1].pos_x  # o'ngga (cx 0.9) qaradi -> manba chapga siljiydi
    assert [ly.role for ly in second.layers] == ["top", "bottom"]
    assert second.rec_in == pytest.approx(6.0)
    # 1:1 nisbat
    r = c.post(f"/v1/episodes/{eid}/clips/{clip.id}:hostplan",
               json={"out_dir": str(tmp_path / "o"), "aspect": "1:1"})
    assert r.json()["sequence"]["height"] == 1080


def test_out_dir_rules_and_errors(tmp_path, monkeypatch):
    c, st = make_client(tmp_path, monkeypatch)
    eid, clip, _, _ = _seed_clip(st, tmp_path)
    url = f"/v1/episodes/{eid}/clips/{clip.id}:hostplan"
    r = c.post(url, json={"out_dir": str(tmp_path / "yoq" / "ichki")})
    assert r.status_code == 400 and "ota papkasi" in r.json()["detail"]
    r = c.post(url, json={"out_dir": "nisbiy/papka"})
    assert r.status_code == 400
    f = tmp_path / "fayl.txt"
    f.write_text("x")
    assert c.post(url, json={"out_dir": str(f)}).status_code == 400
    assert c.post(f"/v1/episodes/{eid}/clips/yoq:hostplan",
                  json={"out_dir": str(tmp_path)}).json()["detail"] == "klip topilmadi"
    r = c.post(url, json={"out_dir": str(tmp_path / "yangi")})
    assert r.status_code == 200 and (tmp_path / "yangi").is_dir()


# ---- Montaj ---------------------------------------------------------------------


def _timeline(tmp_path: Path) -> MontageTimeline:
    src = tmp_path / "a.mp4"
    src.write_bytes(b"\x00")
    music = tmp_path / "m.mp3"
    music.write_bytes(b"\x00")
    lut = tmp_path / "x.cube"
    lut.write_text("LUT_3D_SIZE 2\n")
    media = {"a": MediaRef(id="a", path=str(src), duration_ms=60_000, width=1920, height=1080, fps=25),
             "v": MediaRef(id="v", path=str(src), duration_ms=60_000, width=1080, height=1920, fps=30),
             "mu": MediaRef(id="mu", path=str(music), duration_ms=90_000, width=0, height=0, fps=0)}
    tr = [None, "uz.lahza.tr.dissolve", "uz.lahza.tr.fadeblack", "uz.lahza.tr.wipeleft",
          "uz.lahza.tr.slideup", "uz.lahza.tr.circleopen", "uz.lahza.tr.cut"]
    video = []
    for i, t in enumerate(tr):
        fx: list[FxRef] = []
        if i == 0:
            fx = [FxRef(plugin="uz.lahza.motion.punch-in", at_ms=500, dur_ms=1000)]
        if i == 1:
            fx = [FxRef(plugin="uz.lahza.motion.shake"), FxRef(plugin="uz.lahza.speed.freeze", at_ms=200)]
        if i == 2:
            fx = [FxRef(plugin="uz.lahza.color.lut", params={"file": str(lut)})]
        if i == 3:
            fx = [FxRef(plugin="uz.lahza.motion.pan", params={"yonalish": "onga"})]
        video.append(VideoItem(
            id=f"e{i}", media="v" if i == 4 else "a", src_in_ms=i * 5000, src_out_ms=i * 5000 + 3000,
            reframe="fit_blur" if i == 2 else "auto", fx=fx,
            transition_in=TransitionRef(plugin=t, dur_ms=400) if t else None,
            role="hook" if i == 0 else "asosiy", speed=2.0 if i == 5 else 1.0))
    words = [Word(text=x, start_ms=k * 400, end_ms=k * 400 + 350) for k, x in
             enumerate(["Bugun", "o'zbek", "tilida", "gaplashamiz", "va", "ko'ramiz"])]
    return MontageTimeline(
        media=media, video=video,
        text=[TextItem(id="t1", start_ms=0, end_ms=1500, text="Sarlavha o'zbekcha", kind="hook",
                       animation="pop")],
        music=[MusicItem(media="mu", gain_db=-18)],
        captions=Captions(enabled=True, words=words),
        color=FxRef(plugin="uz.lahza.color.warm"),
    )


def test_plan_from_montage_mapping(tmp_path):
    from lahza_engine.hostplan.build import plan_from_montage

    tl = _timeline(tmp_path)
    from lahza_engine.montage.model import StickerItem

    tl.stickers = [StickerItem(id="sticker1", path=str(tmp_path / "badge.png"), start_ms=0, end_ms=1000)]
    plan = plan_from_montage(tl, "m1", "Mening montajim", tmp_path / "out", Settings(data_dir=tmp_path))
    HostPlan.model_validate(plan.to_json())
    kinds = [v.transition_in.kind if v.transition_in else None for v in plan.video]
    assert kinds == [None, "cross_dissolve", "dip_to_black", "wipe", "push", "cross_dissolve", "cut"]
    assert plan.video[1].transition_in.dur_s == pytest.approx(0.4)
    assert plan.video[1].rec_in == pytest.approx(plan.video[0].rec_out - 0.4)  # ustma-ust
    starts = tl.item_starts()
    assert [v.rec_in for v in plan.video] == pytest.approx([s / 1000 for s in starts])
    assert plan.sequence.duration_s == pytest.approx(tl.duration_ms / 1000)
    assert plan.video[5].speed == 2.0 and plan.video[5].rec_out - plan.video[5].rec_in == pytest.approx(1.5)
    notes = " | ".join(plan.not_translated)
    for word in ("shake", "freeze", "circleopen", "animatsiya", "Stiker"):
        assert word in notes
    # punch-in: 0.5 s da boshlanadi, 0.62 s da 1.25x, 1.5 s dan keyin 1x
    keys = plan.video[0].layers[0].keys
    base = keys[0].scale_pct
    at = {k.t: k.scale_pct for k in keys}
    assert at[0.5] == pytest.approx(base) and at[0.62] == pytest.approx(base * 1.25, rel=1e-3)
    assert at[1.501] == pytest.approx(base)
    # fit_blur + lut + global warm
    e2 = plan.video[2]
    assert [ly.role for ly in e2.layers] == ["bg", "main"]
    eff = {e.kind for e in e2.layers[1].effects}
    assert eff == {"lut", "lumetri_preset"}
    assert any(e.preset == "warm" for e in plan.video[0].layers[0].effects)
    # pan (manbada gorizontal zaxira bor) - pos_x o'zgaradi, scale o'zgarmaydi
    pk = plan.video[3].layers[0].keys
    assert pk[0].pos_x != pk[-1].pos_x and pk[0].scale_pct == pk[-1].scale_pct
    # tik manba 9:16 da to'liq (center crop)
    assert plan.video[4].layers[0].keys[0].scale_pct == pytest.approx(100.0)
    assert plan.music[0].volume_db == -18 and plan.music[0].rec_out == pytest.approx(tl.duration_ms / 1000)
    assert plan.text[0].kind == "hook" and "oʻzbekcha" in plan.text[0].text
    assert plan.captions.lines and Path(plan.captions.srt_path).name == "mening-montajim.srt"
    assert plan.markers[0].kind == "hook" and plan.markers[0].t == 0
    assert {m.id for m in plan.media} == {"a", "v", "mu"}


def test_montage_hostplan_endpoint(tmp_path, monkeypatch):
    c, st = make_client(tmp_path, monkeypatch)
    tl = _timeline(tmp_path)
    st.lib_write("INSERT INTO montages(id, name, template_id, sources_json, status, timeline_json)"
                 " VALUES ('m1', 'Montaj', 't', '[]', 'ready', ?)", (json.dumps(tl.to_json()),))
    st.lib_write("INSERT INTO montages(id, name, template_id, sources_json, status)"
                 " VALUES ('m2', 'Bo''sh', 't', '[]', 'failed')")
    r = c.post("/v1/montages/m1:hostplan", json={"out_dir": str(tmp_path / "mo")})
    assert r.status_code == 200, r.text
    assert r.json()["schema"] == "lahza.hostplan/1" and r.json()["source"] == "montage"
    assert (tmp_path / "mo" / "montaj.srt").is_file()
    assert c.post("/v1/montages/m2:hostplan", json={"out_dir": str(tmp_path)}).status_code == 409
    assert c.post("/v1/montages/yoq:hostplan", json={"out_dir": str(tmp_path)}).status_code == 404


# ---- CORS ------------------------------------------------------------------------


def _cors_client(tmp_path, monkeypatch, adobe: str | None = None) -> TestClient:
    monkeypatch.delenv("LAHZA_DEV", raising=False)
    if adobe is not None:
        monkeypatch.setenv("LAHZA_ADOBE_CORS", adobe)
    return TestClient(create_app(Settings(data_dir=tmp_path / "d"), token="tok"))


@pytest.mark.parametrize("origin", ["null", "file://"])
def test_cors_allows_cep_origins_but_token_required(tmp_path, monkeypatch, origin):
    c = _cors_client(tmp_path, monkeypatch)
    pre = c.options("/v1/hostplan/schema", headers={
        "Origin": origin, "Access-Control-Request-Method": "GET",
        "Access-Control-Request-Headers": "authorization"})
    assert pre.status_code == 200 and pre.headers["access-control-allow-origin"] == origin
    assert c.get("/v1/hostplan/schema", headers={"Origin": origin}).status_code == 401
    ok = c.get("/v1/hostplan/schema", headers={"Origin": origin, "Authorization": "Bearer tok"})
    assert ok.status_code == 200 and ok.headers["access-control-allow-origin"] == origin
    assert "access-control-allow-credentials" not in ok.headers


def test_cors_rejects_other_origins_and_can_be_disabled(tmp_path, monkeypatch):
    c = _cors_client(tmp_path, monkeypatch)
    pre = c.options("/v1/health", headers={"Origin": "https://evil.example",
                                           "Access-Control-Request-Method": "GET"})
    assert pre.status_code == 400 and "access-control-allow-origin" not in pre.headers
    c2 = _cors_client(tmp_path, monkeypatch, adobe="0")
    pre = c2.options("/v1/health", headers={"Origin": "null", "Access-Control-Request-Method": "GET"})
    assert pre.status_code == 400


def test_clip_srt_uppercase(tmp_path, monkeypatch):
    c, st = make_client(tmp_path, monkeypatch)
    eid, clip, _, _ = _seed_clip(st, tmp_path)
    r = c.post(f"/v1/episodes/{eid}/clips/{clip.id}:hostplan",
               json={"out_dir": str(tmp_path / "u"), "style": {"uppercase": True}})
    assert r.status_code == 200, r.text
    srt = Path(r.json()["captions"]["srt_path"]).read_text(encoding="utf-8")
    assert "SOʻZ0_0" in srt and "-->" in srt and "soʻz" not in srt
    assert r.json()["captions"]["lines"][0]["words"][0]["text"] == "soʻz0_0"  # JSON asl registrda
