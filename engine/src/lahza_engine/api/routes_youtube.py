"""YouTube havolasidan import (YT-1, ADR-0010): sozlama, holat va `/v1/media:import-url`.

* Funksiya standart holatda O'CHIQ; yoqilgani `library.db` -> `settings` jadvalida
  (`youtube_import` kaliti) saqlanadi - sxema o'zgarmaydi.
* Har importda `consent: true` majburiy ("menga tegishli yoki ruxsatim bor" + YouTube shartlari).
* Yuklash `download` vazifasida, yt-dlp esa alohida jarayonda (`media/youtube.py`). Tayyor fayl
  oddiy import kabi `create_episode` + `submit_analysis` ga uzatiladi.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel

from lahza_engine.api.routes_episodes import create_episode, submit_analysis
from lahza_engine.api.state import State
from lahza_engine.core.jobs import Job
from lahza_engine.media import youtube

SETTING_KEY = "youtube_import"
_UNSAFE = re.compile(r'[/\\:*?"<>|\x00-\x1f]+')


class ImportUrlIn(BaseModel):
    project_id: str
    url: str
    consent: bool = False
    title: str | None = None
    focus: str | None = None
    num_speakers: int | None = None
    force_lite: bool = False


class YoutubeSettingIn(BaseModel):
    enabled: bool


def import_enabled(s: State) -> bool:
    rows = s.lib("SELECT value_json FROM settings WHERE key = ?", (SETTING_KEY,))
    if not rows:
        return False
    try:
        return json.loads(rows[0]["value_json"]).get("enabled") is True
    except (ValueError, AttributeError):
        return False


def set_import_enabled(s: State, enabled: bool) -> None:
    s.lib_write("INSERT INTO settings(key, value_json) VALUES (?, ?) ON CONFLICT(key)"
                " DO UPDATE SET value_json = excluded.value_json",
                (SETTING_KEY, json.dumps({"enabled": enabled})))


def downloads_dir(s: State, video_id: str) -> Path:
    """Har video uchun alohida papka: qayta urinishda `.part` fayllar davom ettiriladi."""
    return s.settings.data_dir / "Imports" / "youtube" / video_id


def safe_title(title: str | None, fallback: str) -> str:
    """Epizod papkasi nomiga yaroqli sarlavha (YouTube sarlavhasida `/` va h.k. bo'lishi mumkin)."""
    t = _UNSAFE.sub("_", (title or "").strip()).strip(" ._")
    return t[:80] or fallback


def _download_running(s: State, video_id: str) -> bool:
    return any(j.meta.get("video_id") == video_id and j.status in ("queued", "running")
               for j in s.jobs.list_jobs("download"))


def register(app: FastAPI, auth: Callable[..., State]) -> None:
    def setting_view(s: State) -> dict[str, Any]:
        return {"enabled": import_enabled(s), **youtube.status(s.settings.data_dir)}

    @app.get("/v1/settings/youtube-import")
    def youtube_setting(s: State = Depends(auth)) -> dict[str, Any]:
        return setting_view(s)

    @app.put("/v1/settings/youtube-import")
    def put_youtube_setting(body: YoutubeSettingIn, s: State = Depends(auth)) -> dict[str, Any]:
        set_import_enabled(s, body.enabled)
        return setting_view(s)

    @app.post("/v1/media:import-url")
    def import_url(body: ImportUrlIn, s: State = Depends(auth)) -> dict[str, Any]:
        if not import_enabled(s):
            raise HTTPException(403, "YouTube havolasidan import o'chiq - Sozlamalarda yoqing")
        if body.consent is not True:
            raise HTTPException(400, "rozilik kerak: video sizga tegishli yoki ruxsatingiz borligini"
                                     " va YouTube shartlari haqidagi ogohlantirishni tasdiqlang")
        try:
            video_id = youtube.parse_video_id(body.url)
        except youtube.InvalidUrl as e:
            raise HTTPException(400, f"havola noto'g'ri: {e}") from None
        if not s.lib("SELECT id FROM shows WHERE id = ?", (body.project_id,)):
            raise HTTPException(404, "loyiha topilmadi")
        if body.num_speakers is not None and not 1 <= body.num_speakers <= 20:
            raise HTTPException(400, "spikerlar soni 1..20 oralig'ida bo'lishi kerak")
        if youtube.find_ytdlp(youtube.component_paths(s.settings.data_dir)) is None:
            raise HTTPException(409, youtube.MESSAGES["not_installed"])
        if _download_running(s, video_id):
            raise HTTPException(409, "bu video allaqachon yuklanmoqda")

        url = youtube.canonical_url(video_id)
        out_dir = downloads_dir(s, video_id)
        project_id = body.project_id

        def work(job: Job) -> dict[str, Any]:
            def progress(frac: float, info: dict[str, Any]) -> None:
                job.meta["download"] = {k: info.get(k) for k in
                                        ("downloaded_bytes", "total_bytes", "speed", "eta")}
                s.jobs.progress(job, "download", frac)

            def on_info(info: dict[str, Any]) -> None:
                if info.get("title"):
                    job.meta["title"] = info["title"]

            try:
                res = youtube.download(url, out_dir, cancel=job.cancel, on_progress=progress,
                                       on_info=on_info, data_dir=s.settings.data_dir,
                                       keep_partial=lambda: s.jobs.closing)
            except youtube.YoutubeError as e:
                job.meta["error_code"] = e.code
                raise
            title = body.title or safe_title(res.title, video_id)
            eid, pdir = create_episode(s, project_id, res.path, title)
            job.meta["episode_id"] = eid
            analysis = submit_analysis(s, eid, project_id, pdir, res.path, body.focus,
                                       body.num_speakers, body.force_lite, source_url=url)
            return {"episode_id": eid, "analysis_job_id": analysis.id, "path": str(res.path),
                    "title": res.title, "reused": res.reused}

        job = s.jobs.submit("download", work, op="youtube", project_id=project_id, url=url,
                            video_id=video_id)
        return {"job": job.public()}
