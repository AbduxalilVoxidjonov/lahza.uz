"""API testlari uchun umumiy yordamchilar (tahlilsiz tayyor epizod yaratish)."""

from __future__ import annotations

import time
import uuid
import wave
from pathlib import Path

import numpy as np
from conftest import make_sentences
from fastapi.testclient import TestClient

from lahza_engine.api.app import create_app
from lahza_engine.api.state import State
from lahza_engine.config import Settings
from lahza_engine.core.services import Services
from lahza_engine.db import store as db
from lahza_engine.types import Transcript

TOKEN = "test-token"


def make_client(tmp_path: Path, monkeypatch) -> tuple[TestClient, State]:
    monkeypatch.setenv("LAHZA_DEV", "1")
    app = create_app(Settings(data_dir=tmp_path / "data"), token=TOKEN)
    st: State = app.state.lahza
    st._services = Services()  # og'ir backendlarsiz
    c = TestClient(app)
    c.headers["Authorization"] = f"Bearer {TOKEN}"
    return c, st


def write_wav(path: Path, duration_ms: int, rate: int = 16_000) -> None:
    n = rate * duration_ms // 1000
    t = np.arange(n) / rate
    amp = 0.2 + 0.6 * (np.sin(2 * np.pi * 0.1 * t) > 0)
    pcm = (amp * np.sin(2 * np.pi * 220 * t) * 32767).astype("<i2")
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm.tobytes())


def seed_episode(st: State, tmp_path: Path, n: int = 12, wav: bool = True,
                 show_name: str = "Shou") -> tuple[str, str, Path]:
    """Shou + epizod + project.db (media, transkript). Qaytaradi: (show_id, episode_id, pdir)."""
    sid = uuid.uuid4().hex[:12]
    eid = uuid.uuid4().hex[:12]
    pdir = st.settings.library_dir / show_name / f"ep-{eid[:6]}.lahza"
    pdir.mkdir(parents=True, exist_ok=True)
    st.lib_write("INSERT INTO shows(id, name) VALUES (?, ?)", (sid, show_name))
    st.lib_write("INSERT INTO episodes(id, show_id, title, project_dir, status) VALUES (?,?,?,?,?)",
                 (eid, sid, "Birinchi epizod", str(pdir), "ready"))
    src = tmp_path / f"src-{eid}.mp4"
    src.write_bytes(b"\x00" * 4096)
    sentences = make_sentences(n)
    for i, s in enumerate(sentences):
        spk = f"SPEAKER_0{i % 2}"
        s.speaker = spk
        for w in s.words:
            w.speaker = spk
    conn = db.open_project(pdir)
    with conn:
        conn.execute("INSERT INTO media(id, path, hash, duration_ms, fps, width, height, audio_channels)"
                     " VALUES (?,?,?,?,?,?,?,?)",
                     (eid, str(src), "h", sentences[-1].end_ms + 500, 25.0, 1920, 1080, 2))
    db.save_transcript(conn, eid, Transcript(sentences=sentences))
    conn.close()
    if wav:
        write_wav(pdir / "cache" / "audio16k.wav", sentences[-1].end_ms + 500)
    return sid, eid, pdir


def wait_job(st: State, job_id: str, timeout: float = 10.0):
    end = time.time() + timeout
    while time.time() < end:
        j = st.jobs.jobs[job_id]
        if j.status in ("done", "failed", "cancelled"):
            return j
        time.sleep(0.02)
    raise TimeoutError(job_id)
