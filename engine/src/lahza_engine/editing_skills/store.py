"""Bounded extraction and atomic publication of explicitly selected local packages."""
from __future__ import annotations

import json
import os
import shutil
import stat
import tempfile
import threading
import uuid
import zipfile
from pathlib import Path

from .model import Skill, Sticker, safe_asset

LOCK = threading.RLock()
MAX_ARCHIVE = 32 * 1024 * 1024
MAX_TOTAL = 32 * 1024 * 1024
MAX_FILE = 16 * 1024 * 1024
MAX_MANIFEST = 64 * 1024
MAX_ENTRIES = 128


def parse(raw: bytes) -> Skill:
    if len(raw) > MAX_MANIFEST:
        raise ValueError("Manifest exceeds 64 KiB")
    def unique(pairs):
        obj = {}
        for k, v in pairs:
            if k in obj:
                raise ValueError("Duplicate JSON key")
            obj[k] = v
        return obj
    return Skill.model_validate(json.loads(raw, object_pairs_hook=unique))


class SkillStore:
    def __init__(self, data_dir: Path):
        self.root = data_dir.resolve() / "Skills"
        if self.root.is_symlink():
            raise ValueError("Skills directory must not be a symlink")
        self.root.mkdir(parents=True, exist_ok=True)

    def directory(self, sid: str) -> Path:
        from pydantic import TypeAdapter

        from .model import Slug
        TypeAdapter(Slug).validate_python(sid)
        p = self.root / sid
        if p.is_symlink() or p.resolve().parent != self.root:
            raise ValueError("Unsafe installed skill path")
        return p

    def load(self, sid: str) -> Skill:
        return parse((self.directory(sid) / "skill.json").read_bytes())

    def items(self) -> list[dict]:
        out = []
        for p in sorted(self.root.iterdir()):
            if p.name.startswith(".") or not p.is_dir():
                continue
            skill = self.load(p.name)
            out.append(skill.model_dump(mode="json", by_alias=True))
        return out

    def install(self, source: str, replace: bool = False) -> Skill:
        if ":" in source or source.startswith(("//", "\\\\")) or "\0" in source:
            raise ValueError("Select a local .lahzaskill or JSON file")
        path = Path(source).expanduser()
        if not path.is_file() or path.stat().st_size > MAX_ARCHIVE:
            raise ValueError("Missing file or package exceeds 32 MiB")
        with LOCK, tempfile.TemporaryDirectory(prefix=".install-", dir=self.root) as tmp:
            stage = Path(tmp) / "package"
            stage.mkdir()
            if path.suffix.lower() == ".json":
                skill = parse(path.read_bytes())
                if any(isinstance(a, Sticker) for a in skill.actions):
                    raise ValueError("Standalone manifests cannot use assets")
            elif path.suffix.lower() == ".lahzaskill":
                with zipfile.ZipFile(path) as archive:
                    entries = archive.infolist()
                    if len(entries) > MAX_ENTRIES or sum(e.file_size for e in entries) > MAX_TOTAL:
                        raise ValueError("Package exceeds entry/expanded size limits")
                    seen = set()
                    for e in entries:
                        name = e.filename
                        # Directory records are unnecessary; accepting them only under assets is safe.
                        clean = name.rstrip("/") if e.is_dir() else name
                        if clean != "skill.json":
                            if e.is_dir():
                                if not clean.startswith("assets") or any(x in {"", ".", ".."} for x in clean.split("/")) or "\\" in clean or ":" in clean:
                                    raise ValueError("Unsafe archive directory")
                            else:
                                safe_asset(clean)
                        mode = e.external_attr >> 16
                        if clean in seen or e.flag_bits & 1 or (mode & 0o111) or stat.S_IFMT(mode) not in {0, stat.S_IFREG, stat.S_IFDIR}:
                            raise ValueError("Duplicate, encrypted, symlink or executable entry")
                        seen.add(clean)
                        if e.file_size > (MAX_MANIFEST if clean == "skill.json" else MAX_FILE):
                            raise ValueError("Archive member exceeds size limit")
                        if e.is_dir():
                            continue
                        dest = stage / clean
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        with archive.open(e) as src, dest.open("xb") as dst:
                            remaining = e.file_size
                            while chunk := src.read(min(65536, remaining + 1)):
                                remaining -= len(chunk)
                                if remaining < 0:
                                    raise ValueError("Expanded member exceeds declared size")
                                dst.write(chunk)
                    skill = parse((stage / "skill.json").read_bytes())
            else:
                raise ValueError("Only .lahzaskill ZIP and .json manifests are supported")
            for action in skill.actions:
                if isinstance(action, Sticker):
                    from lahza_engine.stickers import inspect_sticker
                    inspect_sticker(str(stage / safe_asset(action.asset)))
            (stage / "skill.json").write_text(skill.model_dump_json(by_alias=True), encoding="utf-8")
            dest = self.directory(skill.id)
            if dest.exists():
                if not replace:
                    raise FileExistsError("Skill already installed; explicit replace required")
                backup = self.root / (".replaced-" + uuid.uuid4().hex)
                os.replace(dest, backup)
                try:
                    os.replace(stage, dest)
                except BaseException:
                    os.replace(backup, dest)
                    raise
                shutil.rmtree(backup)
            else:
                os.replace(stage, dest)
            return skill

    def remove(self, sid: str) -> None:
        with LOCK:
            p = self.directory(sid)
            if not p.is_dir():
                raise FileNotFoundError("Skill not installed")
            trash = self.root / (".removed-" + uuid.uuid4().hex)
            os.replace(p, trash)
            shutil.rmtree(trash)
