"""Uchinchi tomon litsenziyalari: LICENSES-THIRD-PARTY.md va UI uchun JSON generatsiyasi (V1-5).

    engine/.venv/bin/python scripts/gen_licenses.py                  # ikkala faylni yangilash
    engine/.venv/bin/python scripts/gen_licenses.py --check          # eskirgan bo'lsa 1 qaytaradi
    python3 scripts/gen_licenses.py --check --reuse python           # CI: venv'siz, Python qismi keshdan
    engine/.venv/bin/python scripts/gen_licenses.py --stdout         # faqat jadvallarni chiqarish

Tarmoqqa chiqmaydi: faqat lokal metama'lumot o'qiladi (taxmin yo'q, topilmagani `ANIQLANSIN`).

Manbalar (guruhlar):
* python  - `lahza-engine` runtime bog'liqliklari (+ SHIPPED_EXTRAS) tranzitiv yopilmasi, versiya va
  litsenziya `importlib.metadata` dan (License-Expression > License > classifier), matn dist-info'dan.
  G'ildiraklarga biriktirilgan native kutubxonalar (`.dylibs`, `*.libs`) ham sanaladi. CPython va
  PyInstaller bootloader shu guruhda. Shu sababli skript engine venv'idagi Python bilan ishga tushiriladi.
* npm     - `app/package-lock.json` production paketlari; litsenziya lock'dan yoki node_modules'dan.
* rust    - `app/src-tauri/Cargo.lock` dagi barcha crate'lar; litsenziya lokal cargo registry
  manbasidagi `Cargo.toml` dan (cargo buyrug'i kerak emas).
* runtime - `third_party/runtimes.toml` + lokal alfa pinlari (`scripts/setup_local_*.py`) + staging
  qilingan `app/src-tauri/resources/bin/licenses/` (Homebrew SBOM `licenseConcluded`, LICENSE fayllari).
* font    - `engine/src/lahza_engine/subtitle/fonts/` (SOURCE.txt, OFL.txt).
* model   - `catalog/catalog.json` yozuvlari.

Kesh: lokal manba topilmasa (masalan CI'da registry/staging yo'q), oldingi `licenses.json` dagi aynan
shu nom@versiya yozuvi o'zgarishsiz qayta ishlatiladi. Shu tufayli `--check` mashinalararo barqaror.

Faylning qo'lda yoziladigan qismlari o'zgarmaydi: faqat `<!-- gen_licenses:<bo'lim>:start -->` ...
`:end -->` belgilari orasi qayta yoziladi.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import tomllib
from collections.abc import Callable, Iterable
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "LICENSES-THIRD-PARTY.md"
JSON_OUT = ROOT / "app" / "src" / "generated" / "licenses.json"
LOCK = ROOT / "app" / "package-lock.json"
PYPROJECT = ROOT / "engine" / "pyproject.toml"
NODE_MODULES = ROOT / "app" / "node_modules"
CARGO_LOCK = ROOT / "app" / "src-tauri" / "Cargo.lock"
RUNTIMES = ROOT / "third_party" / "runtimes.toml"
STAGED = ROOT / "app" / "src-tauri" / "resources" / "bin" / "licenses"
FONTS = ROOT / "engine" / "src" / "lahza_engine" / "subtitle" / "fonts"
CATALOG = ROOT / "catalog" / "catalog.json"
SETUP_RENDER = ROOT / "scripts" / "setup_local_render.py"
SETUP_LLM = ROOT / "scripts" / "setup_local_llm.py"

SCHEMA_VERSION = 1
UNKNOWN = "ANIQLANSIN"
GROUPS = ("python", "npm", "rust", "runtime", "font", "model")

ENGINE_DIST = "lahza-engine"
# Mahsulotga kiradigan ekstralar: `desktop` - lokal alfa sidecar'i (faster-whisper bog'liqliklari, ONNX,
# fontTools), `onnx`/`fonts` - CI sidecar'i. Og'ir/platformaga xos qolgan ekstralar alohida.
SHIPPED_EXTRAS = ["desktop", "onnx", "fonts"]
# `pip install --no-deps -r` bilan o'rnatiladigan paketlar (faster-whisper: PyAV'siz, ADR-0015).
# Ular yopilmaga kiradi, lekin ularning e'lon qilingan bog'liqliklari kuzatilmaydi.
NODEPS_REQUIREMENTS = ROOT / "engine" / "requirements-desktop-nodeps.txt"
# Sidecar'ga hech qachon kirmasligi shart bo'lgan Python paketlari (scripts/build_sidecar.py
# FORBIDDEN_MODULES bilan bir xil). PyAV g'ildiraklari GPL libx264/libx265 olib keladi.
FORBIDDEN_PYTHON = {"av"}

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
_TEXT_NAME = re.compile(r"^(LICEN[CS]E|COPYING|NOTICE|UNLICENSE|COPYRIGHT)([-._].*)?$", re.I)
_TEXT_SKIP_SUFFIX = {".py", ".pyc", ".js", ".cjs", ".mjs", ".ts", ".json", ".h", ".rs", ".html"}

# G'ildirakka biriktirilgan native kutubxonalar: metama'lumotda litsenziyasi yo'q, shuning uchun
# ma'lum loyiha nomlari bo'yicha (basis "nom jadvali"; yuridik tekshiruvda tasdiqlanadi).
NATIVE_KNOWN = {
    "x264": "GPL-2.0-or-later",
    "x265": "GPL-2.0-or-later",
    "avcodec": "LGPL-3.0-or-later", "avformat": "LGPL-3.0-or-later", "avutil": "LGPL-3.0-or-later",
    "avdevice": "LGPL-3.0-or-later", "avfilter": "LGPL-3.0-or-later",
    "swscale": "LGPL-3.0-or-later", "swresample": "LGPL-3.0-or-later",
    "aom": "BSD-2-Clause", "dav1d": "BSD-2-Clause", "openh264": "BSD-2-Clause",
    "mp3lame": "LGPL-2.0-or-later",
    "opencore-amrnb": "Apache-2.0", "opencore-amrwb": "Apache-2.0",
    "opus": "BSD-3-Clause", "speex": "BSD-3-Clause", "ogg": "BSD-3-Clause",
    "vorbis": "BSD-3-Clause", "vorbisenc": "BSD-3-Clause", "vpx": "BSD-3-Clause",
    "webp": "BSD-3-Clause", "webpmux": "BSD-3-Clause", "sharpyuv": "BSD-3-Clause",
    "SvtAv1Enc": "BSD-3-Clause-Clear",
    "ctranslate2": "MIT",
}

# Staging qilingan native kutubxonalar bo'yicha izohlar (SBOM ifodasi butun formula uchun).
NATIVE_NOTES = {
    "gettext": "Faqat libintl (LGPL-2.1-or-later) ko'chiriladi; GPL-3.0 qismi (gettext vositalari) ilovaga kirmaydi.",
    "fribidi": "Kutubxona LGPL-2.1-or-later; GPL-2.0 qismi faqat CLI vositasiga tegishli.",
    "graphite2": "Ko'p litsenziyali: MIT tanlanadi.",
    "freetype": "FTL yoki GPL-2.0 tanlovi: FTL tanlanadi.",
}

LGPL_NOTICE_MD = """\
Ilovadagi LGPL komponentlari (FFmpeg, FriBiDi, GLib, gettext/libintl va boshqalar) quyidagi shartlarda
tarqatiladi (LGPL-2.1 6-bo'lim; yuridik xulosa R0-LEG-1 da):

1. **Dinamik bog'lanish.** FFmpeg `--enable-shared --disable-static` bilan yig'iladi; kutubxonalar
   ilova paketida alohida `.dylib`/`.dll` fayllar sifatida turadi (`bin/`, `bin/lib/`) va
   `@loader_path` orqali yuklanadi. Foydalanuvchi ularni mos ABI'li o'z yig'masi bilan almashtira oladi.
2. **GPL/nonfree qismlarsiz.** `--enable-gpl`, `--enable-nonfree`, `--enable-version3` yo'q, libx264/libx265
   qo'shilmaydi (ADR-0004; `scripts/setup_local_render.py` buni tekshiradi). Konfiguratsiya qatori
   `bin/licenses/local-render/manifest.json` da ilova bilan birga beriladi.
3. **Litsenziya matnlari.** LGPL-2.1 to'liq matni va FFmpeg `LICENSE.md` ilova ichida (`bin/licenses/`) va
   "Sozlamalar -> Litsenziyalar" oynasida.
4. **Teskari muhandislik.** EULA LGPL kutubxonalarini o'zgartirish uchun zarur bo'lgan teskari muhandislik
   va disk raskadrovkani taqiqlamaydi.
5. **Manba taklifi** (ilovada ham ko'rsatiladi):

> Lahza Studio tarkibidagi LGPL litsenziyali komponentlarning (FFmpeg {ffmpeg} va ro'yxatdagi boshqa LGPL
> kutubxonalar) aynan shu relizda ishlatilgan to'liq manba kodini, yig'ish skriptlari va konfiguratsiya
> bayroqlari bilan birga, mahsulot tarqatilgan kundan boshlab kamida 3 yil davomida har qanday uchinchi
> shaxsga tarqatish xarajatidan oshmaydigan haq evaziga taqdim etamiz. So'rov manzili: ANIQLANSIN
> (rasmiy aloqa e-pochtasi relizdan oldin belgilanadi). FFmpeg manbasi: {ffmpeg_url} (SHA-256 {ffmpeg_sha}).
"""


# ---------------------------------------------------------------- umumiy yordamchilar

def _norm(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def _clean_text(body: str) -> str:
    lines = [ln.rstrip() for ln in body.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    return "\n".join(lines).strip() + "\n"


class Texts:
    """Litsenziya matnlari puli: bir xil matn bir marta saqlanadi (id = sha256[:12])."""

    def __init__(self) -> None:
        self.items: dict[str, dict[str, str]] = {}

    def add(self, title: str, body: str) -> str:
        body = _clean_text(body)
        tid = hashlib.sha256(body.encode()).hexdigest()[:12]
        self.items.setdefault(tid, {"title": title, "body": body})
        return tid

    def add_file(self, path: Path, title: str | None = None) -> str | None:
        try:
            body = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return None
        if not body.strip():
            return None
        return self.add(title or path.name, body)

    def add_dir(self, directory: Path) -> list[str]:
        """Katalog ildizidagi LICENSE/COPYING/NOTICE fayllari (tartiblangan)."""
        if not directory.is_dir():
            return []
        ids = []
        for p in sorted(directory.iterdir(), key=lambda x: x.name):
            if p.is_file() and _TEXT_NAME.match(p.name) and p.suffix.lower() not in _TEXT_SKIP_SUFFIX:
                tid = self.add_file(p)
                if tid and tid not in ids:
                    ids.append(tid)
        return ids


def component(group: str, name: str, version: str, license: str, *, basis: str, texts: list[str] | None = None,
              via: str = "", url: str = "", notes: str = "", attribution: str = "", risk: str = "",
              category: str | None = None) -> dict:
    lic = (license or "").strip() or UNKNOWN
    return {
        "id": f"{category or group}:{name}@{version}",
        "group": group,
        "category": category or group,
        "name": name,
        "version": version or UNKNOWN,
        "license": lic,
        "basis": basis,
        "via": via,
        "url": url,
        "notes": notes,
        "attribution": attribution,
        "risk": risk,
        "texts": texts or [],
    }


class Cache:
    """Oldingi generatsiya: lokal manba bo'lmaganda bir xil nom@versiya yozuvi qayta ishlatiladi."""

    def __init__(self, data: dict | None) -> None:
        data = data or {}
        self.components: dict[str, dict] = {c["id"]: c for c in data.get("components", [])}
        self.texts: dict[str, dict[str, str]] = data.get("texts", {})

    def get(self, cid: str) -> dict | None:
        return self.components.get(cid)

    def group(self, group: str) -> list[dict]:
        return [c for c in self.components.values() if c.get("group") == group]

    def revive(self, comp: dict, texts: Texts) -> dict:
        out = dict(comp)  # basis o'zgarmaydi: --check mashinalararo bir xil natija berishi kerak
        for tid in comp.get("texts", []):
            if tid in self.texts and tid not in texts.items:
                texts.items[tid] = self.texts[tid]
        out["texts"] = [t for t in comp.get("texts", []) if t in texts.items]
        return out


# ---------------------------------------------------------------- Python

def python_license(meta) -> str:
    expr = meta.get("License-Expression")
    if expr:
        return expr.strip()
    lic = (meta.get("License") or "").strip()
    if lic and len(lic) <= 60 and "\n" not in lic:
        return _ALIASES.get(lic, lic)
    for c in meta.get_all("Classifier") or []:
        if c.startswith("License :: OSI Approved :: "):
            return _CLASSIFIER.get(c.removeprefix("License :: OSI Approved :: "), c.rsplit(" :: ", 1)[-1])
    return UNKNOWN


def _requirements(dist, extras: list[str]) -> list[str]:
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
    seen, out = set(), []
    for r in raw:
        name = Requirement(r).name
        if _norm(name) not in seen:
            seen.add(_norm(name))
            out.append(name)
    return out


def nodeps_requirements() -> list[str]:
    """`requirements-desktop-nodeps.txt` dagi paket nomlari (izoh/bo'sh qatorlarsiz)."""
    from packaging.requirements import Requirement

    if not NODEPS_REQUIREMENTS.is_file():
        return []
    out = []
    for line in NODEPS_REQUIREMENTS.read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if line and not line.startswith("-"):
            out.append(Requirement(line).name)
    return out


def gpl_violations(data: dict) -> list[str]:
    """Sidecar'ga kiradigan Python/native qismlardagi GPL komponentlar (ADR-0004, ADR-0015)."""
    bad = []
    for c in data["components"]:
        if c["category"] not in ("python", "python-native"):
            continue
        lic = c["license"]
        gpl = "GPL" in lic and "LGPL" not in lic and "Bootloader-exception" not in lic
        if _norm(c["name"]) in FORBIDDEN_PYTHON or c.get("risk") == "GPL" or gpl:
            bad.append(f"{c['id']} ({lic}; {c['via']})")
    return bad


def _dist_license_texts(dist, texts: Texts) -> list[str]:
    ids: list[str] = []
    for f in sorted(dist.files or [], key=str):
        parts = Path(str(f)).parts
        if not parts:
            continue
        name = parts[-1]
        if parts[0].endswith(".dist-info"):
            if not _TEXT_NAME.match(name) and "licenses" not in parts:
                continue
        elif not (len(parts) == 2 and (_TEXT_NAME.match(name) or name.startswith("ThirdPartyNotices"))):
            continue  # paket ildizidagi LICENSE/ThirdPartyNotices (masalan onnxruntime)
        if Path(name).suffix.lower() in _TEXT_SKIP_SUFFIX or "__pycache__" in parts or name.startswith("AUTHORS"):
            continue
        tid = texts.add_file(Path(str(dist.locate_file(f))), name)
        if tid and tid not in ids:
            ids.append(tid)
    return ids


def _native_libs(dist) -> list[str]:
    """G'ildirak ichidagi delocate/auditwheel/delvewheel kutubxonalari (`.dylibs/`, `<pkg>.libs/`)."""
    out = []
    for f in dist.files or []:
        parts = Path(str(f)).parts
        if (len(parts) >= 2 and (parts[-2] == ".dylibs" or parts[-2].endswith(".libs"))
                and re.search(r"\.(dylib|so(\.\d+)*|dll)$", parts[-1])):
            out.append(parts[-1])
    return sorted(set(out))


def native_base(filename: str) -> str:
    """`libx264.165.dylib` -> `x264`, `libavcodec-62.dll` -> `avcodec`, `libvpx-1a2b3c.so.9` -> `vpx`."""
    stem = filename.split(".", 1)[0]
    stem = stem.removeprefix("lib")
    stem = re.sub(r"-[0-9a-f]{8,}$", "", stem)  # auditwheel/delvewheel xesh qo'shimchasi
    stem = re.sub(r"-\d+$", "", stem)  # Windows: avcodec-62
    return stem


def python_packages(texts: Texts | None = None) -> list[tuple[str, str, str, str]]:
    """[(nom, versiya, litsenziya, kim tortgan)] - lahza-engine runtime yopilmasi."""
    return [(c["name"], c["version"], c["license"], c["via"])
            for c in python_components(texts or Texts()) if c["category"] == "python"]


def python_components(texts: Texts) -> list[dict]:
    import importlib.metadata as md

    seen: dict[str, dict] = {}
    natives: list[dict] = []
    missing: list[str] = []
    nodeps = {_norm(n) for n in nodeps_requirements()}
    queue = [(n, "to'g'ridan") for n in root_requirements()]
    queue += [(n, "to'g'ridan (--no-deps)") for n in nodeps_requirements()]
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
        seen[key] = component("python", meta["Name"], meta["Version"], python_license(meta), basis="metadata",
                              texts=_dist_license_texts(dist, texts), via=via)
        for lib in _native_libs(dist):
            base = native_base(lib)
            lic = NATIVE_KNOWN.get(base, UNKNOWN)
            risk = "GPL" if "GPL" in lic and "LGPL" not in lic else ""
            natives.append(component(
                "python", base, lib, lic, basis="nom jadvali" if lic != UNKNOWN else "topilmadi",
                via=f"{meta['Name']} {meta['Version']} g'ildiragi", category="python-native", risk=risk,
                notes="G'ildirakka biriktirilgan native kutubxona; litsenziya fayl nomi bo'yicha, tasdiqlansin."))
        if key not in nodeps:
            queue += [(n, meta["Name"]) for n in _requirements(dist, [])]
    if missing:
        print("ogohlantirish: o'rnatilmagan, jadvalga kirmadi: " + ", ".join(sorted(set(missing))),
              file=sys.stderr)
    extra = []
    # Sidecar'ning o'zi: PyInstaller CPython interpretatorini va bootloader'ni qo'shadi.
    base = Path(sys.base_prefix)
    lic_file = next((p for p in (base / "lib" / f"python{sys.version_info.major}.{sys.version_info.minor}" / "LICENSE.txt",
                                 base / "LICENSE.txt") if p.is_file()), None)
    extra.append(component("python", "CPython", ".".join(map(str, sys.version_info[:3])), "PSF-2.0",
                           basis="interpretator", via="sidecar ichida (PyInstaller)",
                           texts=[t for t in [texts.add_file(lic_file, "LICENSE.txt")] if t] if lic_file else []))
    try:
        pi = md.distribution("pyinstaller")
        extra.append(component("python", "PyInstaller bootloader", pi.version,
                               "GPL-2.0-or-later WITH Bootloader-exception", basis="metadata",
                               via="build vositasi (bootloader sidecar ichida)",
                               notes="Bootloader istisnosi yig'ilgan dasturni istalgan litsenziyada tarqatishga ruxsat beradi.",
                               texts=_dist_license_texts(pi, texts)))
    except md.PackageNotFoundError:
        pass
    return sorted(seen.values(), key=lambda c: c["name"].lower()) + extra + sorted(
        natives, key=lambda c: (c["name"].lower(), c["version"]))


# ---------------------------------------------------------------- npm

def _npm_texts(name: str, texts: Texts) -> list[str]:
    return texts.add_dir(NODE_MODULES / name)


def npm_packages() -> list[tuple[str, str, str]]:
    return [(c["name"], c["version"], c["license"]) for c in npm_components(Texts(), Cache(None))]


def npm_components(texts: Texts, cache: Cache) -> list[dict]:
    lock = json.loads(LOCK.read_text(encoding="utf-8"))
    out: dict[str, dict] = {}
    for path, info in lock.get("packages", {}).items():
        if not path.startswith("node_modules/") or info.get("dev") or info.get("devOptional"):
            continue
        name = path.rsplit("node_modules/", 1)[-1]
        version = info.get("version", "?")
        lic, basis = info.get("license"), "package-lock"
        pj = NODE_MODULES / name / "package.json"
        if not lic and pj.exists():
            lic, basis = json.loads(pj.read_text(encoding="utf-8")).get("license"), "package.json"
        if isinstance(lic, dict):
            lic = lic.get("type")
        comp = component("npm", name, version, lic or UNKNOWN, basis=basis if lic else "topilmadi",
                         texts=_npm_texts(name, texts))
        cached = cache.get(comp["id"])
        if cached and (not comp["texts"] or comp["license"] == UNKNOWN):
            comp = cache.revive(cached, texts)
        out[name] = comp
    return sorted(out.values(), key=lambda c: c["name"].lower())


# ---------------------------------------------------------------- Rust

def cargo_registry_dirs() -> list[Path]:
    home = Path(os.environ.get("CARGO_HOME") or Path.home() / ".cargo")
    src = home / "registry" / "src"
    return sorted(p for p in src.iterdir() if p.is_dir()) if src.is_dir() else []


def rust_components(texts: Texts, cache: Cache, registries: list[Path] | None = None) -> list[dict]:
    lock = tomllib.loads(CARGO_LOCK.read_text(encoding="utf-8"))
    registries = cargo_registry_dirs() if registries is None else registries
    pkgs = [p for p in lock.get("package", []) if p.get("source")]
    local_versions: dict[str, list[str]] = {}
    for p in pkgs:
        local_versions.setdefault(p["name"], []).append(p["version"])
    out = []
    for p in pkgs:
        name, version = p["name"], p["version"]
        crate = next((r / f"{name}-{version}" for r in registries if (r / f"{name}-{version}").is_dir()), None)
        if crate is not None:
            manifest = tomllib.loads((crate / "Cargo.toml").read_text(encoding="utf-8")).get("package", {})
            lic = manifest.get("license") or ""
            ids = texts.add_dir(crate)
            lf = manifest.get("license-file")
            if lf and (crate / lf).is_file():
                tid = texts.add_file(crate / lf)
                if tid and tid not in ids:
                    ids.append(tid)
            if not lic and lf:
                lic = f"license-file: {lf}"
            out.append(component("rust", name, version, lic or UNKNOWN, basis="cargo registry", texts=ids,
                                 url=manifest.get("repository", "")))
            continue
        cid = f"rust:{name}@{version}"
        cached = cache.get(cid)
        if cached:
            out.append(cache.revive(cached, texts))
            continue
        others = [v for v in local_versions[name] if v != version]
        note = "Lokal cargo registry'da manba yo'q: odatda boshqa platforma (Windows/Linux/Android) crate'i"
        if others:
            note += f"; Cargo.lock'dagi boshqa versiya: {', '.join(others)}"
        out.append(component("rust", name, version, UNKNOWN, basis="topilmadi",
                             notes=note + ". `cargo about` yoki shu platformadagi registry bilan to'ldiriladi."))
    return sorted(out, key=lambda c: (c["name"].lower(), c["version"]))


# ---------------------------------------------------------------- runtime'lar

def _pin(path: Path, var: str) -> str:
    m = re.search(rf'^{var}\s*=\s*"([^"]+)"', path.read_text(encoding="utf-8"), re.M) if path.is_file() else None
    return m.group(1) if m else ""


def runtime_components(texts: Texts, cache: Cache, staged: Path = STAGED) -> list[dict]:
    rt = tomllib.loads(RUNTIMES.read_text(encoding="utf-8")) if RUNTIMES.is_file() else {}
    out: list[dict] = []

    def ref_note(key: str) -> str:
        ref = (rt.get(key) or {}).get("ref", "")
        return f"runtimes.toml ref: {ref}" if ref else f"runtimes.toml ref bo'sh ({UNKNOWN}, R0-RT-1)"

    def from_cache_or(comp: dict) -> dict:
        cached = cache.get(comp["id"])
        if cached and not comp["texts"]:
            return cache.revive(cached, texts)
        return comp

    # FFmpeg (LGPL yig'ma)
    ff_version = (rt.get("ffmpeg") or {}).get("ref") or _pin(SETUP_RENDER, "VERSION") or UNKNOWN
    ff_dir = staged / "local-render"
    ff_texts = [t for t in (texts.add_file(ff_dir / "LICENSE.md", "FFmpeg LICENSE.md"),
                            texts.add_file(ff_dir / "COPYING.LGPLv2.1")) if t]
    flags = " ".join((rt.get("ffmpeg") or {}).get("configure_common", []))
    out.append(from_cache_or(component(
        "runtime", "FFmpeg", ff_version, "LGPL-2.1-or-later", basis="setup_local_render.py + runtimes.toml",
        texts=ff_texts, url=f"https://ffmpeg.org/releases/ffmpeg-{ff_version}.tar.xz",
        notes=(f"GPL/nonfree/version3 o'chiq, dinamik bog'lanadi (ADR-0004). {ref_note('ffmpeg')}. "
               f"Reliz bayroqlari: {flags}"))))

    # dav1d (AV1 dekoderi, BSD-2) - FFmpeg ichiga statik bog'langan.
    dav1d = rt.get("dav1d") or {}
    dav1d_version = dav1d.get("version") or _pin(SETUP_RENDER, "DAV1D_VERSION") or UNKNOWN
    out.append(from_cache_or(component(
        "runtime", "dav1d", dav1d_version, dav1d.get("license") or "BSD-2-Clause",
        basis="setup_local_render.py + runtimes.toml",
        texts=[t for t in [texts.add_file(ff_dir / "dav1d.COPYING", "dav1d COPYING")] if t],
        url=dav1d.get("url") or f"https://downloads.videolan.org/pub/videolan/dav1d/{dav1d_version}/",
        via="FFmpeg (--enable-libdav1d)",
        notes=(f"AV1 dasturiy dekoderi. Statik yig'iladi va FFmpeg ichiga bog'lanadi (alohida dylib yo'q); "
               f"BSD-2 shartiga ko'ra COPYING matni `bin/licenses/local-render/dav1d.COPYING` da. "
               f"SHA-256 {dav1d.get('sha256') or _pin(SETUP_RENDER, 'DAV1D_SHA256') or UNKNOWN}."))))

    # llama.cpp (ggml)
    llama_src = staged / "llama.cpp" / "SOURCE.json"
    llama_meta = json.loads(llama_src.read_text(encoding="utf-8")) if llama_src.is_file() else {}
    llama_version = (rt.get("llama_cpp") or {}).get("ref") or llama_meta.get("release") or _pin(SETUP_LLM, "RUNTIME_RELEASE")
    out.append(from_cache_or(component(
        "runtime", "llama.cpp (ggml)", llama_version or UNKNOWN, llama_meta.get("license") or "MIT",
        basis="SOURCE.json" if llama_meta else "TZ 16-bo'lim",
        texts=[t for t in [texts.add_file(staged / "llama.cpp" / "LICENSE", "llama.cpp LICENSE")] if t],
        url=llama_meta.get("source_url", "https://github.com/ggml-org/llama.cpp"),
        notes=f"llama-server va libggml/libllama dylib'lari. {ref_note('llama_cpp')}.")))

    # whisper.cpp - reja (runtimes.toml), lokal alfada yig'ilmagan.
    wref = (rt.get("whisper_cpp") or {}).get("ref") or UNKNOWN
    out.append(from_cache_or(component(
        "runtime", "whisper.cpp (ggml)", wref, "MIT", basis="TZ 16-bo'lim",
        url=(rt.get("whisper_cpp") or {}).get("repo", ""),
        notes=f"{ref_note('whisper_cpp')}. Lokal alfa paketiga kirmaydi (ASR: faster-whisper). LICENSE matni lokal yo'q.")))

    # FFmpeg/libass'ning Homebrew'dan ko'chirilgan dylib'lari (lokal alfa staging).
    if ff_dir.is_dir():
        for d in sorted(p for p in ff_dir.iterdir() if p.is_dir()):
            sbom = d / "sbom.spdx.json"
            version, lic = UNKNOWN, UNKNOWN
            if sbom.is_file():
                pk = next((p for p in json.loads(sbom.read_text(encoding="utf-8")).get("packages", [])
                           if p.get("name") == d.name), None)
                if pk:
                    version = pk.get("versionInfo") or UNKNOWN
                    concl = pk.get("licenseConcluded") or ""
                    lic = concl if concl and concl != "NOASSERTION" else UNKNOWN
            ids = texts.add_dir(d)
            out.append(component("runtime", d.name, version, lic, basis="Homebrew SBOM", texts=ids,
                                 category="native", via="FFmpeg/libass bog'liqligi (lokal alfa, Homebrew bottle)",
                                 notes=" ".join(x for x in ("Dinamik bog'lanadi (bin/lib).", NATIVE_NOTES.get(d.name, ""),
                                                          "" if ids else "LICENSE fayli bottle'da yo'q.") if x)))
    else:
        out += [cache.revive(c, texts) for c in cache.group("runtime") if c["category"] == "native"]
    return out


# ---------------------------------------------------------------- shriftlar va modellar

def font_components(texts: Texts, fonts: Path = FONTS) -> list[dict]:
    out = []
    source = fonts / "SOURCE.txt"
    meta = source.read_text(encoding="utf-8") if source.is_file() else ""

    def field(label: str) -> str:
        m = re.search(rf"^{label}:\s*(.+)$", meta, re.M)
        return m.group(1).strip() if m else ""

    ofl = texts.add_file(fonts / "OFL.txt", "OFL.txt")
    for f in sorted(p for p in fonts.glob("*") if p.suffix.lower() in {".ttf", ".otf"}):
        lic = field("License")
        spdx = "OFL-1.1" if "Open Font License 1.1" in lic else (lic or UNKNOWN)
        copyright_line = next((ln for ln in meta.splitlines() if ln.startswith("Copyright")), "")
        out.append(component("font", field("Family").split(";")[0].strip() or f.stem, field("Commit")[:12] or UNKNOWN, spdx,
                             basis="SOURCE.txt", texts=[ofl] if ofl else [],
                             url=field("Source repository"), attribution=copyright_line,
                             notes=f"{f.name}: subtitr render'i uchun (o'zgartirilmagan)."))
    return out


def model_components(catalog: Path = CATALOG) -> list[dict]:
    data = json.loads(catalog.read_text(encoding="utf-8")) if catalog.is_file() else {}
    out = []
    for e in data.get("entries", []):
        out.append(component(
            "model", e.get("name") or e["id"], e.get("version") or UNKNOWN, e.get("license") or UNKNOWN,
            basis="catalog.json", url=e.get("source_url", ""), attribution=e.get("attribution") or "",
            via=f"{e['id']} ({e.get('task', '?')}, holat: {e.get('status', '?')})",
            notes="Katalogdan foydalanuvchi roziligi bilan yuklanadi; ilova paketiga kirmaydi."))
    return sorted(out, key=lambda c: c["name"].lower())


# ---------------------------------------------------------------- yig'ish

def collect(reuse: Iterable[str] = (), previous: dict | None = None) -> dict:
    reuse = set(reuse)
    texts = Texts()
    cache = Cache(previous)
    collectors: dict[str, Callable[[], list[dict]]] = {
        "python": lambda: python_components(texts),
        "npm": lambda: npm_components(texts, cache),
        "rust": lambda: rust_components(texts, cache),
        "runtime": lambda: runtime_components(texts, cache),
        "font": lambda: font_components(texts),
        "model": lambda: model_components(),
    }
    comps: list[dict] = []
    for group in GROUPS:
        if group in reuse:
            comps += [cache.revive(c, texts) for c in cache.group(group)]
        else:
            comps += collectors[group]()
    used = {t for c in comps for t in c["texts"]}
    return {
        "schema_version": SCHEMA_VERSION,
        "generator": "scripts/gen_licenses.py",
        "components": comps,
        "texts": {k: texts.items[k] for k in sorted(used)},
    }


def unresolved(data: dict) -> list[dict]:
    return [c for c in data["components"] if UNKNOWN in c["license"] or UNKNOWN in c["version"]]


def counts(data: dict) -> dict[str, int]:
    out: dict[str, int] = {}
    for c in data["components"]:
        out[c["category"]] = out.get(c["category"], 0) + 1
    return out


# ---------------------------------------------------------------- Markdown

def _cell(s: str) -> str:
    return (s or "").replace("|", "\\|").replace("\n", " ")


def _table(header: list[str], rows: list[tuple[str, ...]]) -> str:
    lines = ["| " + " | ".join(header) + " |", "| " + " | ".join("---" for _ in header) + " |"]
    lines += ["| " + " | ".join(_cell(x) for x in r) + " |" for r in rows]
    return "\n".join(lines)


def sections(data: dict) -> dict[str, str]:
    by = {}
    for c in data["components"]:
        by.setdefault(c["category"], []).append(c)
    py = [c for c in by.get("python", [])]
    native = by.get("python-native", [])
    npm = by.get("npm", [])
    rust = by.get("rust", [])
    rust_unknown = [c for c in rust if c["license"] == UNKNOWN]
    runtime = by.get("runtime", []) + by.get("native", [])
    ff = next((c for c in runtime if c["name"] == "FFmpeg"), None)
    out = {
        "python": (f"`{ENGINE_DIST}` + ekstralar: {', '.join(SHIPPED_EXTRAS)}; CPython va PyInstaller bootloader. "
                   f"{len(py)} komponent.\n\n"
                   + _table(["Paket", "Versiya", "Litsenziya", "Kim tortgan"],
                            [(c["name"], c["version"], c["license"], c["via"]) for c in py])),
        "python-native": (f"Python g'ildiraklariga biriktirilgan native kutubxonalar: {len(native)} ta. Litsenziya fayl nomi "
                          "bo'yicha (\"nom jadvali\"), yuridik tekshiruvda tasdiqlanadi. **GPL** belgisi - "
                          "ADR-0004 ga zid: generator bunday holatda yiqiladi (ADR-0015).\n\n"
                          + _table(["Kutubxona", "Fayl", "Litsenziya", "Manba", "Xavf"],
                                   [(c["name"], c["version"], c["license"], c["via"], c["risk"] and f"**{c['risk']}**")
                                    for c in native])),
        "npm": (f"`app/package-lock.json` production bog'liqliklari. {len(npm)} paket.\n\n"
                + _table(["Paket", "Versiya", "Litsenziya"], [(c["name"], c["version"], c["license"]) for c in npm])),
        "rust": (f"`app/src-tauri/Cargo.lock`: {len(rust)} crate (build vaqtidagilari ham, xavfsiz tomonga). "
                 f"{len(rust) - len(rust_unknown)} tasining litsenziyasi lokal cargo registry `Cargo.toml` idan; "
                 f"{len(rust_unknown)} tasi lokal registry'da yo'q (asosan Windows/Linux/Android crate'lari) - "
                 f"`{UNKNOWN}`, shu platformadagi build muhitida to'ldiriladi.\n\n"
                 "<details><summary>Crate'lar ro'yxati</summary>\n\n"
                 + _table(["Crate", "Versiya", "Litsenziya"], [(c["name"], c["version"], c["license"]) for c in rust])
                 + "\n\n</details>"),
        "runtimes": (_table(["Komponent", "Versiya", "Litsenziya", "Izoh"],
                            [(c["name"], c["version"], c["license"], c["notes"] or c["via"]) for c in runtime])),
        "fonts": _table(["Shrift", "Manba commit", "Litsenziya", "Mualliflik"],
                        [(c["name"], c["version"], c["license"], c["attribution"]) for c in by.get("font", [])]),
        "models": (f"`catalog/catalog.json`: {len(by.get('model', []))} yozuv.\n\n"
                   + _table(["Model", "Katalog ID", "Litsenziya", "Muallifni ko'rsatish"],
                            [(c["name"], c["via"], c["license"], c["attribution"] and f"**Majburiy:** \"{c['attribution']}\"")
                             for c in by.get("model", [])])),
        "lgpl": LGPL_NOTICE_MD.format(
            ffmpeg=ff["version"] if ff else UNKNOWN, ffmpeg_url=ff["url"] if ff else UNKNOWN,
            ffmpeg_sha=_pin(SETUP_RENDER, "SHA256") or UNKNOWN).rstrip(),
        "unresolved": _unresolved_md(data),
    }
    return out


def _unresolved_md(data: dict) -> str:
    items = unresolved(data)
    if not items:
        return "Hammasi aniqlangan."
    rust = [c for c in items if c["category"] == "rust"]
    other = [c for c in items if c["category"] != "rust"]
    lines = [f"Jami {len(items)} ta yozuvda `{UNKNOWN}` bor."]
    if other:
        lines.append("")
        lines.append(_table(["Turi", "Komponent", "Versiya", "Litsenziya"],
                            [(c["category"], c["name"], c["version"], c["license"]) for c in other]))
    if rust:
        lines.append("")
        lines.append(f"Rust ({len(rust)} crate, lokal registry'da yo'q): "
                     + ", ".join(sorted({c['name'] for c in rust})) + ".")
    return "\n".join(lines)


def render(text: str, secs: dict[str, str]) -> str:
    for name, body in secs.items():
        start, end = f"<!-- gen_licenses:{name}:start -->", f"<!-- gen_licenses:{name}:end -->"
        pat = re.compile(re.escape(start) + r".*?" + re.escape(end), re.S)
        block = f"{start}\n{body}\n{end}"
        if not pat.search(text):
            raise SystemExit(f"{OUT.name} da '{start}' belgisi topilmadi")
        text = pat.sub(lambda _m, b=block: b, text)
    return text


def dump_json(data: dict) -> str:
    return json.dumps(data, ensure_ascii=False, indent=1, sort_keys=True) + "\n"


def load_previous(path: Path = JSON_OUT) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Uchinchi tomon litsenziyalari (Markdown + UI JSON) generatsiyasi.")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--check", action="store_true", help="fayllar eskirgan bo'lsa 1 bilan chiqish")
    g.add_argument("--stdout", action="store_true", help="jadvallarni ekranga chiqarish")
    ap.add_argument("--reuse", default="", help=f"vergul bilan guruhlar ({', '.join(GROUPS)}): lokal manba "
                    "o'qilmaydi, oldingi licenses.json dan olinadi (masalan CI'da `python`)")
    ap.add_argument("--report", action="store_true", help=f"{UNKNOWN} yozuvlar va sonlarni chiqarish")
    a = ap.parse_args(argv)

    reuse = [r.strip() for r in a.reuse.split(",") if r.strip()]
    bad = set(reuse) - set(GROUPS)
    if bad:
        ap.error(f"noma'lum guruh: {', '.join(sorted(bad))}")
    data = collect(reuse, load_previous())
    violations = gpl_violations(data)
    if violations:
        print("XATO: sidecar'ga GPL komponent kiradi (ADR-0004, ADR-0015):\n  " + "\n  ".join(violations),
              file=sys.stderr)
        return 2
    secs = sections(data)
    if a.report:
        print(json.dumps({"counts": counts(data), "unresolved": [c["id"] for c in unresolved(data)]},
                         ensure_ascii=False, indent=1))
    if a.stdout:
        for name, body in secs.items():
            print(f"## {name}\n\n{body}\n")
        return 0
    old_md = OUT.read_text(encoding="utf-8")
    new_md = render(old_md, secs)
    new_json = dump_json(data)
    old_json = JSON_OUT.read_text(encoding="utf-8") if JSON_OUT.is_file() else ""
    if a.check:
        stale = [p.relative_to(ROOT).as_posix() for p, o, n in ((OUT, old_md, new_md), (JSON_OUT, old_json, new_json))
                 if o != n]
        if stale:
            print(f"eskirgan: {', '.join(stale)} - `make licenses` ni ishga tushiring", file=sys.stderr)
            return 1
        print("ok")
        return 0
    OUT.write_text(new_md, encoding="utf-8")
    JSON_OUT.parent.mkdir(parents=True, exist_ok=True)
    JSON_OUT.write_text(new_json, encoding="utf-8")
    print(f"yangilandi: {OUT.relative_to(ROOT)}, {JSON_OUT.relative_to(ROOT)} ({len(data['components'])} komponent)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
