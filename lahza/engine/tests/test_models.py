import base64
import hashlib
import http.server
import io
import threading
from functools import partial
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from lahza_engine.models import catalog as cat
from lahza_engine.models.downloader import DownloadError, download
from lahza_engine.models.hardware import Gpu, HardwareProfile, Tier, classify
from lahza_engine.models.store import ModelStore, sniff_custom_file


def hw(os_="darwin", arch="arm64", ram=16.0, gpus=None, disk=500.0) -> HardwareProfile:
    return HardwareProfile(os_, "x", arch, "cpu", ram, disk, gpus or [])


@pytest.mark.parametrize(
    "profile, tier",
    [
        (hw(ram=8), Tier.LITE),
        (hw(ram=16), Tier.STANDARD),
        (hw(ram=64), Tier.PRO),
        (hw(arch="x86_64"), Tier.UNSUPPORTED),
        (hw("win32", "x86_64", 16, [Gpu("nvidia", "RTX", 8)]), Tier.STANDARD),
        (hw("win32", "x86_64", 32, [Gpu("nvidia", "RTX", 24)]), Tier.PRO),
        (hw("win32", "x86_64", 16, [Gpu("amd", "Radeon", None)]), Tier.LITE),
        (hw("win32", "x86_64", 8), Tier.UNSUPPORTED),
    ],
)
def test_tier(profile, tier) -> None:
    assert classify(profile).tier is tier


def _entry(id_, task, tiers, status="approved", platforms=("darwin-arm64",), score=0.0, **kw):
    files = [cat.ModelFile(path="m.bin", urls=["http://x/m.bin"], sha256="0" * 64, size_bytes=10)]
    return cat.CatalogEntry(id=id_, task=task, name=id_, version="1", backend="whisper.cpp",
                            files=files, platforms=list(platforms), tiers=list(tiers), license="MIT",
                            source_url="http://x", status=status, eval={"score": score}, **kw)


def test_approved_requires_hashes() -> None:
    with pytest.raises(ValueError):
        cat.CatalogEntry(id="a", task="asr", name="a", version="1", backend="whisper.cpp",
                         files=[cat.ModelFile(path="m", urls=[])], platforms=["darwin-arm64"],
                         tiers=["lite"], license="MIT", source_url="x", status="approved")


def test_sign_and_verify() -> None:
    priv = Ed25519PrivateKey.generate()
    from cryptography.hazmat.primitives.serialization import NoEncryption, PrivateFormat

    raw = priv.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption())
    pub = priv.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    c = cat.Catalog(catalog_version="t", entries=[_entry("a", "asr", ["lite"])])
    signed = cat.sign(c, base64.b64encode(raw).decode())
    cat.verify(signed, base64.b64encode(pub).decode())
    tampered = signed.model_copy(update={"catalog_version": "boshqa"})
    with pytest.raises(cat.SignatureError):
        cat.verify(tampered, base64.b64encode(pub).decode())


def test_select_bundle_prefers_tier_and_score_and_skips_candidates() -> None:
    entries = [
        _entry("asr-small", "asr", ["lite"], score=0.5),
        _entry("asr-big", "asr", ["standard", "pro"], score=0.9),
        _entry("asr-new", "asr", ["standard"], status="candidate"),
        _entry("llm-9b", "llm", ["pro"], min_ram_gb=32),
    ]
    c = cat.Catalog(catalog_version="t", entries=entries)
    items = {i.task: i for i in cat.select_bundle(c, hw(ram=16), Tier.STANDARD)}
    assert items[cat.Task.ASR].entry.id == "asr-big"
    assert items[cat.Task.LLM].entry is None  # RAM yetmaydi -> Lite rejim
    assert "Lite" in items[cat.Task.LLM].reason
    assert items[cat.Task.ASR].mandatory and not items[cat.Task.LLM].mandatory


def test_incompatible_vram_reason() -> None:
    e = _entry("x", "llm", ["standard"], platforms=("win32-x86_64",), min_vram_gb=8)
    compat, why = cat.compatibility(e, hw("win32", "x86_64", 16, [Gpu("nvidia", "g", 4)]), Tier.LITE)
    assert compat is cat.Compat.INCOMPATIBLE and "8 GB VRAM" in why


class RangeHandler(http.server.SimpleHTTPRequestHandler):
    """Range sarlavhasini qo'llovchi oddiy test serveri."""

    def log_message(self, *a):
        pass

    def send_head(self):
        rng = self.headers.get("Range")
        path = Path(self.translate_path(self.path))
        if not rng or not path.is_file():
            return super().send_head()
        start = int(rng.split("=")[1].split("-")[0])
        data = path.read_bytes()
        self.send_response(206)
        self.send_header("Content-Length", str(len(data) - start))
        self.end_headers()
        return io.BytesIO(data[start:])


@pytest.fixture()
def http_dir(tmp_path: Path):
    root = tmp_path / "srv"
    root.mkdir()
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), partial(RangeHandler, directory=str(root)))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield root, f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


def test_download_resume_and_hash(http_dir, tmp_path: Path) -> None:
    root, base = http_dir
    data = bytes(range(256)) * 4000
    (root / "model.bin").write_bytes(data)
    dest = tmp_path / "out" / "model.bin"
    dest.parent.mkdir()
    (dest.parent / "model.bin.part").write_bytes(data[:1000])  # yarim yuklangan
    sha = hashlib.sha256(data).hexdigest()
    seen = []
    download([f"{base}/yoq.bin", f"{base}/model.bin"], dest, sha, len(data),
             progress=lambda h, t: seen.append(h))
    assert dest.read_bytes() == data
    assert seen[0] > 1000  # davom ettirildi, boshidan emas


def test_download_sha_mismatch(http_dir, tmp_path: Path) -> None:
    root, base = http_dir
    (root / "m.bin").write_bytes(b"abc")
    with pytest.raises(DownloadError):
        download([f"{base}/m.bin"], tmp_path / "d" / "m.bin", "0" * 64, 3)


def test_store_scan_custom_accepts_gguf_rejects_exe(tmp_path: Path) -> None:
    store = ModelStore(tmp_path)
    llm = tmp_path / "llm"
    llm.mkdir()
    (llm / "good.gguf").write_bytes(b"GGUF" + b"\0" * 100)
    (llm / "evil.gguf").write_bytes(b"MZ" + b"\0" * 100)
    added = store.scan_custom()
    assert [m.id for m in added] == ["custom:good"]
    assert added[0].verified is False
    assert sniff_custom_file(llm / "evil.gguf") is None
    assert store.scan_custom() == []  # takror qo'shilmaydi


def test_store_refuses_candidate(tmp_path: Path) -> None:
    store = ModelStore(tmp_path)
    with pytest.raises(ValueError):
        store.install(_entry("c", "asr", ["lite"], status="candidate"))
