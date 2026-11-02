"""Tizim: imkoniyatlar (ffmpeg/libass/enkoderlar/servislar), diagnostika, fayl menejerida ko'rsatish."""

from __future__ import annotations

import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Query
from pydantic import BaseModel

from lahza_engine.api.state import State


class OutDirIn(BaseModel):
    out_dir: str


class RevealIn(BaseModel):
    path: str


def ffmpeg_capabilities() -> dict[str, Any]:
    from lahza_engine.media.tools import ToolNotFound, find_tool
    from lahza_engine.render.capabilities import has_filter
    from lahza_engine.render.encoders import DEV_FALLBACKS, PRIORITY, list_encoders

    try:
        ff = str(find_tool("ffmpeg"))
    except ToolNotFound:
        return {"ffmpeg": False, "libass": False, "encoders": []}
    known = {n for names in PRIORITY.values() for n in names} | set(DEV_FALLBACKS)
    avail = list_encoders(ff)
    encoders = sorted(n for n in avail if n in known or "264" in n or n.startswith("hevc_"))
    return {"ffmpeg": True, "libass": has_filter(ff, "ass"), "encoders": encoders}


def capabilities(s: State, refresh: bool = False) -> dict[str, Any]:
    if s.capabilities_cache is not None and not refresh:
        return s.capabilities_cache
    svc = s.services(refresh=False)
    caps = {
        **ffmpeg_capabilities(),
        "vad": "silero" if svc.vad is not None and getattr(svc.vad, "method", "silero") == "silero"
        else "energy",
        "aligner": getattr(svc, "aligner", None) is not None,
        "diarizer": svc.diarizer is not None,
        "face_detector": svc.face_detector is not None,
        "llm": svc.llm_model_path is not None,
    }
    s.capabilities_cache = caps
    return caps


def reveal_command(path: Path, platform: str = sys.platform) -> list[str]:
    """Shell'siz argumentlar massivi (NFR-08)."""
    p = str(path.resolve())
    if platform == "darwin":
        return ["open", "-R", p]
    if platform == "win32":
        return ["explorer", f"/select,{p}"]
    return ["xdg-open", p if path.is_dir() else str(path.resolve().parent)]


def register(app: FastAPI, auth: Callable[..., State]) -> None:
    @app.get("/v1/capabilities")
    def get_capabilities(refresh: bool = Query(False), s: State = Depends(auth)) -> dict[str, Any]:
        return capabilities(s, refresh)

    @app.post("/v1/diagnostics")
    def diagnostics(body: OutDirIn, s: State = Depends(auth)) -> dict[str, Any]:
        from lahza_engine.core.diagnostics import build_diagnostics
        from lahza_engine.models.hardware import classify, detect

        out = Path(body.out_dir)
        if not out.parent.is_dir():
            raise HTTPException(400, "papka topilmadi")
        try:
            hw = detect(str(Path.home()))
            hardware: dict[str, Any] | None = {"profile": hw.to_dict(), "tier": classify(hw).tier}
        except Exception:  # noqa: BLE001 - diagnostika har holda yig'iladi
            hardware = None
        try:
            caps: dict[str, Any] | None = capabilities(s)
        except Exception:  # noqa: BLE001
            caps = None
        with s.lib_lock:
            path = build_diagnostics(out, s.settings.logs_dir, s.library, hardware, caps,
                                     s.store.load().model_dump(mode="json"))
        return {"path": str(path)}

    @app.post("/v1/system:reveal")
    def reveal(body: RevealIn, s: State = Depends(auth)) -> dict[str, Any]:
        p = Path(body.path)
        if not body.path or not p.exists():
            raise HTTPException(404, "yo'l topilmadi")
        try:
            subprocess.Popen(reveal_command(p), stdin=subprocess.DEVNULL,  # noqa: S603
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError as e:
            raise HTTPException(500, "fayl menejerini ochib bo'lmadi") from e
        return {"ok": True}
