"""Epizodlar: import, qayta tahlil, epizod ma'lumoti, transkript va so'z tahriri, to'lqin shakli,
spikerlar."""

from __future__ import annotations

import json
import uuid
import wave
from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np
from fastapi import Depends, FastAPI, HTTPException, Query
from pydantic import BaseModel

from lahza_engine.api.state import State
from lahza_engine.core.jobs import Job
from lahza_engine.db import store as db
from lahza_engine.types import Sentence, Word

WAV_NAME = "audio16k.wav"


class ImportIn(BaseModel):
    project_id: str
    path: str
    title: str | None = None
    focus: str | None = None
    num_speakers: int | None = None
    force_lite: bool = False


class ReanalyzeIn(BaseModel):
    force_lite: bool = False
    focus: str | None = None
    num_speakers: int | None = None


class WordEditIn(BaseModel):
    sentence_id: int
    ord: int
    text: str


class SpeakerIn(BaseModel):
    display_name: str | None = None


def sentence_json(s: Sentence) -> dict[str, Any]:
    return {**s.model_dump(mode="json"), "text": s.text}


def lexicon_for(s: State, show_id: str | None) -> tuple[list[str], dict[str, str]]:
    """Shou + umumiy lug'atdan ASR hotwords va normallashtirish xaritasi (variant -> atama)."""
    from lahza_engine.text.orthography import normalize

    rows = s.lib("SELECT term, variants_json FROM lexicon WHERE show_id IS NULL OR show_id = ?"
                 " ORDER BY id", (show_id,))
    hot: list[str] = []
    mapping: dict[str, str] = {}
    for r in rows:
        term = normalize(r["term"]).strip()
        if not term:
            continue
        if term not in hot:
            hot.append(term)
        for v in [term, *json.loads(r["variants_json"] or "[]")]:
            key = normalize(str(v)).strip().lower()
            if key:
                mapping.setdefault(key, term)
    return hot, mapping


def _analysis_running(s: State, eid: str) -> bool:
    return any(j.meta.get("episode_id") == eid and j.status in ("queued", "running")
               for j in s.jobs.list_jobs("analyze"))


def create_episode(s: State, project_id: str, src: Path, title: str | None) -> tuple[str, Path]:
    """Epizod qatori va `.lahza` papkasi (import, YouTube va partiyaviy navbat uchun umumiy).

    Video kodekini bundled ffmpeg dekodlay olmasa (masalan, AV1) - epizod yaratilMAYDI,
    `UnsupportedCodec` ko'tariladi (aks holda tahlil audio orqali o'tib, eksport yiqiladi)."""
    from lahza_engine.media.codec_check import check_decodable

    shows = s.lib("SELECT * FROM shows WHERE id = ?", (project_id,))
    if not shows:
        raise HTTPException(404, "loyiha topilmadi")
    check_decodable(src)
    eid = uuid.uuid4().hex[:12]
    title = title or src.stem
    pdir = s.settings.library_dir / shows[0]["name"] / f"{title}-{eid[:6]}.lahza"
    pdir.mkdir(parents=True, exist_ok=True)
    s.lib_write("INSERT INTO episodes(id, show_id, title, project_dir, status) VALUES (?,?,?,?,?)",
                (eid, project_id, title, str(pdir), "analyzing"))
    return eid, pdir


def submit_analysis(s: State, eid: str, show_id: str, pdir: Path, src: Path,
                    focus: str | None, num_speakers: int | None, force_lite: bool,
                    *, on_change: Callable[[Job], None] | None = None, **meta: Any) -> Job:
    from lahza_engine.core.analyze import analyze
    from lahza_engine.core.runner import StageContext
    from lahza_engine.media.probe import fast_hash

    hotwords, lexicon_map = lexicon_for(s, show_id)
    s.lib_write("UPDATE episodes SET status = 'analyzing' WHERE id = ?", (eid,))

    def work(job: Job) -> dict[str, Any]:
        conn = db.open_project(pdir)
        status, mode = "failed", None
        try:
            svc = s.services()
            ctx = StageContext(
                media_id=eid, media_hash=fast_hash(src), project_dir=pdir, conn=conn,
                services={"src": str(src), "svc": svc, "focus": focus,
                          "num_speakers": num_speakers, "force_lite": force_lite,
                          "hotwords": hotwords, "lexicon_map": lexicon_map,
                          "aligner": getattr(svc, "aligner", None)},
                cancel=job.cancel,
                on_progress=lambda stage, frac: s.jobs.progress(job, stage, frac),
            )
            res = analyze(ctx, s.settings)
            status, mode = "ready", res["highlight"]["mode"]
            return {"episode_id": eid, "mode": mode, "clips": len(res["highlight"]["clips"])}
        finally:
            s.lib_write("UPDATE episodes SET status = ?, highlight_mode = COALESCE(?, highlight_mode)"
                        " WHERE id = ?", (status, mode, eid))
            conn.close()

    return s.jobs.submit("analyze", work, on_change=on_change, episode_id=eid, **meta)


def wav_peaks(wav: Path, buckets: int) -> tuple[int, list[float]]:
    """16-bit WAV -> har bo'lakdagi |max| (0..1, butun fayl maksimumiga normallangan).
    Fayl bo'lakma-bo'lak o'qiladi: 1 soatlik audio ham xotiraga to'liq yuklanmaydi."""
    with wave.open(str(wav), "rb") as w:
        if w.getsampwidth() != 2:
            raise HTTPException(500, "faqat 16-bit PCM WAV qo'llanadi")
        n, rate = w.getnframes(), w.getframerate()
        duration_ms = int(n * 1000 / rate) if rate else 0
        buckets = max(1, min(buckets, n)) if n else 0
        peaks = np.zeros(buckets, dtype=np.float32)
        bounds = (np.arange(buckets + 1, dtype=np.int64) * n) // max(1, buckets)
        for i in range(buckets):
            cnt = int(bounds[i + 1] - bounds[i])
            if cnt <= 0:
                continue
            raw = w.readframes(cnt)
            arr = np.frombuffer(raw, dtype="<i2")
            if arr.size:
                peaks[i] = np.abs(arr.astype(np.int32)).max() / 32768.0
    top = float(peaks.max()) if buckets else 0.0
    if top > 0:
        peaks = peaks / top
    return duration_ms, [round(float(x), 4) for x in peaks]


def edit_sentence_word(sent: Sentence, ord_: int, text: str) -> Sentence:
    """So'zni almashtiradi. Bo'sh matn - so'z o'chiriladi; bo'shliqli matn - bir nechta so'zga
    bo'linadi (eski so'z oralig'i harf soniga proporsional taqsimlanadi, qolgan so'zlar vaqti
    o'zgarmaydi)."""
    from lahza_engine.align.realign import distribute

    old = sent.words[ord_]
    tokens = text.split()
    orig = old.original_text if old.edited and old.original_text is not None else old.text
    new: list[Word] = []
    if tokens:
        pieces = [old.model_copy(update={"text": t, "edited": True, "original_text": orig})
                  for t in tokens]
        new = pieces if len(pieces) == 1 else distribute(pieces, old.start_ms, old.end_ms)
    words = sent.words[:ord_] + new + sent.words[ord_ + 1:]
    return sent.model_copy(update={"words": words})


def register(app: FastAPI, auth: Callable[..., State]) -> None:
    @app.post("/v1/media:import")
    def import_media(body: ImportIn, s: State = Depends(auth)) -> dict[str, Any]:
        src = Path(body.path)
        if not src.is_file():
            raise HTTPException(400, "fayl topilmadi")
        from lahza_engine.media.codec_check import UnsupportedCodec

        try:
            eid, pdir = create_episode(s, body.project_id, src, body.title)
        except UnsupportedCodec as e:
            raise HTTPException(415, e.detail()) from None
        job = submit_analysis(s, eid, body.project_id, pdir, src, body.focus, body.num_speakers,
                              body.force_lite)
        return {"episode_id": eid, "job": job.public()}

    @app.post("/v1/episodes/{eid}:reanalyze")
    def reanalyze(eid: str, body: ReanalyzeIn | None = None, s: State = Depends(auth)) -> dict[str, Any]:
        body = body or ReanalyzeIn()
        row = s.episode_row(eid)
        if _analysis_running(s, eid):
            raise HTTPException(409, "bu epizod allaqachon tahlil qilinmoqda")
        pdir = Path(row["project_dir"])
        with s.project(eid) as conn:
            media = conn.execute("SELECT path FROM media WHERE id = ?", (eid,)).fetchone()
        if media is None:
            raise HTTPException(409, "epizod hali import qilinmagan (media yo'q)")
        src = Path(media["path"])
        if not src.is_file():
            raise HTTPException(400, "asl video fayl topilmadi")
        job = submit_analysis(s, eid, row["show_id"], pdir, src, body.focus, body.num_speakers,
                              body.force_lite)
        return job.public()

    @app.get("/v1/episodes/{eid}")
    def episode(eid: str, s: State = Depends(auth)) -> dict[str, Any]:
        row = s.episode_row(eid)
        with s.project(eid) as conn:
            m = conn.execute("SELECT * FROM media WHERE id = ?", (eid,)).fetchone()
        media = None if m is None else {"duration_ms": m["duration_ms"], "fps": m["fps"],
                                        "width": m["width"], "height": m["height"], "path": m["path"]}
        return {"id": row["id"], "show_id": row["show_id"], "title": row["title"],
                "status": row["status"], "project_dir": row["project_dir"], "media": media,
                "highlight_mode": row["highlight_mode"]}

    @app.get("/v1/episodes/{eid}/transcript")
    def transcript(eid: str, s: State = Depends(auth)) -> dict[str, Any]:
        with s.project(eid) as conn:
            tr = db.load_transcript(conn, eid)
        return {"sentences": [sentence_json(x) for x in tr.sentences]}

    @app.patch("/v1/episodes/{eid}/words")
    def edit_word(eid: str, body: WordEditIn, s: State = Depends(auth)) -> dict[str, Any]:
        from lahza_engine.align.realign import realign_sentence
        from lahza_engine.text.orthography import normalize

        pdir = s.episode_dir(eid)
        with s.project(eid) as conn:
            sent = db.load_sentence(conn, eid, body.sentence_id)
            if sent is None:
                raise HTTPException(404, "gap topilmadi")
            if not 0 <= body.ord < len(sent.words):
                raise HTTPException(404, "so'z topilmadi")
            before = sent.text
            edited = edit_sentence_word(sent, body.ord, normalize(body.text).strip())
            wav = pdir / "cache" / WAV_NAME
            svc = s.peek_services()
            aligner = getattr(svc, "aligner", None) if svc is not None else None
            out = realign_sentence(edited, wav if wav.exists() else None, aligner)
            # Aligner faqat vaqtlarni beradi: matn va tahrir belgilarini saqlab qolamiz.
            out = out.model_copy(update={"words": [
                w.model_copy(update={"text": e.text, "edited": e.edited,
                                     "original_text": e.original_text, "conf": e.conf,
                                     "speaker": e.speaker})
                for w, e in zip(out.words, edited.words, strict=True)]})
            db.replace_sentence(conn, eid, out)
            if out.text != before:
                db.add_correction(conn, eid, out.id, f"cache/{WAV_NAME}#{out.start_ms}-{out.end_ms}",
                                  before, out.text)
        return {"ok": True, "sentence": sentence_json(out)}

    @app.get("/v1/episodes/{eid}/waveform")
    def waveform(eid: str, buckets: int = Query(2000, ge=10, le=20000),
                 s: State = Depends(auth)) -> dict[str, Any]:
        cache = s.episode_dir(eid) / "cache"
        wav = cache / WAV_NAME
        if not wav.exists():
            raise HTTPException(404, "audio hali tayyor emas")
        stamp = int(wav.stat().st_mtime)
        cached = cache / f"waveform-{buckets}-{stamp}.json"
        if cached.exists():
            return json.loads(cached.read_text(encoding="utf-8"))
        duration_ms, peaks = wav_peaks(wav, buckets)
        res = {"duration_ms": duration_ms, "peaks": peaks}
        for old in cache.glob(f"waveform-{buckets}-*.json"):
            old.unlink(missing_ok=True)
        cached.write_text(json.dumps(res), encoding="utf-8")
        return res

    @app.get("/v1/episodes/{eid}/speakers")
    def speakers(eid: str, s: State = Depends(auth)) -> list[dict[str, Any]]:
        with s.project(eid) as conn:
            return db.list_speakers(conn, eid)

    @app.patch("/v1/episodes/{eid}/speakers/{label}")
    def rename_speaker(eid: str, label: str, body: SpeakerIn, s: State = Depends(auth)) -> dict[str, Any]:
        name = (body.display_name or "").strip() or None
        with s.project(eid) as conn:
            if label not in {x["label"] for x in db.list_speakers(conn, eid)}:
                raise HTTPException(404, "spiker topilmadi")
            db.set_speaker_name(conn, label, name)
        return {"ok": True}
