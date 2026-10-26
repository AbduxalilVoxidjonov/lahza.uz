"""Litsenziya (V1-3, ADR-0016): holat, kalit kiritish, o'chirish. Tarmoqsiz (NFR-01).

Bayroq o'chiq bo'lsa (`Settings.licensing_enabled`, standart) GET `{"enabled": false,
"state": "disabled"}` qaytaradi, kiritish 409 beradi va hech narsa bloklanmaydi.
Holat kutubxona bazasidagi mavjud `settings` (key/value_json) jadvalida saqlanadi.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, Field

from lahza_engine import __version__
from lahza_engine.api.state import State
from lahza_engine.licensing import keys
from lahza_engine.licensing.device import device_fingerprint
from lahza_engine.licensing.keyformat import LicenseError
from lahza_engine.licensing.manager import DISABLED, LicenseManager


class LicenseIn(BaseModel):
    key: str = Field(min_length=1, max_length=4000)


class LibrarySettingsStore:
    """`settings` jadvali ustidagi kalit-qiymat ombori."""

    def __init__(self, s: State) -> None:
        self.s = s

    def get(self, key: str) -> dict[str, Any] | None:
        rows = self.s.lib("SELECT value_json FROM settings WHERE key = ?", (key,))
        if not rows:
            return None
        try:
            v = json.loads(rows[0]["value_json"])
        except ValueError:
            return None
        return v if isinstance(v, dict) else None

    def set(self, key: str, value: dict[str, Any]) -> None:
        self.s.lib_write("INSERT INTO settings(key, value_json) VALUES (?, ?) "
                         "ON CONFLICT(key) DO UPDATE SET value_json = excluded.value_json",
                         (key, json.dumps(value, ensure_ascii=False)))

    def delete(self, key: str) -> None:
        self.s.lib_write("DELETE FROM settings WHERE key = ?", (key,))


def manager(s: State) -> LicenseManager:
    return LicenseManager(LibrarySettingsStore(s), enabled=s.settings.licensing_enabled,
                          public_keys=keys.trusted_keys(), app_version=__version__,
                          device_id=device_fingerprint)


def register(app: FastAPI, auth: Callable[..., State]) -> None:
    @app.get("/v1/license")
    def get_license(s: State = Depends(auth)) -> dict[str, Any]:
        return manager(s).status()

    @app.put("/v1/license")
    def put_license(body: LicenseIn, s: State = Depends(auth)) -> dict[str, Any]:
        m = manager(s)
        try:
            return m.activate(body.key)
        except LicenseError as e:
            code = 409 if e.code == DISABLED else 400
            # `detail` - "kod: xabar" (UI kod bo'yicha tarjima qiladi, app/src/lib/license-key.ts)
            raise HTTPException(code, f"{e.code}: {e}") from e

    @app.delete("/v1/license")
    def delete_license(s: State = Depends(auth)) -> dict[str, Any]:
        m = manager(s)
        if not m.enabled:
            raise HTTPException(409, f"{DISABLED}: litsenziyalash o'chiq")
        return m.deactivate()
