"""Authenticated draft-only editing API; no saved timeline or database writes."""
from fastapi import Depends, FastAPI, HTTPException

from lahza_engine.api.state import State
from lahza_engine.editing_agent import planner
from lahza_engine.editing_agent.executor import StalePlan, preview
from lahza_engine.editing_agent.model import PlanIn, PlanOut, PreviewIn, PreviewOut, Status


def guarded(fn):
    try:
        return fn()
    except (StalePlan, planner.Busy) as exc:
        raise HTTPException(409, str(exc)) from exc
    except planner.Unavailable as exc:
        raise HTTPException(503, str(exc)) from exc
    except (ValueError, KeyError) as exc:
        raise HTTPException(422, str(exc)) from exc


def register(app: FastAPI, auth) -> None:
    @app.get("/v1/editing-agent/status", response_model=Status)
    def status(s: State = Depends(auth)):
        return planner.status(s.store)

    @app.post("/v1/editing-agent:plan", response_model=PlanOut)
    def plan(body: PlanIn, s: State = Depends(auth)):
        if body.planner == "claude":
            # Lazy import: lokal rejim Claude ko'prigiga bog'liq emas (docs/15-claude-montaj.md).
            from lahza_engine.api.routes_claude import claude_plan
            return guarded(lambda: claude_plan(body, s))
        return guarded(lambda: planner.plan(body, s.store, s.settings))

    @app.post("/v1/editing-agent:preview", response_model=PreviewOut)
    def apply_preview(body: PreviewIn, s: State = Depends(auth)):
        return guarded(lambda: preview(body.timeline, body.plan, body.selected_video_id, s.settings))
