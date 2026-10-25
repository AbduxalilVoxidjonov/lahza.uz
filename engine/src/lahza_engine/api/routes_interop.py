"""Authenticated local external-asset inspection. Timeline apply uses existing PUT API."""
from collections.abc import Callable
from xml.etree.ElementTree import ParseError
from zipfile import BadZipFile
from zlib import error as ZlibError

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, Field

from lahza_engine.api.state import State
from lahza_engine.interop import inspect_asset


class InspectIn(BaseModel):
    path: str = Field(min_length=1, max_length=4096)


def register(app: FastAPI, auth: Callable) -> None:
    @app.post('/v1/interop/inspect')
    def inspect(body: InspectIn, s: State = Depends(auth)) -> dict:
        try:
            return inspect_asset(body.path)
        except (OSError, ValueError, ParseError, BadZipFile, RuntimeError, NotImplementedError, EOFError, ZlibError) as exc:
            raise HTTPException(400, f'Asset inspection failed: {exc}') from exc
