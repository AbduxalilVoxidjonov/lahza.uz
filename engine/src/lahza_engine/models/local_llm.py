"""Pinned, packaged-engine Qwen installer; never invokes development scripts."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import httpx

from lahza_engine.models.catalog import Task
from lahza_engine.models.downloader import ProgressFn, download, sha256_file
from lahza_engine.models.store import InstalledModel, ModelStore

MODEL_REPO = "Qwen/Qwen3-4B-GGUF"
MODEL_REVISION = "bc640142c66e1fdd12af0bd68f40445458f3869b"
MODEL_FILE = "Qwen3-4B-Q4_K_M.gguf"
MODEL_SIZE = 2497280256
MODEL_SHA256 = "7485fe6f11af29433bc51cab58009521f205840f5b4ae3a32fa7f92e8534fdf5"
MODEL_ID = "custom:qwen3-4b-q4-k-m"
MODEL_BASE = f"https://huggingface.co/{MODEL_REPO}/resolve/{MODEL_REVISION}"


def verify_installation(weights: Path) -> None:
    """Verify the pinned payload and both notices without any network access."""
    if weights.stat().st_size != MODEL_SIZE or sha256_file(weights) != MODEL_SHA256:
        raise ValueError("LLM sha256 mos emas")
    metadata = weights.parent / "metadata"
    source = json.loads((metadata / "SOURCE.json").read_text(encoding="utf-8"))
    if (source.get("revision") != MODEL_REVISION or source.get("repository") != MODEL_REPO
            or source.get("sha256") != MODEL_SHA256 or source.get("size_bytes") != MODEL_SIZE):
        raise ValueError("LLM provenance mos emas")
    notices = source.get("notices", [])
    if {notice["file"] for notice in notices} != {"LICENSE", "README.md"}:
        raise ValueError("LLM litsenziya fayllari yetishmaydi")
    for notice in notices:
        path = metadata / notice["file"]
        if sha256_file(path) != notice["sha256"]:
            raise ValueError("LLM notice sha256 mos emas")


def _register(store: ModelStore, weights: Path) -> InstalledModel:
    model = InstalledModel(id=MODEL_ID, task=Task.LLM, version=MODEL_REVISION,
                           path=str(weights), source="custom", verified=False)
    store.register([model])
    return model


def install_model(store: ModelStore, *, consent: bool = False,
                  progress: ProgressFn | None = None) -> InstalledModel:
    if not consent:
        raise ValueError("Model installation requires consent=true")
    target = store.model_dir(Task.LLM, "qwen3-4b-q4-k-m").resolve()
    weights = target / MODEL_FILE
    if weights.is_file():
        try:
            verify_installation(weights)
        except (OSError, ValueError, KeyError, TypeError):
            pass  # resume/repair only with the caller's explicit consent
        else:
            if progress:
                progress(MODEL_SIZE, MODEL_SIZE)
            return _register(store, weights)
    weights = download([f"{MODEL_BASE}/{MODEL_FILE}"], weights,
                       MODEL_SHA256, MODEL_SIZE, progress=progress)
    metadata = target / "metadata"
    metadata.mkdir(exist_ok=True)
    with httpx.Client(timeout=60, follow_redirects=True) as client:
        response = client.get(
            f"https://huggingface.co/api/models/{MODEL_REPO}/revision/{MODEL_REVISION}",
            params={"blobs": "true"})
        response.raise_for_status()
        tree = response.json()
        if tree["sha"] != MODEL_REVISION:
            raise ValueError("Model metadata revision mismatch")
        entries = {f["rfilename"]: f for f in tree["siblings"]}
        records = []
        for name in ("LICENSE", "README.md"):
            if progress:
                progress(MODEL_SIZE, MODEL_SIZE)
            entry = entries[name]
            if not 0 < entry["size"] <= 2_000_000:
                raise ValueError("Unexpected model notice size")
            dest = metadata / name
            download([f"{MODEL_BASE}/{name}"], dest, None, entry["size"], client=client)
            content = dest.read_bytes()
            blob = hashlib.sha1(b"blob " + str(len(content)).encode() + b"\0" + content).hexdigest()
            if blob != entry["blobId"]:
                dest.unlink(missing_ok=True)
                raise ValueError(f"Pinned notice verification failed: {name}")
            records.append({"file": name, "size_bytes": len(content),
                            "sha256": sha256_file(dest), "blob": blob})
    source = {"repository": MODEL_REPO, "revision": MODEL_REVISION, "license": "Apache-2.0",
              "file": MODEL_FILE, "size_bytes": MODEL_SIZE, "sha256": MODEL_SHA256,
              "notices": records, "catalog_approved": False}
    temporary = metadata / "SOURCE.tmp"
    temporary.write_text(json.dumps(source, indent=2) + "\n", encoding="utf-8")
    temporary.replace(metadata / "SOURCE.json")
    if progress:
        progress(MODEL_SIZE, MODEL_SIZE)
    return _register(store, weights)
