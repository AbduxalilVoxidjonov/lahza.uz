"""Reliz tekshiruvi (docs/10): versiya raqami hamma manifestlarda bir xilmi.

    python scripts/check_versions.py                 # hammasi bir xilmi
    python scripts/check_versions.py --expect 1.0.0  # va aynan shu versiyami (v1.0.0 ham bo'ladi)
    python scripts/check_versions.py --json

Tekshiriladi: engine/pyproject.toml, app/package.json, app/package-lock.json (ikki joy),
app/src-tauri/Cargo.toml, app/src-tauri/Cargo.lock (lahza-studio paketi), app/src-tauri/tauri.conf.json.
Faqat standart kutubxona (Python 3.11+, tomllib) - CI'da engine o'rnatilmasdan ham ishlaydi.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Tauri/Cargo/npm uchun umumiy maxraj: SemVer 2.0 (masalan 1.0.0, 1.2.0-beta.1).
SEMVER = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$"
)

PYPROJECT = Path("engine/pyproject.toml")
PACKAGE_JSON = Path("app/package.json")
PACKAGE_LOCK = Path("app/package-lock.json")
CARGO_TOML = Path("app/src-tauri/Cargo.toml")
CARGO_LOCK = Path("app/src-tauri/Cargo.lock")
TAURI_CONF = Path("app/src-tauri/tauri.conf.json")
CRATE_NAME = "lahza-studio"


def _toml(path: Path) -> dict:
    with path.open("rb") as f:
        return tomllib.load(f)


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def collect(root: Path = ROOT) -> dict[str, str | None]:
    """Har manba -> versiya (fayl bo'lmasa yoki maydon yo'q bo'lsa None)."""
    out: dict[str, str | None] = {}

    def put(key: str, path: Path, fn) -> None:  # type: ignore[no-untyped-def]
        p = root / path
        if not p.exists():
            out[key] = None
            return
        try:
            v = fn(p)
        except (KeyError, TypeError, ValueError):
            v = None
        out[key] = v if isinstance(v, str) else None

    put(str(PYPROJECT), PYPROJECT, lambda p: _toml(p)["project"]["version"])
    put(str(PACKAGE_JSON), PACKAGE_JSON, lambda p: _json(p)["version"])
    put(f"{PACKAGE_LOCK} (version)", PACKAGE_LOCK, lambda p: _json(p)["version"])
    put(f'{PACKAGE_LOCK} (packages[""])', PACKAGE_LOCK, lambda p: _json(p)["packages"][""]["version"])
    put(str(CARGO_TOML), CARGO_TOML, lambda p: _toml(p)["package"]["version"])

    def cargo_lock(p: Path) -> str | None:
        for pkg in _toml(p).get("package", []):
            if pkg.get("name") == CRATE_NAME:
                return pkg.get("version")
        return None

    put(f"{CARGO_LOCK} ({CRATE_NAME})", CARGO_LOCK, cargo_lock)
    put(str(TAURI_CONF), TAURI_CONF, lambda p: _json(p)["version"])
    return out


# Lock fayllar ixtiyoriy (masalan Cargo.lock hali yaratilmagan bo'lishi mumkin).
OPTIONAL = {f"{PACKAGE_LOCK} (version)", f'{PACKAGE_LOCK} (packages[""])', f"{CARGO_LOCK} ({CRATE_NAME})"}


def check(versions: dict[str, str | None], expect: str | None = None) -> list[str]:
    errors: list[str] = []
    for k, v in versions.items():
        if v is None and k not in OPTIONAL:
            errors.append(f"{k}: versiya topilmadi")
        elif v is not None and not SEMVER.match(v):
            errors.append(f"{k}: '{v}' SemVer emas")
    present = {v for v in versions.values() if v is not None}
    if len(present) > 1:
        errors.append("versiyalar mos emas: " + ", ".join(sorted(present)))
    if expect is not None:
        exp = expect.removeprefix("v")
        if present != {exp}:
            errors.append(f"kutilgan versiya {exp}, topilgani: {', '.join(sorted(present)) or '-'}")
    return errors


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Manifestlardagi versiyalar bir xilligini tekshiradi.")
    ap.add_argument("--expect", help="kutilgan versiya (masalan 1.0.0 yoki v1.0.0 git tegi)")
    ap.add_argument("--json", action="store_true", help="natijani JSON ko'rinishida chiqarish")
    ap.add_argument("--root", type=Path, default=ROOT, help=argparse.SUPPRESS)
    a = ap.parse_args(argv)

    versions = collect(a.root)
    errors = check(versions, a.expect)
    if a.json:
        print(json.dumps({"versions": versions, "ok": not errors, "errors": errors},
                         ensure_ascii=False, indent=2))
    else:
        width = max(len(k) for k in versions)
        for k, v in versions.items():
            print(f"{k:<{width}}  {v if v is not None else '-'}")
        print()
        if errors:
            for e in errors:
                print(f"XATO: {e}", file=sys.stderr)
        else:
            print(f"ok: hamma joyda {next(iter({v for v in versions.values() if v}))}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
