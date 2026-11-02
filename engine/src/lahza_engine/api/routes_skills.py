"""Authenticated local editing skill installation and saved timeline application."""
from __future__ import annotations

import zipfile

from fastapi import Depends, FastAPI, HTTPException
from pydantic import Field

from lahza_engine.api.state import State
from lahza_engine.editing_skills.apply import apply_saved
from lahza_engine.editing_skills.builtins import BUILTIN_DIR, builtins
from lahza_engine.editing_skills.model import Slug, Strict
from lahza_engine.editing_skills.store import LOCK, SkillStore


class InstallIn(Strict):
    path: str = Field(min_length=1, max_length=4096)
    replace: bool = False


class ApplyIn(Strict):
    montage_id: str = Field(min_length=1, max_length=128)
    title: str = Field("", max_length=500, pattern=r"^[^{}\\\x00-\x08\x0b-\x1f]*$")
    video_id: str | None = Field(None, min_length=1, max_length=128)
    start_ms: int = Field(0, ge=0, le=600_000)
    expected_timeline: str | None = Field(None, pattern=r"^[a-f0-9]{64}$")


def guarded(fn):
    try:
        return fn()
    except FileExistsError as exc:
        raise HTTPException(409, str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(404, "Skill or local file not found") from exc
    except (ValueError, OSError, zipfile.BadZipFile, zipfile.LargeZipFile, RuntimeError) as exc:
        raise HTTPException(400, str(exc)) from exc


def register(app: FastAPI, auth) -> None:
    @app.get("/v1/skills")
    def list_skills(s: State = Depends(auth)):
        def work():
            with LOCK:
                return {"items": SkillStore(s.settings.data_dir).items(),
                        "builtins": [{**b.model_dump(mode="json", by_alias=True),
                                      "path": str(BUILTIN_DIR / (b.id + ".json"))} for b in builtins()]}
        return guarded(work)

    @app.post("/v1/skills:install")
    def install(body: InstallIn, s: State = Depends(auth)):
        return guarded(lambda: SkillStore(s.settings.data_dir).install(body.path, body.replace).model_dump(mode="json", by_alias=True))

    @app.post("/v1/skills/{sid}:apply")
    def apply(sid: Slug, body: ApplyIn, s: State = Depends(auth)):
        return guarded(lambda: apply_saved(s, sid, **body.model_dump()))

    @app.delete("/v1/skills/{sid}")
    def remove(sid: Slug, s: State = Depends(auth)):
        guarded(lambda: SkillStore(s.settings.data_dir).remove(sid))
        return {"ok": True}
