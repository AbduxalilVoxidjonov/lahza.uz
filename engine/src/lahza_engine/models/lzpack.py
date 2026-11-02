"""`.lzpack` - modellarni oflayn ko'chirish paketi (M2-APP-9).

Format (zip):
* `manifest.json` - `{"format": 1, "created_at", "registry": {"models": [...], "defaults": {...}},
  "files": [{"path": "Models/<vazifa>/<id>/...", "sha256", "size"}]}`.
  Registry'dagi `path` lar `Models/` ga nisbiy yoziladi (boshqa kompyuterda qayta hisoblanadi).
* `Models/...` - model fayllari.
* `signature` (ixtiyoriy) - `manifest.json` baytlarining Ed25519 imzosi (base64).

Import xavfsizligi:
* har fayl sha256 va hajmi manifest bilan solishtiriladi (doim);
* imzo bo'lsa va `LAHZA_PACK_PUBKEY` berilgan bo'lsa - tekshiriladi; kalit berilgan-u imzo
  bo'lmasa, `LAHZA_DEV=1` bo'lmaguncha rad etiladi;
* zip-slip: absolyut yo'l, `..`, `\\`, `Models/` dan tashqari yo'l, symlink - rad;
* bajariladigan fayllar (sarlavha yoki kengaytma bo'yicha) - rad;
* manifestda yo'q fayl yoki fayli yo'q manifest yozuvi - rad.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import shutil
import stat
import tempfile
import zipfile
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath

from lahza_engine.models.store import _EXECUTABLE_MAGICS, InstalledModel, ModelStore, Registry

FORMAT = 1
MANIFEST = "manifest.json"
SIGNATURE = "signature"
PREFIX = "Models"
_BAD_SUFFIXES = {".exe", ".dll", ".so", ".dylib", ".sh", ".bat", ".cmd", ".ps1", ".command",
                 ".app", ".msi", ".com", ".scr", ".jar", ".py", ".pyc"}
_CHUNK = 1 << 20

Progress = Callable[[float], None]


class PackError(RuntimeError):
    pass


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(_CHUNK):
            h.update(chunk)
    return h.hexdigest()


def _model_files(store: ModelStore, m: InstalledModel) -> list[Path]:
    p = Path(m.path)
    root = store.root.resolve()
    if not p.exists():
        raise PackError(f"model fayllari topilmadi: {m.id}")
    try:
        p.resolve().relative_to(root)
    except ValueError as e:
        raise PackError(f"model Models/ papkasidan tashqarida: {m.id}") from e
    if p.is_file():
        return [p]
    return sorted(x for x in p.rglob("*") if x.is_file() and not x.is_symlink())


def export_pack(
    store: ModelStore,
    out: Path,
    model_ids: list[str] | None = None,
    private_key_b64: str | None = None,
    progress: Progress | None = None,
    is_cancelled: Callable[[], bool] = lambda: False,
) -> dict:
    reg = store.load()
    models = [m for m in reg.models if model_ids is None or m.id in model_ids]
    if not models:
        raise PackError("eksport uchun model yo'q")
    root = store.root.resolve()
    files: list[tuple[Path, str]] = []
    rel_models = []
    for m in models:
        for f in _model_files(store, m):
            files.append((f, f"{PREFIX}/{f.resolve().relative_to(root).as_posix()}"))
        rel = Path(m.path).resolve().relative_to(root).as_posix()
        rel_models.append(m.model_copy(update={"path": f"{PREFIX}/{rel}"}).model_dump(mode="json"))
    total = sum(f.stat().st_size for f, _ in files) or 1
    entries = []
    done = 0
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(out.suffix + ".part")
    try:
        with zipfile.ZipFile(tmp, "w", compression=zipfile.ZIP_STORED, allowZip64=True) as z:
            for f, arc in files:
                if is_cancelled():
                    raise PackError("bekor qilindi")
                z.write(f, arc)
                size = f.stat().st_size
                entries.append({"path": arc, "sha256": _sha256(f), "size": size})
                done += size
                if progress:
                    progress(0.95 * done / total)
            ids = {m["id"] for m in rel_models}
            manifest = {
                "format": FORMAT,
                "created_at": datetime.now(UTC).isoformat(),
                "registry": {"models": rel_models,
                             "defaults": {k: v for k, v in reg.defaults.items() if v in ids}},
                "files": entries,
            }
            raw = json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True).encode()
            z.writestr(MANIFEST, raw)
            if private_key_b64:
                from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

                key = Ed25519PrivateKey.from_private_bytes(base64.b64decode(private_key_b64))
                z.writestr(SIGNATURE, base64.b64encode(key.sign(raw)).decode())
        tmp.replace(out)
    finally:
        tmp.unlink(missing_ok=True)
    if progress:
        progress(1.0)
    return {"path": str(out), "models": sorted(ids), "files": len(entries)}


def _safe_member(name: str) -> PurePosixPath:
    if "\\" in name or name.startswith("/") or ":" in name.split("/")[0]:
        raise PackError(f"yaroqsiz yo'l paketda: {name!r}")
    p = PurePosixPath(name)
    if any(part in ("..", "") for part in p.parts) or p.parts[0] != PREFIX or len(p.parts) < 2:
        raise PackError(f"yaroqsiz yo'l paketda: {name!r}")
    if p.suffix.lower() in _BAD_SUFFIXES:
        raise PackError(f"bajariladigan fayl rad etildi: {name!r}")
    return p


def _verify_signature(raw: bytes, sig_b64: bytes | None, pubkey_b64: str | None, dev: bool) -> None:
    if pubkey_b64 is None:
        return
    if sig_b64 is None:
        if dev:
            return
        raise PackError("paket imzolanmagan (LAHZA_PACK_PUBKEY sozlangan)")
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

    key = Ed25519PublicKey.from_public_bytes(base64.b64decode(pubkey_b64))
    try:
        key.verify(base64.b64decode(sig_b64), raw)
    except (InvalidSignature, ValueError) as e:
        raise PackError("paket imzosi yaroqsiz") from e


def import_pack(
    store: ModelStore,
    pack: Path,
    pubkey_b64: str | None = None,
    dev: bool | None = None,
    progress: Progress | None = None,
    is_cancelled: Callable[[], bool] = lambda: False,
) -> dict:
    dev = os.environ.get("LAHZA_DEV") == "1" if dev is None else dev
    if pubkey_b64 is None:
        pubkey_b64 = os.environ.get("LAHZA_PACK_PUBKEY") or None
    if not zipfile.is_zipfile(pack):
        raise PackError("fayl .lzpack (zip) emas")
    with zipfile.ZipFile(pack) as z:
        names = z.namelist()
        if MANIFEST not in names:
            raise PackError("manifest.json topilmadi")
        raw = z.read(MANIFEST)
        sig = z.read(SIGNATURE) if SIGNATURE in names else None
        _verify_signature(raw, sig, pubkey_b64, dev)
        try:
            manifest = json.loads(raw)
            reg = Registry.model_validate(manifest["registry"])
            files = {f["path"]: f for f in manifest["files"]}
        except (ValueError, KeyError, TypeError) as e:
            raise PackError("manifest.json yaroqsiz") from e
        if manifest.get("format") != FORMAT:
            raise PackError("paket formati qo'llanmaydi")

        members = [i for i in z.infolist() if i.filename not in (MANIFEST, SIGNATURE)]
        for info in members:
            if info.is_dir():
                _safe_member(info.filename.rstrip("/") + "/x")
                continue
            _safe_member(info.filename)
            if stat.S_ISLNK(info.external_attr >> 16):
                raise PackError(f"symlink rad etildi: {info.filename!r}")
            if info.filename not in files:
                raise PackError(f"manifestda yo'q fayl: {info.filename!r}")
        present = {i.filename for i in members if not i.is_dir()}
        missing = set(files) - present
        if missing:
            raise PackError(f"paketda fayl yetishmaydi: {sorted(missing)[0]!r}")
        for m in reg.models:
            _safe_member(m.path if m.path.startswith(PREFIX + "/") else f"{PREFIX}/{m.path}")

        total = sum(int(f["size"]) for f in files.values()) or 1
        done = 0
        root = store.root.resolve()
        staging = Path(tempfile.mkdtemp(prefix=".lzpack-", dir=root))
        try:
            for info in members:
                if info.is_dir():
                    continue
                if is_cancelled():
                    raise PackError("bekor qilindi")
                rel = PurePosixPath(info.filename).relative_to(PREFIX)
                dst = staging.joinpath(*rel.parts)
                dst.parent.mkdir(parents=True, exist_ok=True)
                exp = files[info.filename]
                h = hashlib.sha256()
                size = 0
                with z.open(info) as src, dst.open("wb") as out:
                    head = src.read(8)
                    if any(head.startswith(mg) for mg in _EXECUTABLE_MAGICS):
                        raise PackError(f"bajariladigan fayl rad etildi: {info.filename!r}")
                    chunk = head
                    while chunk:
                        h.update(chunk)
                        out.write(chunk)
                        size += len(chunk)
                        if size > int(exp["size"]):
                            raise PackError(f"hajm mos emas: {info.filename!r}")
                        chunk = src.read(_CHUNK)
                if size != int(exp["size"]) or h.hexdigest() != exp["sha256"]:
                    raise PackError(f"sha256/hajm mos emas: {info.filename!r}")
                done += size
                if progress:
                    progress(0.9 * done / total)
            # Hammasi tekshirildi - joyiga ko'chirish.
            for p in sorted(staging.rglob("*")):
                if p.is_file():
                    target = root / p.relative_to(staging)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    os.replace(p, target)
        finally:
            shutil.rmtree(staging, ignore_errors=True)

    imported = []
    for m in reg.models:
        rel = PurePosixPath(m.path)
        rel = rel.relative_to(PREFIX) if rel.parts[0] == PREFIX else rel
        imported.append(m.model_copy(update={"path": str(root.joinpath(*rel.parts)),
                                             "self_test_ok": None}))
    store.register(imported)
    if progress:
        progress(1.0)
    return {"imported": [m.id for m in imported], "files": len(files)}
