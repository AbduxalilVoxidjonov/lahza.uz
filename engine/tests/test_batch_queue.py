"""Partiyaviy tahlil navbati (PRO-5): navbat mantig'i (soxta runner), tiklanish, API va CLI."""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

import pytest
from _api_helpers import TOKEN, make_client, wait_job
from fastapi.testclient import TestClient

from lahza_engine.api.app import create_app
from lahza_engine.config import Settings
from lahza_engine.core.batch import AnalysisQueue, QueueConflict
from lahza_engine.core.events import EventBus
from lahza_engine.core.jobs import Job, JobManager
from lahza_engine.core.runner import Cancelled
from lahza_engine.core.services import Services
from lahza_engine.db import store as db


class Lib:
    """`State.lib`/`lib_write` ning minimal o'xshashi."""

    def __init__(self, path: Path) -> None:
        self.conn = db.open_library(path)
        self.lock = threading.RLock()
        with self.conn:
            self.conn.execute("INSERT INTO shows(id, name) VALUES ('s1', 'Shou')")

    def lib(self, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
        with self.lock:
            return self.conn.execute(sql, params).fetchall()

    def lib_write(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        with self.lock, self.conn:
            return self.conn.execute(sql, params)


class FakeRunner:
    """Har element - `heavy` oqimdagi vazifa; `release(path)` chaqirilguncha kutadi."""

    def __init__(self, jobs: JobManager, lib: Lib) -> None:
        self.jobs = jobs
        self.lib = lib
        self.started: list[str] = []
        self.gates: dict[str, threading.Event] = {}
        self.fail: set[str] = set()
        self.fail_start: set[str] = set()
        self.max_parallel = 0
        self._running = 0
        self._lock = threading.Lock()

    def gate(self, path: str) -> threading.Event:
        return self.gates.setdefault(path, threading.Event())

    def release(self, path: str) -> None:
        self.gate(path).set()

    def __call__(self, item: dict[str, Any], on_change) -> Job:
        path = item["path"]
        if path in self.fail_start:
            raise ValueError(f"fayl topilmadi: {path}")
        self.started.append(path)
        gate = self.gate(path)
        eid = f"ep-{path}"  # create_episode o'rnida
        self.lib.lib_write("INSERT OR IGNORE INTO episodes(id, show_id, title, project_dir)"
                           " VALUES (?,?,?,?)", (eid, item["show_id"], path, "/yoq"))

        def work(job: Job) -> dict[str, Any]:
            with self._lock:
                self._running += 1
                self.max_parallel = max(self.max_parallel, self._running)
            try:
                while not gate.wait(0.01):
                    if job.cancel.is_set():
                        raise Cancelled()
                self.jobs.progress(job, "asr", 0.5)
                if path in self.fail:
                    raise RuntimeError("yiqildi")
                return {"path": path}
            finally:
                with self._lock:
                    self._running -= 1

        return self.jobs.submit("analyze", work, on_change=on_change, episode_id=eid)


_MANAGERS: list[JobManager] = []


@pytest.fixture(autouse=True)
def _stop_jobs():
    """Test yiqilsa ham kutayotgan soxta vazifalar to'xtatiladi (aks holda pytest osilib qoladi)."""
    yield
    while _MANAGERS:
        _MANAGERS.pop().shutdown()


def _manager() -> JobManager:
    m = JobManager(EventBus())
    _MANAGERS.append(m)
    return m


def _queue(tmp_path: Path) -> tuple[AnalysisQueue, FakeRunner, Lib]:
    lib = Lib(tmp_path)
    jobs = _manager()
    runner = FakeRunner(jobs, lib)
    return AnalysisQueue(lib, jobs, runner), runner, lib


def _wait(pred, timeout: float = 5.0) -> None:
    end = time.time() + timeout
    while time.time() < end:
        if pred():
            return
        time.sleep(0.01)
    raise TimeoutError


def _statuses(q: AnalysisQueue) -> dict[str, str]:
    return {x["path"]: x["status"] for x in q.list()}


# ---- navbat mantig'i -----------------------------------------------------------------------

def test_sequential_one_at_a_time_and_failure_does_not_stop(tmp_path: Path) -> None:
    q, r, _ = _queue(tmp_path)
    r.fail.add("b")
    items = q.add("s1", ["a", "b", "c"], {"force_lite": True})
    assert [x["status"] for x in items] == ["running", "queued", "queued"]
    assert items[0]["options"] == {"force_lite": True}
    assert r.started == ["a"]
    r.release("a")
    _wait(lambda: _statuses(q)["b"] == "running")
    assert _statuses(q)["a"] == "done"
    r.release("b")
    r.release("c")
    _wait(lambda: _statuses(q)["c"] == "done")
    st = {x["path"]: x for x in q.list()}
    assert st["b"]["status"] == "failed" and st["b"]["error"] == "yiqildi"
    assert st["a"]["episode_id"] == "ep-a" and st["a"]["progress"] == 1.0
    assert r.started == ["a", "b", "c"] and r.max_parallel == 1
    q.jobs.shutdown()


def test_start_error_marks_failed_and_continues(tmp_path: Path) -> None:
    q, r, _ = _queue(tmp_path)
    r.fail_start.add("yoq")
    q.add("s1", ["yoq", "a"])
    st = {x["path"]: x for x in q.list()}
    assert st["yoq"]["status"] == "failed" and "fayl topilmadi" in st["yoq"]["error"]
    assert st["a"]["status"] == "running"
    r.release("a")
    _wait(lambda: _statuses(q)["a"] == "done")
    q.jobs.shutdown()


def test_reorder_remove_cancel_retry(tmp_path: Path) -> None:
    q, r, _ = _queue(tmp_path)
    items = q.add("s1", ["a", "b", "c", "d"])
    ids = {x["path"]: x["id"] for x in items}
    # Ishlayotgan elementni tartiblab/olib tashlab bo'lmaydi.
    with pytest.raises(ValueError, match="kutayotgan"):
        q.reorder([ids["a"]])
    with pytest.raises(ValueError, match="takroriy"):
        q.reorder([ids["c"], ids["c"]])
    with pytest.raises(QueueConflict):
        q.remove(ids["a"])
    # d birinchi, qolganlari eski tartibda.
    order = [x["path"] for x in q.reorder([ids["d"]]) if x["status"] == "queued"]
    assert order == ["d", "b", "c"]
    q.remove(ids["b"])
    with pytest.raises(KeyError):
        q.get(ids["b"])
    assert q.cancel(ids["c"])["status"] == "cancelled"
    with pytest.raises(QueueConflict):
        q.cancel(ids["c"])
    # Ishlayotgan elementni bekor qilish - vazifa to'xtaydi, navbat davom etadi.
    q.cancel(ids["a"])
    _wait(lambda: _statuses(q)["a"] == "cancelled")
    _wait(lambda: _statuses(q)["d"] == "running")
    assert r.started == ["a", "d"]
    # Qayta urinish: oxiriga qo'yiladi.
    with pytest.raises(QueueConflict):
        q.retry(ids["d"])
    assert q.retry(ids["c"])["status"] == "queued"
    r.release("d")
    r.release("c")
    _wait(lambda: _statuses(q)["c"] == "done")
    assert r.started == ["a", "d", "c"]
    assert q.clear_finished() == 3
    assert q.list() == []
    q.jobs.shutdown()


def test_events_published(tmp_path: Path) -> None:
    q, r, _ = _queue(tmp_path)
    seen: list[dict] = []
    q.jobs.bus.publish = lambda type_, **data: seen.append({"type": type_, **data})  # type: ignore[method-assign]
    q.add("s1", ["a"])
    r.release("a")
    _wait(lambda: _statuses(q)["a"] == "done")
    kinds = [e["type"] for e in seen]
    assert "queue" in kinds and "job" in kinds
    last = [e for e in seen if e["type"] == "queue" and e["item"]][-1]
    assert last["item"]["status"] == "done"
    q.jobs.shutdown()


# ---- tiklanish -----------------------------------------------------------------------------

def test_recover_running_to_queued(tmp_path: Path) -> None:
    q, r, lib = _queue(tmp_path)
    q.add("s1", ["a", "b"])
    assert _statuses(q) == {"a": "running", "b": "queued"}
    # Engine to'xtaydi: bekor qilingan vazifa elementni `cancelled` qilmasligi kerak.
    q.jobs.shutdown()
    time.sleep(0.1)
    assert _statuses(q)["a"] == "running"
    # Yangi jarayon: o'sha baza, yangi JobManager.
    jobs2 = _manager()
    r2 = FakeRunner(jobs2, lib)
    q2 = AnalysisQueue(lib, jobs2, r2)
    assert _statuses(q2) == {"a": "queued", "b": "queued"}
    q2.resume()
    assert r2.started == ["a"]
    a = next(x for x in q2.list() if x["path"] == "a")
    assert a["episode_id"] == "ep-a"
    r2.release("a")
    r2.release("b")
    _wait(lambda: _statuses(q2) == {"a": "done", "b": "done"})
    jobs2.shutdown()


# ---- API ----------------------------------------------------------------------------------

def _videos(tmp_path: Path, n: int) -> list[str]:
    out = []
    for i in range(n):
        p = tmp_path / f"video{i}.mp4"
        p.write_bytes(bytes([i]) * 2048)
        out.append(str(p))
    return out


def _fake_analyze(monkeypatch, fail: set[str] | None = None, gate: threading.Event | None = None):
    seen: list[dict] = []

    def fake(ctx, settings):
        if gate is not None:
            while not gate.wait(0.01):
                ctx.check_cancel()
        seen.append(dict(ctx.services))
        ctx.on_progress("asr", 0.5)
        if fail and Path(ctx.services["src"]).name in fail:
            raise RuntimeError("ASR yiqildi")
        return {"highlight": {"mode": "lite", "clips": ["x"]}}

    monkeypatch.setattr("lahza_engine.core.analyze.analyze", fake)
    return seen


def _wait_queue(c, pred, timeout: float = 10.0) -> list[dict]:
    end = time.time() + timeout
    while time.time() < end:
        items = c.get("/v1/queue").json()
        if pred(items):
            return items
        time.sleep(0.02)
    raise TimeoutError([(x["status"], x["error"]) for x in items])


def _client(tmp_path: Path, monkeypatch):
    c, st = make_client(tmp_path, monkeypatch)
    _MANAGERS.append(st.jobs)
    return c, st


def test_api_queue_flow(tmp_path: Path, monkeypatch) -> None:
    c, st = _client(tmp_path, monkeypatch)
    seen = _fake_analyze(monkeypatch, fail={"video1.mp4"})
    pid = c.post("/v1/projects", json={"name": "Shou"}).json()["id"]
    paths = _videos(tmp_path, 3)
    r = c.post("/v1/queue", json={"project_id": pid, "paths": paths, "focus": "biznes",
                                  "force_lite": True})
    assert r.status_code == 200
    assert len(r.json()) == 3 and r.json()[0]["project_id"] == pid
    items = _wait_queue(c, lambda xs: all(x["status"] in ("done", "failed") for x in xs))
    assert [x["status"] for x in items] == ["done", "failed", "done"]
    assert items[1]["error"] == "ASR yiqildi"
    assert all(s["focus"] == "biznes" and s["force_lite"] is True for s in seen)
    # Har element mavjud import oqimi orqali epizod yaratadi.
    eps = c.get(f"/v1/projects/{pid}/episodes").json()
    assert len(eps) == 3
    by_id = {e["id"]: e for e in eps}
    assert by_id[items[0]["episode_id"]]["status"] == "ready"
    assert by_id[items[1]["episode_id"]]["status"] == "failed"
    assert by_id[items[0]["episode_id"]]["title"] == "video0"
    job = st.jobs.jobs[items[0]["job_id"]]
    assert job.kind == "analyze" and job.meta["queue_item_id"] == items[0]["id"]
    # Filtr va tozalash.
    assert c.get("/v1/queue", params={"project_id": "boshqa"}).json() == []
    # Qayta urinish xuddi shu epizodni qayta tahlil qiladi (yangi epizod yaratilmaydi).
    _fake_analyze(monkeypatch)
    assert c.post(f"/v1/queue/{items[1]['id']}:retry").status_code == 200
    items = _wait_queue(c, lambda xs: all(x["status"] == "done" for x in xs))
    assert len(c.get(f"/v1/projects/{pid}/episodes").json()) == 3
    assert c.post("/v1/queue:clear", json={}).json() == {"removed": 3}
    assert c.get("/v1/queue").json() == []


def test_api_queue_validation_and_errors(tmp_path: Path, monkeypatch) -> None:
    c, _ = _client(tmp_path, monkeypatch)
    gate = threading.Event()
    _fake_analyze(monkeypatch, gate=gate)
    pid = c.post("/v1/projects", json={"name": "Shou"}).json()["id"]
    paths = _videos(tmp_path, 3)
    assert c.post("/v1/queue", json={"project_id": "yoq", "paths": paths}).status_code == 404
    r = c.post("/v1/queue", json={"project_id": pid, "paths": [" "]})
    assert r.status_code == 400 and r.json()["detail"] == "fayllar ro'yxati bo'sh"
    r = c.post("/v1/queue", json={"project_id": pid, "paths": [paths[0], "/yoq/x.mp4"]})
    assert r.status_code == 400 and "/yoq/x.mp4" in r.json()["detail"]
    assert c.get("/v1/queue").json() == []  # qisman qo'shilmaydi
    assert c.post("/v1/queue", json={"project_id": pid, "paths": paths,
                                     "num_speakers": 99}).status_code == 400

    items = c.post("/v1/queue", json={"project_id": pid, "paths": paths}).json()
    a, b, d = (x["id"] for x in items)
    assert c.delete(f"/v1/queue/{a}").status_code == 409
    assert c.delete("/v1/queue/yoq").status_code == 404
    assert c.post("/v1/queue/yoq:cancel").status_code == 404
    r = c.post("/v1/queue:reorder", json={"ids": [a]})
    assert r.status_code == 400 and "kutayotgan" in r.json()["detail"]
    order = [x["id"] for x in c.post("/v1/queue:reorder", json={"ids": [d, b]}).json()]
    assert order == [a, d, b]
    assert c.delete(f"/v1/queue/{b}").json() == {"ok": True}
    assert c.post(f"/v1/queue/{a}:cancel").status_code == 200
    _wait_queue(c, lambda xs: xs[0]["status"] == "cancelled")
    gate.set()
    items = _wait_queue(c, lambda xs: [x["status"] for x in xs] == ["cancelled", "done"])
    assert c.post(f"/v1/queue/{d}:cancel").status_code == 409
    assert c.post(f"/v1/queue/{d}:retry").status_code == 409


def test_api_queue_restart_recovery(tmp_path: Path, monkeypatch) -> None:
    """Engine qayta ishga tushganda `running` -> `queued` va navbat avtomatik davom etadi."""
    c, st = _client(tmp_path, monkeypatch)
    gate = threading.Event()
    _fake_analyze(monkeypatch, gate=gate)
    pid = c.post("/v1/projects", json={"name": "Shou"}).json()["id"]
    paths = _videos(tmp_path, 2)
    items = c.post("/v1/queue", json={"project_id": pid, "paths": paths}).json()
    first_ep = _wait_queue(c, lambda xs: xs[0]["episode_id"] is not None)[0]["episode_id"]
    st.jobs.shutdown()  # jarayon to'xtaydi (lifespan)
    time.sleep(0.1)
    # Eski oqim hali lib_write qilayotgan bo'lishi mumkin: yozuv o'rtasida yopish Windows'da qulatadi.
    with st.lib_lock:
        st.library.close()
    seen = _fake_analyze(monkeypatch)
    app2 = create_app(Settings(data_dir=tmp_path / "data"), token=TOKEN)
    st2 = app2.state.lahza
    _MANAGERS.append(st2.jobs)
    st2._services = Services()
    c2 = TestClient(app2)
    c2.headers["Authorization"] = f"Bearer {TOKEN}"
    done = _wait_queue(c2, lambda xs: all(x["status"] == "done" for x in xs))
    assert [x["id"] for x in done] == [x["id"] for x in items]
    # Tiklangan element o'sha epizodni davom ettiradi (yangisini yaratmaydi).
    assert done[0]["episode_id"] == first_ep
    assert len(c2.get(f"/v1/projects/{pid}/episodes").json()) == 2
    assert len(seen) == 2
    st2.jobs.shutdown()


def test_reanalyze_conflict_while_queue_runs(tmp_path: Path, monkeypatch) -> None:
    c, st = _client(tmp_path, monkeypatch)
    gate = threading.Event()
    _fake_analyze(monkeypatch, gate=gate)
    pid = c.post("/v1/projects", json={"name": "Shou"}).json()["id"]
    items = c.post("/v1/queue", json={"project_id": pid, "paths": _videos(tmp_path, 1)}).json()
    eid = items[0]["episode_id"]
    assert eid
    assert c.post(f"/v1/episodes/{eid}:reanalyze").status_code == 409
    gate.set()
    wait_job(st, items[0]["job_id"])


# ---- CLI ----------------------------------------------------------------------------------

def test_cli_batch(tmp_path: Path, monkeypatch, capsys) -> None:
    from lahza_engine import cli

    monkeypatch.setenv("LAHZA_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setattr(cli, "_build_services", lambda settings: object())
    seen = _fake_analyze(monkeypatch, fail={"video1.mp4"})
    paths = _videos(tmp_path, 3)
    out = tmp_path / "out"
    code = cli.main(["batch", paths[0], paths[1], str(tmp_path / "yoq.mp4"), paths[2], paths[0],
                     "--out-dir", str(out), "--lite", "--focus", "texnologiya"])
    assert code == 1
    res = json.loads(capsys.readouterr().out)
    assert [x["status"] for x in res["items"]] == ["done", "failed", "failed", "done", "done"]
    assert res["done"] == 3 and res["failed"] == 2 and res["cancelled"] == 0
    assert res["items"][2]["error"] == "fayl topilmadi"
    assert res["items"][1]["error"] == "ASR yiqildi"
    # Bir xil nomli fayl alohida papkaga.
    assert res["items"][0]["project_dir"] == str(out / "video0.lahza")
    assert res["items"][4]["project_dir"] == str(out / "video0-2.lahza")
    assert (out / "video0.lahza" / "project.db").exists()
    assert all(s["force_lite"] is True and s["focus"] == "texnologiya" for s in seen)

    seen.clear()
    assert cli.main(["batch", paths[0], "--out-dir", str(out)]) == 0
    assert json.loads(capsys.readouterr().out)["done"] == 1


def test_cli_batch_interrupt_cancels_rest(tmp_path: Path, monkeypatch, capsys) -> None:
    from lahza_engine import cli

    monkeypatch.setenv("LAHZA_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setattr(cli, "_build_services", lambda settings: object())

    def interrupt(ctx, settings):
        raise KeyboardInterrupt

    monkeypatch.setattr("lahza_engine.core.analyze.analyze", interrupt)
    paths = _videos(tmp_path, 3)
    assert cli.main(["batch", *paths, "--out-dir", str(tmp_path / "o")]) == 1
    res = json.loads(capsys.readouterr().out)
    assert res["cancelled"] == 3 and res["done"] == 0
