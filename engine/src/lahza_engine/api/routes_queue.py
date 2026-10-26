"""Partiyaviy tahlil navbati (PRO-5): bir nechta epizodni navbatga qo'yish, tartib, bekor qilish.

Navbat mantig'i - `core/batch.py`; bu yerda faqat HTTP qatlami va elementni ishga tushirish
(`start_item`), u mavjud bitta-epizod oqimini (`create_episode` + `submit_analysis`) ishlatadi.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

from lahza_engine.api.routes_episodes import _analysis_running, create_episode, submit_analysis
from lahza_engine.api.state import State
from lahza_engine.core.batch import QueueConflict
from lahza_engine.core.errors import ALREADY_RUNNING, FILE_NOT_FOUND, CodedError
from lahza_engine.core.jobs import Job

MAX_BATCH = 500


class QueueAddIn(BaseModel):
    project_id: str
    paths: list[str] = Field(max_length=MAX_BATCH)
    focus: str | None = None
    num_speakers: int | None = None
    force_lite: bool = False


class QueueReorderIn(BaseModel):
    ids: list[str]


class QueueClearIn(BaseModel):
    project_id: str | None = None


def start_item(s: State, item: dict[str, Any], on_change: Callable[[Job], None]) -> Job:
    """Navbat elementi -> analyze vazifasi. Tiklangan elementda epizod allaqachon bo'lsa, o'shani
    qayta tahlil qiladi (bosqich keshi tufayli tugagan bosqichlar o'tkazib yuboriladi)."""
    src = Path(item["path"])
    if not src.is_file():
        raise CodedError(FILE_NOT_FOUND, f"fayl topilmadi: {src}", path=src.name)
    opts = json.loads(item["options_json"] or "{}")
    show_id = item["show_id"]
    eid = item["episode_id"]
    rows = s.lib("SELECT * FROM episodes WHERE id = ?", (eid,)) if eid else []
    if rows:
        if _analysis_running(s, eid):
            raise CodedError(ALREADY_RUNNING, "bu epizod allaqachon tahlil qilinmoqda")
        pdir = Path(rows[0]["project_dir"])
    else:
        try:
            eid, pdir = create_episode(s, show_id, src, item["title"])
        except HTTPException as e:
            d = e.detail
            if isinstance(d, dict) and isinstance(d.get("code"), str):
                params = {k: v for k, v in d.items() if k not in ("code", "message")}
                raise CodedError(d["code"], str(d.get("message") or d["code"]), **params) from e
            raise ValueError(str(d)) from e
    return submit_analysis(s, eid, show_id, pdir, src, opts.get("focus"), opts.get("num_speakers"),
                           bool(opts.get("force_lite")), on_change=on_change, queue_item_id=item["id"])


def register(app: FastAPI, auth: Callable[..., State]) -> None:
    def item_or_404(item_id: str, fn: Callable[[str], Any]) -> Any:
        try:
            return fn(item_id)
        except KeyError:
            raise HTTPException(404, "navbat elementi topilmadi") from None
        except QueueConflict as e:
            raise HTTPException(409, str(e)) from None

    @app.get("/v1/queue")
    def queue_list(project_id: str | None = Query(None), s: State = Depends(auth)) -> list[dict[str, Any]]:
        return s.queue.list(project_id)

    @app.post("/v1/queue")
    def queue_add(body: QueueAddIn, s: State = Depends(auth)) -> list[dict[str, Any]]:
        if not s.lib("SELECT id FROM shows WHERE id = ?", (body.project_id,)):
            raise HTTPException(404, "loyiha topilmadi")
        paths = [p.strip() for p in body.paths if p.strip()]
        if not paths:
            raise HTTPException(400, "fayllar ro'yxati bo'sh")
        missing = [p for p in paths if not Path(p).is_file()]
        if missing:
            raise HTTPException(400, f"fayl topilmadi: {', '.join(missing)}")
        if body.num_speakers is not None and not 1 <= body.num_speakers <= 20:
            raise HTTPException(400, "spikerlar soni 1..20 oralig'ida bo'lishi kerak")
        opts = {"focus": body.focus or None, "num_speakers": body.num_speakers,
                "force_lite": body.force_lite}
        return s.queue.add(body.project_id, paths, opts)

    @app.delete("/v1/queue/{item_id}")
    def queue_remove(item_id: str, s: State = Depends(auth)) -> dict[str, Any]:
        item_or_404(item_id, s.queue.remove)
        return {"ok": True}

    @app.post("/v1/queue/{item_id}:cancel")
    def queue_cancel(item_id: str, s: State = Depends(auth)) -> dict[str, Any]:
        return item_or_404(item_id, s.queue.cancel)

    @app.post("/v1/queue/{item_id}:retry")
    def queue_retry(item_id: str, s: State = Depends(auth)) -> dict[str, Any]:
        return item_or_404(item_id, s.queue.retry)

    @app.post("/v1/queue:reorder")
    def queue_reorder(body: QueueReorderIn, s: State = Depends(auth)) -> list[dict[str, Any]]:
        try:
            return s.queue.reorder(body.ids)
        except ValueError as e:
            raise HTTPException(400, str(e)) from None

    @app.post("/v1/queue:clear")
    def queue_clear(body: QueueClearIn | None = None, s: State = Depends(auth)) -> dict[str, Any]:
        return {"removed": s.queue.clear_finished((body or QueueClearIn()).project_id)}
