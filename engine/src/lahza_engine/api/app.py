"""Engine HTTP/WebSocket API (docs/04-engine-api.md).

Xavfsizlik (NFR-08): faqat 127.0.0.1, har ishga tushishda yangi sessiya tokeni.
Token `Authorization: Bearer <t>` sarlavhasida yoki media/WS uchun `?t=<t>` parametrida.

Endpointlar mavzu bo'yicha modullarga bo'lingan:
* `routes_episodes` - import, qayta tahlil, epizod, transkript, to'lqin shakli, spikerlar;
* `routes_queue` - partiyaviy tahlil navbati (bir nechta epizod ketma-ket);
* `routes_youtube` - YouTube havolasidan import (YT-1, standart o'chiq, alohida jarayon);
* `routes_clips` - kliplar, matn orqali montaj, kalit kadrlar, preview, o'xshashlar, eksport;
* `routes_library` - lug'at, uslub shablonlari, shriftlar;
* `routes_montage` - fx plaginlari, video shablonlar, avtomontaj, timeline, montaj render;
* `routes_models` - modellar, .lzpack;
* `routes_system` - imkoniyatlar, diagnostika, Finder/Explorer'da ko'rsatish.
"""

from __future__ import annotations

import asyncio
import contextlib
import os
import secrets
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from lahza_engine import __version__
from lahza_engine.api import (
    routes_claude,
    routes_clips,
    routes_editing_agent,
    routes_episodes,
    routes_hostplan,
    routes_interop,
    routes_learning,
    routes_library,
    routes_license,
    routes_models,
    routes_montage,
    routes_queue,
    routes_setup,
    routes_skills,
    routes_stickers,
    routes_system,
    routes_youtube,
)
from lahza_engine.api.state import State
from lahza_engine.config import Settings
from lahza_engine.models.hardware import classify, detect

__all__ = ["State", "create_app"]


class ProjectIn(BaseModel):
    name: str


# UI webview kelib chiqishi (origin): macOS/Linux `tauri://localhost`, Windows `http(s)://tauri.localhost`.
# Engine boshqa portda bo'lgani uchun brauzer CORS talab qiladi (Authorization sarlavhasi -> preflight).
TAURI_ORIGINS = ["tauri://localhost", "http://tauri.localhost", "https://tauri.localhost"]
# Vite dev server (app/vite.config.ts, `npm run dev`) - faqat LAHZA_DEV=1 da.
DEV_ORIGINS = ["http://127.0.0.1:1420", "http://localhost:1420"]
# Adobe plaginlari (docs/04 "Adobe plaginlari"):
# * CEP paneli (After Effects) - HTML `file://` dan yuklanadi; Chromium (CEF) bunday sahifa
#   so'rovlarida `Origin: null` yuboradi. "file://" - ba'zi CEF versiyalari uchun zaxira.
#   CEP 11+ CORS tekshiruvini qat'iylashtirgan (CEP 12 HTML Extension Cookbook, "CORS checks").
# * Premiere UXP - brauzer emas; rasmiy hujjat (developer.adobe.com/premiere-pro/uxp/resources/
#   recipes/network) faqat "server Access-Control-Allow-Origin bilan UXP so'rovlariga ruxsat
#   bersin" deydi, aniq Origin qiymatini aytmaydi. ANIQLANSIN: haqiqiy host'da Origin sarlavhasi
#   (kutilgan: yo'q yoki "null"); yo'q bo'lsa CORS umuman qo'llanmaydi.
# "null" origin har qanday sandbox iframe'da ham bo'ladi - shuning uchun token majburiy qoladi,
# allow_credentials=False, engine faqat 127.0.0.1 da. O'chirish: LAHZA_ADOBE_CORS=0.
ADOBE_ORIGINS = ["null", "file://"]


def cors_origins() -> list[str]:
    origins = list(TAURI_ORIGINS)
    if os.environ.get("LAHZA_ADOBE_CORS", "1") != "0":
        origins += ADOBE_ORIGINS
    if os.environ.get("LAHZA_DEV") == "1":
        origins += DEV_ORIGINS
    extra = os.environ.get("LAHZA_CORS_ORIGINS", "")
    origins += [o.strip() for o in extra.split(",") if o.strip()]
    return origins


def create_app(settings: Settings | None = None, token: str | None = None) -> FastAPI:
    st = State(settings or Settings(), token or secrets.token_urlsafe(24))

    @asynccontextmanager
    async def lifespan(a: FastAPI):
        # Fon vazifalari (masalan, fayl-IPC sikli) - server event loop'ida.
        tasks = [asyncio.create_task(f()) for f in getattr(a.state, "background", [])]
        yield
        for t in tasks:
            t.cancel()
        for t in tasks:
            with contextlib.suppress(BaseException):
                await t
        st.jobs.shutdown()
        for hook in list(getattr(a.state, "shutdown_hooks", [])):
            # To'xtashda bitta ilgak xatosi qolganini to'xtatmasin.
            with contextlib.suppress(Exception):
                hook()

    app = FastAPI(title="Lahza Engine", version=__version__, docs_url=None, redoc_url=None,
                  lifespan=lifespan)
    app.state.lahza = st
    app.state.shutdown_hooks = []  # to'xtashda chaqiriladi (masalan, engine.json o'chirish)
    app.state.background = []  # coroutine fabrikalari: ishga tushishda task, to'xtashda bekor (fayl-IPC)
    # Token baribir majburiy; CORS faqat webview/dev origin'iga javobni o'qishga ruxsat beradi.
    app.add_middleware(CORSMiddleware, allow_origins=cors_origins(), allow_credentials=False,
                       allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
                       allow_headers=["Authorization", "Content-Type"])

    def auth(request: Request, t: str | None = Query(None)) -> State:
        header = request.headers.get("authorization", "")
        given = header.removeprefix("Bearer ").strip() if header else (t or "")
        if not secrets.compare_digest(given, st.token):
            raise HTTPException(401, "token noto'g'ri")
        return st

    # ---- Tizim -------------------------------------------------------------
    @app.get("/v1/health")
    def health(s: State = Depends(auth)) -> dict[str, Any]:
        return {"version": __version__, "ok": True}

    @app.get("/v1/hardware")
    def hardware(s: State = Depends(auth)) -> dict[str, Any]:
        hw = detect(str(s.settings.data_dir if s.settings.data_dir.exists() else Path.home()))
        d = classify(hw)
        return {"profile": hw.to_dict(), "tier": d.tier, "reasons": d.reasons}

    # ---- Loyihalar ---------------------------------------------------------
    @app.get("/v1/projects")
    def projects(s: State = Depends(auth)) -> list[dict[str, Any]]:
        return [dict(r) for r in s.lib("SELECT * FROM shows ORDER BY created_at DESC")]

    @app.post("/v1/projects")
    def create_project(body: ProjectIn, s: State = Depends(auth)) -> dict[str, Any]:
        name = body.name.strip()
        if not name:
            raise HTTPException(400, "loyiha nomi bo'sh")
        pid = uuid.uuid4().hex[:12]
        s.lib_write("INSERT INTO shows(id, name) VALUES (?, ?)", (pid, name))
        return {"id": pid, "name": name}

    @app.get("/v1/projects/{project_id}/episodes")
    def episodes(project_id: str, s: State = Depends(auth)) -> list[dict[str, Any]]:
        rows = s.lib("SELECT * FROM episodes WHERE show_id = ? ORDER BY created_at DESC", (project_id,))
        return [dict(r) for r in rows]

    # ---- Vazifalar ---------------------------------------------------------
    @app.get("/v1/jobs/{job_id}")
    def get_job(job_id: str, s: State = Depends(auth)) -> dict[str, Any]:
        job = s.jobs.jobs.get(job_id)
        if job is None:
            raise HTTPException(404, "vazifa topilmadi")
        return job.public()

    @app.post("/v1/jobs/{job_id}:cancel")
    def cancel_job(job_id: str, s: State = Depends(auth)) -> dict[str, Any]:
        if job_id not in s.jobs.jobs:
            raise HTTPException(404, "vazifa topilmadi")
        job = s.jobs.cancel(job_id)
        if job.meta.get("op") == "setup":
            from lahza_engine.models.setup import coordinator
            coordinator(s.store, s.jobs).cancel(job_id)
        return job.public()

    routes_editing_agent.register(app, auth)
    routes_models.register(app, auth)
    routes_setup.register(app, auth)
    routes_episodes.register(app, auth)
    routes_queue.register(app, auth)
    routes_clips.register(app, auth)
    routes_library.register(app, auth)
    routes_stickers.register(app, auth)
    routes_montage.register(app, auth)
    routes_hostplan.register(app, auth)
    routes_system.register(app, auth)
    routes_interop.register(app, auth)
    routes_skills.register(app, auth)
    routes_youtube.register(app, auth)
    routes_license.register(app, auth)
    routes_learning.register(app, auth)
    routes_claude.register(app, auth)

    # ---- Hodisalar ---------------------------------------------------------
    @app.websocket("/v1/events")
    async def events(ws: WebSocket, t: str = Query("")) -> None:
        # Avval qabul qilamiz: aks holda server HTTP 403 qaytaradi va mijoz 4401 kodini ko'rmaydi.
        await ws.accept()
        if not secrets.compare_digest(t, st.token):
            await ws.close(code=4401)
            return
        q = st.bus.subscribe()

        async def pump() -> None:
            while True:
                await ws.send_json(await q.get())

        # Mijoz uzilishini (yoki server to'xtashini) receive orqali sezamiz: faqat send kutilsa,
        # hodisa bo'lmaganda handler abadiy osilib, uvicorn to'xtashini to'sardi.
        sender = asyncio.create_task(pump())
        try:
            while not sender.done():
                msg = await ws.receive()
                if msg.get("type") == "websocket.disconnect":
                    break
        except (WebSocketDisconnect, RuntimeError):
            pass
        finally:
            sender.cancel()
            with contextlib.suppress(BaseException):
                await sender
            st.bus.unsubscribe(q)

    return app
