"""Servis tavsifi: qaysi buyruq, qaysi muhit, qayerga log - platformadan mustaqil."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

from lahza_engine.service import SERVICE_DIR

PASS_ENV = ("LAHZA_BIN_DIR", "LAHZA_CATALOG", "LAHZA_CATALOG_PUBKEY", "LAHZA_DATA_DIR", "LAHZA_ADOBE_CORS",
            "PYTHONPATH")
"""O'rnatish paytidagi muhitdan servisga o'tkaziladigan o'zgaruvchilar (bo'lsa). Token hech qachon emas:
servis har ishga tushishda yangi token yaratadi va uni faqat `engine.json` (0600) ga yozadi."""

SERVE_ARGS = ("serve", "--service")


def default_program() -> list[str]:
    """Joriy engine'ni ishga tushiruvchi buyruq: PyInstaller sidecar'i - o'zi; dev - `python -m lahza_engine`."""
    if getattr(sys, "frozen", False):
        return [sys.executable]
    return [sys.executable, "-m", "lahza_engine"]


@dataclass(frozen=True)
class ServiceSpec:
    program: list[str]
    data_dir: Path
    env: dict[str, str] = field(default_factory=dict)

    @property
    def args(self) -> list[str]:
        return [*self.program, *SERVE_ARGS]

    @property
    def logs_dir(self) -> Path:
        return self.data_dir / "Logs"

    @property
    def state_dir(self) -> Path:
        return self.data_dir / SERVICE_DIR

    @property
    def stdout_log(self) -> Path:
        return self.logs_dir / "engine-service.out.log"

    @property
    def stderr_log(self) -> Path:
        return self.logs_dir / "engine-service.err.log"


def build_spec(data_dir: Path, program: str | None = None, environ: dict[str, str] | None = None
               ) -> ServiceSpec:
    environ = dict(os.environ if environ is None else environ)
    env = {k: environ[k] for k in PASS_ENV if environ.get(k)}
    prog = [str(Path(program).expanduser())] if program else default_program()
    return ServiceSpec(program=prog, data_dir=Path(data_dir), env=env)
