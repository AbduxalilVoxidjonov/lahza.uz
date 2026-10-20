"""Montaj: fx plaginlari, video shablonlar (retseptlar), avtomontaj, timeline tahriri, preview va render
(docs/11 5-6, 10-bo'limlar; ADR-0011/0012/0013; docs/04 "Montaj").

Og'ir modullar (fx reestri, shablonlar ombori, manba tahlili, rejalashtiruvchi, montaj render) faqat
endpoint ichida yuklanadi (lazy import): engine ishga tushishi tez bo'lishi va modul yo'q bo'lsa ham
qolgan API ishlashi uchun (yo'q bo'lsa - 501).
"""

from __future__ import annotations

import copy
import inspect
import json
import os
import re
import shutil
import sqlite3
import uuid
from collections.abc import Callable
from dataclasses import fields as dc_fields
from pathlib import Path
from typing import Annotated, Any, Literal

from fastapi import Body, Depends, FastAPI, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field, ValidationError

from lahza_engine.api.state import State
from lahza_engine.core.jobs import Job
from lahza_engine.core.runner import Cancelled
from lahza_engine.db import store as db
from lahza_engine.montage.model import MediaRef, MontageTimeline
from lahza_engine.subtitle.style import StyleTemplate
from lahza_engine.templates.model import LocalText, Template
from lahza_engine.timeline import Timeline
from lahza_engine.types import Clip, ClipStatus, Sentence

MAX_TEMPLATE_FILE = 1024 * 1024
MAX_SOURCES = 50
LIBASS_MONTAGE_MSG = ("FFmpeg libass'siz yig'ilgan: montajdagi matn va subtitrlarni videoga chizib bo'lmaydi. "
                      "Dastur bilan kelgan FFmpeg'dan foydalaning yoki matnsiz renderni tanlang "
                      "(allow_no_subs=true).")


# ---- Kirish modellari -----------------------------------------------------------

class FileSource(BaseModel):
    kind: Literal["file"]
    path: str


class ClipSourceIn(BaseModel):
    kind: Literal["clip"]
    episode_id: str
    clip_id: str


class EpisodeSource(BaseModel):
    kind: Literal["episode"]
    episode_id: str


Source = Annotated[FileSource | ClipSourceIn | EpisodeSource, Field(discriminator="kind")]
JsonBody = Annotated[dict[str, Any], Body()]  # xom JSON: validatsiya xatosi 400 (o'zbekcha), 422 emas


class OverridesIn(BaseModel):
    """`montage.planner.MontageOverrides` ning JSON ko'rinishi (hammasi ixtiyoriy)."""

    target_duration_ms: int | None = Field(None, ge=5_000, le=600_000)
    aspect: Literal["9:16", "1:1", "16:9"] | None = None
    music_path: str | None = None
    title: str | None = None
    cta: str | None = None
    shou: str | None = None
    captions: bool | None = None
    caption_style: StyleTemplate | None = None
    logo_path: str | None = None
    transition: str | None = None
    color: str | None = None


class MontageIn(BaseModel):
    name: str | None = None
    project_id: str | None = None
    template_id: str
    sources: list[Source]
    overrides: OverridesIn | None = None


class ReplanIn(BaseModel):
    template_id: str | None = None
    overrides: OverridesIn | None = None
    force: bool = False


class PreviewIn(BaseModel):
    t_ms: int = Field(0, ge=0)
    # Saqlanmagan draft (ixtiyoriy): berilsa kadr shu timeline bo'yicha chiziladi.
    timeline: dict[str, Any] | None = None


class MediaIn(BaseModel):
    path: str
    role: Literal["music"] = "music"


class RenderIn(BaseModel):
    out_dir: str
    filename: str | None = None
    allow_no_subs: bool = False


class PathIn(BaseModel):
    path: str


class DuplicateIn(BaseModel):
    name: str | None = None


# ---- Umumiy yordamchilar ----------------------------------------------------------

def _validation_msg(prefix: str, e: ValidationError) -> str:
    err = e.errors()[0] if e.errors() else {}
    loc = ".".join(str(x) for x in err.get("loc", ()) if x != "__root__")
    msg = str(err.get("msg", "")).removeprefix("Value error, ")
    return f"{prefix}: {loc + ': ' if loc else ''}{msg}"


def _fx_registry():
    """`fx.registry` moduli (hali yo'q bo'lsa None - plagin tekshiruvi o'tkazib yuboriladi)."""
    try:
        from lahza_engine.fx import registry
    except ImportError:
        return None
    return registry


def _check_plugins(ids: list[str], what: str) -> None:
    reg = _fx_registry()
    if reg is None:
        return
    for pid in ids:
        try:
            reg.get_plugin(pid)
        except KeyError as e:
            raise HTTPException(400, f"{what}: noma'lum plagin '{pid}'") from e


def _template_plugins(t: Template) -> list[str]:
    ids = [r.plugin for r in t.fx]
    if t.transition:
        ids.append(t.transition.plugin)
    if t.color:
        ids.append(t.color)
    return ids


def _timeline_plugins(tl: MontageTimeline) -> list[str]:
    ids: list[str] = []
    for it in tl.video:
        ids += [f.plugin for f in it.fx]
        if it.transition_in:
            ids.append(it.transition_in.plugin)
    if tl.color:
        ids.append(tl.color.plugin)
    return ids


# ---- Shablonlar ------------------------------------------------------------------

def _builtin_templates() -> list[Template]:
    try:
        from lahza_engine.templates.store import builtin_templates
    except ImportError:
        return []
    return [t.model_copy(update={"builtin": True}) for t in builtin_templates()]


def _builtin_ids() -> set[str]:
    return {t.id for t in _builtin_templates()}


def _user_templates(s: State) -> list[Template]:
    out = []
    for r in s.lib("SELECT json FROM user_templates ORDER BY created_at, id"):
        try:
            out.append(Template.model_validate_json(r["json"]).model_copy(update={"builtin": False}))
        except ValidationError:
            continue  # buzilgan yozuv ro'yxatni to'xtatmaydi
    return out


def find_template(s: State, tid: str) -> Template:
    for t in _builtin_templates():
        if t.id == tid:
            return t
    rows = s.lib("SELECT json FROM user_templates WHERE id = ?", (tid,))
    if not rows:
        raise HTTPException(404, "shablon topilmadi")
    return Template.model_validate_json(rows[0]["json"]).model_copy(update={"builtin": False})


def _validate_template(data: Any) -> Template:
    if not isinstance(data, dict):
        raise HTTPException(400, "shablon JSON obyekt bo'lishi kerak")
    try:
        t = Template.model_validate(data)
    except ValidationError as e:
        raise HTTPException(400, _validation_msg("shablon yaroqsiz", e)) from e
    try:
        from lahza_engine.templates.store import TemplateError, validate_template
    except ImportError:
        _check_plugins(_template_plugins(t), "shablon")
        return t
    try:
        return validate_template(t)
    except TemplateError as e:
        raise HTTPException(400, f"shablon yaroqsiz: {e}") from e


def _new_user_id() -> str:
    return f"user.{uuid.uuid4().hex[:12]}"


def _insert_user_template(s: State, t: Template) -> Template:
    t = t.model_copy(update={"builtin": False})
    s.lib_write("INSERT INTO user_templates(id, json) VALUES (?, ?)",
                (t.id, json.dumps(t.to_json(), ensure_ascii=False)))
    return t


def _user_id_for(s: State, wanted: str | None) -> str:
    """Builtin yoki band id, bo'sh id - yangi `user.<uuid12>`."""
    wanted = (wanted or "").strip()
    if not wanted or wanted in _builtin_ids() or s.lib("SELECT 1 FROM user_templates WHERE id = ?", (wanted,)):
        return _new_user_id()
    return wanted


def _tpl_out(t: Template) -> dict[str, Any]:
    d = t.to_json()
    d["builtin"] = t.builtin
    return d


# ---- Montaj yozuvlari --------------------------------------------------------------

def montage_dir(s: State, mid: str) -> Path:
    return s.settings.library_dir / "_montage" / mid


def _row(s: State, mid: str) -> sqlite3.Row:
    rows = s.lib("SELECT * FROM montages WHERE id = ?", (mid,))
    if not rows:
        raise HTTPException(404, "montaj topilmadi")
    return _heal(s, rows[0])


def _heal(s: State, r: sqlite3.Row) -> sqlite3.Row:
    """Engine qayta ishga tushgandan keyin 'planning' da qolib ketgan montaj (vazifasi xotirada yo'q)."""
    if r["status"] != "planning" or (r["job_id"] and r["job_id"] in s.jobs.jobs):
        return r
    status = "ready" if r["timeline_json"] else "failed"
    s.lib_write("UPDATE montages SET status = ?, error = ?, updated_at = datetime('now') WHERE id = ?",
                (status, "rejalashtirish to'xtatildi (engine qayta ishga tushdi) - qayta rejalashtiring",
                 r["id"]))
    return s.lib("SELECT * FROM montages WHERE id = ?", (r["id"],))[0]


def _timeline(r: sqlite3.Row) -> MontageTimeline | None:
    return MontageTimeline.model_validate_json(r["timeline_json"]) if r["timeline_json"] else None


def _summary(r: sqlite3.Row) -> dict[str, Any]:
    return {"id": r["id"], "name": r["name"], "template_id": r["template_id"], "status": r["status"],
            "duration_ms": r["duration_ms"], "created_at": r["created_at"], "updated_at": r["updated_at"],
            "project_id": r["project_id"]}


def _detail(s: State, r: sqlite3.Row) -> dict[str, Any]:
    tl = _timeline(r)
    exports = [dict(x) for x in s.lib(
        "SELECT id, job_id, path, status, error, created_at, finished_at FROM montage_exports"
        " WHERE montage_id = ? ORDER BY created_at DESC, rowid DESC", (r["id"],))]
    return {**_summary(r), "sources": json.loads(r["sources_json"]),
            "overrides": json.loads(r["overrides_json"] or "{}"),
            "timeline": tl.to_json() if tl else None, "error": r["error"],
            "user_edited": bool(r["user_edited"]), "job_id": r["job_id"], "exports": exports}


def _resolve_sources(s: State, sources: list[Any]) -> list[dict[str, Any]]:
    """Validatsiya va yechish: har manbaga `media_id` (src1..) va asl fayl yo'li `path` beriladi."""
    if not sources:
        raise HTTPException(400, "kamida bitta manba tanlang")
    if len(sources) > MAX_SOURCES:
        raise HTTPException(400, f"manbalar soni {MAX_SOURCES} tadan oshmasligi kerak")
    out = []
    for i, src in enumerate(sources):
        d: dict[str, Any] = src.model_dump()
        d["media_id"] = f"src{i + 1}"
        if isinstance(src, FileSource):
            p = Path(src.path).expanduser()
            if not p.is_file():
                raise HTTPException(400, f"fayl topilmadi: {p.name or src.path}")
            d["path"] = str(p.resolve())
        else:
            ep = s.episode_row(src.episode_id)  # 404 "epizod topilmadi"
            with s.project(src.episode_id) as conn:
                m = conn.execute("SELECT path FROM media WHERE id = ?", (src.episode_id,)).fetchone()
                if m is None:
                    raise HTTPException(409, "epizod hali tahlil qilinmagan")
                if isinstance(src, ClipSourceIn) and db.get_clip(conn, src.episode_id, src.clip_id) is None:
                    raise HTTPException(404, "klip topilmadi")
            if not Path(m["path"]).is_file():
                raise HTTPException(400, f"epizodning asl fayli topilmadi: {ep['title']}")
            d["path"] = m["path"]
            d["title"] = ep["title"]
        out.append(d)
    return out


def _check_override_paths(o: OverridesIn | None) -> None:
    if o is None:
        return
    for label, p in (("musiqa", o.music_path), ("logotip", o.logo_path)):
        if p and not Path(p).expanduser().is_file():
            raise HTTPException(400, f"{label} fayli topilmadi")
    _check_plugins([x for x in (o.transition, o.color) if x], "sozlama")


def _overrides(planner, data: dict[str, Any]):
    names = {f.name for f in dc_fields(planner.MontageOverrides)}
    o = OverridesIn.model_validate(data or {})
    kwargs = {k: getattr(o, k) for k in OverridesIn.model_fields if k in names and getattr(o, k) is not None}
    return planner.MontageOverrides(**kwargs)


# ---- Manba tahlili (vazifa ichida) ---------------------------------------------------

def _episode_context(s: State, eid: str) -> tuple[list[Sentence], list[Clip], Any]:
    from lahza_engine.api.routes_clips import _signals

    pdir = s.episode_dir(eid)
    conn = db.open_project(pdir)
    try:
        sentences = db.load_transcript(conn, eid).sentences
        clips = [c for c in db.load_clips(conn, eid) if c.status != ClipStatus.REJECTED]
        signals = None
        if sentences:
            try:
                signals = _signals(conn, pdir, eid, sentences)
            except Exception:  # noqa: BLE001 - signallar ixtiyoriy boyitish
                signals = None
    finally:
        conn.close()
    return sentences, clips, signals


def _enrich(an, sa, sentences: list[Sentence], clips: list[Clip], signals) -> Any:
    """`analyze.enrich_with_transcript` (bo'lsa) yoki minimal boyitish: gaplar + klip highlight'lari."""
    fn = getattr(an, "enrich_with_transcript", None)
    if fn is not None:
        params = inspect.signature(fn).parameters
        avail = {"sentences": sentences, "clips": clips, "signals": signals}
        kwargs = {k: v for k, v in avail.items() if k in params}
        res = fn(sa, **kwargs)
        return sa if res is None else res
    sa = copy.copy(sa)
    sa.sentences = list(sentences)
    sa.highlights = [an.HighlightSeg(start_ms=c.start_ms, end_ms=c.end_ms, score=c.score, title=c.title,
                                     clip_id=c.id) for c in clips]
    return sa


def _intersect(a: int, b: int, segs: list[tuple[int, int]]) -> list[tuple[int, int]]:
    return [(max(a, x), min(b, y)) for x, y in segs if min(b, y) > max(a, x)]


def restrict_to_clip(an, sa, clip: Clip) -> Any:
    """Klip manbasi: faqat klip oralig'i (kesimlar chiqarib tashlangan) qoladi; highlight - klipning o'zi."""
    segs = [(g.src_start_ms, g.src_end_ms) for g in Timeline(clip.start_ms, clip.end_ms, clip.cuts).segments]

    def inside(t: int) -> bool:
        return any(x <= t < y for x, y in segs)

    out = copy.copy(sa)
    shots = []
    for sh in sa.shots:
        for a, b in _intersect(sh.start_ms, sh.end_ms, segs):
            part = copy.copy(sh)
            part.start_ms, part.end_ms = a, b
            shots.append(part)
    out.shots = shots
    out.speech = [ab for a, b in sa.speech for ab in _intersect(a, b, segs)]
    sentences = []
    for st in sa.sentences or []:
        if st.end_ms <= clip.start_ms or st.start_ms >= clip.end_ms:
            continue
        words = [w for w in st.words if inside((w.start_ms + w.end_ms) // 2)]
        if st.words and not words:
            continue
        if words:
            st = st.model_copy(update={"words": words, "start_ms": words[0].start_ms,
                                       "end_ms": words[-1].end_ms})
        sentences.append(st)
    out.sentences = sentences
    score = clip.score / 100.0 if clip.score > 1.0 else clip.score  # HighlightSeg.score 0..1
    out.highlights = [an.HighlightSeg(start_ms=a, end_ms=b, score=round(max(0.0, min(1.0, score)), 4),
                                      title=clip.title, clip_id=clip.id) for a, b in segs]
    out.emphasis_ms = [t for t in sa.emphasis_ms if inside(t)]
    out.speaker_changes_ms = [t for t in sa.speaker_changes_ms if inside(t)]
    return out


def _analyze_source(s: State, an, src: dict[str, Any], cache_dir: Path, job: Job,
                    on_progress: Callable[[float], None] | None = None) -> Any:
    kwargs: dict[str, Any] = {"cancel": job.cancel}
    if on_progress is not None and "on_progress" in inspect.signature(an.analyze_file).parameters:
        kwargs["on_progress"] = on_progress
    sa = an.analyze_file(Path(src["path"]), src["media_id"], cache_dir, s.settings, **kwargs)
    if src["kind"] == "file":
        return sa
    eid = src["episode_id"]
    sentences, clips, signals = _episode_context(s, eid)
    if src["kind"] == "clip":
        clip = next((c for c in clips if c.id == src["clip_id"]), None)
        if clip is None:  # rad etilgan bo'lsa ham manba sifatida tanlangan - to'g'ridan-to'g'ri o'qiymiz
            with s.project(eid) as conn:
                clip = db.get_clip(conn, eid, src["clip_id"])
        if clip is None:
            raise RuntimeError("klip topilmadi (o'chirilgan bo'lishi mumkin)")
        sa = _enrich(an, sa, sentences, [clip], signals)
        sa = restrict_to_clip(an, sa, clip)
        origin = f"clip:{eid}/{clip.id}"
    else:
        sa = _enrich(an, sa, sentences, clips, signals)
        origin = f"episode:{eid}"
    media = getattr(sa, "media", None)
    if media is not None and hasattr(media, "model_copy"):
        sa = copy.copy(sa)
        sa.media = media.model_copy(update={"origin": origin})
    return sa


# ---- Rejalashtirish vazifasi ---------------------------------------------------------

def submit_plan(s: State, mid: str, template: Template, sources: list[dict[str, Any]],
                overrides: dict[str, Any]) -> Job:
    try:
        from lahza_engine.montage import analyze as an
        from lahza_engine.montage import planner
    except ImportError as e:
        raise HTTPException(501, "avtomontaj bu versiyada mavjud emas") from e
    ov = _overrides(planner, overrides)
    cache_dir = montage_dir(s, mid) / "cache"
    name = s.lib("SELECT name FROM montages WHERE id = ?", (mid,))[0]["name"]

    def work(job: Job) -> dict[str, Any]:
        n = len(sources)
        try:
            cache_dir.mkdir(parents=True, exist_ok=True)
            analyses = []
            for i, src in enumerate(sources):
                if job.cancel.is_set():
                    raise Cancelled()
                s.jobs.progress(job, "analyze", 0.9 * i / n)

                def sub(f: float, i: int = i) -> None:
                    s.jobs.progress(job, "analyze", 0.9 * (i + max(0.0, min(1.0, f))) / n)

                analyses.append(_analyze_source(s, an, src, cache_dir, job, sub))
            if job.cancel.is_set():
                raise Cancelled()
            s.jobs.progress(job, "plan", 0.9)
            tl = planner.plan_montage(template, analyses, ov, s.settings)
            data = json.dumps(tl.to_json(), ensure_ascii=False)
            s.lib_write("UPDATE montages SET timeline_json = ?, duration_ms = ?, status = 'ready', error = NULL,"
                        " user_edited = 0, updated_at = datetime('now') WHERE id = ?",
                        (data, tl.duration_ms, mid))
            return {"montage_id": mid, "duration_ms": tl.duration_ms, "items": len(tl.video)}
        except Cancelled:
            _plan_failed(s, mid, "rejalashtirish bekor qilindi")
            raise
        except Exception as e:
            if job.cancel.is_set():  # masalan analyze.AnalysisCancelled
                _plan_failed(s, mid, "rejalashtirish bekor qilindi")
                raise Cancelled() from e
            _plan_failed(s, mid, str(e) or type(e).__name__)
            raise

    job = s.jobs.submit("montage", work, montage_id=mid, title=name)
    s.lib_write("UPDATE montages SET job_id = ? WHERE id = ?", (job.id, mid))
    return job


def _plan_failed(s: State, mid: str, msg: str) -> None:
    """Xato: avvalgi timeline bo'lsa u saqlanadi (status 'ready' + error), bo'lmasa 'failed'."""
    s.lib_write("UPDATE montages SET status = CASE WHEN timeline_json IS NULL THEN 'failed' ELSE 'ready' END,"
                " error = ?, updated_at = datetime('now') WHERE id = ?", (msg[:500], mid))


def _known_paths(r: sqlite3.Row, tl: MontageTimeline | None) -> set[str]:
    """Montajning mavjud media yo'llari (saqlangan timeline + manbalar)."""
    known = {m.path for m in tl.media.values()} if tl else set()
    known |= {x.get("path") for x in json.loads(r["sources_json"]) if x.get("path")}
    return known


def _draft_timeline(r: sqlite3.Row, saved: MontageTimeline | None, data: dict[str, Any]) -> MontageTimeline:
    """Preview uchun saqlanmagan draft: validatsiya, media faqat montajning mavjud fayllaridan."""
    try:
        tl = MontageTimeline.model_validate(data)
    except ValidationError as e:
        raise HTTPException(400, _validation_msg("timeline yaroqsiz", e)) from e
    known = _known_paths(r, saved)
    old = saved.media if saved else {}
    for m in tl.media.values():
        if m.path not in known:
            raise HTTPException(400, f"media '{m.id}': montajda yo'q fayl (avval media qo'shing)")
        if m.id in old and old[m.id].path != m.path:  # o'lcham/davomiylik boshqa faylniki bo'lib qoladi
            raise HTTPException(400, f"media '{m.id}': mavjud media yo'lini almashtirib bo'lmaydi")
    if tl.brand.logo_path and not Path(tl.brand.logo_path).is_file():
        raise HTTPException(400, "logotip fayli topilmadi")
    _check_plugins(_timeline_plugins(tl), "timeline")
    return tl


def _music_media_id(tl: MontageTimeline) -> str:
    if "music" not in tl.media:
        return "music"
    i = 2
    while f"music{i}" in tl.media:
        i += 1
    return f"music{i}"


# ---- Render --------------------------------------------------------------------------

def _needs_libass(tl: MontageTimeline) -> bool:
    return bool(tl.text) or (tl.captions.enabled and bool(tl.captions.words))


def _libass_preflight(tl: MontageTimeline, allow_no_subs: bool) -> None:
    if allow_no_subs or not _needs_libass(tl):
        return
    from lahza_engine.media.tools import ToolNotFound, find_tool

    try:
        from lahza_engine.render.capabilities import has_filter

        ff = find_tool("ffmpeg")
    except (ImportError, ToolNotFound):
        return  # ffmpeg yo'qligi vazifa ichida aniq xato bilan chiqadi
    if not has_filter(ff, "ass"):
        raise HTTPException(422, LIBASS_MONTAGE_MSG)


def _safe_filename(name: str) -> str:
    base = re.sub(r"[\\/:*?\"<>|\x00-\x1f]", "_", name).strip().strip(".") or "montaj"
    base = base[:120]
    return base if base.lower().endswith(".mp4") else base + ".mp4"


def _unique_path(p: Path) -> Path:
    if not p.exists():
        return p
    for i in range(2, 1000):
        q = p.with_name(f"{p.stem}_{i}{p.suffix}")
        if not q.exists():
            return q
    return p.with_name(f"{p.stem}_{uuid.uuid4().hex[:6]}{p.suffix}")


def submit_render(s: State, mid: str, body: RenderIn, retry_of: str | None = None) -> Job:
    r = _row(s, mid)
    tl = _timeline(r)
    if r["status"] == "planning" or tl is None:
        raise HTTPException(409, "montaj hali tayyor emas")
    if not tl.video:
        raise HTTPException(409, "montajda video elementlar yo'q")
    try:
        from lahza_engine.render import montage_render
    except ImportError as e:
        raise HTTPException(501, "montaj render bu versiyada mavjud emas") from e
    _libass_preflight(tl, body.allow_no_subs)
    out_dir = Path(body.out_dir).expanduser()
    if not out_dir.is_dir() and not out_dir.parent.is_dir():
        raise HTTPException(400, "papka topilmadi")
    export_id = uuid.uuid4().hex[:12]
    s.lib_write("INSERT INTO montage_exports(id, montage_id, status) VALUES (?, ?, 'queued')", (export_id, mid))
    filename = _safe_filename(body.filename or r["name"])

    def work(job: Job) -> dict[str, Any]:
        from lahza_engine.media.tools import find_tool
        from lahza_engine.models.hardware import detect as hw_detect
        from lahza_engine.render.encoders import choose_encoder

        workdir = montage_dir(s, mid) / "work" / job.id
        s.lib_write("UPDATE montage_exports SET status = 'running' WHERE id = ?", (export_id,))
        try:
            out_dir.mkdir(parents=True, exist_ok=True)
            workdir.mkdir(parents=True, exist_ok=True)
            out = _unique_path(out_dir / filename)
            gpu = hw_detect().best_gpu()
            enc = choose_encoder(find_tool("ffmpeg"), gpu.vendor if gpu else None,
                                 s.settings.render.video_bitrate_kbps,
                                 allow_dev_fallback=os.environ.get("LAHZA_DEV") == "1")
            res = montage_render.render_montage(
                tl, out, workdir, enc, s.settings, detector=s.services().face_detector,
                allow_no_subs=body.allow_no_subs,
                on_progress=lambda f: s.jobs.progress(job, "render", max(0.0, min(1.0, f))),
                cancel=job.cancel)
            s.lib_write("UPDATE montage_exports SET status = 'done', path = ?, finished_at = datetime('now')"
                        " WHERE id = ?", (str(res.video), export_id))
            return {"video": str(res.video), "edl": str(res.edl) if res.edl else None,
                    "srt": str(res.srt) if res.srt else None, "warnings": list(res.warnings or []),
                    "encoder": enc.name, "export_id": export_id, "montage_id": mid}
        except Cancelled:
            _export_done(s, export_id, "cancelled", None)
            raise
        except Exception as e:
            _export_done(s, export_id, "failed", f"{type(e).__name__}: {str(e)[:300]}")
            if type(e).__name__ == "LibassMissing":
                raise RuntimeError(LIBASS_MONTAGE_MSG) from e
            raise
        finally:
            shutil.rmtree(workdir, ignore_errors=True)

    meta: dict[str, Any] = {"montage_id": mid, "title": r["name"], "export_id": export_id}
    if retry_of:
        meta["retry_of"] = retry_of
    job = s.jobs.submit("export", work, **meta)
    s.lib_write("UPDATE montage_exports SET job_id = ? WHERE id = ?", (job.id, export_id))
    s.montage_export_params[job.id] = (mid, body)
    return job


def _export_done(s: State, export_id: str, status: str, error: str | None) -> None:
    s.lib_write("UPDATE montage_exports SET status = ?, error = ?, finished_at = datetime('now') WHERE id = ?",
                (status, error, export_id))


def retry_render(s: State, job: Job) -> Job:
    """`/v1/jobs/{id}:retry` uchun: montaj eksportini xuddi shu parametrlar bilan qayta yuborish."""
    params = s.montage_export_params.get(job.id)
    if params is None:
        raise HTTPException(409, "vazifa parametrlari topilmadi")
    mid, body = params
    return submit_render(s, mid, body, retry_of=job.id)


# ---- Endpointlar -----------------------------------------------------------------------

def register(app: FastAPI, auth: Callable[..., State]) -> None:
    # ---- Plaginlar ------------------------------------------------------------------
    @app.get("/v1/fx")
    def fx(kind: str | None = Query(None), s: State = Depends(auth)) -> list[dict[str, Any]]:
        reg = _fx_registry()
        if reg is None:
            raise HTTPException(501, "plaginlar reestri bu versiyada mavjud emas")
        return [m.model_dump(mode="json", by_alias=True) for m in reg.list_plugins(kind)]

    # ---- Shablonlar -----------------------------------------------------------------
    @app.get("/v1/templates")
    def templates(s: State = Depends(auth)) -> list[dict[str, Any]]:
        return [_tpl_out(t) for t in [*_builtin_templates(), *_user_templates(s)]]

    @app.get("/v1/templates/{tid}")
    def get_template(tid: str, s: State = Depends(auth)) -> dict[str, Any]:
        return _tpl_out(find_template(s, tid))

    @app.post("/v1/templates")
    def create_template(body: JsonBody, s: State = Depends(auth)) -> dict[str, Any]:
        data = dict(body)
        data["id"] = _user_id_for(s, data.get("id") if isinstance(data.get("id"), str) else None)
        data["builtin"] = False
        return _tpl_out(_insert_user_template(s, _validate_template(data)))

    @app.put("/v1/templates/{tid}")
    def update_template(tid: str, body: JsonBody, s: State = Depends(auth)) -> dict[str, Any]:
        if tid in _builtin_ids():
            raise HTTPException(409, "o'rnatilgan shablonni o'zgartirib bo'lmaydi - nusxa oling")
        if not s.lib("SELECT 1 FROM user_templates WHERE id = ?", (tid,)):
            raise HTTPException(404, "shablon topilmadi")
        t = _validate_template({**body, "id": tid, "builtin": False})
        s.lib_write("UPDATE user_templates SET json = ?, updated_at = datetime('now') WHERE id = ?",
                    (json.dumps(t.to_json(), ensure_ascii=False), tid))
        return _tpl_out(t)

    @app.delete("/v1/templates/{tid}")
    def delete_template(tid: str, s: State = Depends(auth)) -> dict[str, Any]:
        if tid in _builtin_ids():
            raise HTTPException(409, "o'rnatilgan shablonni o'chirib bo'lmaydi")
        if s.lib_write("DELETE FROM user_templates WHERE id = ?", (tid,)).rowcount == 0:
            raise HTTPException(404, "shablon topilmadi")
        return {"ok": True}

    @app.post("/v1/templates/{tid}:duplicate")
    def duplicate_template(tid: str, body: DuplicateIn | None = None,
                           s: State = Depends(auth)) -> dict[str, Any]:
        src = find_template(s, tid)
        new_name = (body.name or "").strip() if body else ""
        name = LocalText(uz=new_name) if new_name else src.name.model_copy(update={"uz": f"{src.name.uz} (nusxa)"})
        t = src.model_copy(update={"id": _new_user_id(), "builtin": False, "name": name})
        return _tpl_out(_insert_user_template(s, t))

    @app.post("/v1/templates:import")
    def import_template(body: PathIn, s: State = Depends(auth)) -> dict[str, Any]:
        p = Path(body.path).expanduser()
        if not p.is_file() or p.suffix.lower() != ".json":
            raise HTTPException(400, "JSON fayl topilmadi")
        if p.stat().st_size > MAX_TEMPLATE_FILE:
            raise HTTPException(400, "fayl juda katta (1 MB dan oshmasligi kerak)")
        try:
            from lahza_engine.templates.store import TemplateError, load_template_file
        except ImportError:
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
            except (ValueError, UnicodeDecodeError) as e:
                raise HTTPException(400, "shablon fayli yaroqsiz: JSON o'qilmadi") from e
            t = _validate_template(data)
        else:
            try:
                t = load_template_file(p)
            except TemplateError as e:
                raise HTTPException(400, str(e) or "shablon fayli yaroqsiz") from e
            except (ValueError, UnicodeDecodeError) as e:
                raise HTTPException(400, "shablon fayli yaroqsiz") from e
        t = t.model_copy(update={"id": _user_id_for(s, t.id), "builtin": False})
        return _tpl_out(_insert_user_template(s, t))

    @app.post("/v1/templates/{tid}:export")
    def export_template(tid: str, body: PathIn, s: State = Depends(auth)) -> dict[str, Any]:
        t = find_template(s, tid)
        p = Path(body.path).expanduser()
        if p.suffix.lower() != ".json":
            p = p.with_suffix(".json")
        if not p.parent.is_dir():
            raise HTTPException(400, "papka topilmadi")
        try:
            from lahza_engine.templates.store import save_template_file
        except ImportError:
            p.write_text(json.dumps(t.to_json(), ensure_ascii=False, indent=2), encoding="utf-8")
        else:
            save_template_file(t, p)
        return {"ok": True}

    # ---- Montajlar ------------------------------------------------------------------
    @app.get("/v1/montages")
    def montages(project_id: str | None = Query(None), s: State = Depends(auth)) -> list[dict[str, Any]]:
        if project_id:
            rows = s.lib("SELECT * FROM montages WHERE project_id = ? ORDER BY created_at DESC, rowid DESC",
                         (project_id,))
        else:
            rows = s.lib("SELECT * FROM montages ORDER BY created_at DESC, rowid DESC")
        return [_summary(_heal(s, r)) for r in rows]

    @app.post("/v1/montages")
    def create_montage(body: MontageIn, s: State = Depends(auth)) -> dict[str, Any]:
        tpl = find_template(s, body.template_id)
        if body.project_id and not s.lib("SELECT 1 FROM shows WHERE id = ?", (body.project_id,)):
            raise HTTPException(404, "loyiha topilmadi")
        sources = _resolve_sources(s, body.sources)
        _check_override_paths(body.overrides)
        overrides = body.overrides.model_dump(mode="json", exclude_none=True) if body.overrides else {}
        name = (body.name or "").strip() or f"{tpl.name.uz} montaji"
        mid = uuid.uuid4().hex[:12]
        s.lib_write("INSERT INTO montages(id, project_id, name, template_id, sources_json, overrides_json, status)"
                    " VALUES (?,?,?,?,?,?, 'planning')",
                    (mid, body.project_id, name, tpl.id, json.dumps(sources, ensure_ascii=False),
                     json.dumps(overrides, ensure_ascii=False)))
        try:
            job = submit_plan(s, mid, tpl, sources, overrides)
        except HTTPException:
            s.lib_write("DELETE FROM montages WHERE id = ?", (mid,))
            raise
        return {"montage_id": mid, "job": job.public()}

    @app.get("/v1/montages/{mid}")
    def get_montage(mid: str, s: State = Depends(auth)) -> dict[str, Any]:
        return _detail(s, _row(s, mid))

    @app.put("/v1/montages/{mid}/timeline")
    def put_timeline(mid: str, body: JsonBody, s: State = Depends(auth)) -> dict[str, Any]:
        r = _row(s, mid)
        if r["status"] == "planning":
            raise HTTPException(409, "montaj hozir rejalashtirilmoqda")
        try:
            tl = MontageTimeline.model_validate(body)
        except ValidationError as e:
            raise HTTPException(400, _validation_msg("timeline yaroqsiz", e)) from e
        known = _known_paths(r, _timeline(r))
        for m in tl.media.values():
            if m.path not in known and not Path(m.path).is_file():
                raise HTTPException(400, f"media '{m.id}': fayl topilmadi")
        if tl.brand.logo_path and not Path(tl.brand.logo_path).is_file():
            raise HTTPException(400, "logotip fayli topilmadi")
        _check_plugins(_timeline_plugins(tl), "timeline")
        s.lib_write("UPDATE montages SET timeline_json = ?, duration_ms = ?, user_edited = 1, status = 'ready',"
                    " error = NULL, updated_at = datetime('now') WHERE id = ?",
                    (json.dumps(tl.to_json(), ensure_ascii=False), tl.duration_ms, mid))
        return {"ok": True, "timeline": tl.to_json()}

    @app.post("/v1/montages/{mid}:replan")
    def replan(mid: str, body: ReplanIn | None = None, s: State = Depends(auth)) -> dict[str, Any]:
        body = body or ReplanIn()
        r = _row(s, mid)
        if r["status"] == "planning":
            raise HTTPException(409, "montaj hozir rejalashtirilmoqda")
        tl = _timeline(r)
        edited = bool(r["user_edited"]) or bool(tl and any(it.user_edited for it in tl.video))
        if edited and not body.force:
            raise HTTPException(409, "montaj qo'lda tahrirlangan: qayta reja tahrirlarni almashtiradi "
                                     "(davom etish uchun force=true)")
        tpl = find_template(s, body.template_id or r["template_id"])
        _check_override_paths(body.overrides)
        overrides = (body.overrides.model_dump(mode="json", exclude_none=True) if body.overrides
                     else json.loads(r["overrides_json"] or "{}"))
        sources = json.loads(r["sources_json"])
        for src in sources:
            if not Path(src["path"]).is_file():
                raise HTTPException(400, f"manba fayli topilmadi: {Path(src['path']).name}")
        s.lib_write("UPDATE montages SET template_id = ?, overrides_json = ?, status = 'planning', error = NULL,"
                    " updated_at = datetime('now') WHERE id = ?",
                    (tpl.id, json.dumps(overrides, ensure_ascii=False), mid))
        try:
            job = submit_plan(s, mid, tpl, sources, overrides)
        except HTTPException:
            _plan_failed(s, mid, "avtomontaj mavjud emas")
            raise
        return job.public()

    @app.post("/v1/montages/{mid}:preview")
    def preview(mid: str, body: PreviewIn | None = None, s: State = Depends(auth)) -> Response:
        body = body or PreviewIn()
        r = _row(s, mid)
        tl = _timeline(r)
        if tl is None:
            raise HTTPException(409, "montaj hali tayyor emas")
        if body.timeline is not None:
            tl = _draft_timeline(r, tl, body.timeline)
        if not tl.video:
            raise HTTPException(409, "montajda video elementlar yo'q")
        try:
            from lahza_engine.render.montage_render import render_montage_frame
        except ImportError as e:
            raise HTTPException(501, "kadr ko'rinishi bu versiyada mavjud emas") from e
        t = min(body.t_ms, max(0, tl.duration_ms - 1))
        out = montage_dir(s, mid) / "work" / "preview" / f"{uuid.uuid4().hex[:10]}.jpg"
        out.parent.mkdir(parents=True, exist_ok=True)
        try:
            res = render_montage_frame(tl, t, out, s.settings, detector=s.services().face_detector)
            data = Path(res or out).read_bytes()
        except (RuntimeError, OSError) as e:  # ffmpeg xatosi - aniq 500 (ulanish uzilmaydi)
            raise HTTPException(500, f"kadr chizilmadi: {str(e)[:300]}") from e
        finally:
            out.unlink(missing_ok=True)
        return Response(content=data, media_type="image/jpeg")

    @app.post("/v1/montages/{mid}/media")
    def add_media(mid: str, body: MediaIn, s: State = Depends(auth)) -> dict[str, Any]:
        """Muharrirdan musiqa qo'shish: fayl tekshiriladi va saqlangan timeline `media` lug'atiga qo'shiladi."""
        r = _row(s, mid)
        if r["status"] == "planning":
            raise HTTPException(409, "montaj hozir rejalashtirilmoqda")
        tl = _timeline(r)
        if tl is None:
            raise HTTPException(409, "montaj hali tayyor emas")
        p = Path(body.path).expanduser()
        if not p.is_file():
            raise HTTPException(400, "musiqa fayli topilmadi")
        from lahza_engine.media.probe import MediaError, fast_hash
        from lahza_engine.media.tools import ToolNotFound
        from lahza_engine.montage.analyze import probe_media

        try:
            info = probe_media(p)
        except ToolNotFound as e:
            raise HTTPException(500, str(e)) from e
        except (MediaError, OSError, ValueError) as e:
            raise HTTPException(400, f"musiqa faylini o'qib bo'lmadi: {e}") from e
        if not info.has_audio:
            raise HTTPException(400, "musiqa faylida ovoz yo'q")
        if info.duration_ms <= 0:
            raise HTTPException(400, "musiqa faylining davomiyligi noma'lum")
        path = str(p.resolve())
        same = next((m for m in tl.media.values() if m.path == path and m.id.startswith("music")), None)
        ref = same or MediaRef(id=_music_media_id(tl), path=path, hash=fast_hash(path),
                               duration_ms=info.duration_ms, width=0, height=0, fps=0.0, has_audio=True,
                               origin="file")
        if same is None:
            tl.media[ref.id] = ref
            s.lib_write("UPDATE montages SET timeline_json = ?, user_edited = 1, updated_at = datetime('now')"
                        " WHERE id = ?", (json.dumps(tl.to_json(), ensure_ascii=False), mid))
        return {"media": ref.model_dump(mode="json")}

    @app.post("/v1/montages/{mid}:render")
    def render(mid: str, body: RenderIn, s: State = Depends(auth)) -> dict[str, Any]:
        return submit_render(s, mid, body).public()

    @app.get("/v1/montages/{mid}/sources/{media_id}/thumb")
    def thumb(mid: str, media_id: str, t_ms: int = Query(0, ge=0), s: State = Depends(auth)) -> Response:
        r = _row(s, mid)
        tl = _timeline(r)
        path: str | None = None
        dur: int | None = None
        if tl and media_id in tl.media:
            path, dur = tl.media[media_id].path, tl.media[media_id].duration_ms
        else:
            path = next((x.get("path") for x in json.loads(r["sources_json"]) if x.get("media_id") == media_id),
                        None)
        if path is None:
            raise HTTPException(404, "manba topilmadi")
        if not Path(path).is_file():
            raise HTTPException(404, "manba fayli topilmadi")
        if dur:
            t_ms = min(t_ms, max(0, dur - 100))
        out = montage_dir(s, mid) / "thumbs" / f"{media_id}-{t_ms}.jpg"
        if not out.exists():
            from lahza_engine.media.tools import ToolNotFound, find_tool, run

            try:
                ff = find_tool("ffmpeg")
            except ToolNotFound as e:
                raise HTTPException(500, str(e)) from e
            out.parent.mkdir(parents=True, exist_ok=True)
            tmp = out.with_name(f".{uuid.uuid4().hex[:8]}.jpg")
            res = run([ff, "-hide_banner", "-loglevel", "error", "-ss", f"{t_ms / 1000:.3f}", "-i", path,
                       "-frames:v", "1", "-vf", "scale=320:-2", "-q:v", "5", "-y", tmp], timeout=60)
            if res.returncode != 0 or not tmp.exists():
                tmp.unlink(missing_ok=True)
                raise HTTPException(500, "kadr olinmadi")
            tmp.replace(out)
        return Response(content=out.read_bytes(), media_type="image/jpeg")

    @app.delete("/v1/montages/{mid}")
    def delete_montage(mid: str, s: State = Depends(auth)) -> dict[str, Any]:
        r = _row(s, mid)
        job = s.jobs.jobs.get(r["job_id"]) if r["job_id"] else None
        if job is not None and job.status in ("queued", "running"):
            s.jobs.cancel(job.id)
        s.lib_write("DELETE FROM montages WHERE id = ?", (mid,))
        shutil.rmtree(montage_dir(s, mid), ignore_errors=True)
        return {"ok": True}
