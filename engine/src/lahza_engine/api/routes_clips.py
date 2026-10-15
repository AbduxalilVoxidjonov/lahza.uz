"""Kliplar: ro'yxat, tahrir, qo'lda yaratish, matn orqali montaj (cuts), kalit kadrlar, preview,
o'xshash nomzodlar, eksport, eksportlar ro'yxati va qayta urinish."""

from __future__ import annotations

import inspect
import json
import os
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any, Literal

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field

from lahza_engine.api.state import State
from lahza_engine.core.jobs import Job
from lahza_engine.core.runner import Cancelled
from lahza_engine.db import store as db
from lahza_engine.subtitle.style import StyleTemplate
from lahza_engine.text.orthography import Orthography
from lahza_engine.timeline import Timeline
from lahza_engine.types import Clip, ClipSource, ClipStatus, Sentence

MIN_CLIP_AFTER_CUTS_MS = 1000
MAX_SIMILAR = 3


class ClipPatchIn(BaseModel):
    start_ms: int | None = None
    end_ms: int | None = None
    title: str | None = None
    caption: str | None = None
    hashtags: list[str] | None = None
    status: ClipStatus | None = None  # noto'g'ri qiymat - 422 (avval bazada CHECK -> 500 edi)


class ClipCreateIn(BaseModel):
    start_sentence_id: int
    end_sentence_id: int
    title: str | None = None


class CutsIn(BaseModel):
    cuts: list[tuple[int, int]]


class KeyframeIn(BaseModel):
    t_ms: int = Field(ge=0)
    layout: Literal["focus", "split", "fit_blur", "manual"]
    cx: float | None = Field(None, ge=0, le=1)
    cy: float | None = Field(None, ge=0, le=1)
    zoom: float = Field(1.0, ge=0.5, le=4.0)
    lane: Literal["a", "b"] = "a"
    source: str | None = None  # e'tiborsiz: doim 'qolda' saqlanadi


class KeyframesIn(BaseModel):
    keyframes: list[KeyframeIn]


class PreviewIn(BaseModel):
    t_ms: int = Field(ge=0)
    style: StyleTemplate = StyleTemplate()
    orthography: Orthography | None = None


class ExportIn(BaseModel):
    out_dir: str
    style: StyleTemplate = StyleTemplate()
    orthography: Orthography | None = None
    filename_template: str | None = None
    allow_no_subs: bool = False  # libass yo'q bo'lsa subtitrsiz eksport (SRT/VTT baribir yoziladi)
    platform: str = "instagram_reels"


LIBASS_MSG = ("FFmpeg libass'siz yig'ilgan: subtitrni videoga chizib bo'lmaydi. Dastur bilan kelgan "
              "FFmpeg'dan foydalaning yoki subtitrsiz eksportni tanlang (allow_no_subs=true).")


def _libass_preflight(body: ExportIn) -> None:
    """libass yo'q va subtitrsiz eksportga ruxsat berilmagan bo'lsa - 422 (vazifa yaratilmaydi)."""
    if body.allow_no_subs:
        return
    from lahza_engine.media.tools import ToolNotFound, find_tool

    try:
        from lahza_engine.render.capabilities import has_filter

        ff = find_tool("ffmpeg")
    except (ImportError, ToolNotFound):
        return  # ffmpeg yo'qligi vazifa ichida aniq xato bilan chiqadi
    if not has_filter(ff, "ass"):
        raise HTTPException(422, LIBASS_MSG)


# ---- Yordamchilar ------------------------------------------------------------

def _clip_or_404(conn, eid: str, cid: str) -> Clip:
    clip = db.get_clip(conn, eid, cid)
    if clip is None:
        raise HTTPException(404, "klip topilmadi")
    return clip


def normalize_cuts(clip: Clip, sentences: list[Sentence], cuts: list[tuple[int, int]]
                   ) -> list[tuple[int, int]]:
    """Validatsiya: klip ichida, a < b; so'z chegarasiga snap; saralash va birlashtirish."""
    words = [w for s in sentences for w in s.words
             if w.end_ms > clip.start_ms and w.start_ms < clip.end_ms]
    out: list[tuple[int, int]] = []
    for a, b in cuts:
        if b <= a:
            raise HTTPException(400, "kesim boshi oxiridan kichik bo'lishi kerak")
        if a < clip.start_ms or b > clip.end_ms:
            raise HTTPException(400, "kesim klip chegarasi ichida bo'lishi kerak")
        for w in words:  # so'z o'rtasidan kesilmaydi: butun so'z olib tashlanadi
            if w.start_ms < a < w.end_ms:
                a = w.start_ms
            if w.start_ms < b < w.end_ms:
                b = w.end_ms
        a, b = max(a, clip.start_ms), min(b, clip.end_ms)
        if b > a:
            out.append((a, b))
    out.sort()
    merged: list[tuple[int, int]] = []
    for a, b in out:
        if merged and a <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], b))
        else:
            merged.append((a, b))
    return merged


def _signals(conn, pdir: Path, eid: str, sentences: list[Sentence]):
    """Highlight signallari: keshdan (signals bosqichi), bo'lmasa qayta hisoblash."""
    from lahza_engine.highlight.signals import SentenceSignals, SignalReport, compute_signals

    row = conn.execute("SELECT status, result_path FROM stage_runs WHERE media_id = ? AND stage = ?",
                       (eid, "signals")).fetchone()
    if row and row["status"] == "done" and row["result_path"] and Path(row["result_path"]).exists():
        data = json.loads(Path(row["result_path"]).read_text(encoding="utf-8"))
        rep = SignalReport([SentenceSignals(**d) for d in data["sentences"]])
        if {x.sentence_id for x in rep.sentences} >= {s.id for s in sentences}:
            return rep
    wav = pdir / "cache" / "audio16k.wav"
    pcm, sr = None, 16_000
    if wav.exists():
        from lahza_engine.media.probe import read_wav_mono

        pcm, sr = read_wav_mono(wav)
    return compute_signals(sentences, pcm, sr)


def similar_candidates(clip: Clip, existing: list[Clip], sentences: list[Sentence], signals,
                       cfg) -> list[Clip]:
    """Lite nomzodlardan: mavjud kliplar bilan ustma-ust tushmaydigan, signal bali va
    davomiyligi berilgan klipga eng yaqin <= 3 ta."""
    from lahza_engine.highlight.boundaries import ClipSpan
    from lahza_engine.highlight.finder import (
        Scored,
        _first_strong_sentence,
        _penalty,
        _signal_score,
        iou,
        lite_candidates,
    )

    pos = {s.id: i for i, s in enumerate(sentences)}
    if clip.start_sentence_id not in pos or clip.end_sentence_id not in pos:
        return []
    target_span = ClipSpan(pos[clip.start_sentence_id], pos[clip.end_sentence_id],
                           clip.start_ms, clip.end_ms)
    target = _signal_score(target_span, signals)
    scored = []
    for span in lite_candidates(sentences, cfg):
        if any(span.start_ms < c.end_ms and c.start_ms < span.end_ms for c in existing):
            continue
        sig = _signal_score(span, signals)
        pen, reasons = _penalty(span, sentences, cfg)
        scored.append(Scored(span, max(0.0, min(100.0, sig - 30.0 * pen)), {"signal": sig}, reasons))
    # O'xshashlik bo'yicha saralab, bir-biri bilan ham ustma-ust tushmaydiganlarini olamiz.
    scored.sort(key=lambda x: abs(x.score - target) + abs(x.span.duration_ms - clip.duration_ms) / 10_000)
    pool: list[Scored] = []
    for cand in scored:
        if all(iou(cand.span, q.span) == 0.0 for q in pool):
            pool.append(cand)
        if len(pool) >= MAX_SIMILAR:
            break
    out = []
    for p in pool[:MAX_SIMILAR]:
        out.append(Clip(
            id=uuid.uuid4().hex[:12], media_id=clip.media_id, start_ms=p.span.start_ms,
            end_ms=p.span.end_ms, start_sentence_id=sentences[p.span.start_id].id,
            end_sentence_id=sentences[p.span.end_id].id,
            title=_first_strong_sentence(p.span, sentences, signals), score=round(p.score, 1),
            scores={k: round(v, 1) for k, v in p.parts.items()},
            reason=f"O'xshash nomzod ('{clip.title[:40]}' kabi)"
            + ("; " + "; ".join(p.reasons) if p.reasons else ""),
            source=ClipSource.AI_LITE,
        ))
    return out


def submit_export(s: State, eid: str, cid: str, body: ExportIn, retry_of: str | None = None) -> Job:
    from lahza_engine.core.export import export_clip

    pdir = s.episode_dir(eid)
    ep = s.episode_row(eid)
    show = s.lib("SELECT name FROM shows WHERE id = ?", (ep["show_id"],))
    show_name = show[0]["name"] if show else "lahza"
    with s.project(eid) as conn:
        clip = _clip_or_404(conn, eid, cid)
        export_id = uuid.uuid4().hex[:12]
        db.record_export(conn, export_id, cid, "", body.model_dump(mode="json"))
    style = body.style
    if body.orthography:
        style = style.model_copy(update={"orthography": body.orthography})

    def work(job: Job) -> dict[str, Any]:
        from lahza_engine.media.tools import find_tool
        from lahza_engine.models.hardware import detect as hw_detect
        from lahza_engine.render.encoders import choose_encoder

        conn = db.open_project(pdir)
        try:
            db.finish_export(conn, export_id, "running")
            clips = db.load_clips(conn, eid)
            c = next((x for x in clips if x.id == cid), None)
            if c is None:
                raise KeyError("klip topilmadi")
            index = clips.index(c) + 1  # klip tartibi (vaqt bo'yicha)
            gpu = hw_detect().best_gpu()
            enc = choose_encoder(find_tool("ffmpeg"), gpu.vendor if gpu else None,
                                 s.settings.render.video_bitrate_kbps,
                                 allow_dev_fallback=os.environ.get("LAHZA_DEV") == "1")
            kwargs: dict[str, Any] = {"detector": s.services().face_detector,
                                      "show_name": show_name, "episode": ep["title"], "index": index}
            params = inspect.signature(export_clip).parameters
            if body.filename_template and "filename_template" in params:
                kwargs["filename_template"] = body.filename_template
            if "allow_no_subs" in params:
                kwargs["allow_no_subs"] = body.allow_no_subs
            if "platform" in params:
                kwargs["platform"] = body.platform
            res = export_clip(conn, eid, c, Path(body.out_dir), pdir / "work" / f"{cid}-{job.id}",
                              s.settings, enc, style, **kwargs)
            db.finish_export(conn, export_id, "done", path=str(res.video))
            return {"video": str(res.video), "srt": str(res.srt), "caption": str(res.caption),
                    "cover": str(res.cover) if res.cover else None, "encoder": enc.name,
                    "vtt": str(res.vtt) if getattr(res, "vtt", None) else None,
                    "warnings": list(getattr(res, "warnings", []) or []), "export_id": export_id}
        except Cancelled:
            db.finish_export(conn, export_id, "cancelled")
            raise
        except Exception as e:
            db.finish_export(conn, export_id, "failed", error=f"{type(e).__name__}: {str(e)[:300]}")
            if type(e).__name__ == "LibassMissing":
                raise RuntimeError(LIBASS_MSG) from e
            raise
        finally:
            conn.close()

    meta: dict[str, Any] = {"episode_id": eid, "clip_id": cid, "title": clip.title,
                            "export_id": export_id}
    if retry_of:
        meta["retry_of"] = retry_of
    job = s.jobs.submit("export", work, **meta)
    with s.project(eid) as conn, conn:
        conn.execute("UPDATE exports SET job_id = ? WHERE id = ?", (job.id, export_id))
    s.export_params[job.id] = (eid, cid, body)
    return job


# ---- Endpointlar ---------------------------------------------------------------

def register(app: FastAPI, auth: Callable[..., State]) -> None:
    @app.get("/v1/episodes/{eid}/clips")
    def clips(eid: str, s: State = Depends(auth)) -> list[dict[str, Any]]:
        with s.project(eid) as conn:
            return [c.model_dump(mode="json") for c in db.load_clips(conn, eid)]

    @app.post("/v1/episodes/{eid}/clips")
    def create_clip(eid: str, body: ClipCreateIn, s: State = Depends(auth)) -> dict[str, Any]:
        from lahza_engine.highlight.boundaries import snap

        cfg = s.settings.highlight
        with s.project(eid) as conn:
            sentences = db.load_transcript(conn, eid).sentences
            if not sentences:
                raise HTTPException(409, "transkript hali tayyor emas")
            pos = {x.id: i for i, x in enumerate(sentences)}
            if body.start_sentence_id not in pos or body.end_sentence_id not in pos:
                raise HTTPException(404, "gap topilmadi")
            a, b = pos[body.start_sentence_id], pos[body.end_sentence_id]
            if b < a:
                raise HTTPException(400, "boshlanish gapi tugash gapidan oldin bo'lishi kerak")
            # Qo'lda tanlov: boshlanishni pauzaga surmaymiz, minimal davomiylik majburiy emas.
            span = snap(sentences, a, b, cfg.model_copy(update={"min_pause_before_start_ms": 0}),
                        min_ms=0, max_ms=cfg.hard_max_ms)
            title = (body.title or "").strip() or sentences[span.start_id].text[:80].strip()
            clip = Clip(id=uuid.uuid4().hex[:12], media_id=eid, start_ms=span.start_ms,
                        end_ms=span.end_ms, start_sentence_id=sentences[span.start_id].id,
                        end_sentence_id=sentences[span.end_id].id, title=title,
                        reason="Qo'lda yaratilgan", status=ClipStatus.CANDIDATE,
                        source=ClipSource.MANUAL)
            db.insert_manual_clip(conn, clip)
            return clip.model_dump(mode="json")

    @app.patch("/v1/episodes/{eid}/clips/{cid}")
    def patch_clip(eid: str, cid: str, body: ClipPatchIn, s: State = Depends(auth)) -> dict[str, Any]:
        with s.project(eid) as conn:
            clip = _clip_or_404(conn, eid, cid)
            start = clip.start_ms if body.start_ms is None else body.start_ms
            end = clip.end_ms if body.end_ms is None else body.end_ms
            if start < 0 or end <= start:
                raise HTTPException(400, "klip boshi oxiridan kichik bo'lishi kerak")
            db.update_clip(conn, cid, **body.model_dump(mode="json"))
        return {"ok": True}

    @app.put("/v1/episodes/{eid}/clips/{cid}/cuts")
    def put_cuts(eid: str, cid: str, body: CutsIn, s: State = Depends(auth)) -> dict[str, Any]:
        with s.project(eid) as conn:
            clip = _clip_or_404(conn, eid, cid)
            sentences = db.load_transcript(conn, eid).sentences
            cuts = normalize_cuts(clip, sentences, [tuple(c) for c in body.cuts])
            if Timeline(clip.start_ms, clip.end_ms, cuts).duration_ms < MIN_CLIP_AFTER_CUTS_MS:
                raise HTTPException(400, "klipning deyarli hammasi kesib tashlandi")
            db.set_cuts(conn, cid, cuts)
            return _clip_or_404(conn, eid, cid).model_dump(mode="json")

    @app.get("/v1/episodes/{eid}/clips/{cid}/keyframes")
    def get_keyframes(eid: str, cid: str, s: State = Depends(auth)) -> list[dict[str, Any]]:
        with s.project(eid) as conn:
            _clip_or_404(conn, eid, cid)
            return db.load_keyframes(conn, cid)

    @app.put("/v1/episodes/{eid}/clips/{cid}/keyframes")
    def put_keyframes(eid: str, cid: str, body: KeyframesIn, s: State = Depends(auth)) -> dict[str, Any]:
        with s.project(eid) as conn:
            clip = _clip_or_404(conn, eid, cid)
            dur = Timeline(clip.start_ms, clip.end_ms, clip.cuts).duration_ms
            if any(k.t_ms > dur for k in body.keyframes):
                raise HTTPException(400, "kalit kadr vaqti klip davomiyligidan oshmasligi kerak")
            seen = set()
            for k in body.keyframes:
                if (k.lane, k.t_ms) in seen:
                    raise HTTPException(400, "bir yo'lakda bir vaqtda ikkita kalit kadr")
                seen.add((k.lane, k.t_ms))
            db.save_manual_keyframes(conn, cid, [k.model_dump() for k in body.keyframes])
        return {"ok": True}

    @app.post("/v1/episodes/{eid}/clips/{cid}:preview")
    def preview(eid: str, cid: str, body: PreviewIn, s: State = Depends(auth)) -> Response:
        try:
            from lahza_engine.core.export import render_preview_frame
        except ImportError as e:
            raise HTTPException(501, "kadr ko'rinishi bu versiyada mavjud emas") from e
        pdir = s.episode_dir(eid)
        style = body.style
        if body.orthography:
            style = style.model_copy(update={"orthography": body.orthography})
        out = pdir / "work" / "preview" / f"{cid}-{uuid.uuid4().hex[:8]}.jpg"
        out.parent.mkdir(parents=True, exist_ok=True)
        with s.project(eid) as conn:
            clip = _clip_or_404(conn, eid, cid)
            dur = Timeline(clip.start_ms, clip.end_ms, clip.cuts).duration_ms
            t = min(body.t_ms, max(0, dur - 1))
            try:
                render_preview_frame(conn, eid, clip, t, style, s.settings, out,
                                     detector=s.services().face_detector)
                data = out.read_bytes()
            finally:
                out.unlink(missing_ok=True)
        return Response(content=data, media_type="image/jpeg")

    @app.post("/v1/episodes/{eid}/clips/{cid}:similar")
    def similar(eid: str, cid: str, s: State = Depends(auth)) -> list[dict[str, Any]]:
        pdir = s.episode_dir(eid)
        with s.project(eid) as conn:
            clip = _clip_or_404(conn, eid, cid)
            sentences = db.load_transcript(conn, eid).sentences
            existing = [c for c in db.load_clips(conn, eid) if c.status != ClipStatus.REJECTED]
            signals = _signals(conn, pdir, eid, sentences)
            found = similar_candidates(clip, existing, sentences, signals, s.settings.highlight)
            if found:
                db.save_clips(conn, found, replace_ai=False)
        return [c.model_dump(mode="json") for c in found]

    @app.post("/v1/episodes/{eid}/clips/{cid}:export")
    def export(eid: str, cid: str, body: ExportIn, s: State = Depends(auth)) -> dict[str, Any]:
        with s.project(eid) as conn:
            _clip_or_404(conn, eid, cid)
        _libass_preflight(body)
        return submit_export(s, eid, cid, body).public()

    @app.get("/v1/exports")
    def exports(s: State = Depends(auth)) -> list[dict[str, Any]]:
        return [{"job": j.public(), "episode_id": j.meta.get("episode_id"),
                 "clip_id": j.meta.get("clip_id"), "title": j.meta.get("title", "")}
                for j in s.jobs.list_jobs("export")]

    @app.post("/v1/jobs/{job_id}:retry")
    def retry(job_id: str, s: State = Depends(auth)) -> dict[str, Any]:
        job = s.jobs.jobs.get(job_id)
        if job is None:
            raise HTTPException(404, "vazifa topilmadi")
        if job.kind != "export" or job.status not in ("failed", "cancelled"):
            raise HTTPException(409, "faqat muvaffaqiyatsiz yoki bekor qilingan eksportni qayta urinish mumkin")
        params = s.export_params.get(job_id)
        if params is None:
            raise HTTPException(409, "vazifa parametrlari topilmadi")
        eid, cid, body = params
        _libass_preflight(body)
        return submit_export(s, eid, cid, body, retry_of=job_id).public()

    @app.get("/v1/episodes/{eid}/proxy")
    def proxy(eid: str, s: State = Depends(auth)) -> FileResponse:
        p = s.episode_dir(eid) / "cache" / "proxy.mp4"
        if not p.exists():
            raise HTTPException(404, "proksi hali tayyor emas")
        return FileResponse(p, media_type="video/mp4")
