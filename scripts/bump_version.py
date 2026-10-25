"""Versiyani hamma manifestlarda bir yo'la o'zgartiradi (fayl formatini saqlagan holda).

    python scripts/bump_version.py 1.0.0
    python scripts/bump_version.py patch|minor|major
    python scripts/bump_version.py 1.0.0 --dry-run

Qo'shimcha: engine/src/lahza_engine/__init__.py (`__version__`) ham yangilanadi.
So'ng `python scripts/check_versions.py --expect <versiya>` bilan tekshiradi.
Lock fayllar (package-lock.json, Cargo.lock) ham yangilanadi - `npm ci` / `cargo --locked` buzilmasin.
"""

from __future__ import annotations

import argparse
import re
import sys
from collections.abc import Callable
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from check_versions import (  # noqa: E402
    CARGO_LOCK,
    CARGO_TOML,
    CRATE_NAME,
    PACKAGE_JSON,
    PACKAGE_LOCK,
    PYPROJECT,
    ROOT,
    SEMVER,
    TAURI_CONF,
    check,
    collect,
)

Sub = Callable[[str, str], tuple[str, int]]


def _re(pattern: str, flags: int = 0, count: int = 1) -> Sub:
    rx = re.compile(pattern, flags)

    def apply(text: str, version: str) -> tuple[str, int]:
        return rx.subn(lambda m: f"{m.group(1)}{version}{m.group(2)}", text, count=count)

    return apply


def _toml_section(section: str) -> Sub:
    # [section] dan keyingi birinchi `version = "..."` (boshqa bo'limga o'tmasdan).
    return _re(rf'(?ms)(^\[{re.escape(section)}\]\n(?:(?!^\[).)*?^version\s*=\s*")[^"]*(")')


# check_versions.py ro'yxatidan tashqari: engine runtime versiyasi (API /health, discovery, diagnostika).
ENGINE_INIT = Path("engine/src/lahza_engine/__init__.py")

TOP_JSON_VERSION = _re(r'(?m)(^  "version":\s*")[^"]*(")')
LOCK_ROOT_PACKAGE = _re(r'("packages":\s*\{\s*"":\s*\{[^{}]*?"version":\s*")[^"]*(")')

TARGETS: list[tuple[Path, list[Sub], bool]] = [
    (PYPROJECT, [_toml_section("project")], True),
    (PACKAGE_JSON, [TOP_JSON_VERSION], True),
    (PACKAGE_LOCK, [TOP_JSON_VERSION, LOCK_ROOT_PACKAGE], False),
    (CARGO_TOML, [_toml_section("package")], True),
    (CARGO_LOCK, [_re(rf'(name = "{re.escape(CRATE_NAME)}"\nversion = ")[^"]*(")')], False),
    (TAURI_CONF, [TOP_JSON_VERSION], True),
    (ENGINE_INIT, [_re(r'(?m)(^__version__\s*=\s*")[^"]*(")')], False),
]


def resolve(spec: str, current: str) -> str:
    if spec in {"major", "minor", "patch"}:
        m = SEMVER.match(current)
        if not m:
            raise SystemExit(f"joriy versiya '{current}' SemVer emas - aniq versiya bering")
        ma, mi, pa = (int(x) for x in m.groups()[:3])
        return {"major": f"{ma + 1}.0.0", "minor": f"{ma}.{mi + 1}.0", "patch": f"{ma}.{mi}.{pa + 1}"}[spec]
    v = spec.removeprefix("v")
    if not SEMVER.match(v):
        raise SystemExit(f"'{spec}' SemVer emas (masalan 1.0.0 yoki 1.1.0-beta.1)")
    return v


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Versiyani hamma manifestlarda o'zgartiradi.")
    ap.add_argument("version", help="yangi versiya (1.0.0) yoki major|minor|patch")
    ap.add_argument("--dry-run", action="store_true", help="fayllarni yozmasdan nima o'zgarishini ko'rsatish")
    ap.add_argument("--root", type=Path, default=ROOT, help=argparse.SUPPRESS)
    a = ap.parse_args(argv)

    before = collect(a.root)
    errors = check(before)
    current = before[str(PYPROJECT)] or "0.0.0"
    if errors and a.version in {"major", "minor", "patch"}:
        print("ogohlantirish: joriy versiyalar mos emas, asos sifatida engine/pyproject.toml olindi",
              file=sys.stderr)
    new = resolve(a.version, current)

    # Avval hamma fayl tekshiriladi, keyin yoziladi - yarim yangilangan holat qolmasin.
    pending: list[tuple[Path, Path, str]] = []
    for rel, subs, required in TARGETS:
        p = a.root / rel
        if not p.exists():
            if required:
                raise SystemExit(f"{rel} topilmadi")
            print(f"o'tkazildi (yo'q): {rel}")
            continue
        text = p.read_text(encoding="utf-8")
        for sub in subs:
            text, n = sub(text, new)
            if n != 1:
                raise SystemExit(f"{rel}: versiya maydoni topilmadi (format o'zgarganmi?)")
        pending.append((rel, p, text))

    for rel, p, text in pending:
        if a.dry_run:
            print(f"[dry-run] {rel}: -> {new}")
        else:
            p.write_text(text, encoding="utf-8")
            print(f"{rel}: -> {new}")

    if a.dry_run:
        return 0
    errors = check(collect(a.root), new)
    init = a.root / ENGINE_INIT
    if init.exists() and f'__version__ = "{new}"' not in init.read_text(encoding="utf-8"):
        errors.append(f"{ENGINE_INIT}: __version__ {new} emas")
    for e in errors:
        print(f"XATO: {e}", file=sys.stderr)
    if not errors:
        print(f"ok: versiya {current} -> {new}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
