"""Partiyaviy tahlil navbati (PRO-5): bir nechta epizod ketma-ket tahlil qilinadi.

* Navbat `library.db`dagi `analysis_queue` jadvalida saqlanadi (holat, tartib, xato, epizod).
* Bir vaqtda faqat bitta element ishga tushiriladi: keyingisi oldingisi tugagach (done/failed/
  cancelled) yuboriladi. Shuning uchun tartibni o'zgartirish va olib tashlash ishga tushguncha
  ta'sir qiladi, og'ir resurs (GPU/CPU) esa mavjud "heavy" oqimda bittadan ishlatiladi.
* Bitta elementning xatosi navbatni to'xtatmaydi - keyingisi davom etadi.
* Engine qayta ishga tushganda `running` elementlar `queued` ga qaytariladi va navbat davom etadi
  (tahlil bosqichlari keshi tufayli tugagan bosqichlar qayta hisoblanmaydi).

Elementni haqiqiy ishga tushirish (`starter`) API qatlamida - mavjud bitta-epizod oqimi
(`routes_episodes.submit_analysis`) qayta ishlatiladi.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
import uuid
from collections.abc import Callable
from typing import Any, Protocol

from lahza_engine.core.jobs import Job, JobManager

log = logging.getLogger(__name__)

QUEUE_STATUSES = ("queued", "running", "done", "failed", "cancelled")
FINISHED = ("done", "failed", "cancelled")


class QueueConflict(Exception):
    """Amal elementning joriy holatida bajarilmaydi (API: 409)."""


class LibraryDb(Protocol):
    def lib(self, sql: str, params: tuple = ()) -> list[sqlite3.Row]: ...

    def lib_write(self, sql: str, params: tuple = ()) -> sqlite3.Cursor: ...


# (navbat elementi qatori, vazifa holati o'zgarganda chaqiriladigan funksiya) -> analyze vazifasi
Starter = Callable[[dict[str, Any], Callable[[Job], None]], Job]


class AnalysisQueue:
    def __init__(self, db: LibraryDb, jobs: JobManager, starter: Starter) -> None:
        self.db = db
        self.jobs = jobs
        self._starter = starter
        self._lock = threading.RLock()
        self._active: str | None = None  # ishlayotgan element id
        self.recover()

    # ---- tiklanish ------------------------------------------------------------------------
    def recover(self) -> int:
        """Oldingi jarayonda `running` qolgan elementlar -> `queued` (vazifasi xotirada yo'q)."""
        with self._lock:
            cur = self.db.lib_write("UPDATE analysis_queue SET status = 'queued', job_id = NULL,"
                                    " started_at = NULL WHERE status = 'running'")
            n = cur.rowcount or 0
        if n:
            log.info("tahlil navbati: %d ta element qayta navbatga qo'yildi", n)
        return n

    def resume(self) -> None:
        """Navbatdagi birinchi elementni ishga tushiradi (engine ishga tushganda ham chaqiriladi)."""
        self._pump()

    # ---- o'qish ---------------------------------------------------------------------------
    def _row(self, item_id: str) -> sqlite3.Row:
        rows = self.db.lib("SELECT * FROM analysis_queue WHERE id = ?", (item_id,))
        if not rows:
            raise KeyError(item_id)
        return rows[0]

    def public(self, r: sqlite3.Row) -> dict[str, Any]:
        job = self.jobs.jobs.get(r["job_id"]) if r["job_id"] else None
        status = r["status"]
        if status == "done":
            progress = 1.0
        elif job is not None and status == "running":
            progress = job.progress
        else:
            progress = 0.0
        return {
            "id": r["id"], "project_id": r["show_id"], "episode_id": r["episode_id"],
            "path": r["path"], "title": r["title"], "options": json.loads(r["options_json"] or "{}"),
            "position": r["position"], "status": status, "progress": progress,
            "stage": job.stage if job is not None and status == "running" else None,
            "error": r["error"], "job_id": r["job_id"], "created_at": r["created_at"],
            "started_at": r["started_at"], "finished_at": r["finished_at"],
        }

    def get(self, item_id: str) -> dict[str, Any]:
        return self.public(self._row(item_id))

    def list(self, project_id: str | None = None) -> list[dict[str, Any]]:
        """Navbat tartibida (position); tugaganlari ham ko'rsatiladi."""
        sql = "SELECT * FROM analysis_queue"
        params: tuple = ()
        if project_id:
            sql += " WHERE show_id = ?"
            params = (project_id,)
        return [self.public(r) for r in self.db.lib(sql + " ORDER BY position, created_at", params)]

    # ---- o'zgartirish ---------------------------------------------------------------------
    def _next_position(self) -> int:
        row = self.db.lib("SELECT COALESCE(MAX(position), 0) AS m FROM analysis_queue")
        return int(row[0]["m"]) + 1

    def add(self, project_id: str, paths: list[str], options: dict[str, Any] | None = None,
            titles: list[str | None] | None = None) -> list[dict[str, Any]]:
        opts = json.dumps(options or {}, ensure_ascii=False)
        ids: list[str] = []
        with self._lock:
            pos = self._next_position()
            for i, p in enumerate(paths):
                iid = uuid.uuid4().hex[:12]
                title = titles[i] if titles and i < len(titles) else None
                self.db.lib_write("INSERT INTO analysis_queue(id, show_id, path, title, options_json,"
                                  " position) VALUES (?,?,?,?,?,?)",
                                  (iid, project_id, p, title, opts, pos + i))
                ids.append(iid)
        self._publish()
        self._pump()
        return [self.get(i) for i in ids]

    def cancel(self, item_id: str) -> dict[str, Any]:
        with self._lock:
            r = self._row(item_id)
            if r["status"] in FINISHED:
                raise QueueConflict("element allaqachon tugagan")
            if r["status"] == "queued":
                self.db.lib_write("UPDATE analysis_queue SET status = 'cancelled',"
                                  " finished_at = datetime('now') WHERE id = ?", (item_id,))
                self._publish()
            elif r["job_id"] in self.jobs.jobs:
                # Holat vazifa to'xtaganda (`_on_job`) yoziladi.
                self.jobs.cancel(r["job_id"])
            else:
                self._finish(item_id, r["job_id"], "cancelled", None)
        return self.get(item_id)

    def retry(self, item_id: str) -> dict[str, Any]:
        """Xato bilan tugagan yoki bekor qilingan elementni navbat oxiriga qaytaradi."""
        with self._lock:
            r = self._row(item_id)
            if r["status"] not in ("failed", "cancelled"):
                raise QueueConflict("faqat xato bilan tugagan yoki bekor qilingan elementni qayta urinish mumkin")
            self.db.lib_write("UPDATE analysis_queue SET status = 'queued', error = NULL, job_id = NULL,"
                              " started_at = NULL, finished_at = NULL, position = ? WHERE id = ?",
                              (self._next_position(), item_id))
        self._publish()
        self._pump()
        return self.get(item_id)

    def remove(self, item_id: str) -> None:
        with self._lock:
            r = self._row(item_id)
            if r["status"] == "running":
                raise QueueConflict("element tahlil qilinmoqda - avval bekor qiling")
            self.db.lib_write("DELETE FROM analysis_queue WHERE id = ?", (item_id,))
        self._publish()

    def clear_finished(self, project_id: str | None = None) -> int:
        sql = "DELETE FROM analysis_queue WHERE status IN ('done','failed','cancelled')"
        params: tuple = ()
        if project_id:
            sql += " AND show_id = ?"
            params = (project_id,)
        with self._lock:
            n = self.db.lib_write(sql, params).rowcount or 0
        if n:
            self._publish()
        return n

    def reorder(self, ids: list[str]) -> list[dict[str, Any]]:
        """Kutayotgan elementlar tartibi: `ids` birinchi, qolgan kutayotganlar eski tartibda keyin.
        Ishlayotgan va tugagan elementlar o'z joyida qoladi."""
        if len(set(ids)) != len(ids):
            raise ValueError("ro'yxatda takroriy element bor")
        with self._lock:
            queued = [r["id"] for r in self.db.lib(
                "SELECT id FROM analysis_queue WHERE status = 'queued' ORDER BY position, created_at")]
            unknown = [i for i in ids if i not in queued]
            if unknown:
                raise ValueError(f"navbatda kutayotgan element emas: {', '.join(unknown)}")
            order = ids + [i for i in queued if i not in ids]
            base = self._next_position()
            for n, iid in enumerate(order):
                self.db.lib_write("UPDATE analysis_queue SET position = ? WHERE id = ?", (base + n, iid))
        self._publish()
        return self.list()

    # ---- bajarish -------------------------------------------------------------------------
    def _pump(self) -> None:
        with self._lock:
            while self._active is None and not self.jobs.closing:
                rows = self.db.lib("SELECT * FROM analysis_queue WHERE status = 'queued'"
                                   " ORDER BY position, created_at LIMIT 1")
                if not rows:
                    return
                item = dict(rows[0])
                iid = item["id"]
                self.db.lib_write("UPDATE analysis_queue SET status = 'running', error = NULL,"
                                  " started_at = datetime('now'), finished_at = NULL WHERE id = ?", (iid,))
                try:
                    job = self._starter(item, lambda j, _iid=iid: self._on_job(_iid, j))
                except Exception as e:  # noqa: BLE001 - xato elementga yoziladi, navbat davom etadi
                    log.error("navbat elementi %s ishga tushmadi: %s", iid, type(e).__name__)
                    self._finish(iid, None, "failed", str(e) or type(e).__name__)
                    continue
                self._active = iid
                self.db.lib_write("UPDATE analysis_queue SET job_id = ?,"
                                  " episode_id = COALESCE(?, episode_id) WHERE id = ?",
                                  (job.id, job.meta.get("episode_id"), iid))
                self._publish(iid)

    def _on_job(self, item_id: str, job: Job) -> None:
        if job.status not in FINISHED:
            return  # progress - `job` hodisasi orqali; bazaga yozilmaydi
        if self.jobs.closing:
            return  # engine to'xtamoqda: element `running` qoladi va keyingi ishga tushishda tiklanadi
        with self._lock:
            self._finish(item_id, job.id, job.status, job.error)
            if self._active == item_id:
                self._active = None
        self._pump()

    def _finish(self, item_id: str, job_id: str | None, status: str, error: str | None) -> None:
        sql = ("UPDATE analysis_queue SET status = ?, error = ?, finished_at = datetime('now')"
               " WHERE id = ? AND status = 'running'")
        params: tuple = (status, error, item_id)
        if job_id is not None:
            sql += " AND job_id = ?"
            params += (job_id,)
        self.db.lib_write(sql, params)
        if self._active == item_id:
            self._active = None
        self._publish(item_id)

    def _publish(self, item_id: str | None = None) -> None:
        item = None
        if item_id is not None:
            try:
                item = self.get(item_id)
            except KeyError:
                item = None
        self.jobs.bus.publish("queue", item=item)
