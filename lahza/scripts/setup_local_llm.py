#!/usr/bin/env python3
"""Explicit, pinned local Qwen3 bootstrap. No arguments prints a plan without I/O.

Run using engine/.venv/bin/python with the engine installed editable.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

import httpx
from lahza_engine.models.catalog import Task
from lahza_engine.models.downloader import download, sha256_file
from lahza_engine.models.store import InstalledModel, ModelStore

ROOT = Path(__file__).resolve().parents[1]
MODEL_REPO = "Qwen/Qwen3-4B-GGUF"
MODEL_REVISION = "bc640142c66e1fdd12af0bd68f40445458f3869b"
MODEL_FILE = "Qwen3-4B-Q4_K_M.gguf"
MODEL_SIZE = 2497280256
MODEL_SHA256 = "7485fe6f11af29433bc51cab58009521f205840f5b4ae3a32fa7f92e8534fdf5"
MODEL_ID = "custom:qwen3-4b-q4-k-m"
MODEL_BASE = f"https://huggingface.co/{MODEL_REPO}/resolve/{MODEL_REVISION}"
RUNTIME_RELEASE = "b11669"
RUNTIME_FILE = "llama-b11669-bin-macos-arm64.tar.gz"
RUNTIME_URL = f"https://github.com/ggml-org/llama.cpp/releases/download/{RUNTIME_RELEASE}/{RUNTIME_FILE}"
RUNTIME_SIZE = 12191582
RUNTIME_SHA256 = "dbed55493d72bc1ba2babc8770d669c2289b5bc4ee9fb2a4dfc158d45b7d13fd"


def verified_file(url: str, dest: Path, digest: str, size: int, *, consent: bool) -> Path:
    """Always hash the full existing file; never silently replace a corrupt artifact."""
    if dest.exists():
        if dest.stat().st_size != size or sha256_file(dest) != digest:
            raise ValueError(f"Existing artifact failed verification: {dest}")
        return dest
    if not consent:
        raise ValueError("Network access requires --consent")
    return download([url], dest, digest, size)


def install_model(root: Path, *, consent: bool, set_default: bool = False) -> InstalledModel:
    if not consent:
        raise ValueError("Model installation requires --model --consent")
    store = ModelStore(root)
    target = store.model_dir(Task.LLM, "qwen3-4b-q4-k-m").resolve()
    weights = verified_file(f"{MODEL_BASE}/{MODEL_FILE}", target / MODEL_FILE,
                            MODEL_SHA256, MODEL_SIZE, consent=consent)
    metadata = target / "metadata"
    metadata.mkdir(exist_ok=True)
    # Git-tracked notices are verified against blobs in the pinned HF tree.
    with httpx.Client(timeout=60, follow_redirects=True) as client:
        response = client.get(
            f"https://huggingface.co/api/models/{MODEL_REPO}/revision/{MODEL_REVISION}",
            params={"blobs": "true"},
        )
        response.raise_for_status()
        tree = response.json()
        if tree["sha"] != MODEL_REVISION:
            raise ValueError("Model metadata revision mismatch")
        entries = {f["rfilename"]: f for f in tree["siblings"]}
        records = []
        for name in ("LICENSE", "README.md"):
            entry = entries[name]
            dest = metadata / name
            if not dest.exists():
                download([f"{MODEL_BASE}/{name}"], dest, None, entry["size"], client=client)
            content = dest.read_bytes()
            blob = hashlib.sha1(b"blob " + str(len(content)).encode() + b"\0" + content).hexdigest()
            if len(content) != entry["size"] or blob != entry["blobId"]:
                raise ValueError(f"Pinned notice verification failed: {name}")
            records.append({"file": name, "sha256": sha256_file(dest), "blob": blob})
    (metadata / "SOURCE.json").write_text(json.dumps({
        "repository": MODEL_REPO, "revision": MODEL_REVISION, "license": "Apache-2.0",
        "url": f"{MODEL_BASE}/{MODEL_FILE}", "file": MODEL_FILE,
        "size_bytes": MODEL_SIZE, "sha256": MODEL_SHA256, "notices": records,
        "catalog_approved": False,
    }, indent=2) + "\n", encoding="utf-8")
    model = InstalledModel(id=MODEL_ID, task=Task.LLM, version=MODEL_REVISION,
                           path=str(weights), source="custom", verified=False)
    store.register([model])  # register preserves an existing default via setdefault.
    if set_default:
        store.set_default(Task.LLM, model.id)
    return model


def safe_extract(archive: Path, destination: Path) -> Path:
    """Validate every member/link before extracting; forbid writes outside one root."""
    base = destination.resolve()
    with tarfile.open(archive) as tar:
        members = tar.getmembers()
        for member in members:
            path = base / member.name
            if not path.resolve().is_relative_to(base) or Path(member.name).is_absolute():
                raise ValueError(f"Unsafe archive path: {member.name}")
            if not (member.isfile() or member.isdir() or member.issym()):
                raise ValueError(f"Unsupported archive member: {member.name}")
            if member.issym():
                link = Path(member.linkname)
                if link.is_absolute() or not (path.parent / link).resolve().is_relative_to(base):
                    raise ValueError(f"Unsafe archive link: {member.name}")
        # data_filter also checks link chains, modes and symlink traversal on extraction.
        if not hasattr(tarfile, "data_filter"):
            raise RuntimeError("Python with tarfile.data_filter required")
        tar.extractall(base, members=members, filter="data")
    runtime = base / f"llama-{RUNTIME_RELEASE}"
    if not (runtime / "llama-server").is_file() or not (runtime / "LICENSE").is_file():
        raise ValueError("Runtime archive missing server or LICENSE")
    return runtime


def run(args: list[str], **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(args, check=True, capture_output=True, text=True, **kwargs)


def dependencies(binary: Path) -> list[str]:
    lines = run(["otool", "-L", str(binary)]).stdout.splitlines()[1:]
    deps = [line.strip().split(" (compatibility version", 1)[0] for line in lines]
    return deps[1:] if binary.suffix == ".dylib" else deps


def system_library(dep: str) -> bool:
    return dep.startswith(("/usr/lib/", "/System/Library/"))


def audit_runtime(runtime: Path) -> list[dict]:
    """Audit load commands, install IDs, rpaths and architectures of the full bundle."""
    inventory = []
    for binary in sorted({p.resolve() for p in runtime.iterdir()
                          if p.name == "llama-server" or p.suffix == ".dylib"}):
        arches = run(["lipo", "-archs", str(binary)]).stdout.strip()
        if "arm64" not in arches.split():
            raise ValueError(f"Not arm64: {binary}")
        loads = run(["otool", "-l", str(binary)]).stdout
        rpaths = re.findall(r"cmd LC_RPATH\s+cmdsize \d+\s+path (.*?) \(offset", loads)
        if any(p not in ("@loader_path", "@executable_path") for p in rpaths):
            raise ValueError(f"Nonrelocatable rpath in {binary}: {rpaths}")
        deps = dependencies(binary)
        for dep in deps:
            if system_library(dep):
                continue
            if not dep.startswith(("@rpath/", "@loader_path/", "@executable_path/")):
                raise ValueError(f"Nonrelocatable dependency: {dep}")
            name = dep.split("/", 1)[1]
            resolved = (runtime / name).resolve()
            if not resolved.is_relative_to(runtime.resolve()) or not resolved.is_file():
                raise ValueError(f"Missing runtime dependency: {dep}")
            if dep.startswith("@rpath/") and not rpaths:
                raise ValueError(f"Missing loader rpath in {binary}")
        if binary.suffix == ".dylib":
            install_id = run(["otool", "-D", str(binary)]).stdout.splitlines()[1].strip()
            if not install_id.startswith(("@rpath/", "@loader_path/")):
                raise ValueError(f"Nonrelocatable dylib ID: {install_id}")
        inventory.append({"file": binary.name, "sha256": sha256_file(binary),
                          "architectures": arches, "dependencies": deps, "rpaths": rpaths,
                          "minos": re.findall(r"\bminos\s+(\S+)", loads)})
    return inventory


def publish_runtime(stage: Path, destination: Path) -> None:
    """Preflight every collision before writing; never overwrite another runtime."""
    files = [p for p in stage.rglob("*") if p.is_file() or p.is_symlink()]
    for source in files:
        target = destination / source.relative_to(stage)
        for parent in target.parents:
            if parent == destination.parent:
                break
            if parent.is_symlink() or (parent.exists() and not parent.is_dir()):
                raise ValueError(f"Unsafe destination directory: {parent}")
        if target.exists() or target.is_symlink():
            same = (target.is_symlink() and source.is_symlink()
                    and os.readlink(target) == os.readlink(source))
            if not target.is_symlink() and not source.is_symlink() and target.is_file():
                same = sha256_file(target) == sha256_file(source)
            if not same:
                raise ValueError(f"Refusing to overwrite staged artifact: {target}")
    for source in files:
        target = destination / source.relative_to(stage)
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists() and not target.is_symlink():
            if source.is_symlink():
                target.symlink_to(os.readlink(source))
            else:
                shutil.copy2(source, target)


def stage_runtime(cache: Path, destination: Path, *, consent: bool) -> None:
    if sys.platform != "darwin" or platform.machine() != "arm64":
        raise ValueError("Runtime staging requires macOS arm64")
    archive = verified_file(RUNTIME_URL, cache / RUNTIME_FILE,
                            RUNTIME_SHA256, RUNTIME_SIZE, consent=consent)
    # Re-extract verified archive into a fresh directory, never reuse mutable extraction.
    with tempfile.TemporaryDirectory(prefix="lahza-llm-") as temporary:
        work = Path(temporary)
        runtime = safe_extract(archive, work / "extract")
        inventory = audit_runtime(runtime)
        stage = work / "relocated runtime"
        stage.mkdir()
        for source in runtime.iterdir():
            if source.name == "llama-server" or source.suffix == ".dylib":
                shutil.copy2(source, stage / source.name, follow_symlinks=False)
        audit_runtime(stage)
        env = {k: v for k, v in os.environ.items() if not k.startswith("DYLD_")}
        result = run([str(stage / "llama-server"), "--version"], cwd=work, env=env, timeout=30)
        loaded = run([str(stage / "llama-server"), "--version"], cwd=work,
                     env={**env, "DYLD_PRINT_LIBRARIES": "1"}, timeout=30)
        if "/opt/homebrew/" in loaded.stderr or "/usr/local/" in loaded.stderr:
            raise ValueError("Relocated server loaded external libraries")
        notices = stage / "licenses/llama.cpp"
        notices.mkdir(parents=True)
        shutil.copy2(runtime / "LICENSE", notices / "LICENSE")
        (notices / "SOURCE.json").write_text(json.dumps({
            "repository": "ggml-org/llama.cpp", "release": RUNTIME_RELEASE, "license": "MIT",
            "url": RUNTIME_URL, "size_bytes": RUNTIME_SIZE, "sha256": RUNTIME_SHA256,
            "source_url": f"https://github.com/ggml-org/llama.cpp/tree/{RUNTIME_RELEASE}",
            "source_archive": f"https://github.com/ggml-org/llama.cpp/archive/refs/tags/{RUNTIME_RELEASE}.tar.gz",
            "version": result.stdout + result.stderr, "inventory": inventory,
        }, indent=2) + "\n", encoding="utf-8")
        publish_runtime(stage, destination)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--consent", action="store_true", help="Allow explicit network access")
    parser.add_argument("--model", action="store_true", help="Install pinned Qwen3 GGUF (2.50 GB)")
    parser.add_argument("--set-default", action="store_true", help="Replace existing LLM default")
    parser.add_argument("--stage", nargs="?", type=Path, metavar="BIN_DIR",
                        const=ROOT / "app/src-tauri/resources/bin",
                        help="Stage pinned macOS arm64 runtime, preserving existing files")
    parser.add_argument("--cache-dir", type=Path, default=ROOT / "build/local-llm")
    parser.add_argument("--models-dir", type=Path)
    args = parser.parse_args(argv)
    if args.set_default and not args.model:
        parser.error("--set-default requires --model")
    if (args.model or args.stage is not None) and not args.consent:
        parser.error("--model / --stage requires --consent; no files changed")
    if not args.model and args.stage is None:
        print(f"Plan only: {MODEL_REPO}@{MODEL_REVISION}/{MODEL_FILE} (Apache-2.0, {MODEL_SIZE} bytes)")
        print(f"Runtime: {RUNTIME_URL} (MIT, {RUNTIME_SIZE} bytes)")
        print("Use --model and/or --stage with --consent to install.")
        return 0
    try:
        if args.stage is not None:
            stage_runtime(args.cache_dir, args.stage, consent=args.consent)
        if args.model:
            from lahza_engine.config import Settings
            model = install_model(args.models_dir or Settings().models_dir,
                                  consent=args.consent, set_default=args.set_default)
            print(model.model_dump_json(indent=2))
    except (ValueError, OSError, RuntimeError, httpx.HTTPError, subprocess.SubprocessError,
            tarfile.TarError, KeyError) as exc:
        parser.exit(1, f"Local LLM setup failed: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
