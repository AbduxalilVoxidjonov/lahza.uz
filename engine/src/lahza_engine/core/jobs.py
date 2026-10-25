"""Vazifalar navbati: og'ir ishlar fon oqimlarida, holati xotirada (TZ 3-bo'lim, NFR-04).

Tahlil va montaj rejalashtirish (`montage`) vazifalari bitta oqimda (GPU'da bir vaqtda bitta og'ir
model), eksport (klip va montaj render) - alohida oqimlarda
(soni `LAHZA_EXPORT_WORKERS`, standart 2), model o'rnatish va .lzpack - alohida I/O oqimida.
"""

from __future__ import annotations

import copy
import logging
import os
import threading
import time
import traceback
import uuid
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field, fields
from typing import Any

from lahza_engine.core.events import EventBus
from lahza_engine.core.runner import Cancelled

log = logging.getLogger(__name__)
DEFAULT_EXPORT_WORKERS = 2


def export_workers_from_env() -> int:
    try:
        n = int(os.environ.get("LAHZA_EXPORT_WORKERS", DEFAULT_EXPORT_WORKERS))
    except ValueError:
        n = DEFAULT_EXPORT_WORKERS
    return max(1, min(8, n))


@dataclass
class Job:
    id: str
    kind: str  # analyze | export | install | pack | montage
    status: str = "queued"  # queued | running | done | failed | cancelled
    progress: float = 0.0
    stage: str | None = None
    error: str | None = None
    result: dict[str, Any] | None = None
    meta: dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    on_change: Callable[[Job], None] | None = field(default=None, repr=False)
    cancel: threading.Event = field(default_factory=threading.Event, repr=False)

    def public(self) -> dict[str, Any]:
        # asdict() threading.Event'ni nusxalay olmaydi - maydonlar qo'lda olinadi.
        return {f.name: copy.deepcopy(getattr(self, f.name)) for f in fields(self)
                if f.name not in ("cancel", "on_change")}


class JobManager:
    def __init__(self, bus: EventBus, export_workers: int | None = None) -> None:
        self.bus = bus
        self.jobs: dict[str, Job] = {}
        self.export_workers = export_workers or export_workers_from_env()
        self._heavy = ThreadPoolExecutor(max_workers=1, thread_name_prefix="heavy")
        self._export = ThreadPoolExecutor(max_workers=self.export_workers, thread_name_prefix="export")
        self._io = ThreadPoolExecutor(max_workers=1, thread_name_prefix="io")
        self._lock = threading.Lock()

    def submit(self, kind: str, fn: Callable[[Job], dict[str, Any] | None],
               *, on_change: Callable[[Job], None] | None = None, **meta: Any) -> Job:
        job = Job(id=uuid.uuid4().hex[:12], kind=kind, meta=meta, on_change=on_change)
        with self._lock:
            self.jobs[job.id] = job
        pool = {"export": self._export, "install": self._io, "pack": self._io}.get(kind, self._heavy)
        self._notify(job)
        future = pool.submit(self._run, job, fn)

        def cancelled_before_run(future: Future) -> None:
            if future.cancelled():
                job.status = "cancelled"
                self._notify(job)

        future.add_done_callback(cancelled_before_run)
        return job

    def _notify(self, job: Job) -> None:
        if job.on_change is not None:
            job.on_change(job)
        self.bus.publish("job", job=job.public())

    def _run(self, job: Job, fn: Callable[[Job], dict[str, Any] | None]) -> None:
        if job.cancel.is_set():
            job.status = "cancelled"
            self._notify(job)
            return
        job.status = "running"
        self._notify(job)
        try:
            job.result = fn(job) or {}
            job.status, job.progress = "done", 1.0
        except Cancelled:
            job.status = "cancelled"
        except Exception as e:  # noqa: BLE001 - xato foydalanuvchiga ko'rsatiladi
            job.status = "failed"
            job.error = str(e) or type(e).__name__
            job.meta["trace"] = traceback.format_exc(limit=8)
            # NFR-02: logga faqat turi va joyi; xabar matnida transkript bo'lishi mumkin.
            log.error("vazifa %s (%s) xato bilan tugadi: %s", job.id, job.kind, type(e).__name__)
        self._notify(job)

    def progress(self, job: Job, stage: str, frac: float) -> None:
        job.stage, job.progress = stage, round(frac, 4)
        self._notify(job)

    def list_jobs(self, kind: str | None = None) -> list[Job]:
        """Yangisi oldin."""
        with self._lock:
            items = list(self.jobs.values())
        items = [j for j in items if kind is None or j.kind == kind]
        return sorted(items, key=lambda j: j.created_at, reverse=True)

    def cancel(self, job_id: str) -> Job:
        job = self.jobs[job_id]
        job.cancel.set()
        return job

    def shutdown(self) -> None:
        for j in self.jobs.values():
            j.cancel.set()
        self._heavy.shutdown(wait=False, cancel_futures=True)
        self._export.shutdown(wait=False, cancel_futures=True)
        self._io.shutdown(wait=False, cancel_futures=True)
