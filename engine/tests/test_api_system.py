import json
import logging
import subprocess
import zipfile
from pathlib import Path

from _api_helpers import make_client, seed_episode

from lahza_engine.api import routes_system
from lahza_engine.core import logs
from lahza_engine.db import store as db


def test_capabilities(tmp_path: Path, monkeypatch) -> None:
    c, st = make_client(tmp_path, monkeypatch)
    monkeypatch.setattr(routes_system, "ffmpeg_capabilities",
                        lambda: {"ffmpeg": True, "libass": False, "encoders": ["libx264"]})
    r = c.get("/v1/capabilities").json()
    assert r == {"ffmpeg": True, "libass": False, "encoders": ["libx264"], "vad": "energy",
                 "aligner": False, "diarizer": False, "face_detector": False, "llm": False}

    class Vad:
        method = "silero"

    st._services.vad = Vad()
    st._services.aligner = object()
    assert c.get("/v1/capabilities").json()["vad"] == "energy"  # keshdan
    r = c.get("/v1/capabilities", params={"refresh": True}).json()
    assert r["vad"] == "silero" and r["aligner"] is True


def test_ffmpeg_capabilities_without_ffmpeg(monkeypatch) -> None:
    from lahza_engine.media import tools

    def nf(name):
        raise tools.ToolNotFound(name)

    monkeypatch.setattr(tools, "find_tool", nf)
    assert routes_system.ffmpeg_capabilities() == {"ffmpeg": False, "libass": False, "encoders": []}


def test_reveal(tmp_path: Path, monkeypatch) -> None:
    f = tmp_path / "a.mp4"
    f.write_bytes(b"x")
    assert routes_system.reveal_command(f, "darwin") == ["open", "-R", str(f.resolve())]
    assert routes_system.reveal_command(f, "win32") == ["explorer", f"/select,{f.resolve()}"]
    assert routes_system.reveal_command(f, "linux") == ["xdg-open", str(tmp_path.resolve())]
    assert routes_system.reveal_command(tmp_path, "linux") == ["xdg-open", str(tmp_path.resolve())]

    c, _ = make_client(tmp_path, monkeypatch)
    calls = []

    class P:
        def __init__(self, args, **kw):
            assert "shell" not in kw
            calls.append(args)

    monkeypatch.setattr(subprocess, "Popen", P)
    assert c.post("/v1/system:reveal", json={"path": str(f)}).json() == {"ok": True}
    assert calls and isinstance(calls[0], list)
    assert c.post("/v1/system:reveal", json={"path": str(tmp_path / "yoq")}).status_code == 404
    assert c.post("/v1/system:reveal", json={"path": ""}).status_code == 404


def test_safe_formatter_hides_transcript() -> None:
    secret = "Bu juda maxfiy transkript gapi bo'lib, logga hech qachon tushmasligi kerak edi"
    fmt = logs.SafeFormatter("%(message)s")
    rec = logging.LogRecord("lahza_engine.x", logging.INFO, __file__, 1, "matn: %s", (secret,), None)
    out = fmt.format(rec)
    assert secret not in out and "belgi" in out
    rec = logging.LogRecord("x", logging.INFO, __file__, 1, "so'zlar: %s", (["a", "b"],), None)
    assert "list" in fmt.format(rec)
    rec = logging.LogRecord("x", logging.INFO, __file__, 1, "qisqa %s %d", ("asr", 3), None)
    assert fmt.format(rec) == "qisqa asr 3"
    try:
        raise ValueError(secret)
    except ValueError:
        import sys

        rec = logging.LogRecord("x", logging.ERROR, __file__, 1, "xato", (), sys.exc_info())
    assert secret not in fmt.format(rec)


def test_file_logging_rotation_and_tail(tmp_path: Path) -> None:
    path = logs.setup_file_logging(tmp_path)
    try:
        logs.setup_file_logging(tmp_path)  # takroriy chaqiriq handler qo'shmaydi
        lg = logging.getLogger("lahza_engine")
        assert sum(1 for h in lg.handlers if h.get_name() == "lahza-file") == 1
        h = next(h for h in lg.handlers if h.get_name() == "lahza-file")
        assert h.maxBytes == 2 * 1024 * 1024 and h.backupCount == 4
        lg.info("sinov %s", "satr")
        h.flush()
        assert path.exists() and any("sinov satr" in x for x in logs.tail(tmp_path, 10))
    finally:
        logs.remove_file_logging()


def test_diagnostics_has_no_transcript_text(tmp_path: Path, monkeypatch) -> None:
    c, st = make_client(tmp_path, monkeypatch)
    _, eid, pdir = seed_episode(st, tmp_path)
    secret = "MAXFIYSOZ"
    conn = db.open_project(pdir)
    with conn:
        conn.execute("UPDATE words SET text = ? WHERE media_id = ?", (secret, eid))
        conn.execute("UPDATE sentences SET text = ? WHERE media_id = ?", (secret + " gap", eid))
        conn.execute("INSERT INTO stage_runs(media_id, stage, version, param_hash, cache_key, status, error)"
                     " VALUES (?,?,?,?,?,?,?)",
                     (eid, "asr", 1, "p", "k", "failed",
                      f"ValueError: {secret} " + "uzun xabar " * 20))
    monkeypatch.setattr(routes_system, "ffmpeg_capabilities",
                        lambda: {"ffmpeg": False, "libass": False, "encoders": []})
    logs_dir = st.settings.logs_dir
    logs.setup_file_logging(logs_dir)
    try:
        logging.getLogger("lahza_engine.test").info("gap: %s", f"{secret} " * 20)
        logging.getLogger("lahza_engine.test").warning("oddiy hodisa")
    finally:
        logs.remove_file_logging()
    out = tmp_path / "diag"
    r = c.post("/v1/diagnostics", json={"out_dir": str(out)})
    assert r.status_code == 200
    zp = Path(r.json()["path"])
    with zipfile.ZipFile(zp) as z:
        names = set(z.namelist())
        assert names == {"diagnostics.json", "engine.log.txt"}
        blob = b"".join(z.read(n) for n in names).decode()
        info = json.loads(z.read("diagnostics.json"))
    assert secret not in blob
    assert "oddiy hodisa" in blob
    assert info["versions"]["engine"] and info["capabilities"]["ffmpeg"] is False
    assert info["stage_errors"][0]["stage"] == "asr" and info["stage_errors"][0]["error_type"] == "ValueError"
    assert c.post("/v1/diagnostics", json={"out_dir": str(tmp_path / "a" / "b" / "c")}).status_code == 400
