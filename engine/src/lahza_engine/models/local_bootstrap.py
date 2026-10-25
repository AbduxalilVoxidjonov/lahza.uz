"""Explicit opt-in Uzbek ASR installation; no catalog or quality approval."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import httpx

from lahza_engine.config import Settings
from lahza_engine.models.catalog import Task
from lahza_engine.models.downloader import ProgressFn, download, sha256_file
from lahza_engine.models.store import InstalledModel, ModelStore

REPO = "Mavlyudabegim/navai-base-uzbek-ct2"
REVISION = "44ca86c6da92fd9eecaf09e25655d222cdc6cde9"
SOURCE_REPO = "navai-uz/whisper-base-uzbek"
SOURCE_REVISION = "377a0da45851aeec93fe9883dc39492c38858533"
# Independently reproduced from SOURCE_REVISION with CT2 4.8.3, float16 conversion.
WEIGHTS_SHA256 = "cb5d527b50c63d80c82d6608d2da8713d4ce21e391b0da4402bf7659f2685699"
MODEL_ID = "custom:navai-whisper-base-uzbek"
MODEL_FOLDER = "navai-whisper-base-uzbek"
TOKENIZER_SOURCE = ("Systran/faster-whisper-base", "ebe41f70d5b6dfa9166e2c581c45c9c0cfc57b66")
SOURCES = {
    **{n: (REPO, REVISION) for n in
       ("config.json", "model.bin", "vocabulary.json", "preprocessor_config.json")},
    "tokenizer.json": TOKENIZER_SOURCE,
    **{n: (SOURCE_REPO, SOURCE_REVISION) for n in ("LICENSE", "NOTICE", "README.md")},
}
FILES = tuple(SOURCES)
MAX_BYTES = 2_000_000_000
SILERO_REVISION = "6478567951ae5c9979ad7b234185b5515f4be7a1"
SILERO_SHA256 = "2623a2953f6ff3d2c1e61740c6cdb7168133479b267dfef114a4a3cc5bdd788f"


def bootstrap(
    store: ModelStore, *, consent: bool = False, progress: ProgressFn | None = None,
) -> InstalledModel:
    """Download pinned files, check CPU load, register custom ASR and select it.

    Progress is aggregate bytes. Callback exceptions propagate, including cancellation.
    Serialize jobs per store. No conversion dependency is needed at inference/install time.
    """
    if not consent:
        raise ValueError("Downloading requires explicit --download --consent")
    from faster_whisper import WhisperModel

    target = store.model_dir(Task.ASR, MODEL_FOLDER).resolve()
    with httpx.Client(timeout=120, follow_redirects=True) as client:
        manifests = {}
        for repo, revision in dict.fromkeys(SOURCES.values()):
            response = client.get(
                f"https://huggingface.co/api/models/{repo}/revision/{revision}",
                params={"blobs": "true"},
            )
            response.raise_for_status()
            metadata = response.json()
            if metadata["sha"] != revision:
                raise ValueError("Upstream revision mismatch")
            manifests[(repo, revision)] = {f["rfilename"]: f for f in metadata["siblings"]}
        total = sum(manifests[SOURCES[name]][name]["size"] for name in FILES)
        if total > MAX_BYTES:
            raise ValueError("Model exceeds 2 GB download budget")
        completed = 0
        if progress:
            progress(0, total)
        records = []
        for name, (repo, revision) in SOURCES.items():
            entry = manifests[(repo, revision)][name]
            url = f"https://huggingface.co/{repo}/resolve/{revision}/{name}"
            dest = target / name
            expected = WEIGHTS_SHA256 if name == "model.bin" else entry.get("lfs", {}).get("sha256")

            def report(have: int, _total: int | None, base: int = completed) -> None:
                if progress:
                    progress(base + have, total)

            download([url], dest, expected, entry["size"], progress=report, client=client)
            completed += entry["size"]
            if not expected:
                data = dest.read_bytes()
                blob = hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
                if blob != entry["blobId"]:
                    dest.unlink()
                    raise ValueError(f"Git blob mismatch: {name}")
            records.append({"path": name, "url": url, "size_bytes": dest.stat().st_size,
                            "sha256": sha256_file(dest), "upstream_blob": entry["blobId"]})
    model = WhisperModel(str(target), device="cpu", compute_type="int8", local_files_only=True)
    del model
    provenance = {
        "repository": REPO, "revision": REVISION, "upstream_model": SOURCE_REPO,
        "upstream_revision": SOURCE_REVISION, "license": "Apache-2.0 (weights); MIT (tokenizer)",
        "source_url": f"https://huggingface.co/{SOURCE_REPO}", "catalog_approved": False,
        "conversion": {"ctranslate2": "4.8.3", "quantization": "float16",
                       "independently_reproduced_weights_sha256": WEIGHTS_SHA256,
                       "source_safetensors_sha256": "c1209e5d6215fa5021e336a523bae6c77bdb7049efdf00db8b5bd7abdb3ad0b8",
                       "transformers": "4.57.6", "torch": "2.14.1"},
        "files": records,
    }
    (target / "provenance.json").write_text(json.dumps(provenance, indent=2) + "\n")
    installed = InstalledModel(id=MODEL_ID, task=Task.ASR, version=REVISION, path=str(target),
                               source="custom", verified=False)
    store.register([installed])
    store.set_default(Task.ASR, installed.id)
    return installed


def bootstrap_vad(
    store: ModelStore, *, consent: bool = False, progress: ProgressFn | None = None,
) -> InstalledModel:
    """Install official Silero v5.1.2 ONNX (MIT), without torch or silero-vad package."""
    if not consent:
        raise ValueError("Downloading requires explicit consent")
    from lahza_engine.vad.silero_onnx import SileroOnnxVad

    target = store.model_dir(Task.VAD, "silero-v5.1.2").resolve()
    base = f"https://raw.githubusercontent.com/snakers4/silero-vad/{SILERO_REVISION}"
    url = f"{base}/src/silero_vad/data/silero_vad.onnx"
    download([url], target / "silero_vad.onnx", SILERO_SHA256, 2327524, progress=progress)
    SileroOnnxVad(target / "silero_vad.onnx")
    download([f"{base}/LICENSE"], target / "LICENSE",
             "2e63e9a38b6e8fc0c7bc37ce174caca1862870856c6daf5697cfb785e925520b", 1075,
             progress=(lambda _have, _total: progress(2327524, 2327524)) if progress else None)
    (target / "provenance.json").write_text(json.dumps({
        "repository": "snakers4/silero-vad", "revision": SILERO_REVISION, "license": "MIT",
        "catalog_approved": False, "files": [{"path": "silero_vad.onnx", "url": url,
            "size_bytes": 2327524, "sha256": SILERO_SHA256},
            {"path": "LICENSE", "url": f"{base}/LICENSE",
             "sha256": sha256_file(target / "LICENSE")}],
    }, indent=2) + "\n")
    model = InstalledModel(id="custom:silero-v5.1.2", task=Task.VAD, version=SILERO_REVISION,
                           path=str(target), source="custom", verified=False)
    if progress:
        progress(2327524, 2327524)
    store.register([model])
    store.set_default(Task.VAD, model.id)
    return model


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--download", action="store_true", help="Download pinned NavAI Uzbek base")
    parser.add_argument("--consent", action="store_true", help="Allow model network download")
    parser.add_argument("--with-vad", action="store_true", help="Also install official Silero ONNX")
    parser.add_argument("--models-dir", type=Path, default=None)
    args = parser.parse_args(argv)
    if not (args.download and args.consent):
        parser.error("explicit --download --consent required; no files changed")
    try:
        store = ModelStore(args.models_dir or Settings().models_dir)
        model = bootstrap(store, consent=True)
        print(model.model_dump_json(indent=2))
        if args.with_vad:
            print(bootstrap_vad(store, consent=True).model_dump_json(indent=2))
    except (ValueError, RuntimeError, OSError, ImportError, httpx.HTTPError) as exc:
        parser.exit(1, f"Bootstrap failed: {exc}\n")
    return 0
