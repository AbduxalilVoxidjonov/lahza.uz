"""Authenticated local sticker catalog and actual decode inspection."""
from collections.abc import Callable

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, Field

from lahza_engine.api.state import State
from lahza_engine.stickers import StickerError, inspect_sticker, list_stickers


class InspectIn(BaseModel):
    path: str = Field(min_length=1, max_length=4096)


def register(app: FastAPI, auth: Callable[..., State]) -> None:
    @app.get("/v1/stickers")
    def catalog(s: State = Depends(auth)) -> dict:
        return list_stickers(s.settings.data_dir / "Assets" / "stickers")

    @app.post("/v1/stickers:inspect")
    def inspect(body: InspectIn, s: State = Depends(auth)) -> dict:
        try:
            return inspect_sticker(body.path)
        except StickerError as exc:
            raise HTTPException(400, str(exc)) from exc
