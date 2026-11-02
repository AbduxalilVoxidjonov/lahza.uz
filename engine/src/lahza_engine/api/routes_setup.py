"""First launch setup: GET is offline; POST requires literal JSON consent=true."""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, StrictBool

from lahza_engine.api.state import State
from lahza_engine.models.setup import coordinator


class SetupIn(BaseModel):
    consent: StrictBool


def register(app: FastAPI, auth: Callable[..., State]) -> None:
    @app.get("/v1/setup")
    def status(s: State = Depends(auth)) -> dict[str, Any]:
        return coordinator(s.store, s.jobs).status()

    @app.post("/v1/setup:start")
    def start(body: SetupIn, s: State = Depends(auth)) -> dict[str, Any]:
        if body.consent is not True:
            raise HTTPException(400, "Yuklash uchun consent=true roziligi kerak.")
        try:
            setup = coordinator(s.store, s.jobs)
            job = setup.start(s.invalidate_services)
            # Concurrent API States still expose the shared job through standard endpoints.
            s.jobs.jobs[job.id] = job
            return job.public()
        except (RuntimeError, OSError, ValueError) as exc:
            raise HTTPException(409, str(exc)) from exc
