"""`enabled` sozlamasi (`library.db` -> `settings`, `youtube_import` bilan bir xil usul) va
oxirgi auth tekshiruvi natijasi (faqat xotirada; e-pochta va tokenlar saqlanmaydi)."""

from __future__ import annotations

import json
import threading
from datetime import UTC, datetime
from typing import Any

SETTING_KEY = "claude_montage"
AUTH_STATES = ("unknown", "ok", "not_logged_in", "error")


def is_enabled(s: Any) -> bool:
    rows = s.lib("SELECT value_json FROM settings WHERE key = ?", (SETTING_KEY,))
    if not rows:
        return False
    try:
        return json.loads(rows[0]["value_json"]).get("enabled") is True
    except (ValueError, AttributeError):
        return False


def set_enabled(s: Any, enabled: bool) -> None:
    s.lib_write("INSERT INTO settings(key, value_json) VALUES (?, ?) ON CONFLICT(key)"
                " DO UPDATE SET value_json = excluded.value_json",
                (SETTING_KEY, json.dumps({"enabled": enabled})))
    if not enabled:
        reset_auth()


_lock = threading.Lock()
_auth: dict[str, Any] = {"state": "unknown", "detail": None, "checked_at": None}


def auth() -> dict[str, Any]:
    with _lock:
        return dict(_auth)


def set_auth(state: str, detail: str | None) -> dict[str, Any]:
    assert state in AUTH_STATES
    with _lock:
        _auth.update(state=state, detail=detail,
                     checked_at=datetime.now(UTC).isoformat(timespec="seconds"))
        return dict(_auth)


def reset_auth() -> None:
    with _lock:
        _auth.update(state="unknown", detail=None, checked_at=None)
