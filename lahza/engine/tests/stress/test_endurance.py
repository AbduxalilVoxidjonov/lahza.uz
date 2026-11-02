"""V1-1 chidamlilik testlari: (a) 4 soatlik video to'liq pipeline, (b) navbatda 20 epizod.

ASR va LLM soxta (tez, deterministik), qolgan hamma narsa haqiqiy: ffmpeg dekod/proksi, energiya
VAD, normallashtirish, gaplar, signallar, highlight finder, SQLite, vazifalar navbati va eksport.
Natija JSON hisobotga yoziladi (`LAHZA_STRESS_REPORT`, conftest.py ga qarang).
"""

from __future__ import annotations

import gc
import json
import re
import tempfile
import time
import wave
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from lahza_engine.asr.base import AsrOptions
from lahza_engine.config import Settings
from lahza_engine.core.services import Services
from lahza_engine.db import store as db
from lahza_engine.types import Word

from .conftest import RssSampler, env_float, make_synthetic_video, mb

pytestmark = [pytest.mark.stress]
TOKEN = "stress-token"
psutil = pytest.importorskip("psutil")

STAGES = ("ingest", "vad", "asr", "normalize", "align", "diarize", "sentences", "signals",
          "highlight")
_VOCAB = ("bugun", "biz", "podkast", "haqida", "gaplashamiz", "juda", "muhim", "savol", "javob",
          "o'zbek", "tili", "kelajak", "texnologiya", "loyiha", "natija", "fikr", "albatta", "yaxshi")


class FakeAsr:
    """Bo'lak davomiyligi bo'ylab 300 ms so'zlar; har 10-so'z gap oxiri."""

    model_id = "stress-fake-asr"

    def __init__(self) -> None:
        self.calls = 0
        self.n = 0

    def transcribe_chunk(self, wav: Path, offset_ms: int, opts: AsrOptions) -> list[Word]:
        self.calls += 1
        with wave.open(str(wav), "rb") as w:
            dur_ms = int(w.getnframes() * 1000 / max(1, w.getframerate()))
        out: list[Word] = []
        t = 0
        while t + 300 <= dur_ms:
            self.n += 1
            text = _VOCAB[self.n % len(_VOCAB)]
            if self.n % 10 == 0:
                text += "?" if self.n % 70 == 0 else "."
            out.append(Word(text=text, start_ms=offset_ms + t, end_ms=offset_ms + t + 300,
                            conf=0.9))
            t += 350
        return out


class FakeLlamaServer:
    instances = 0

    def __init__(self, model_path: Path, **_: Any) -> None:
        FakeLlamaServer.instances += 1

    def __enter__(self) -> str:
        return "http://127.0.0.1:9"

    def __exit__(self, *exc: object) -> None:
        return None


class FakeLlmClient:
    """Promptdagi `id | spiker | dur | matn` qatorlaridan oyna chegarasini olib, JSON qaytaradi."""

    calls = 0
    _line = re.compile(r"^(\d+) \| ", re.M)

    def __init__(self, base_url: str, model_id: str, timeout_s: float = 600.0) -> None:
        pass

    def complete_json(self, prompt: str, schema: dict, temperature: float = 0.2) -> str:
        FakeLlmClient.calls += 1
        ids = [int(m) for m in self._line.findall(prompt)]
        cands = []
        for k, start in enumerate(ids[:: max(1, len(ids) // 3)][:3]):
            end = min(start + 11, ids[-1])
            cands.append({"start_id": start, "end_id": end, "hook_id": start, "turi": "maslahat",
                          "mustaqil": True,
                          "ballar": {"hook": 7, "mustaqillik": 8, "hissiyot": 5 + k, "foyda": 7,
                                     "aniqlik": 8},
                          "sarlavha": f"Soxta nomzod {start}", "sabab": "stress test",
                          "izoh_matni": "stress", "heshteglar": ["lahza"]})
        return json.dumps({"nomzodlar": cands})

    def close(self) -> None:
        pass


def _client(data_dir: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[TestClient, Any, FakeAsr]:
    from lahza_engine.api.app import create_app

    monkeypatch.setenv("LAHZA_DEV", "1")
    monkeypatch.setattr("lahza_engine.core.llama_server.LlamaServer", FakeLlamaServer)
    monkeypatch.setattr("lahza_engine.highlight.llm.LlamaServerClient", FakeLlmClient)
    app = create_app(Settings(data_dir=data_dir), token=TOKEN)
    st = app.state.lahza
    asr = FakeAsr()
    st._services = Services(asr=asr, asr_model_id=asr.model_id,
                            llm_model_path=Path("stress-fake.gguf"), llm_model_id="stress-fake-llm")
    c = TestClient(app)
    c.headers["Authorization"] = f"Bearer {TOKEN}"
    return c, st, asr


def _time_stages(monkeypatch: pytest.MonkeyPatch) -> dict[str, float]:
    """Har tahlil bosqichining haqiqiy vaqti (soniya) - bosqich funksiyalari o'raladi."""
    from lahza_engine.core import analyze as analyze_mod

    times: dict[str, float] = {}
    orig = analyze_mod.analysis_stages

    def timed(settings: Settings) -> list:
        stages = orig(settings)
        for sd in stages:
            def wrap(ctx, _fn=sd.fn, _name=sd.name):  # type: ignore[no-untyped-def]
                t = time.perf_counter()
                try:
                    return _fn(ctx)
                finally:
                    times[_name] = round(times.get(_name, 0.0) + time.perf_counter() - t, 3)
            sd.fn = wrap
        return stages

    monkeypatch.setattr(analyze_mod, "analysis_stages", timed)
    return times


def _isolated_tmp(base: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """`tempfile` ni alohida papkaga yo'naltiradi - test oxirida bo'sh bo'lishi kerak."""
    d = base / "pytmp"
    d.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(tempfile, "tempdir", str(d))
    return d


def _leftovers(d: Path) -> list[str]:
    return sorted(str(p.relative_to(d)) for p in d.rglob("*"))


def _dir_size(d: Path) -> int:
    return sum(p.stat().st_size for p in d.rglob("*") if p.is_file())


def _wait(pred, timeout: float, what: str, poll: float = 0.2) -> None:
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if pred():
            return
        time.sleep(poll)
    raise TimeoutError(what)


def _check_project(pdir: Path, eid: str) -> dict[str, Any]:
    """Loyiha bazasi izchilligi: 9 bosqich `done`, natija fayllari bor, transkript va kliplar."""
    conn = db.open_project(pdir)
    try:
        assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        runs = {r["stage"]: dict(r) for r in conn.execute(
            "SELECT stage, status, result_path FROM stage_runs WHERE media_id = ?", (eid,))}
        assert set(runs) == set(STAGES), sorted(runs)
        bad = {k: v["status"] for k, v in runs.items() if v["status"] != "done"}
        assert not bad, bad
        assert all(Path(v["result_path"]).is_file() for v in runs.values())
        sentences = conn.execute("SELECT COUNT(*) FROM sentences WHERE media_id = ?",
                                 (eid,)).fetchone()[0]
        words = conn.execute("SELECT COUNT(*) FROM words WHERE media_id = ?", (eid,)).fetchone()[0]
        clips = db.load_clips(conn, eid)
        media = conn.execute("SELECT duration_ms FROM media WHERE id = ?", (eid,)).fetchone()
    finally:
        conn.close()
    assert sentences > 0 and words > 0 and clips and media is not None
    return {"sentences": sentences, "words": words, "clips": len(clips),
            "duration_ms": media["duration_ms"]}


# --- (a) uzun video -------------------------------------------------------------------------

def test_long_video_full_pipeline(stress_tmp: Path, stress_report: dict, monkeypatch) -> None:
    hours = env_float("LAHZA_STRESS_HOURS", 4.0)
    seconds = int(hours * 3600)
    rss_limit = env_float("LAHZA_STRESS_RSS_MB", 1500 + 600 * hours) * 2**20
    root = stress_tmp / "long"
    root.mkdir()
    tmpd = _isolated_tmp(root, monkeypatch)

    t0 = time.monotonic()
    src = make_synthetic_video(root / "uzun.mp4", seconds)
    gen_s = time.monotonic() - t0

    c, st, asr = _client(root / "data", monkeypatch)
    proc = psutil.Process()
    try:
        gc.collect()
        base_rss = proc.memory_info().rss
        base_fds = proc.num_fds()
        pid = c.post("/v1/projects", json={"name": "Stress"}).json()["id"]
        stage_t = _time_stages(monkeypatch)
        with RssSampler() as sampler:
            t1 = time.monotonic()
            r = c.post("/v1/media:import", json={"project_id": pid, "path": str(src)})
            assert r.status_code == 200, r.text
            eid, job_id = r.json()["episode_id"], r.json()["job"]["id"]
            job = st.jobs.jobs[job_id]
            end = time.monotonic() + max(3600.0, seconds)  # 1x real vaqtdan oshmasin
            while job.status not in ("done", "failed", "cancelled"):
                if time.monotonic() > end:
                    raise TimeoutError("uzun video tahlili")
                time.sleep(0.05)
            analyze_s = time.monotonic() - t1
            assert job.status == "done", (job.error, job.meta.get("trace"))
            peak_analyze = sampler.peak

            # Bitta klip eksporti (render) - xuddi shu jarayonda.
            t2 = time.monotonic()
            export = _export_first_clip(st, eid)
            export_s = time.monotonic() - t2
        gc.collect()
        after_rss = proc.memory_info().rss
        after_fds = proc.num_fds()
        pdir = st.episode_dir(eid)
        consistency = _check_project(pdir, eid)
        ep = st.episode_row(eid)
        assert ep["status"] == "ready" and ep["highlight_mode"] == "llm"
        cache = pdir / "cache"
        leftovers = _leftovers(tmpd)
        result = {
            "params": {"hours": hours, "video": "320x180 5fps x264 + 220Hz sinus 8s/jimlik 2s",
                       "video_bytes": src.stat().st_size, "generate_s": round(gen_s, 1),
                       "rss_limit_mb": mb(rss_limit)},
            "analyze_s": round(analyze_s, 1),
            "analyze_rtf": round(analyze_s / seconds, 4),
            "stage_s": stage_t,
            "export": {**export, "seconds": round(export_s, 1)},
            "rss_mb": {"baseline": mb(base_rss), "peak_analyze": mb(peak_analyze),
                       "peak_total": mb(sampler.peak), "after_gc": mb(after_rss),
                       "retained_after": mb(after_rss - base_rss),
                       "peak_children_ffmpeg": mb(sampler.peak_children),
                       "timeline_5s": [(t, mb(r)) for t, r in sampler.samples]},
            "fds": {"before": base_fds, "after": after_fds},
            "asr_chunks": asr.calls, "llm_calls": FakeLlmClient.calls,
            "cache_mb": mb(_dir_size(cache)),
            "cache_files": sorted(p.name for p in cache.iterdir()),
            "temp_leftovers": leftovers,
            "db": consistency,
        }
        stress_report["long_video"] = result
        assert not leftovers, leftovers
        assert sampler.peak <= rss_limit, f"RSS cho'qqisi {mb(sampler.peak)} MB > {mb(rss_limit)} MB"
        assert after_fds - base_fds <= 5, (base_fds, after_fds)
        # Uzun video uchun 512 MB'dan ko'p xotira tahlildan keyin ushlanib qolmasligi kerak.
        assert after_rss - base_rss <= 512 * 2**20, mb(after_rss - base_rss)
        assert consistency["duration_ms"] >= seconds * 1000 - 2000
    finally:
        c.close()
        st.jobs.shutdown()


def _export_first_clip(st: Any, eid: str) -> dict[str, Any]:
    from lahza_engine.core.export import export_clip
    from lahza_engine.media.probe import probe
    from lahza_engine.media.tools import find_tool
    from lahza_engine.render.encoders import choose_encoder
    from lahza_engine.subtitle.style import StyleTemplate

    pdir = st.episode_dir(eid)
    conn = db.open_project(pdir)
    try:
        clip = db.load_clips(conn, eid)[0]
        ffmpeg = find_tool("ffmpeg")
        enc = choose_encoder(ffmpeg, None, st.settings.render.video_bitrate_kbps,
                             allow_dev_fallback=True)
        res = export_clip(conn, eid, clip, pdir / "export", pdir / "work", st.settings, enc,
                          StyleTemplate(), allow_no_subs=True)
        info = probe(res.video)
    finally:
        conn.close()
    assert (info.width, info.height) == (1080, 1920)
    return {"encoder": enc.name, "clip_ms": clip.end_ms - clip.start_ms,
            "out_ms": info.duration_ms, "warnings": res.warnings}


# --- (b) navbatda 20 epizod -----------------------------------------------------------------

def test_batch_queue_many_episodes(stress_tmp: Path, stress_report: dict, monkeypatch) -> None:
    n = int(env_float("LAHZA_STRESS_EPISODES", 20))
    ep_s = int(env_float("LAHZA_STRESS_EP_MIN", 3) * 60)
    leak_limit = env_float("LAHZA_STRESS_LEAK_MB", 150) * 2**20
    root = stress_tmp / "batch"
    root.mkdir()
    tmpd = _isolated_tmp(root, monkeypatch)
    # Ikki xil manba navbatma-navbat (bir xil fayl ham alohida epizod bo'lishi kerak).
    srcs = [make_synthetic_video(root / f"ep{i}.mp4", ep_s + 7 * i) for i in range(2)]
    paths = [str(srcs[i % 2]) for i in range(n)]

    c, st, asr = _client(root / "data", monkeypatch)
    proc = psutil.Process()
    try:
        pid = c.post("/v1/projects", json={"name": "Navbat"}).json()["id"]
        gc.collect()
        base = {"rss": proc.memory_info().rss, "fds": proc.num_fds(), "threads": proc.num_threads()}
        per_ep: list[dict[str, Any]] = []
        seen_done: set[str] = set()
        t0 = time.monotonic()
        with RssSampler() as sampler:
            items = c.post("/v1/queue", json={"project_id": pid, "paths": paths}).json()
            assert len(items) == n

            def tick() -> bool:
                xs = c.get("/v1/queue", params={"project_id": pid}).json()
                running = [x for x in xs if x["status"] == "running"]
                assert len(running) <= 1, "navbatda bir vaqtda faqat bitta element ishlashi kerak"
                for x in xs:
                    if x["status"] in ("done", "failed", "cancelled") and x["id"] not in seen_done:
                        seen_done.add(x["id"])
                        gc.collect()
                        per_ep.append({"n": len(seen_done), "status": x["status"],
                                       "t_s": round(time.monotonic() - t0, 1),
                                       "rss_mb": mb(proc.memory_info().rss),
                                       "fds": proc.num_fds(), "threads": proc.num_threads()})
                return len(seen_done) == n

            _wait(tick, timeout=max(1800.0, n * ep_s * 2.0), what="navbat", poll=0.1)
        total_s = time.monotonic() - t0
        xs = c.get("/v1/queue", params={"project_id": pid}).json()
        statuses = [x["status"] for x in xs]
        positions = [x["position"] for x in xs]
        eps = {e["id"]: e for e in c.get(f"/v1/projects/{pid}/episodes").json()}
        checks = [_check_project(Path(st.episode_row(x["episode_id"])["project_dir"]),
                                 x["episode_id"]) for x in xs if x["status"] == "done"]
        lib_ok = st.lib("PRAGMA integrity_check")[0][0]
        stuck = st.lib("SELECT COUNT(*) AS k FROM analysis_queue WHERE status IN ('queued','running')")[0]["k"]
        jobs = st.jobs.list_jobs("analyze")
        gc.collect()
        end = {"rss": proc.memory_info().rss, "fds": proc.num_fds(), "threads": proc.num_threads()}
        warm = per_ep[min(4, len(per_ep) - 1)]
        growth = (end["rss"] - warm["rss_mb"] * 2**20)
        leftovers = _leftovers(tmpd)
        result = {
            "params": {"episodes": n, "episode_s": ep_s, "leak_limit_mb": mb(leak_limit)},
            "total_s": round(total_s, 1),
            "per_episode_s": round(total_s / max(1, n), 2),
            "statuses": {s: statuses.count(s) for s in set(statuses)},
            "rss_mb": {"baseline": mb(base["rss"]), "after_ep5": warm["rss_mb"],
                       "end": mb(end["rss"]), "growth_ep5_to_end": mb(growth),
                       "peak": mb(sampler.peak)},
            "fds": {"baseline": base["fds"], "end": end["fds"]},
            "threads": {"baseline": base["threads"], "end": end["threads"]},
            "per_episode": per_ep,
            "db": {"library_integrity": lib_ok, "stuck_queue_items": stuck,
                   "episodes": len(eps), "episodes_ready": sum(e["status"] == "ready" for e in eps.values()),
                   "jobs_done": sum(j.status == "done" for j in jobs),
                   "words_per_ep": sorted({ch["words"] for ch in checks}),
                   "clips_per_ep": sorted({ch["clips"] for ch in checks})},
            "asr_chunks": asr.calls, "llm_calls": FakeLlmClient.calls,
            "temp_leftovers": leftovers,
        }
        stress_report["batch_queue"] = result
        assert statuses == ["done"] * n, statuses
        assert positions == sorted(positions)
        assert lib_ok == "ok" and stuck == 0
        assert len(eps) == n and all(e["status"] == "ready" for e in eps.values())
        assert len(jobs) == n and all(j.status == "done" for j in jobs)
        assert len(checks) == n
        assert not leftovers, leftovers
        assert growth <= leak_limit, f"RSS o'sishi {mb(growth)} MB > {mb(leak_limit)} MB"
        assert end["fds"] - base["fds"] <= 5, (base["fds"], end["fds"])
        assert end["threads"] - base["threads"] <= 4, (base["threads"], end["threads"])
    finally:
        c.close()
        st.jobs.shutdown()

