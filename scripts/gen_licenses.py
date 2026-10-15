"""LICENSES-THIRD-PARTY.md dagi avtomatik jadvallarni lokal o'rnatilgan paketlardan yangilaydi (V1-5).

    engine/.venv/bin/python scripts/gen_licenses.py            # faylni yangilash
    engine/.venv/bin/python scripts/gen_licenses.py --check    # eskirgan bo'lsa 1 qaytaradi
    engine/.venv/bin/python scripts/gen_licenses.py --stdout   # faqat jadvallarni chiqarish

Manbalar (taxmin yo'q - faqat o'rnatilgan metama'lumot):
* Python: `lahza-engine` ning runtime bog'liqliklari (+ `onnx`, `fonts` ekstralari) tranzitiv yopilmasi,
  versiya va litsenziya `importlib.metadata` dan (License-Expression > License > classifier).
  Shu sababli skript engine venv'idagi Python bilan ishga tushiriladi.
* npm: `app/package-lock.json` dagi production (dev bo'lmagan) paketlar; litsenziya lock fayldan,
  bo'lmasa `app/node_modules/<paket>/package.json` dan.

Faylning qo'lda yoziladigan qismlari (FFmpeg, modellar, Rust crate'lar) o'zgarmaydi: faqat
`<!-- gen_licenses:<bo'lim>:start -->` ... `:end -->` belgilari orasi qayta yoziladi.
"""

from __future__ import annotations

import argparse
import importlib.metadata as md
import json
import re
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "LICENSES-THIRD-PARTY.md"
LOCK = ROOT / "app" / "package-lock.json"
PYPROJECT = ROOT / "engine" / "pyproject.toml"
NODE_MODULES = ROOT / "app" / "node_modules"

ENGINE_DIST = "lahza-engine"
# Mahsulotga kiradigan ekstralar (sidecar'ga yig'iladi). Og'ir/platformaga xos ekstralar alohida.
SHIPPED_EXTRAS = ["onnx", "fonts"]

_CLASSIFIER = {
    "MIT License": "MIT",
    "BSD License": "BSD",
    "Apache Software License": "Apache-2.0",
    "Mozilla Public License 2.0 (MPL 2.0)": "MPL-2.0",
    "Python Software Foundation License": "PSF-2.0",
    "ISC License (ISCL)": "ISC",
    "GNU Lesser General Public License v2 or later (LGPLv2+)": "LGPL-2.0-or-later",
    "GNU Library or Lesser General Public License (LGPL)": "LGPL",
}
_ALIASES = {
    "MIT License": "MIT",
    "Apache 2.0": "Apache-2.0",
    "Apache License 2.0": "Apache-2.0",
    "Apache Software License": "Apache-2.0",
    "3-Clause BSD License": "BSD-3-Clause",
    "BSD 3-Clause": "BSD-3-Clause",
    "BSD": "BSD",
}


def _norm(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def python_license(meta: md.PackageMetadata) -> str:
    expr = meta.get("License-Expression")
    if expr:
        return expr.strip()
    lic = (meta.get("License") or "").strip()
    if lic and len(lic) <= 60 and "\n" not in lic:
        return _ALIASES.get(lic, lic)
    for c in meta.get_all("Classifier") or []:
        if c.startswith("License :: OSI Approved :: "):
            return _CLASSIFIER.get(c.removeprefix("License :: OSI Approved :: "), c.rsplit(" :: ", 1)[-1])
    return "ANIQLANSIN"


def _requirements(dist: md.Distribution, extras: list[str]) -> list[str]:
    from packaging.requirements import Requirement  # engine venv'da bor (pip/pytest bog'liqligi)

    names = []
    for raw in dist.requires or []:
        req = Requirement(raw)
        envs = [{"extra": e} for e in ["", *extras]]
        if req.marker is None or any(req.marker.evaluate(env) for env in envs):
            names.append(req.name)
    return names


def root_requirements() -> list[str]:
    """Ildiz bog'liqliklar engine/pyproject.toml dan (o'rnatilgan metama'lumot eskirgan bo'lishi mumkin)."""
    from packaging.requirements import Requirement

    with PYPROJECT.open("rb") as f:
        proj = tomllib.load(f)["project"]
    raw = list(proj.get("dependencies", []))
    for extra in SHIPPED_EXTRAS:
        raw += proj.get("optional-dependencies", {}).get(extra, [])
    return [Requirement(r).name for r in raw]


def python_packages() -> list[tuple[str, str, str, str]]:
    """[(nom, versiya, litsenziya, kim tortgan)] - lahza-engine runtime yopilmasi."""
    seen: dict[str, tuple[str, str, str, str]] = {}
    missing: list[str] = []
    queue = [(n, "to'g'ridan") for n in root_requirements()]
    while queue:
        name, via = queue.pop(0)
        key = _norm(name)
        if key in seen:
            continue
        try:
            dist = md.distribution(name)
        except md.PackageNotFoundError:
            missing.append(name)  # bu platformada o'rnatilmagan (masalan Windows'ga xos)
            continue
        meta = dist.metadata
        seen[key] = (meta["Name"], meta["Version"], python_license(meta), via)
        queue += [(n, meta["Name"]) for n in _requirements(dist, [])]
    if missing:
        print("ogohlantirish: o'rnatilmagan, jadvalga kirmadi: " + ", ".join(sorted(set(missing))),
              file=sys.stderr)
    return sorted(seen.values(), key=lambda r: r[0].lower())


def npm_packages() -> list[tuple[str, str, str]]:
    lock = json.loads(LOCK.read_text(encoding="utf-8"))
    out = {}
    for path, info in lock.get("packages", {}).items():
        if not path.startswith("node_modules/") or info.get("dev") or info.get("devOptional"):
            continue
        name = path.rsplit("node_modules/", 1)[-1]
        lic = info.get("license")
        if not lic:
            pj = NODE_MODULES / name / "package.json"
            if pj.exists():
                lic = json.loads(pj.read_text(encoding="utf-8")).get("license")
        if isinstance(lic, dict):
            lic = lic.get("type")
        out[name] = (name, info.get("version", "?"), lic or "ANIQLANSIN")
    return sorted(out.values(), key=lambda r: r[0].lower())


def _table(header: list[str], rows: list[tuple[str, ...]]) -> str:
    lines = ["| " + " | ".join(header) + " |", "| " + " | ".join("---" for _ in header) + " |"]
    lines += ["| " + " | ".join(r) + " |" for r in rows]
    return "\n".join(lines)


def sections() -> dict[str, str]:
    py = python_packages()
    npm = npm_packages()
    py_body = (
        f"Python {sys.version_info.major}.{sys.version_info.minor} muhitidan, "
        f"`{ENGINE_DIST}` + ekstralar: {', '.join(SHIPPED_EXTRAS)}. {len(py)} paket.\n\n"
        + _table(["Paket", "Versiya", "Litsenziya", "Kim tortgan"], py)
    )
    npm_body = (
        f"`app/package-lock.json` production bog'liqliklari. {len(npm)} paket.\n\n"
        + _table(["Paket", "Versiya", "Litsenziya"], npm)
    )
    return {"python": py_body, "npm": npm_body}


def render(text: str, secs: dict[str, str]) -> str:
    for name, body in secs.items():
        start, end = f"<!-- gen_licenses:{name}:start -->", f"<!-- gen_licenses:{name}:end -->"
        pat = re.compile(re.escape(start) + r".*?" + re.escape(end), re.S)
        block = f"{start}\n{body}\n{end}"
        if not pat.search(text):
            raise SystemExit(f"{OUT.name} da '{start}' belgisi topilmadi")
        text = pat.sub(lambda _m, b=block: b, text)
    return text


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Uchinchi tomon litsenziyalari jadvallarini generatsiya qilish.")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--check", action="store_true", help="fayl eskirgan bo'lsa 1 bilan chiqish")
    g.add_argument("--stdout", action="store_true", help="jadvallarni ekranga chiqarish")
    a = ap.parse_args(argv)

    secs = sections()
    if a.stdout:
        for name, body in secs.items():
            print(f"## {name}\n\n{body}\n")
        return 0
    old = OUT.read_text(encoding="utf-8")
    new = render(old, secs)
    if a.check:
        if old != new:
            print(f"{OUT.name} eskirgan: `python scripts/gen_licenses.py` ni ishga tushiring", file=sys.stderr)
            return 1
        print("ok")
        return 0
    OUT.write_text(new, encoding="utf-8")
    print(f"yangilandi: {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
