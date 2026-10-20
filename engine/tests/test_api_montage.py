"""Montaj API: fx, shablonlar CRUD/import/eksport, montaj yaratish -> ready, timeline tahriri, qayta reja,
preview, render (libass 422), thumb, o'chirish. RENDER/PLANNER modullari soxta (monkeypatch)."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import types
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest
from _api_helpers import make_client, seed_episode, wait_job
from conftest import requires_ffmpeg

from lahza_engine.db import store as db
from lahza_engine.media.tools import find_tool as REAL_FIND_TOOL
from lahza_engine.montage.model import Format, MediaRef, MontageTimeline, TextItem, VideoItem
from lahza_engine.render.encoders import EncoderChoice
from lahza_engine.subtitle.style import StyleTemplate
from lahza_engine.templates.model import Template
from lahza_engine.types import Clip

BUILTIN = ["uz.lahza.tpl.podcast-hook", "uz.lahza.tpl.daily-story"]
PLUGINS = ["uz.lahza.tr.fade", "uz.lahza.tr.dissolve", "uz.lahza.motion.punch-in", "uz.lahza.color.warm"]


# ---- Soxta modullar ----------------------------------------------------------------

def fake_module(monkeypatch, name: str, **attrs: Any) -> types.ModuleType:
    mod = types.ModuleType(name)
    for k, v in attrs.items():
        setattr(mod, k, v)
    parent, _, child = name.rpartition(".")
    if parent not in sys.modules:
        fake_module(monkeypatch, parent)
    monkeypatch.setitem(sys.modules, name, mod)
    monkeypatch.setattr(sys.modules[parent], child, mod, raising=False)
    return mod


class FakeManifest:
    def __init__(self, pid: str) -> None:
        self.id, self.kind = pid, pid.split(".")[2]

    def model_dump(self, **_: Any) -> dict[str, Any]:
        return {"schema": "lahza.fx/1", "id": self.id, "kind": self.kind}


def _get_plugin(pid: str) -> FakeManifest:
    if pid not in PLUGINS:
        raise KeyError(pid)
    return FakeManifest(pid)


class TemplateError(ValueError):
    pass


def _load_template_file(p: Path) -> Template:
    try:
        return Template.model_validate(json.loads(Path(p).read_text(encoding="utf-8")))
    except ValueError as e:
        raise TemplateError("shablon fayli yaroqsiz (o'zbekcha)") from e


def _builtin() -> list[Template]:
    return [Template(id=BUILTIN[0], name={"uz": "Podkast hook"}, selection="highlight", captions=True,
                     intro={"text": "{sarlavha}"}),
            Template(id=BUILTIN[1], name={"uz": "Kundalik"}, color="uz.lahza.color.warm")]


@dataclass
class Shot:
    start_ms: int
    end_ms: int
    score: float = 0.5
    sharpness: float = 0.5
    motion: float = 0.1
    energy: float = 0.5
    has_speech: bool = False
    faces: int = 0


@dataclass
class HighlightSeg:
    start_ms: int
    end_ms: int
    score: float
    title: str
    clip_id: str | None = None


@dataclass
class SourceAnalysis:
    media: MediaRef
    shots: list[Shot]
    speech: list[tuple[int, int]] = field(default_factory=list)
    sentences: list[Any] = field(default_factory=list)
    highlights: list[HighlightSeg] = field(default_factory=list)
    emphasis_ms: list[int] = field(default_factory=list)
    speaker_changes_ms: list[int] = field(default_factory=list)


class PlanError(ValueError):
    pass


@dataclass
class MontageOverrides:
    target_duration_ms: int | None = None
    aspect: str | None = None
    music_path: str | None = None
    title: str | None = None
    cta: str | None = None
    shou: str | None = None
    captions: bool | None = None
    caption_style: StyleTemplate | None = None
    logo_path: str | None = None
    transition: str | None = None
    color: str | None = None


class Recorder:
    def __init__(self) -> None:
        self.analyze_calls: list[tuple[Path, str, Path]] = []
        self.plans: list[tuple[Template, list[SourceAnalysis], MontageOverrides]] = []
        self.fail_plan: str | None = None
        self.frames: list[int] = []
        self.renders: list[dict[str, Any]] = []
        self.render_error: Exception | None = None


def _analyze_file(rec: Recorder):
    def analyze_file(path: Path, media_id: str, cache_dir: Path, settings, cancel=None) -> SourceAnalysis:
        rec.analyze_calls.append((Path(path), media_id, Path(cache_dir)))
        dur = 300_000
        m = MediaRef(id=media_id, path=str(path), duration_ms=dur, width=1920, height=1080, fps=25.0)
        shots = [Shot(t, t + 5000) for t in range(0, dur, 5000)]
        return SourceAnalysis(media=m, shots=shots, speech=[(0, dur)], emphasis_ms=[1000, 7000, 50_000],
                              speaker_changes_ms=[6400, 90_000])
    return analyze_file


def _plan_montage(rec: Recorder):
    def plan_montage(template: Template, sources: list[SourceAnalysis], overrides: MontageOverrides, settings):
        rec.plans.append((template, sources, overrides))
        if rec.fail_plan:
            raise PlanError(rec.fail_plan)
        if not sources:
            raise PlanError("manba yo'q")
        items, media = [], {}
        for i, sa in enumerate(sources):
            media[sa.media.id] = sa.media
            seg = sa.highlights[0] if sa.highlights else sa.shots[0]
            items.append(VideoItem(id=f"v{i + 1}", media=sa.media.id, src_in_ms=seg.start_ms,
                                   src_out_ms=min(seg.end_ms, seg.start_ms + 4000), reason="soxta"))
        text = [TextItem(id="t1", start_ms=0, end_ms=1500, text=overrides.title or "Sarlavha")] \
            if template.intro else []
        return MontageTimeline(format=Format.for_aspect(overrides.aspect or template.aspect), media=media,
                               video=items, text=text)
    return plan_montage


class LibassMissing(RuntimeError):
    pass


@dataclass
class FakeRenderResult:
    video: Path
    edl: Path
    srt: Path | None
    warnings: list[str]


def _render_montage(rec: Recorder):
    def render_montage(tl, out: Path, workdir: Path, encoder, settings, *, detector=None, allow_no_subs=False,
                       on_progress=None, cancel=None):
        rec.renders.append({"out": out, "workdir": workdir, "allow_no_subs": allow_no_subs,
                            "encoder": encoder.name})
        assert workdir.is_dir()
        if rec.render_error:
            raise rec.render_error
        if on_progress:
            on_progress(0.5)
        out.write_bytes(b"mp4")
        edl = out.with_name(out.stem + "_edl.json")
        edl.write_text(json.dumps({"haqiqiy_kadr": True}), encoding="utf-8")
        return FakeRenderResult(out, edl, None, ["matn chizilmadi"] if allow_no_subs else [])
    return render_montage


def _render_frame(rec: Recorder):
    def render_montage_frame(tl, t_ms: int, out_jpg: Path, settings, *, detector=None) -> Path:
        rec.frames.append(t_ms)
        out_jpg.write_bytes(b"\xff\xd8\xff\xe0JPEG")
        return out_jpg
    return render_montage_frame


@pytest.fixture
def env(tmp_path: Path, monkeypatch):
    rec = Recorder()
    fake_module(monkeypatch, "lahza_engine.fx.registry",
                list_plugins=lambda kind=None: [FakeManifest(p) for p in PLUGINS
                                                if kind is None or FakeManifest(p).kind == kind],
                get_plugin=_get_plugin)
    fake_module(monkeypatch, "lahza_engine.templates.store", builtin_templates=_builtin,
                load_template_file=_load_template_file, TemplateError=TemplateError,
                save_template_file=lambda t, p: Path(p).write_text(json.dumps(t.to_json()), encoding="utf-8"))
    fake_module(monkeypatch, "lahza_engine.montage.analyze", Shot=Shot, SourceAnalysis=SourceAnalysis,
                HighlightSeg=HighlightSeg, analyze_file=_analyze_file(rec))
    fake_module(monkeypatch, "lahza_engine.montage.planner", MontageOverrides=MontageOverrides,
                PlanError=PlanError, plan_montage=_plan_montage(rec))
    fake_module(monkeypatch, "lahza_engine.render.montage_render", render_montage=_render_montage(rec),
                render_montage_frame=_render_frame(rec), LibassMissing=LibassMissing)
    # Render vazifasi: enkoder/apparat aniqlash soxta (ffmpeg'siz).
    monkeypatch.setattr("lahza_engine.media.tools.find_tool", lambda name: Path("/usr/bin/" + name))
    monkeypatch.setattr("lahza_engine.render.encoders.choose_encoder",
                        lambda *a, **k: EncoderChoice("libx264", (), False))
    monkeypatch.setattr("lahza_engine.models.hardware.detect",
                        lambda *a, **k: types.SimpleNamespace(best_gpu=lambda: None))
    monkeypatch.setattr("lahza_engine.render.capabilities.has_filter", lambda ff, name: True)
    c, st = make_client(tmp_path, monkeypatch)
    return c, st, rec, tmp_path


def _video(tmp_path: Path, name: str = "a.mp4") -> Path:
    p = tmp_path / "media" / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(b"\x00" * 64)
    return p


def _create(c, st, sources, template_id=BUILTIN[1], **extra) -> dict[str, Any]:
    r = c.post("/v1/montages", json={"template_id": template_id, "sources": sources, **extra})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["job"]["kind"] == "montage"
    wait_job(st, body["job"]["id"])
    return c.get(f"/v1/montages/{body['montage_id']}").json()


# ---- fx va shablonlar ------------------------------------------------------------------

def test_fx_list(env) -> None:
    c, *_ = env
    assert [m["id"] for m in c.get("/v1/fx").json()] == PLUGINS
    assert [m["id"] for m in c.get("/v1/fx?kind=tr").json()] == ["uz.lahza.tr.fade", "uz.lahza.tr.dissolve"]


def test_templates_crud_and_builtin_protection(env) -> None:
    c, *_ = env
    lst = c.get("/v1/templates").json()
    assert [t["id"] for t in lst] == BUILTIN and all(t["builtin"] for t in lst)
    assert c.get(f"/v1/templates/{BUILTIN[0]}").json()["selection"] == "highlight"
    assert c.get("/v1/templates/yoq").status_code == 404

    # id'siz va builtin id bilan POST -> yangi user.<uuid12>
    r = c.post("/v1/templates", json={"name": {"uz": "Mening"}, "category": "elon"})
    assert r.status_code == 200, r.text
    t1 = r.json()
    assert t1["id"].startswith("user.") and len(t1["id"]) == 17 and t1["builtin"] is False
    t2 = c.post("/v1/templates", json={"id": BUILTIN[0], "name": {"uz": "Nusxa"}}).json()
    assert t2["id"].startswith("user.") and t2["id"] != t1["id"]
    t3 = c.post("/v1/templates", json={"id": "user.mine", "name": {"uz": "O'zim"}}).json()
    assert t3["id"] == "user.mine"
    assert c.post("/v1/templates", json={"id": "user.mine", "name": {"uz": "Yana"}}).json()["id"] != "user.mine"

    # validatsiya va plagin tekshiruvi -> 400 o'zbekcha
    r = c.post("/v1/templates", json={"name": {"uz": "x"}, "min_shot_ms": 5000, "max_shot_ms": 1000})
    assert r.status_code == 400 and "shablon yaroqsiz" in r.json()["detail"]
    r = c.post("/v1/templates", json={"name": {"uz": "x"}, "fx": [{"plugin": "yoq.plagin", "trigger": "on_cut"}]})
    assert r.status_code == 400 and "noma'lum plagin" in r.json()["detail"]
    assert c.post("/v1/templates", json={"name": {"ru": "без uz"}}).status_code == 400

    # PUT / DELETE
    assert c.put(f"/v1/templates/{BUILTIN[0]}", json={"name": {"uz": "x"}}).status_code == 409
    assert c.delete(f"/v1/templates/{BUILTIN[0]}").status_code == 409
    r = c.put(f"/v1/templates/{t1['id']}", json={"id": "boshqa", "name": {"uz": "Yangi nom"},
                                                 "transition": {"plugin": "uz.lahza.tr.fade"}})
    assert r.status_code == 200, r.text
    assert r.json()["id"] == t1["id"] and r.json()["name"]["uz"] == "Yangi nom"
    assert c.get(f"/v1/templates/{t1['id']}").json()["transition"]["plugin"] == "uz.lahza.tr.fade"
    assert c.put("/v1/templates/user.yoq", json={"name": {"uz": "x"}}).status_code == 404
    assert c.delete(f"/v1/templates/{t1['id']}").json() == {"ok": True}
    assert c.delete(f"/v1/templates/{t1['id']}").status_code == 404

    # Nusxa
    d = c.post(f"/v1/templates/{BUILTIN[0]}:duplicate", json={}).json()
    assert d["id"].startswith("user.") and d["name"]["uz"] == "Podkast hook (nusxa)" and not d["builtin"]
    assert d["selection"] == "highlight"
    d2 = c.post(f"/v1/templates/{d['id']}:duplicate", json={"name": "Boshqa"}).json()
    assert d2["name"]["uz"] == "Boshqa"
    ids = [t["id"] for t in c.get("/v1/templates").json()]
    assert ids[:2] == BUILTIN and d["id"] in ids and d2["id"] in ids


def test_templates_import_export(env) -> None:
    c, _, _, tmp = env
    out = tmp / "eks" / "podkast"
    out.parent.mkdir()
    assert c.post(f"/v1/templates/{BUILTIN[0]}:export", json={"path": str(out)}).json() == {"ok": True}
    f = out.with_suffix(".json")
    assert json.loads(f.read_text())["id"] == BUILTIN[0]
    assert c.post(f"/v1/templates/{BUILTIN[0]}:export",
                  json={"path": str(tmp / "yoq" / "a.json")}).status_code == 400

    r = c.post("/v1/templates:import", json={"path": str(f)})
    assert r.status_code == 200, r.text
    imp = r.json()
    assert imp["id"].startswith("user.") and imp["builtin"] is False  # builtin id -> yangi id
    custom = tmp / "c.json"
    custom.write_text(json.dumps({"schema": "lahza.template/1", "id": "user.import1", "name": {"uz": "I"}}))
    assert c.post("/v1/templates:import", json={"path": str(custom)}).json()["id"] == "user.import1"
    assert c.post("/v1/templates:import", json={"path": str(custom)}).json()["id"] != "user.import1"

    bad = tmp / "bad.json"
    bad.write_text("{not json")
    r = c.post("/v1/templates:import", json={"path": str(bad)})
    assert r.status_code == 400 and "yaroqsiz" in r.json()["detail"]
    txt = tmp / "a.txt"
    txt.write_text("{}")
    assert c.post("/v1/templates:import", json={"path": str(txt)}).status_code == 400
    big = tmp / "big.json"
    big.write_text(" " * (1024 * 1024 + 1))
    r = c.post("/v1/templates:import", json={"path": str(big)})
    assert r.status_code == 400 and "katta" in r.json()["detail"]


# ---- Montaj yaratish --------------------------------------------------------------------

def _seed_clip(st, tmp_path) -> tuple[str, str, Clip]:
    _, eid, pdir = seed_episode(st, tmp_path)
    clip = Clip(id="c1", media_id=eid, start_ms=6400, end_ms=25_600, start_sentence_id=1, end_sentence_id=3,
                title="Klip", score=77.0, cuts=[(12_800, 19_200)])
    conn = db.open_project(pdir)
    db.save_clips(conn, [clip, clip.model_copy(update={"id": "c2", "start_ms": 32_000, "end_ms": 44_800,
                                                        "start_sentence_id": 5, "end_sentence_id": 6,
                                                        "title": "Ikkinchi", "cuts": []})])
    conn.close()
    return eid, pdir, clip


def test_create_montage_ready_with_all_source_kinds(env) -> None:
    c, st, rec, tmp = env
    f = _video(tmp)
    eid, pdir, clip = _seed_clip(st, tmp)
    sid = st.lib("SELECT show_id FROM episodes WHERE id = ?", (eid,))[0]["show_id"]
    m = _create(c, st, [{"kind": "file", "path": str(f)},
                        {"kind": "clip", "episode_id": eid, "clip_id": "c1"},
                        {"kind": "episode", "episode_id": eid}],
                template_id=BUILTIN[0], project_id=sid, name="Mening montajim",
                overrides={"title": "Salom", "aspect": "1:1"})
    assert m["status"] == "ready", m
    assert m["name"] == "Mening montajim" and m["project_id"] == sid and m["template_id"] == BUILTIN[0]
    assert [s["media_id"] for s in m["sources"]] == ["src1", "src2", "src3"]
    assert m["overrides"] == {"title": "Salom", "aspect": "1:1"}
    tl = MontageTimeline.model_validate(m["timeline"])
    assert tl.format.aspect == "1:1" and len(tl.video) == 3 and tl.text[0].text == "Salom"
    assert m["duration_ms"] == tl.duration_ms > 0 and m["error"] is None and m["user_edited"] is False

    # Tahlil: asl fayldan (proksi emas), kesh Library/_montage/<id>/cache
    src_media = Path(db.open_project(pdir).execute("SELECT path FROM media").fetchone()[0])
    assert [a[0] for a in rec.analyze_calls] == [f.resolve(), src_media, src_media]
    assert all(a[2] == st.settings.library_dir / "_montage" / m["id"] / "cache" for a in rec.analyze_calls)

    _, analyses, ov = rec.plans[-1]
    assert ov.title == "Salom" and ov.aspect == "1:1"
    file_sa, clip_sa, ep_sa = analyses
    assert file_sa.highlights == [] and file_sa.media.origin == "file"
    # Klip manbasi: faqat [6400,12800) + [19200,25600), highlight = klipning o'zi
    assert [(h.start_ms, h.end_ms, h.clip_id) for h in clip_sa.highlights] == \
        [(6400, 12_800, "c1"), (19_200, 25_600, "c1")]
    assert all(6400 <= sh.start_ms < sh.end_ms <= 25_600 and not (12_800 < sh.end_ms <= 19_200)
               for sh in clip_sa.shots)
    assert clip_sa.emphasis_ms == [7000] and clip_sa.speaker_changes_ms == [6400]
    assert {s.id for s in clip_sa.sentences} == {1, 3}  # 2-gap kesim ichida
    assert clip_sa.media.origin == f"clip:{eid}/c1"
    # Epizod manbasi: barcha kliplar highlight, barcha gaplar
    assert {h.clip_id for h in ep_sa.highlights} == {"c1", "c2"} and len(ep_sa.sentences) == 12
    assert ep_sa.media.origin == f"episode:{eid}"

    lst = c.get(f"/v1/montages?project_id={sid}").json()
    assert [x["id"] for x in lst] == [m["id"]] and lst[0]["duration_ms"] == tl.duration_ms
    assert c.get("/v1/montages?project_id=boshqa").json() == []
    assert len(c.get("/v1/montages").json()) == 1


def test_create_montage_validation(env) -> None:
    c, st, _, tmp = env
    f = _video(tmp)
    eid, _, _ = _seed_clip(st, tmp)

    def post(sources, tid=BUILTIN[1], **kw):
        return c.post("/v1/montages", json={"template_id": tid, "sources": sources, **kw})

    assert post([]).status_code == 400
    assert post([{"kind": "file", "path": str(f)}] * 51).status_code == 400
    r = post([{"kind": "file", "path": str(tmp / "yoq.mp4")}])
    assert r.status_code == 400 and "fayl topilmadi" in r.json()["detail"]
    assert post([{"kind": "episode", "episode_id": "yoq"}]).status_code == 404
    assert post([{"kind": "clip", "episode_id": eid, "clip_id": "yoq"}]).status_code == 404
    assert post([{"kind": "file", "path": str(f)}], tid="yoq").status_code == 404
    assert post([{"kind": "file", "path": str(f)}], project_id="yoq").status_code == 404
    assert post([{"kind": "boshqa"}]).status_code == 422
    r = post([{"kind": "file", "path": str(f)}], overrides={"music_path": str(tmp / "yoq.mp3")})
    assert r.status_code == 400 and "musiqa" in r.json()["detail"]
    assert post([{"kind": "file", "path": str(f)}], overrides={"color": "yoq"}).status_code == 400
    assert c.get("/v1/montages").json() == []  # hech narsa yaratilmagan


def test_plan_error_marks_failed(env) -> None:
    c, st, rec, tmp = env
    rec.fail_plan = "manbalar montaj uchun yetarli emas"
    m = _create(c, st, [{"kind": "file", "path": str(_video(tmp))}])
    assert m["status"] == "failed" and m["error"] == "manbalar montaj uchun yetarli emas"
    assert m["timeline"] is None
    job = st.jobs.jobs[m["job_id"]]
    assert job.status == "failed" and job.kind == "montage"


def test_stale_planning_is_healed(env) -> None:
    c, st, *_ = env
    st.lib_write("INSERT INTO montages(id, name, template_id, sources_json, status, job_id)"
                 " VALUES ('old', 'Eski', 't', '[]', 'planning', 'yoqjob')")
    m = c.get("/v1/montages/old").json()
    assert m["status"] == "failed" and "qayta" in m["error"]


# ---- Timeline, qayta reja, preview, render, thumb, o'chirish ----------------------------------

def test_timeline_put_and_replan(env) -> None:
    c, st, rec, tmp = env
    m = _create(c, st, [{"kind": "file", "path": str(_video(tmp))}, {"kind": "file", "path": str(_video(tmp, "b.mp4"))}])
    mid, tl = m["id"], m["timeline"]

    bad = json.loads(json.dumps(tl))
    bad["video"][0]["src_out_ms"] = bad["video"][0]["src_in_ms"]
    r = c.put(f"/v1/montages/{mid}/timeline", json=bad)
    assert r.status_code == 400 and r.json()["detail"].startswith("timeline yaroqsiz")
    bad = json.loads(json.dumps(tl))
    bad["video"][0]["media"] = "yoq"
    assert c.put(f"/v1/montages/{mid}/timeline", json=bad).status_code == 400
    bad = json.loads(json.dumps(tl))
    bad["media"]["src1"]["path"] = str(tmp / "begona.mp4")
    r = c.put(f"/v1/montages/{mid}/timeline", json=bad)
    assert r.status_code == 400 and "fayl topilmadi" in r.json()["detail"]
    bad = json.loads(json.dumps(tl))
    bad["video"][1]["transition_in"] = {"plugin": "uz.lahza.tr.yoq"}
    assert c.put(f"/v1/montages/{mid}/timeline", json=bad).status_code == 400

    # Yangi mavjud fayl (musiqa) qo'shish mumkin; element tartibi o'zgaradi
    music = _video(tmp, "music.mp3")
    ok = json.loads(json.dumps(tl))
    ok["video"] = list(reversed(ok["video"]))
    ok["video"][0]["transition_in"] = None
    ok["video"][1]["transition_in"] = {"plugin": "uz.lahza.tr.fade", "dur_ms": 300}
    ok["video"][1]["user_edited"] = True
    ok["media"]["music"] = {"id": "music", "path": str(music), "duration_ms": 60_000, "width": 0, "height": 0,
                            "fps": 0}
    ok["music"] = [{"media": "music"}]
    r = c.put(f"/v1/montages/{mid}/timeline", json=ok)
    assert r.status_code == 200, r.text
    assert r.json()["ok"] is True and r.json()["timeline"]["video"][0]["id"] == "v2"
    m2 = c.get(f"/v1/montages/{mid}").json()
    assert m2["user_edited"] is True and m2["timeline"]["music"][0]["media"] == "music"
    assert m2["duration_ms"] == MontageTimeline.model_validate(ok).duration_ms

    r = c.post(f"/v1/montages/{mid}:replan", json={})
    assert r.status_code == 409 and "force" in r.json()["detail"]
    r = c.post(f"/v1/montages/{mid}:replan", json={"force": True, "template_id": BUILTIN[0],
                                                    "overrides": {"title": "Yangi"}})
    assert r.status_code == 200 and r.json()["kind"] == "montage"
    wait_job(st, r.json()["id"])
    m3 = c.get(f"/v1/montages/{mid}").json()
    assert m3["status"] == "ready" and m3["user_edited"] is False and m3["template_id"] == BUILTIN[0]
    assert m3["timeline"]["text"][0]["text"] == "Yangi" and m3["overrides"] == {"title": "Yangi"}

    # Qayta reja xatosi: eski timeline saqlanadi
    rec.fail_plan = "reja xatosi"
    j = c.post(f"/v1/montages/{mid}:replan", json={}).json()
    wait_job(st, j["id"])
    m4 = c.get(f"/v1/montages/{mid}").json()
    assert m4["status"] == "ready" and m4["error"] == "reja xatosi" and m4["timeline"] == m3["timeline"]


def test_preview(env) -> None:
    c, st, rec, tmp = env
    m = _create(c, st, [{"kind": "file", "path": str(_video(tmp))}])
    r = c.post(f"/v1/montages/{m['id']}:preview", json={"t_ms": 10_000_000})
    assert r.status_code == 200 and r.headers["content-type"] == "image/jpeg" and r.content.startswith(b"\xff\xd8")
    assert rec.frames == [m["duration_ms"] - 1]
    assert list((st.settings.library_dir / "_montage" / m["id"] / "work" / "preview").iterdir()) == []
    assert c.post("/v1/montages/yoq:preview", json={"t_ms": 0}).status_code == 404


def test_render_libass_422_and_ok(env, monkeypatch) -> None:
    c, st, rec, tmp = env
    m = _create(c, st, [{"kind": "file", "path": str(_video(tmp))}], template_id=BUILTIN[0], name="Bayram: 1/2")
    out_dir = tmp / "out"
    monkeypatch.setattr("lahza_engine.render.capabilities.has_filter", lambda ff, name: False)
    r = c.post(f"/v1/montages/{m['id']}:render", json={"out_dir": str(out_dir)})
    assert r.status_code == 422 and "libass" in r.json()["detail"]
    assert c.get(f"/v1/montages/{m['id']}").json()["exports"] == []

    r = c.post(f"/v1/montages/{m['id']}:render", json={"out_dir": str(out_dir), "allow_no_subs": True})
    assert r.status_code == 200, r.text
    job = r.json()
    assert job["kind"] == "export" and job["meta"]["montage_id"] == m["id"] and job["meta"]["title"] == "Bayram: 1/2"
    j = wait_job(st, job["id"])
    assert j.status == "done", j.error
    assert Path(j.result["video"]) == out_dir / "Bayram_ 1_2.mp4" and Path(j.result["video"]).exists()
    assert j.result["edl"].endswith("_edl.json") and j.result["encoder"] == "libx264"
    assert j.result["warnings"] == ["matn chizilmadi"] and j.result["srt"] is None
    assert rec.renders[-1]["allow_no_subs"] is True and not rec.renders[-1]["workdir"].exists()

    # Ikkinchi render ustiga yozmaydi; nom berilsa .mp4 qo'shiladi
    j2 = wait_job(st, c.post(f"/v1/montages/{m['id']}:render",
                             json={"out_dir": str(out_dir), "allow_no_subs": True}).json()["id"])
    assert Path(j2.result["video"]).name == "Bayram_ 1_2_2.mp4"
    j3 = wait_job(st, c.post(f"/v1/montages/{m['id']}:render",
                             json={"out_dir": str(out_dir), "filename": "../reel", "allow_no_subs": True}).json()["id"])
    assert Path(j3.result["video"]) == out_dir / "_reel.mp4"

    ex = c.get(f"/v1/montages/{m['id']}").json()["exports"]
    assert len(ex) == 3 and all(e["status"] == "done" and e["finished_at"] for e in ex)
    lst = [e for e in c.get("/v1/exports").json() if e["montage_id"] == m["id"]]
    assert len(lst) == 3 and lst[0]["title"] == "Bayram: 1/2" and lst[0]["clip_id"] is None

    # Matnsiz timeline: libass talab qilinmaydi
    tl = c.get(f"/v1/montages/{m['id']}").json()["timeline"]
    tl["text"] = []
    assert c.put(f"/v1/montages/{m['id']}/timeline", json=tl).status_code == 200
    r = c.post(f"/v1/montages/{m['id']}:render", json={"out_dir": str(out_dir)})
    assert r.status_code == 200
    assert wait_job(st, r.json()["id"]).status == "done"


def test_render_failure_and_retry(env) -> None:
    c, st, rec, tmp = env
    m = _create(c, st, [{"kind": "file", "path": str(_video(tmp))}])
    rec.render_error = LibassMissing("libass yo'q")
    job = c.post(f"/v1/montages/{m['id']}:render", json={"out_dir": str(tmp / "o")}).json()
    j = wait_job(st, job["id"])
    assert j.status == "failed" and "libass" in j.error
    ex = c.get(f"/v1/montages/{m['id']}").json()["exports"]
    assert ex[0]["status"] == "failed" and "LibassMissing" in ex[0]["error"]

    rec.render_error = None
    r = c.post(f"/v1/jobs/{job['id']}:retry")
    assert r.status_code == 200, r.text
    assert r.json()["meta"]["retry_of"] == job["id"] and r.json()["meta"]["montage_id"] == m["id"]
    assert wait_job(st, r.json()["id"]).status == "done"


def test_render_requires_ready(env) -> None:
    c, st, rec, tmp = env
    rec.fail_plan = "xato"
    m = _create(c, st, [{"kind": "file", "path": str(_video(tmp))}])
    assert c.post(f"/v1/montages/{m['id']}:render", json={"out_dir": str(tmp)}).status_code == 409
    assert c.post(f"/v1/montages/{m['id']}:preview", json={"t_ms": 0}).status_code == 409


def test_delete_montage(env) -> None:
    c, st, _, tmp = env
    m = _create(c, st, [{"kind": "file", "path": str(_video(tmp))}])
    d = st.settings.library_dir / "_montage" / m["id"]
    assert (d / "cache").is_dir()
    assert c.delete(f"/v1/montages/{m['id']}").json() == {"ok": True}
    assert not d.exists()
    assert c.get(f"/v1/montages/{m['id']}").status_code == 404
    assert c.delete(f"/v1/montages/{m['id']}").status_code == 404


@requires_ffmpeg
def test_source_thumb(env, monkeypatch) -> None:
    c, st, _, tmp = env
    monkeypatch.setattr("lahza_engine.media.tools.find_tool", REAL_FIND_TOOL)
    vid = tmp / "media" / "real.mp4"
    vid.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([shutil.which("ffmpeg"), "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i",
                    "testsrc=size=640x360:rate=25:duration=2", "-pix_fmt", "yuv420p", "-y", str(vid)], check=True)
    m = _create(c, st, [{"kind": "file", "path": str(vid)}])
    r = c.get(f"/v1/montages/{m['id']}/sources/src1/thumb?t_ms=500")
    assert r.status_code == 200 and r.headers["content-type"] == "image/jpeg" and r.content[:2] == b"\xff\xd8"
    assert (st.settings.library_dir / "_montage" / m["id"] / "thumbs" / "src1-500.jpg").exists()
    assert c.get(f"/v1/montages/{m['id']}/sources/yoq/thumb").status_code == 404


# ---- Draft preview va muharrirdan musiqa qo'shish ----------------------------------------------

def test_preview_draft_timeline(env, monkeypatch) -> None:
    c, st, rec, tmp = env
    seen: list[MontageTimeline] = []

    def frame(tl, t_ms, out_jpg, settings, *, detector=None):
        seen.append(tl)
        out_jpg.write_bytes(b"\xff\xd8\xff\xe0JPEG")
        return out_jpg

    monkeypatch.setattr(sys.modules["lahza_engine.render.montage_render"], "render_montage_frame", frame)
    m = _create(c, st, [{"kind": "file", "path": str(_video(tmp))}, {"kind": "file", "path": str(_video(tmp, "b.mp4"))}])
    mid, tl = m["id"], m["timeline"]

    draft = json.loads(json.dumps(tl))
    draft["video"] = draft["video"][:1]
    r = c.post(f"/v1/montages/{mid}:preview", json={"t_ms": 100, "timeline": draft})
    assert r.status_code == 200, r.text
    assert len(seen[-1].video) == 1
    # Saqlangan timeline o'zgarmaydi
    assert len(c.get(f"/v1/montages/{mid}").json()["timeline"]["video"]) == len(tl["video"])
    # Draftsiz - saqlangan timeline
    assert c.post(f"/v1/montages/{mid}:preview", json={"t_ms": 0}).status_code == 200
    assert len(seen[-1].video) == len(tl["video"])

    bad = json.loads(json.dumps(tl))
    bad["media"]["src1"]["path"] = str(_video(tmp, "begona.mp4"))  # mavjud, lekin montajda yo'q fayl
    r = c.post(f"/v1/montages/{mid}:preview", json={"t_ms": 0, "timeline": bad})
    assert r.status_code == 400 and "montajda yo'q" in r.json()["detail"]
    bad = json.loads(json.dumps(tl))
    bad["media"]["src1"]["path"] = bad["media"]["src2"]["path"]  # montaj fayli, lekin boshqa id'niki
    r = c.post(f"/v1/montages/{mid}:preview", json={"t_ms": 0, "timeline": bad})
    assert r.status_code == 400 and "almashtirib bo'lmaydi" in r.json()["detail"]
    bad = json.loads(json.dumps(tl))
    bad["video"][0]["src_out_ms"] = bad["video"][0]["src_in_ms"]
    r = c.post(f"/v1/montages/{mid}:preview", json={"t_ms": 0, "timeline": bad})
    assert r.status_code == 400 and r.json()["detail"].startswith("timeline yaroqsiz")
    bad = json.loads(json.dumps(tl))
    bad["video"][1]["transition_in"] = {"plugin": "uz.lahza.tr.yoq"}
    assert c.post(f"/v1/montages/{mid}:preview", json={"t_ms": 0, "timeline": bad}).status_code == 400
    empty = json.loads(json.dumps(tl))
    empty["video"] = []
    assert c.post(f"/v1/montages/{mid}:preview", json={"t_ms": 0, "timeline": empty}).status_code == 409


def test_add_music_media(env, monkeypatch) -> None:
    c, st, rec, tmp = env
    probes: dict[str, Any] = {}

    def probe_media(path):
        return types.SimpleNamespace(**probes[Path(path).name])

    monkeypatch.setattr(sys.modules["lahza_engine.montage.analyze"], "probe_media", probe_media, raising=False)
    m = _create(c, st, [{"kind": "file", "path": str(_video(tmp))}])
    mid, tl = m["id"], m["timeline"]
    song = _video(tmp, "song.mp3")
    silent = _video(tmp, "silent.mp4")
    probes["song.mp3"] = {"duration_ms": 40_000, "has_audio": True, "has_video": False}
    probes["silent.mp4"] = {"duration_ms": 8_000, "has_audio": False, "has_video": True}

    r = c.post(f"/v1/montages/{mid}/media", json={"path": str(song), "role": "music"})
    assert r.status_code == 200, r.text
    ref = r.json()["media"]
    assert ref["id"] == "music" and ref["duration_ms"] == 40_000 and ref["has_audio"] is True and ref["hash"]
    m2 = c.get(f"/v1/montages/{mid}").json()
    assert m2["timeline"]["media"]["music"]["path"] == str(song.resolve()) and m2["user_edited"] is True
    # Xuddi shu fayl - xuddi shu id; boshqa fayl - music2
    assert c.post(f"/v1/montages/{mid}/media", json={"path": str(song)}).json()["media"]["id"] == "music"
    song2 = _video(tmp, "song2.mp3")
    probes["song2.mp3"] = probes["song.mp3"]
    assert c.post(f"/v1/montages/{mid}/media", json={"path": str(song2)}).json()["media"]["id"] == "music2"

    r = c.post(f"/v1/montages/{mid}/media", json={"path": str(silent)})
    assert r.status_code == 400 and "ovoz yo'q" in r.json()["detail"]
    assert c.post(f"/v1/montages/{mid}/media", json={"path": str(tmp / "yoq.mp3")}).status_code == 400
    assert c.post(f"/v1/montages/{mid}/media", json={"path": str(song), "role": "video"}).status_code == 422
    assert c.post("/v1/montages/yoq/media", json={"path": str(song)}).status_code == 404

    # Qo'shilgan musiqa draft preview'da va PUT'da qabul qilinadi
    draft = json.loads(json.dumps(tl))
    draft["media"]["music"] = ref
    draft["music"] = [{"media": "music"}]
    assert c.post(f"/v1/montages/{mid}:preview", json={"t_ms": 0, "timeline": draft}).status_code == 200
    r = c.put(f"/v1/montages/{mid}/timeline", json=draft)
    assert r.status_code == 200 and r.json()["timeline"]["music"][0]["media"] == "music"
