"""Bosqichlarni ketma-ket bajaruvchi: kesh, qayta ishga tushirish, bekor qilish (TZ 4-bo'lim, NFR-05)."""

from __future__ import annotations

import json
import sqlite3
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from lahza_engine.core.cache import param_hash, stage_key


class Cancelled(Exception):
    pass


@dataclass
class StageDef:
    name: str
    version: int
    fn: Callable[[StageContext], dict[str, Any]]
    params: Callable[[StageContext], dict[str, Any]] = lambda ctx: {}
    model_id: Callable[[StageContext], str | None] = lambda ctx: None
    weight: float = 1.0  # umumiy progressdagi ulushi


@dataclass
class StageContext:
    media_id: str
    media_hash: str
    project_dir: Path
    conn: sqlite3.Connection
    results: dict[str, dict[str, Any]] = field(default_factory=dict)
    services: dict[str, Any] = field(default_factory=dict)
    cancel: threading.Event = field(default_factory=threading.Event)
    on_progress: Callable[[str, float], None] = lambda stage, frac: None

    @property
    def cache_dir(self) -> Path:
        d = self.project_dir / "cache"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def check_cancel(self) -> None:
        if self.cancel.is_set():
            raise Cancelled()


def run_stages(stages: list[StageDef], ctx: StageContext) -> dict[str, dict[str, Any]]:
    upstream: list[str] = []
    total = sum(s.weight for s in stages) or 1.0
    done_w = 0.0
    for st in stages:
        ctx.check_cancel()
        params = st.params(ctx)
        model_id = st.model_id(ctx)
        key = stage_key(ctx.media_hash, st.name, st.version, model_id, params, upstream)
        row = ctx.conn.execute(
            "SELECT status, cache_key, result_path FROM stage_runs WHERE media_id = ? AND stage = ?",
            (ctx.media_id, st.name),
        ).fetchone()
        cached = None
        if row and row["status"] == "done" and row["cache_key"] == key and row["result_path"]:
            p = Path(row["result_path"])
            if p.exists():
                cached = json.loads(p.read_text(encoding="utf-8"))
        if cached is not None:
            ctx.results[st.name] = cached
        else:
            with ctx.conn:
                ctx.conn.execute(
                    "INSERT OR REPLACE INTO stage_runs(media_id, stage, version, model_id, param_hash,"
                    " cache_key, status) VALUES (?,?,?,?,?,?,'running')",
                    (ctx.media_id, st.name, st.version, model_id, param_hash(params), key),
                )
            base = done_w

            def prog(frac: float, _base: float = base, _w: float = st.weight, _n: str = st.name) -> None:
                ctx.on_progress(_n, (_base + _w * max(0.0, min(1.0, frac))) / total)

            ctx.services["progress"] = prog
            try:
                result = st.fn(ctx)
            except Cancelled:
                _finish(ctx, st.name, "cancelled", None, None)
                raise
            except Exception as e:
                _finish(ctx, st.name, "failed", None, f"{type(e).__name__}: {e}")
                raise
            out = ctx.cache_dir / f"{st.name}-{key[:12]}.json"
            out.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
            _finish(ctx, st.name, "done", str(out), None)
            ctx.results[st.name] = result
        upstream.append(key)
        done_w += st.weight
        ctx.on_progress(st.name, done_w / total)
    return ctx.results


def _finish(ctx: StageContext, stage: str, status: str, path: str | None, error: str | None) -> None:
    with ctx.conn:
        ctx.conn.execute(
            "UPDATE stage_runs SET status = ?, result_path = ?, error = ?, finished_at = datetime('now')"
            " WHERE media_id = ? AND stage = ?",
            (status, path, error, ctx.media_id, stage),
        )
