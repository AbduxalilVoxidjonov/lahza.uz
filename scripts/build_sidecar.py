"""Engine'ni PyInstaller bilan bitta faylga yig'ib, Tauri sidecar sifatida joylaydi (M2-PKG-1).

    python scripts/build_sidecar.py [--clean] [--target <triple>] [--dry-run]
    python scripts/build_sidecar.py --verify       # binaries/ dagi sidecar xeshini tekshirish

Natija:
    app/src-tauri/binaries/lahza-engine-<target-triple>[.exe]
    app/src-tauri/binaries/lahza-engine-<target-triple>[.exe].sha256
    build/sidecar/sidecar.json                     (triple, sha256, hajm, versiya)

Target triple tartibi: `--target` > `TAURI_ENV_TARGET_TRIPLE` > `rustc -vV` dagi "host:" >
platformadan taxmin (faqat rustc yo'q bo'lsa, ogohlantirish bilan). Tauri talabi: docs/10.

NSIS qayta o'rnatishda eski sidecar qolib ketishi (tauri#15134) sababli har build oldidan shu
triple uchun eski fayllar o'chiriladi va yangi faylning sha256 xeshi yoniga yoziladi; CI
`--verify` bilan xesh mosligini tekshiradi.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENGINE = ROOT / "engine"
PKG_DIR = ENGINE / "src" / "lahza_engine"
BIN_DIR = ROOT / "app" / "src-tauri" / "binaries"
WORK = ROOT / "build" / "sidecar"
NAME = "lahza-engine"

# Paket ichidagi ma'lumot fayllari (`--collect-data lahza_engine` ularni oladi).
# Majburiylari - bo'lmasa build to'xtatiladi; `subtitle/fonts/` bo'lsa u ham avtomatik kiradi.
REQUIRED_DATA = ["highlight/prompts/*.txt", "db/*.sql", "render/*.json"]

# uvicorn protokol/loop implementatsiyalarini satr nomi bilan yuklaydi - statik tahlil ko'rmaydi.
HIDDEN_IMPORTS = [
    "uvicorn.logging",
    "uvicorn.loops.auto",
    "uvicorn.loops.asyncio",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.http.h11_impl",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.protocols.websockets.wsproto_impl",
    "uvicorn.protocols.websockets.websockets_impl",
    # uvicorn >= 0.35: `websockets` o'rnatilgan bo'lsa auto shu sans-I/O implementatsiyani tanlaydi.
    "uvicorn.protocols.websockets.websockets_sansio_impl",
    "websockets",
    "uvicorn.lifespan.on",
    "uvicorn.lifespan.off",
]

# Ixtiyoriy backendlar: venv'da o'rnatilgan bo'lsa kiritiladi (pyproject optional-dependencies).
OPTIONAL_IMPORTS = {
    "faster_whisper": "faster_whisper",
    "ctranslate2": "ctranslate2",
    "tokenizers": "tokenizers",
    "onnxruntime": "onnxruntime",  # Silero VAD (ONNX)
    "fontTools": "fontTools",  # shrift tekshiruvi / subset
    "xxhash": "xxhash",  # tez xesh
}

# Native libraries and runtime data are loaded dynamically by these backends.
COLLECT_ALL = {"faster_whisper", "ctranslate2", "tokenizers", "onnxruntime"}
REQUIRED_BACKENDS = COLLECT_ALL | {"fontTools"}

# GPL komponentlar sidecar'ga hech qachon kirmaydi (ADR-0004, ADR-0015). PyAV (`av`) g'ildiraklari
# libx264/libx265 bilan statik yig'ilgan FFmpeg'ni olib keladi; faster-whisper uni
# `lahza_engine.asr.fw_compat` qo'riqchisi orqali "import" qiladi, dekodni LGPL FFmpeg bajaradi.
FORBIDDEN_MODULES = ["av"]
# PyInstaller TOC'larida shu belgilar uchrasa build rad etiladi (PyAV va uning ichki FFmpeg'i).
FORBIDDEN_TOC_PATTERNS = [
    r"""['"]av(\.[\w.]+)?['"]""",  # PyAV moduli yoki submodullari
    r"av[/\\]\.dylibs", r"av\.libs",  # delocate/auditwheel/delvewheel bilan qo'shilgan dylib/so/dll
    r"libx264", r"libx265",
]


def check_desktop_backends(available: list[str]) -> None:
    missing = REQUIRED_BACKENDS - set(available)
    if missing:
        raise SystemExit("Desktop inference dependencies missing: " + ", ".join(sorted(missing))
                         + "; install engine desktop dependencies before building")


def prepare_local_catalog(destination: Path) -> str:
    """Sign a generated local-alpha catalog; never modify the source catalog.

    The ephemeral private key is discarded. This is local build trust, not a
    production release signing identity.
    """
    import base64

    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from lahza_engine.models.catalog import Catalog, sign

    key = Ed25519PrivateKey.generate()
    private = base64.b64encode(key.private_bytes(
        serialization.Encoding.Raw, serialization.PrivateFormat.Raw,
        serialization.NoEncryption(),
    )).decode()
    public = base64.b64encode(key.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw,
    )).decode()
    catalog = Catalog.model_validate_json((ROOT / "catalog/catalog.json").read_text())
    destination.mkdir(parents=True, exist_ok=True)
    (destination / "catalog.json").write_text(
        sign(catalog, private).model_dump_json(indent=2) + "\n", encoding="utf-8",
    )
    (destination / "catalog.pub").write_text(public + "\n", encoding="utf-8")
    return public

def prepare_catalog(destination: Path) -> str:
    """Use an explicit release identity, or generate trust for a local build."""
    import base64

    from lahza_engine.models.catalog import Catalog, verify

    if "LAHZA_CATALOG_PUBKEY" not in os.environ:
        return prepare_local_catalog(destination)
    public = os.environ["LAHZA_CATALOG_PUBKEY"].strip()
    try:
        raw = base64.b64decode(public, validate=True)
        if len(raw) != 32:
            raise ValueError("expected 32-byte Ed25519 public key")
        source = ROOT / "catalog/catalog.json"
        contents = source.read_bytes()
        verify(Catalog.model_validate_json(contents), public)
    except (ValueError, RuntimeError) as exc:
        raise SystemExit("LAHZA_CATALOG_PUBKEY must verify the signed source catalog") from exc
    destination.mkdir(parents=True, exist_ok=True)
    (destination / "catalog.json").write_bytes(contents)
    (destination / "catalog.pub").write_text(public + "\n", encoding="utf-8")
    return public


# Sidecar'ga hech qachon kerak bo'lmaydigan dasturchi paketlari.
EXCLUDES = ["tkinter", "pytest", "_pytest", "IPython", "matplotlib", "PyInstaller", "mypy", "ruff",
            *FORBIDDEN_MODULES]

_MACHINE = {"arm64": "aarch64", "aarch64": "aarch64", "x86_64": "x86_64", "amd64": "x86_64"}


def _guess_triple() -> str:
    arch = _MACHINE.get(platform.machine().lower())
    if arch is None:
        raise SystemExit(f"noma'lum arxitektura: {platform.machine()} - --target bering")
    if sys.platform == "darwin":
        return f"{arch}-apple-darwin"
    if sys.platform == "win32":
        return f"{arch}-pc-windows-msvc"
    if sys.platform.startswith("linux"):
        return f"{arch}-unknown-linux-gnu"
    raise SystemExit(f"noma'lum platforma: {sys.platform} - --target bering")


def target_triple(explicit: str | None = None) -> tuple[str, str]:
    """(triple, manba)."""
    if explicit:
        return explicit, "--target"
    env = os.environ.get("TAURI_ENV_TARGET_TRIPLE")
    if env:
        return env, "TAURI_ENV_TARGET_TRIPLE"
    if shutil.which("rustc"):
        out = subprocess.run(["rustc", "-vV"], capture_output=True, text=True, check=True).stdout
        for line in out.splitlines():
            if line.startswith("host:"):
                return line.split(":", 1)[1].strip(), "rustc -vV"
        raise SystemExit("rustc -vV dan host triple topilmadi")
    triple = _guess_triple()
    print(f"ogohlantirish: rustc topilmadi, triple platformadan taxmin qilindi: {triple}", file=sys.stderr)
    return triple, "platforma (taxmin)"


def exe_suffix(triple: str) -> str:
    return ".exe" if "windows" in triple else ""


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def engine_version() -> str:
    with (ENGINE / "pyproject.toml").open("rb") as f:
        return tomllib.load(f)["project"]["version"]


def package_data_files() -> list[Path]:
    """lahza_engine ichidagi .py bo'lmagan fayllar - PyInstaller `--collect-data` shularni oladi."""
    skip = {".py", ".pyc", ".pyo"}
    return sorted(
        p.relative_to(PKG_DIR)
        for p in PKG_DIR.rglob("*")
        if p.is_file() and p.suffix not in skip and p.name != ".gitkeep" and "__pycache__" not in p.parts
    )


def check_package_data() -> list[Path]:
    files = package_data_files()
    missing = [pat for pat in REQUIRED_DATA if not list(PKG_DIR.glob(pat))]
    if missing:
        raise SystemExit("paket ma'lumot fayllari topilmadi: " + ", ".join(missing))
    return files


def optional_imports() -> list[str]:
    import importlib.util

    return [mod for mod, name in OPTIONAL_IMPORTS.items() if importlib.util.find_spec(name) is not None]


def forbidden_in_toc(build_dir: Path) -> list[str]:
    """PyInstaller TOC fayllarida GPL komponent (PyAV, libx264/libx265) izlari; bo'sh = toza."""
    import re

    pats = [re.compile(p) for p in FORBIDDEN_TOC_PATTERNS]
    hits: list[str] = []
    for toc in sorted(build_dir.rglob("*.toc")):
        text = toc.read_text(encoding="utf-8", errors="replace")
        for pat in pats:
            m = pat.search(text)
            if m:
                hits.append(f"{toc.name}: {m.group(0)}")
    return hits


def check_no_gpl_bundle(build_dir: Path) -> None:
    """Yig'ilgan sidecar tarkibida GPL komponent bo'lsa build to'xtatiladi (ADR-0015)."""
    if not list(build_dir.rglob("*.toc")):
        raise SystemExit(f"PyInstaller TOC topilmadi ({build_dir}): GPL tekshiruvi bajarilmadi")
    hits = forbidden_in_toc(build_dir)
    if hits:
        raise SystemExit("GPL komponent sidecar'ga kirdi (ADR-0015): " + "; ".join(hits))


def pyinstaller_cmd(entry: Path, clean: bool, extra_hidden: list[str]) -> list[str]:
    cmd = [
        sys.executable, "-m", "PyInstaller", "--onefile", "--noconfirm", "--noupx", "--name", NAME,
        "--distpath", str(WORK / "dist"), "--workpath", str(WORK / "build"), "--specpath", str(WORK),
        "--paths", str(ENGINE / "src"),
        "--collect-data", "lahza_engine",
        "--collect-submodules", "lahza_engine",
    ]
    if clean:
        cmd.append("--clean")
    for mod in [*HIDDEN_IMPORTS, *extra_hidden]:
        cmd += ["--hidden-import", mod]
    for mod in sorted(COLLECT_ALL.intersection(extra_hidden)):
        cmd += ["--collect-all", mod]
    for mod in EXCLUDES:
        cmd += ["--exclude-module", mod]
    cmd.append(str(entry))
    return cmd


def remove_stale(triple: str) -> list[Path]:
    """Shu triple uchun eski sidecar va xesh fayllarini o'chiradi (NSIS eski sidecar muammosi)."""
    removed = []
    if BIN_DIR.exists():
        for p in BIN_DIR.glob(f"{NAME}-{triple}*"):
            p.unlink()
            removed.append(p)
    return removed


def verify(triple: str) -> int:
    target = BIN_DIR / f"{NAME}-{triple}{exe_suffix(triple)}"
    sha_file = target.with_name(target.name + ".sha256")
    if not target.exists():
        print(f"XATO: sidecar yo'q: {target}", file=sys.stderr)
        return 1
    if not sha_file.exists():
        print(f"XATO: xesh fayli yo'q: {sha_file}", file=sys.stderr)
        return 1
    expected = sha_file.read_text(encoding="utf-8").split()[0]
    actual = sha256_file(target)
    if expected != actual:
        print(f"XATO: xesh mos emas\n  kutilgan: {expected}\n  haqiqiy:  {actual}", file=sys.stderr)
        return 1
    print(f"ok: {target.name} sha256 {actual}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Engine sidecar'ini PyInstaller bilan yig'ish (Tauri externalBin).")
    ap.add_argument("--clean", action="store_true", help="PyInstaller keshini tozalash")
    ap.add_argument("--target", help="Rust target triple (standart: rustc -vV host)")
    ap.add_argument("--dry-run", action="store_true",
                    help="hech narsa yig'may/o'chirmay: triple, ma'lumot fayllari va buyruqni ko'rsatish")
    ap.add_argument("--verify", action="store_true", help="binaries/ dagi sidecar sha256 xeshini tekshirish")
    ap.add_argument("--catalog-only", action="store_true",
                    help="prepare signed catalog only; no PyInstaller or sidecar changes")
    a = ap.parse_args(argv)
    if a.catalog_only and (a.dry_run or a.verify):
        ap.error("--catalog-only cannot be combined with --dry-run or --verify")
    if a.catalog_only:
        prepare_catalog(WORK / "catalog")
        return 0

    triple, source = target_triple(a.target)
    if a.verify:
        return verify(triple)

    ext = exe_suffix(triple)
    entry = WORK / "lahza_entry.py"
    data = check_package_data()
    extra = optional_imports()
    cmd = pyinstaller_cmd(entry, a.clean, extra)
    target = BIN_DIR / f"{NAME}-{triple}{ext}"

    print(f"triple: {triple} ({source})")
    print(f"versiya: {engine_version()}")
    print(f"ma'lumot fayllari ({len(data)}): " + ", ".join(str(p) for p in data))
    print(f"ixtiyoriy backendlar: {', '.join(extra) or '-'}")
    print("buyruq: " + " ".join(cmd))
    print(f"natija: {target}")
    if a.dry_run:
        return 0

    check_desktop_backends(extra)

    if (sys.platform == "win32") != (ext == ".exe"):
        raise SystemExit(f"cross-build qo'llanmaydi: {sys.platform} da {triple} uchun yig'ib bo'lmaydi")

    WORK.mkdir(parents=True, exist_ok=True)
    prepare_catalog(WORK / "catalog")
    entry.write_text(
        # PyInstaller must dispatch resource_tracker/spawn helpers before argparse.
        "import multiprocessing\nmultiprocessing.freeze_support()\n\n"
        "import importlib\nimport json\nimport sys\nfrom pathlib import Path\n\n"
        "from lahza_engine.cli import main\n\n"
        "if sys.argv[1:] == ['--packaging-check']:\n"
        "    from lahza_engine.asr.fw_compat import av_guard_active, install_av_guard\n"
        "    install_av_guard()  # faster_whisper `import av` qiladi; PyAV to'plamda yo'q (ADR-0015)\n"
        f"    modules = {extra!r}\n"
        "    for name in modules:\n"
        "        importlib.import_module(name)\n"
        "    if not av_guard_active():\n"
        "        raise SystemExit('PyAV sidecar ichida yuklangan (ADR-0015)')\n"
        "    importlib.import_module('lahza_engine.models.local_bootstrap')\n"
        "    importlib.import_module('lahza_engine.api.app')\n"
        "    package = importlib.import_module('lahza_engine')\n"
        "    fonts = Path(package.__file__).parent / 'subtitle' / 'fonts'\n"
        "    print(json.dumps({'imported_backends': modules, 'av_guard': True,\n"
        "                      'fonts': sorted(p.name for p in fonts.glob('*'))}))\n"
        "elif sys.argv[1:] == ['--packaging-mp-check']:\n"
        "    from multiprocessing import shared_memory\n"
        "    block = shared_memory.SharedMemory(create=True, size=16)\n"
        "    block.close()\n    block.unlink()\n"
        "    print(json.dumps({'shared_memory': True}))\n"
        "elif len(sys.argv) == 4 and sys.argv[1] == '--packaging-asr-check':\n"
        "    from pathlib import Path\n"
        "    from lahza_engine.asr.base import AsrOptions\n"
        "    from lahza_engine.asr.faster_whisper_backend import FasterWhisperBackend\n"
        "    backend = FasterWhisperBackend(Path(sys.argv[2]), 'packaging-smoke', device='cpu')\n"
        "    words = backend.transcribe_chunk(Path(sys.argv[3]), 0, AsrOptions())\n"
        "    print(json.dumps({'words': len(words), 'device': 'cpu', 'compute_type': 'int8'}))\n"
        "    sys.exit(0 if words else 1)\n"
        "else:\n"
        "    sys.exit(main())\n",
        encoding="utf-8",
    )
    subprocess.run(cmd, check=True, cwd=ENGINE)
    check_no_gpl_bundle(WORK / "build" / NAME)

    built = WORK / "dist" / f"{NAME}{ext}"
    BIN_DIR.mkdir(parents=True, exist_ok=True)
    for p in remove_stale(triple):
        print(f"eski fayl o'chirildi: {p.name}")
    shutil.copy2(built, target)
    digest = sha256_file(target)
    target.with_name(target.name + ".sha256").write_text(f"{digest}  {target.name}\n", encoding="utf-8")
    manifest = {
        "name": target.name,
        "triple": triple,
        "sha256": digest,
        "size_bytes": target.stat().st_size,
        "engine_version": engine_version(),
        "python": platform.python_version(),
        "optional_backends": extra,
        "package_data": [str(p) for p in data],
        "catalog_trust": ("explicit-source" if "LAHZA_CATALOG_PUBKEY" in os.environ
                          else "ephemeral-local-alpha"),
    }
    (WORK / "sidecar.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"sidecar: {target}\nsha256: {digest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
