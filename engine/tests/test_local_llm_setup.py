"""Bootstrap tests use tiny artifacts and temporary directories, never app resources."""
from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import subprocess
import tarfile
from pathlib import Path
from unittest.mock import Mock

import pytest

from lahza_engine.models.catalog import Task
from lahza_engine.models.store import InstalledModel, ModelStore

spec = importlib.util.spec_from_file_location(
    "setup_local_llm", Path(__file__).resolve().parents[2] / "scripts/setup_local_llm.py",
)
setup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(setup)


def test_pins():
    assert setup.MODEL_REVISION == "bc640142c66e1fdd12af0bd68f40445458f3869b"
    assert setup.MODEL_SIZE == 2497280256
    assert setup.MODEL_SHA256 == "7485fe6f11af29433bc51cab58009521f205840f5b4ae3a32fa7f92e8534fdf5"
    assert setup.RUNTIME_SIZE == 12191582
    assert setup.RUNTIME_SHA256 == "dbed55493d72bc1ba2babc8770d669c2289b5bc4ee9fb2a4dfc158d45b7d13fd"
    assert "/b11669/" in setup.RUNTIME_URL


def test_plan_help_and_consent(monkeypatch, capsys, tmp_path):
    network = Mock(side_effect=AssertionError("unexpected network"))
    monkeypatch.setattr(setup, "download", network)
    monkeypatch.setattr(setup.httpx, "Client", network)
    assert setup.main([]) == 0
    assert "Plan only" in capsys.readouterr().out
    for args in (["--help"], ["--model"], ["--stage"], ["--set-default"]):
        with pytest.raises(SystemExit) as exc:
            setup.main(args)
        assert exc.value.code == (0 if args == ["--help"] else 2)
    network.assert_not_called()
    assert list(tmp_path.iterdir()) == []


def test_existing_is_fully_revalidated(monkeypatch, tmp_path):
    artifact = tmp_path / "tiny"
    artifact.write_bytes(b"GGUFtiny")
    digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
    downloader = Mock()
    monkeypatch.setattr(setup, "download", downloader)
    assert setup.verified_file("url", artifact, digest, 8, consent=False) == artifact
    artifact.write_bytes(b"GGUFbad!")  # same size, different content
    with pytest.raises(ValueError, match="verification"):
        setup.verified_file("url", artifact, digest, 8, consent=True)
    downloader.assert_not_called()
    artifact.unlink()
    with pytest.raises(ValueError, match="consent"):
        setup.verified_file("url", artifact, digest, 8, consent=False)
    setup.verified_file("url", artifact, digest, 8, consent=True)
    downloader.assert_called_once_with(["url"], artifact, digest, 8)


def make_tar(path, entries):
    with tarfile.open(path, "w:gz") as tar:
        for name, data, link in entries:
            item = tarfile.TarInfo(name)
            if link is not None:
                item.type = tarfile.SYMTYPE
                item.linkname = link
                tar.addfile(item)
            else:
                item.size = len(data)
                tar.addfile(item, io.BytesIO(data))


@pytest.mark.parametrize("name,link", [("../outside", None), ("/outside", None),
                                      ("root/lib.dylib", "../../outside"),
                                      ("root/lib.dylib", "/outside")])
def test_tar_rejects_escape(tmp_path, name, link):
    archive = tmp_path / "fixture.tar.gz"
    make_tar(archive, [(name, b"tiny", link)])
    with pytest.raises(ValueError, match="Unsafe"):
        setup.safe_extract(archive, tmp_path / "unpack")
    assert not (tmp_path / "outside").exists()


def test_extract_keeps_safe_symlinks(tmp_path):
    archive = tmp_path / "fixture.tar.gz"
    prefix = f"llama-{setup.RUNTIME_RELEASE}"
    make_tar(archive, [(f"{prefix}/llama-server", b"tiny", None),
                       (f"{prefix}/LICENSE", b"MIT", None),
                       (f"{prefix}/libx.0.dylib", b"lib", None),
                       (f"{prefix}/libx.dylib", b"", "libx.0.dylib")])
    runtime = setup.safe_extract(archive, tmp_path / "unpack")
    assert (runtime / "libx.dylib").is_symlink()
    assert (runtime / "libx.dylib").read_bytes() == b"lib"


@pytest.fixture
def tiny_model(monkeypatch):
    weights = b"GGUFtiny-model"
    monkeypatch.setattr(setup, "MODEL_SIZE", len(weights))
    monkeypatch.setattr(setup, "MODEL_SHA256", hashlib.sha256(weights).hexdigest())
    notices = {"LICENSE": b"Apache-2.0", "README.md": b"Official model card"}
    calls = []

    def download(urls, dest, digest, size, **kwargs):
        calls.append(dest)
        data = weights if dest.name == setup.MODEL_FILE else notices[dest.name]
        assert len(data) == size
        if digest:
            assert hashlib.sha256(data).hexdigest() == digest
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        return dest

    monkeypatch.setattr(setup, "download", download)
    tree = {"sha": setup.MODEL_REVISION, "siblings": [
        {"rfilename": n, "size": len(v), "blobId": hashlib.sha1(
            b"blob " + str(len(v)).encode() + b"\0" + v).hexdigest()}
        for n, v in notices.items()
    ]}
    response = Mock()
    response.json.return_value = tree
    client = Mock()
    client.__enter__ = Mock(return_value=client)
    client.__exit__ = Mock(return_value=False)
    client.get.return_value = response
    monkeypatch.setattr(setup.httpx, "Client", Mock(return_value=client))
    return calls, tree


@pytest.mark.parametrize("existing,replace", [(False, False), (True, False), (True, True)])
def test_registration_defaults_and_reuse(tmp_path, tiny_model, existing, replace):
    store = ModelStore(tmp_path)
    if existing:
        store.register([InstalledModel(id="custom:other", task=Task.LLM,
                                       version="custom", path="other", source="custom")])
    model = setup.install_model(tmp_path, consent=True, set_default=replace)
    assert model.source == "custom" and not model.verified
    assert Path(model.path).suffix == ".gguf"
    expected = "custom:other" if existing and not replace else setup.MODEL_ID
    assert store.default_for(Task.LLM).id == expected
    metadata = Path(model.path).parent / "metadata"
    assert (metadata / "LICENSE").exists()
    assert json.loads((metadata / "SOURCE.json").read_text())["revision"] == setup.MODEL_REVISION
    count = len(tiny_model[0])
    setup.install_model(tmp_path, consent=True)
    assert len(tiny_model[0]) == count
    assert len([m for m in store.load().models if m.id == model.id]) == 1


def test_notice_tamper_prevents_registration(tmp_path, tiny_model):
    tiny_model[1]["siblings"][0]["blobId"] = "bad"
    with pytest.raises(ValueError, match="notice verification"):
        setup.install_model(tmp_path, consent=True)
    assert ModelStore(tmp_path).load().models == []


def test_publish_protects_existing_runtime(tmp_path):
    stage = tmp_path / "stage"
    dest = tmp_path / "bin"
    stage.mkdir()
    (dest / "lib").mkdir(parents=True)
    (dest / "ffmpeg").write_bytes(b"ffmpeg")
    (dest / "lib/ff.dylib").write_bytes(b"ffmpeg library")
    (stage / "llama-server").write_bytes(b"server")
    (stage / "libx.0.dylib").write_bytes(b"x")
    (stage / "libx.dylib").symlink_to("libx.0.dylib")
    setup.publish_runtime(stage, dest)
    setup.publish_runtime(stage, dest)
    assert (dest / "libx.dylib").is_symlink()
    assert (dest / "ffmpeg").read_bytes() == b"ffmpeg"
    assert (dest / "lib/ff.dylib").read_bytes() == b"ffmpeg library"
    (stage / "llama-server").write_bytes(b"changed")
    (stage / "new.dylib").write_bytes(b"new")
    with pytest.raises(ValueError, match="overwrite"):
        setup.publish_runtime(stage, dest)
    assert not (dest / "new.dylib").exists()
    assert (dest / "llama-server").read_bytes() == b"server"


def test_publish_rejects_symlink_parent(tmp_path):
    stage = tmp_path / "stage"
    (stage / "licenses").mkdir(parents=True)
    (stage / "licenses/LICENSE").write_text("license")
    dest = tmp_path / "bin"
    dest.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (dest / "licenses").symlink_to(outside)
    with pytest.raises(ValueError, match="Unsafe destination"):
        setup.publish_runtime(stage, dest)
    assert list(outside.iterdir()) == []


@pytest.mark.parametrize("dep,rpath,identity,arch,ok", [
    ("@rpath/libx.dylib", "@loader_path", "@rpath/libx.dylib", "arm64", True),
    ("/opt/homebrew/lib/x.dylib", "@loader_path", "@rpath/libx.dylib", "arm64", False),
    ("@rpath/libx.dylib", "/usr/local/lib", "@rpath/libx.dylib", "arm64", False),
    ("@rpath/missing.dylib", "@loader_path", "@rpath/libx.dylib", "arm64", False),
    ("@rpath/libx.dylib", "@loader_path", "/usr/local/libx.dylib", "arm64", False),
    ("@rpath/libx.dylib", "@loader_path", "@rpath/libx.dylib", "x86_64", False),
])
def test_audit(monkeypatch, tmp_path, dep, rpath, identity, arch, ok):
    (tmp_path / "llama-server").write_bytes(b"server")
    (tmp_path / "libx.dylib").write_bytes(b"lib")

    def run(args, **kwargs):
        if args[0] == "lipo":
            stdout = arch
        elif args[1] == "-l":
            stdout = f"cmd LC_RPATH\n cmdsize 32\n path {rpath} (offset 12)\n minos 13.3"
        elif args[1] == "-D":
            stdout = f"file:\n{identity}\n"
        else:
            own = "\t@rpath/libx.dylib (compatibility version 0)\n" if args[2].endswith(".dylib") else ""
            stdout = f"file:\n{own}\t{dep} (compatibility version 0)\n"
        return subprocess.CompletedProcess(args, 0, stdout, "")

    monkeypatch.setattr(setup, "run", run)
    if ok:
        assert len(setup.audit_runtime(tmp_path)) == 2
    else:
        with pytest.raises(ValueError):
            setup.audit_runtime(tmp_path)


def test_staging_uses_verified_archive_and_temporary_relocation(monkeypatch, tmp_path):
    prefix = f"llama-{setup.RUNTIME_RELEASE}"
    cache = tmp_path / "cache"
    cache.mkdir()
    archive = cache / setup.RUNTIME_FILE
    make_tar(archive, [(f"{prefix}/llama-server", b"server", None),
                       (f"{prefix}/LICENSE", b"MIT license", None),
                       (f"{prefix}/libx.0.dylib", b"lib", None),
                       (f"{prefix}/libx.dylib", b"", "libx.0.dylib"),
                       (f"{prefix}/llama-cli", b"unneeded executable", None)])
    monkeypatch.setattr(setup, "RUNTIME_SIZE", archive.stat().st_size)
    monkeypatch.setattr(setup, "RUNTIME_SHA256", setup.sha256_file(archive))
    monkeypatch.setattr(setup.sys, "platform", "darwin")
    monkeypatch.setattr(setup.platform, "machine", lambda: "arm64")
    monkeypatch.setattr(setup, "download", Mock(side_effect=AssertionError("no network")))
    audit = Mock(return_value=[{"file": "libx.0.dylib", "architectures": "arm64"}])
    monkeypatch.setattr(setup, "audit_runtime", audit)
    executions = []

    def run(args, **kwargs):
        executable = Path(args[0])
        assert executable.parent.name == "relocated runtime"
        assert (executable.parent / "libx.dylib").read_bytes() == b"lib"
        assert not (executable.parent / "llama-cli").exists()
        executions.append(kwargs)
        return subprocess.CompletedProcess(args, 0, "build 11669", "")

    monkeypatch.setattr(setup, "run", run)
    dest = tmp_path / "resources/bin"
    setup.stage_runtime(cache, dest, consent=False)
    assert (dest / "llama-server").read_bytes() == b"server"
    assert (dest / "libx.dylib").is_symlink()
    source = json.loads((dest / "licenses/llama.cpp/SOURCE.json").read_text())
    assert source["release"] == setup.RUNTIME_RELEASE
    assert source["license"] == "MIT"
    assert (dest / "licenses/llama.cpp/LICENSE").read_text() == "MIT license"
    assert len(executions) == 2
    assert audit.call_count == 2
    setup.stage_runtime(cache, dest, consent=False)  # stable provenance permits reuse
    assert (dest / "llama-server").read_bytes() == b"server"


def test_corrupt_runtime_rejected_before_extraction(monkeypatch, tmp_path):
    archive = tmp_path / setup.RUNTIME_FILE
    archive.write_bytes(b"not the release")
    monkeypatch.setattr(setup.sys, "platform", "darwin")
    monkeypatch.setattr(setup.platform, "machine", lambda: "arm64")
    extract = Mock()
    monkeypatch.setattr(setup, "safe_extract", extract)
    with pytest.raises(ValueError, match="verification"):
        setup.stage_runtime(tmp_path, tmp_path / "destination", consent=False)
    extract.assert_not_called()
    assert not (tmp_path / "destination").exists()
