"""Engine fayl logi (M2-APP-11, NFR-12) va transkript matnini logdan chiqarish (NFR-02).

* `Logs/engine.log`, aylanma: 2 MB x 5 fayl (joriy + 4 zaxira).
* Qoida: transkript matni log xabariga f-string bilan qo'shilmaydi. Formatter qo'shimcha himoya
  sifatida uzun satr argumentlarini va domen obyektlarini (Word/Sentence/Transcript/Clip)
  `<matn: N belgi>` ko'rinishida yashiradi, istisno xabarlarini qisqartiradi.
"""

from __future__ import annotations

import logging
from collections import deque
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

LOG_FILE = "engine.log"
MAX_BYTES = 2 * 1024 * 1024
BACKUP_COUNT = 4  # jami 5 fayl
MAX_ARG_CHARS = 64
MAX_EXC_CHARS = 300
_FMT = "%(asctime)s %(levelname)s %(name)s [%(threadName)s] %(message)s"
_DOMAIN_TYPES = {"Word", "Sentence", "Transcript", "Clip"}
_HANDLER_NAME = "lahza-file"


def _redact(value: Any) -> Any:
    if isinstance(value, str):
        return value if len(value) <= MAX_ARG_CHARS else f"<matn: {len(value)} belgi>"
    if type(value).__name__ in _DOMAIN_TYPES and type(value).__module__.startswith("lahza_engine"):
        return f"<{type(value).__name__}>"
    if isinstance(value, (list, tuple, dict, set)):
        return f"<{type(value).__name__}: {len(value)} ta>"
    return value


class SafeFormatter(logging.Formatter):
    """Argumentlarni yashiradi; istisno matnini qisqartiradi (NFR-02)."""

    def format(self, record: logging.LogRecord) -> str:
        rec = logging.makeLogRecord(record.__dict__)
        if isinstance(rec.args, tuple):
            rec.args = tuple(_redact(a) for a in rec.args)
        elif isinstance(rec.args, dict):
            rec.args = {k: _redact(v) for k, v in rec.args.items()}
        if not isinstance(rec.msg, str):
            rec.msg = _redact(rec.msg)
        return super().format(rec)

    def formatException(self, ei) -> str:  # noqa: N802 - logging API nomi
        etype, value, tb = ei
        import traceback

        frames = "".join(traceback.format_tb(tb, limit=8)) if tb else ""
        msg = str(value)
        if len(msg) > MAX_EXC_CHARS:
            msg = msg[:MAX_EXC_CHARS] + "..."
        name = etype.__name__ if etype else "Exception"
        return f"Traceback (oxirgi chaqiriqlar):\n{frames}{name}: {_redact(msg)}"


def setup_file_logging(logs_dir: Path, level: int = logging.INFO) -> Path:
    """`lahza_engine` va uvicorn loggerlariga aylanma fayl handler ulaydi (takroriy chaqiriq xavfsiz)."""
    logs_dir.mkdir(parents=True, exist_ok=True)
    path = logs_dir / LOG_FILE
    for name in ("lahza_engine", "uvicorn.error"):
        lg = logging.getLogger(name)
        if any(getattr(h, "name", None) == _HANDLER_NAME for h in lg.handlers):
            continue
        h = RotatingFileHandler(path, maxBytes=MAX_BYTES, backupCount=BACKUP_COUNT, encoding="utf-8")
        h.set_name(_HANDLER_NAME)
        h.setFormatter(SafeFormatter(_FMT))
        lg.addHandler(h)
        lg.setLevel(min(lg.level or level, level))
    return path


def remove_file_logging() -> None:
    for name in ("lahza_engine", "uvicorn.error"):
        lg = logging.getLogger(name)
        for h in [h for h in lg.handlers if getattr(h, "name", None) == _HANDLER_NAME]:
            lg.removeHandler(h)
            h.close()


def tail(logs_dir: Path, lines: int = 500) -> list[str]:
    """Oxirgi N satr (joriy fayl yetmasa - zaxira fayllardan ham)."""
    files = [logs_dir / LOG_FILE] + [logs_dir / f"{LOG_FILE}.{i}" for i in range(1, BACKUP_COUNT + 1)]
    buf: deque[str] = deque(maxlen=lines)
    for f in reversed([p for p in files if p.exists()]):
        with f.open(encoding="utf-8", errors="replace") as fh:
            for line in fh:
                buf.append(line.rstrip("\n"))
    return list(buf)
