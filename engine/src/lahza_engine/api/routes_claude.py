"""Claude montaj API (docs/15-claude-montaj.md, docs/04-engine-api.md "Claude").

Funksiya standart holatda O'CHIQ. Xatolar `detail` = `"kod: xabar"`; kodlar `claude_disabled`,
`claude_not_installed`, `claude_not_logged_in`, `claude_timeout`, `claude_bad_plan`, `claude_busy`,
`claude_cancelled`, `claude_config_invalid`, `claude_error`.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Literal

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel

from lahza_engine.api.state import State
from lahza_engine.claude_bridge import ClaudeError, connect, detect, planner, store
from lahza_engine.editing_agent.model import PlanIn, PlanOut


class ClaudeSettingsIn(BaseModel):
    enabled: bool


class ConnectIn(BaseModel):
    target: Literal["claude_code", "claude_desktop"]
    dry_run: bool = False


def http_error(e: ClaudeError) -> HTTPException:
    return HTTPException(e.http_status, e.detail)


def require_enabled(s: State) -> None:
    if not store.is_enabled(s):
        raise http_error(ClaudeError("claude_disabled", "Claude montaj o'chiq - Sozlamalarda yoqing"))


def status_view(s: State, refresh: bool = False) -> dict[str, Any]:
    det = detect.detect(refresh=refresh)
    command, _ = connect.mcp_command(s.settings.data_dir)
    return {"enabled": store.is_enabled(s), **det.to_dict(), "auth": store.auth(),
            "mcp": {"claude_code": connect.claude_code_connected(),
                    "claude_desktop": connect.claude_desktop_connected()},
            "mcp_command": command}


def claude_plan(body: PlanIn, s: State) -> PlanOut:
    """`POST /v1/editing-agent:plan` `planner: "claude"` tarmog'i."""
    require_enabled(s)
    try:
        return planner.plan(body, detect.detect().cli.path, s.settings)
    except ClaudeError as e:
        if e.code == "claude_not_logged_in":
            store.set_auth("not_logged_in", str(e))
        raise http_error(e) from e


def register(app: FastAPI, auth: Callable[..., State]) -> None:
    @app.get("/v1/claude/status")
    def claude_status(refresh: bool = False, s: State = Depends(auth)) -> dict[str, Any]:
        return status_view(s, refresh)

    @app.put("/v1/claude/settings")
    def claude_settings(body: ClaudeSettingsIn, s: State = Depends(auth)) -> dict[str, Any]:
        store.set_enabled(s, body.enabled)
        return status_view(s)

    @app.post("/v1/claude/check-auth")
    def claude_check_auth(s: State = Depends(auth)) -> dict[str, Any]:
        require_enabled(s)
        try:
            state, detail = planner.check_auth(detect.detect(refresh=True).cli.path)
        except ClaudeError as e:
            if e.code != "claude_timeout":
                raise http_error(e) from e
            state, detail = "error", e.detail
        store.set_auth(state, detail)
        return status_view(s)

    def mcp_change(body: ConnectIn, s: State, connecting: bool) -> dict[str, Any]:
        require_enabled(s)
        command, env = connect.mcp_command(s.settings.data_dir)
        try:
            if body.target == "claude_code":
                actions = connect.run_claude_code(detect.detect().cli.path, command, env, connecting,
                                                  body.dry_run)
            else:
                if not detect.detect().desktop.installed:
                    raise ClaudeError("claude_not_installed", "Claude Desktop topilmadi")
                actions = connect.run_claude_desktop(command, env, connecting, body.dry_run)
        except ClaudeError as e:
            raise http_error(e) from e
        except OSError as e:
            raise http_error(ClaudeError("claude_error", f"konfiguratsiya yozilmadi: {e}")) from e
        return {"actions": actions, "status": status_view(s)}

    @app.post("/v1/claude/connect")
    def claude_connect(body: ConnectIn, s: State = Depends(auth)) -> dict[str, Any]:
        return mcp_change(body, s, True)

    @app.post("/v1/claude/disconnect")
    def claude_disconnect(body: ConnectIn, s: State = Depends(auth)) -> dict[str, Any]:
        return mcp_change(body, s, False)

    @app.post("/v1/claude/cancel")
    def claude_cancel(s: State = Depends(auth)) -> dict[str, bool]:
        return {"cancelled": planner.cancel()}
