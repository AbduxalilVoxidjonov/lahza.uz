"""Diagnostika paketi (M2-APP-11): foydalanuvchi qo'llab-quvvatlashga yuboradigan zip.

Tarkibi: versiyalar, apparat profili, imkoniyatlar, o'rnatilgan modellar (ID/vazifa), oxirgi log
satrlari va bosqich xatolari (stage_runs). Transkript matni (sentences/words), kliplar matni va
media yo'llari KIRMAYDI (NFR-02).
"""

from __future__ import annotations

import json
import platform
import sqlite3
import sys
import zipfile
from datetime import UTC, datetime
from importlib import metadata
from pathlib import Path
from typing import Any

from lahza_engine import __version__
from lahza_engine.core import logs

_PACKAGES = ("fastapi", "uvicorn", "pydantic", "numpy", "cryptography", "faster-whisper",
             "onnxruntime", "torch", "torchaudio", "pyannote.audio", "mediapipe", "fonttools")
MAX_ERROR_CHARS = 200


def versions() -> dict[str, Any]:
    pk: dict[str, str | None] = {}
    for name in _PACKAGES:
        try:
            pk[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            pk[name] = None
    return {"engine": __version__, "python": sys.version.split()[0], "platform": platform.platform(),
            "machine": platform.machine(), "packages": pk}


def stage_errors(library: sqlite3.Connection) -> list[dict[str, Any]]:
    """Barcha epizodlardagi muvaffaqiyatsiz bosqichlar. Xato matni qisqartiriladi."""
    out: list[dict[str, Any]] = []
    for ep in library.execute("SELECT id, project_dir FROM episodes").fetchall():
        db_path = Path(ep["project_dir"]) / "project.db"
        if not db_path.exists():
            continue
        try:
            conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
            try:
                rows = conn.execute(
                    "SELECT stage, version, model_id, status, error, started_at, finished_at"
                    " FROM stage_runs WHERE status IN ('failed','cancelled')").fetchall()
            finally:
                conn.close()
        except sqlite3.Error:
            continue
        for st, ver, mid, status, err, a, b in rows:
            err = (err or "")
            out.append({"episode_id": ep["id"], "stage": st, "version": ver, "model_id": mid,
                        "status": status, "error_type": err.split(":", 1)[0][:60],
                        "error": logs._redact(err[:MAX_ERROR_CHARS]), "started_at": a,
                        "finished_at": b})
    return out


def build_diagnostics(
    out_dir: Path,
    logs_dir: Path,
    library: sqlite3.Connection,
    hardware: dict[str, Any] | None = None,
    capabilities: dict[str, Any] | None = None,
    models: dict[str, Any] | None = None,
    log_lines: int = 500,
) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    path = out_dir / f"lahza-diagnostika-{stamp}.zip"
    info = {
        "created_at": datetime.now(UTC).isoformat(),
        "versions": versions(),
        "hardware": hardware,
        "capabilities": capabilities,
        "models": [{"id": m.get("id"), "task": m.get("task"), "version": m.get("version"),
                    "source": m.get("source"), "self_test_ok": m.get("self_test_ok")}
                   for m in (models or {}).get("models", [])],
        "defaults": (models or {}).get("defaults", {}),
        "stage_errors": stage_errors(library),
    }
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr("diagnostics.json", json.dumps(info, ensure_ascii=False, indent=2, default=str))
        z.writestr("engine.log.txt", "\n".join(logs.tail(logs_dir, log_lines)) + "\n")
    return path
