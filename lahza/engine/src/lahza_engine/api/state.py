"""API holati: sozlamalar, token, vazifalar, kutubxona bazasi, servislar (bitta engine jarayoni)."""

from __future__ import annotations

import os
import sqlite3
import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from fastapi import HTTPException

from lahza_engine.config import Settings
from lahza_engine.core.batch import AnalysisQueue
from lahza_engine.core.events import EventBus
from lahza_engine.core.jobs import Job, JobManager
from lahza_engine.core.services import Services, build_services
from lahza_engine.db import store as db
from lahza_engine.models import catalog as cat
from lahza_engine.models.store import ModelStore


class State:
    def __init__(self, settings: Settings, token: str) -> None:
        self.settings = settings
        self.token = token
        self.bus = EventBus()
        self.jobs = JobManager(self.bus)
        self.store = ModelStore(settings.models_dir)
        self.library = db.open_library(settings.library_dir)
        self.lib_lock = threading.RLock()
        self._services: Services | None = None
        self._svc_lock = threading.Lock()
        self.capabilities_cache: dict[str, Any] | None = None
        # Eksportni qayta urinish uchun parametrlar: job_id -> (eid, cid, body)
        self.export_params: dict[str, tuple[str, str, Any]] = {}
        # Montaj eksportini qayta urinish uchun: job_id -> (montage_id, body)
        self.montage_export_params: dict[str, tuple[str, Any]] = {}
        # Partiyaviy tahlil navbati (PRO-5): holat library.db'da, qayta ishga tushganda davom etadi.
        self.queue = AnalysisQueue(self, self.jobs, self._start_queue_item)
        self.queue.resume()

    def _start_queue_item(self, item: dict[str, Any], on_change: Callable[[Job], None]) -> Job:
        from lahza_engine.api.routes_queue import start_item

        return start_item(self, item, on_change)

    def services(self, refresh: bool = False) -> Services:
        with self._svc_lock:
            if self._services is None or refresh:
                self._services = build_services(self.store)
                self.capabilities_cache = None
            return self._services

    def peek_services(self) -> Services | None:
        """Allaqachon yig'ilgan servislar (yig'ilmagan bo'lsa None - og'ir yuklashsiz)."""
        return self._services

    def invalidate_services(self) -> None:
        with self._svc_lock:
            self._services = None
            self.capabilities_cache = None

    def catalog(self) -> cat.Catalog:
        path = os.environ.get("LAHZA_CATALOG") or str(
            Path(__file__).resolve().parents[4] / "catalog" / "catalog.json")
        c = cat.load_catalog(path)
        pub = os.environ.get("LAHZA_CATALOG_PUBKEY")
        if pub:
            cat.verify(c, pub)
        elif os.environ.get("LAHZA_DEV") != "1":
            raise HTTPException(500, "katalog ochiq kaliti sozlanmagan (LAHZA_CATALOG_PUBKEY)")
        return c

    def lib(self, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
        with self.lib_lock:
            return self.library.execute(sql, params).fetchall()

    def lib_write(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        with self.lib_lock, self.library:
            return self.library.execute(sql, params)

    def episode_row(self, episode_id: str) -> sqlite3.Row:
        rows = self.lib("SELECT * FROM episodes WHERE id = ?", (episode_id,))
        if not rows:
            raise HTTPException(404, "epizod topilmadi")
        return rows[0]

    def episode_dir(self, episode_id: str) -> Path:
        return Path(self.episode_row(episode_id)["project_dir"])

    @contextmanager
    def project(self, episode_id: str) -> Iterator[sqlite3.Connection]:
        conn = db.open_project(self.episode_dir(episode_id))
        try:
            yield conn
        finally:
            conn.close()
