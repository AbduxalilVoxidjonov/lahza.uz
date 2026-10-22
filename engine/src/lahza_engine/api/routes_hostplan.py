"""Adobe plaginlari uchun host-reja (`lahza.hostplan/1`, docs/04 "Adobe plaginlari").

* `POST /v1/episodes/{eid}/clips/{cid}:hostplan` - klip -> host-reja (+ SRT va so'zlar JSON out_dir'ga);
* `POST /v1/montages/{mid}:hostplan` - montaj timeline'i -> host-reja;
* `GET /v1/hostplan/schema` - plagin moslik tekshiruvi.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any, Literal

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel

from lahza_engine import __version__
from lahza_engine.api.state import State
from lahza_engine.hostplan.model import HOSTPLAN_SCHEMA
from lahza_engine.subtitle.style import StyleTemplate
from lahza_engine.text.orthography import Orthography


class ClipHostPlanIn(BaseModel):
    out_dir: str
    style: StyleTemplate = StyleTemplate()
    orthography: Orthography | None = None
    aspect: Literal["9:16", "1:1", "16:9"] = "9:16"


class MontageHostPlanIn(BaseModel):
    out_dir: str


def prepare_out_dir(raw: str) -> Path:
    """out_dir absolyut bo'lishi, ota papkasi mavjud bo'lishi kerak; o'zi bo'lmasa yaratiladi."""
    if not raw or not raw.strip():
        raise HTTPException(400, "chiqish papkasi (out_dir) ko'rsatilmagan")
    p = Path(raw.strip()).expanduser()
    if not p.is_absolute():
        raise HTTPException(400, "chiqish papkasi to'liq (absolyut) yo'l bo'lishi kerak")
    if p.exists():
        if not p.is_dir():
            raise HTTPException(400, "chiqish yo'li papka emas")
        return p
    if not p.parent.is_dir():
        raise HTTPException(400, "chiqish papkasining ota papkasi topilmadi")
    try:
        p.mkdir()
    except OSError as e:
        raise HTTPException(400, f"chiqish papkasini yaratib bo'lmadi: {e.strerror or e}") from e
    return p


def register(app: FastAPI, auth: Callable[..., State]) -> None:
    @app.get("/v1/hostplan/schema")
    def hostplan_schema(s: State = Depends(auth)) -> dict[str, Any]:
        return {"schema": HOSTPLAN_SCHEMA, "engine": __version__}

    @app.post("/v1/episodes/{eid}/clips/{cid}:hostplan")
    def clip_hostplan(eid: str, cid: str, body: ClipHostPlanIn, s: State = Depends(auth)) -> dict[str, Any]:
        from lahza_engine.api.routes_clips import _clip_or_404
        from lahza_engine.hostplan.build import plan_from_clip

        with s.project(eid) as conn:
            clip = _clip_or_404(conn, eid, cid)
            media = conn.execute("SELECT path FROM media WHERE id = ?", (eid,)).fetchone()
            if media is None:
                raise HTTPException(409, "epizod hali tahlil qilinmagan")
            if not Path(media["path"]).is_file():
                raise HTTPException(409, "epizodning asl video fayli topilmadi")
            out = prepare_out_dir(body.out_dir)
            detector = s.services().face_detector
            try:
                plan = plan_from_clip(conn, eid, clip, s.settings, body.style, body.orthography,
                                      body.aspect, out, detector=detector)
            except OSError as e:
                raise HTTPException(500, f"subtitr fayllarini yozib bo'lmadi: {e.strerror or e}") from e
        return plan.to_json()

    @app.post("/v1/montages/{mid}:hostplan")
    def montage_hostplan(mid: str, body: MontageHostPlanIn, s: State = Depends(auth)) -> dict[str, Any]:
        from lahza_engine.api.routes_montage import _row, _timeline
        from lahza_engine.hostplan.build import plan_from_montage

        r = _row(s, mid)
        if r["status"] == "planning":
            raise HTTPException(409, "montaj hozir rejalashtirilmoqda")
        tl = _timeline(r)
        if tl is None or not tl.video:
            raise HTTPException(409, "montaj rejasi hali tayyor emas")
        out = prepare_out_dir(body.out_dir)
        try:
            plan = plan_from_montage(tl, mid, r["name"] or "Lahza montaj", out, s.settings)
        except OSError as e:
            raise HTTPException(500, f"subtitr fayllarini yozib bo'lmadi: {e.strerror or e}") from e
        return plan.to_json()
