"""Local desktop packaging trust and dynamically loaded native backends."""
import importlib.util
import json
import os
import re
import shutil
import subprocess
import time
from pathlib import Path

import httpx
import pytest

from lahza_engine.models.catalog import Catalog, SignatureError, verify

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("build_sidecar", ROOT / "scripts/build_sidecar.py")
packaging = importlib.util.module_from_spec(spec)
spec.loader.exec_module(packaging)


def test_generated_catalog_is_signed_and_tampering_fails(tmp_path):
    original = (ROOT / "catalog/catalog.json").read_bytes()
    public = packaging.prepare_local_catalog(tmp_path)
    catalog = Catalog.model_validate_json((tmp_path / "catalog.json").read_text())
    verify(catalog, public)
    assert (ROOT / "catalog/catalog.json").read_bytes() == original
    assert (tmp_path / "catalog.pub").read_text().strip() == public
    with pytest.raises(SignatureError):
        verify(catalog.model_copy(update={"catalog_version": "tampered"}), public)


def test_default_catalog_uses_ephemeral_identity(tmp_path, monkeypatch):
    monkeypatch.delenv("LAHZA_CATALOG_PUBKEY", raising=False)
    public = packaging.prepare_catalog(tmp_path)
    verify(Catalog.model_validate_json((tmp_path / "catalog.json").read_text()), public)
    assert {p.name for p in tmp_path.iterdir()} == {"catalog.json", "catalog.pub"}


def test_explicit_catalog_preserves_source_identity(tmp_path, monkeypatch):
    source = tmp_path / "source/catalog"
    public = packaging.prepare_local_catalog(source)
    original = (source / "catalog.json").read_bytes()
    monkeypatch.setattr(packaging, "ROOT", source.parent)
    monkeypatch.setenv("LAHZA_CATALOG_PUBKEY", public)
    destination = tmp_path / "staged"
    assert packaging.prepare_catalog(destination) == public
    assert (destination / "catalog.json").read_bytes() == original
    assert (destination / "catalog.pub").read_text().strip() == public
    assert {p.name for p in destination.iterdir()} == {"catalog.json", "catalog.pub"}


@pytest.mark.parametrize("public", ["", "bad-key", "A" * 44])
def test_explicit_bad_key_never_falls_back(tmp_path, monkeypatch, public):
    monkeypatch.setenv("LAHZA_CATALOG_PUBKEY", public)
    with pytest.raises(SystemExit, match="must verify"):
        packaging.prepare_catalog(tmp_path / "staged")
    assert not (tmp_path / "staged").exists()


def test_explicit_mismatched_key_rejected(tmp_path, monkeypatch):
    public = packaging.prepare_local_catalog(tmp_path / "other")
    packaging.prepare_local_catalog(tmp_path / "source/catalog")
    monkeypatch.setattr(packaging, "ROOT", tmp_path / "source")
    monkeypatch.setenv("LAHZA_CATALOG_PUBKEY", public)
    with pytest.raises(SystemExit, match="must verify"):
        packaging.prepare_catalog(tmp_path / "staged")
    assert not (tmp_path / "staged").exists()


def test_catalog_only_skips_sidecar_tools(tmp_path, monkeypatch):
    monkeypatch.delenv("LAHZA_CATALOG_PUBKEY", raising=False)
    monkeypatch.setattr(packaging, "WORK", tmp_path)
    def unexpected(*args, **kwargs):
        pytest.fail("catalog-only must not invoke sidecar tooling")
    monkeypatch.setattr(packaging, "target_triple", unexpected)
    monkeypatch.setattr(packaging, "pyinstaller_cmd", unexpected)
    assert packaging.main(["--catalog-only"]) == 0
    assert {p.name for p in tmp_path.iterdir()} == {"catalog"}
    assert {p.name for p in (tmp_path / "catalog").iterdir()} == {"catalog.json", "catalog.pub"}


def test_dry_run_leaves_catalog_untouched(tmp_path, monkeypatch):
    monkeypatch.setattr(packaging, "WORK", tmp_path)
    catalog = tmp_path / "catalog"
    catalog.mkdir()
    (catalog / "catalog.pub").write_text("existing-key")
    monkeypatch.setattr(packaging, "optional_imports", lambda: [])
    assert packaging.main(["--dry-run", "--target", "aarch64-apple-darwin"]) == 0
    assert (catalog / "catalog.pub").read_text() == "existing-key"
    assert {p.name for p in tmp_path.iterdir()} == {"catalog"}
    assert not (catalog / "catalog.json").exists()


def test_native_asr_collection():
    backends = ["faster_whisper", "ctranslate2", "tokenizers"]
    cmd = packaging.pyinstaller_cmd(Path("entry.py"), False, backends)
    collected = [cmd[i + 1] for i, arg in enumerate(cmd) if arg == "--collect-all"]
    assert set(backends) <= set(collected)


def test_pyav_is_excluded_from_sidecar():
    """ADR-0015: PyAV (GPL libx264/libx265 FFmpeg) hech qachon yig'ilmaydi, venv'da bo'lsa ham."""
    assert "av" not in packaging.OPTIONAL_IMPORTS
    assert "av" not in packaging.COLLECT_ALL and "av" not in packaging.REQUIRED_BACKENDS
    cmd = packaging.pyinstaller_cmd(Path("entry.py"), False, ["faster_whisper", "av"])
    excluded = [cmd[i + 1] for i, arg in enumerate(cmd) if arg == "--exclude-module"]
    collected = [cmd[i + 1] for i, arg in enumerate(cmd) if arg == "--collect-all"]
    assert "av" in excluded
    assert "av" not in collected


def test_gpl_toc_scan(tmp_path):
    build = tmp_path / "build"
    build.mkdir()
    with pytest.raises(SystemExit, match="TOC topilmadi"):
        packaging.check_no_gpl_bundle(build)
    (build / "PYZ-00.toc").write_text(
        "[('faster_whisper.audio', '/x/faster_whisper/audio.py', 'PYMODULE'),"
        " ('avro', '/x/avro.py', 'PYMODULE'), ('lahza_engine.media.pcm', '/x/pcm.py', 'PYMODULE')]")
    packaging.check_no_gpl_bundle(build)  # toza: `avro`/`pcm` PyAV emas
    (build / "Analysis-00.toc").write_text("(['/x'], [], {}, ['tkinter',\n  'av',\n  '__main__'], [])")
    packaging.check_no_gpl_bundle(build)  # toza: `--exclude-module av` ro'yxati
    for bad in ["('av', '/x/av/__init__.py', 'PYMODULE')", "('av.audio.frame', '/x/f.py', 'PYMODULE')",
                "('av/.dylibs/libx264.165.dylib', '/x', 'BINARY')", "('libx265.215.dylib', '/x', 'BINARY')"]:
        (build / "Analysis-00.toc").write_text(f"[{bad}]")
        with pytest.raises(SystemExit, match="GPL komponent"):
            packaging.check_no_gpl_bundle(build)


def test_desktop_build_rejects_missing_inference_dependencies():
    packaging.check_desktop_backends(sorted(packaging.REQUIRED_BACKENDS))
    with pytest.raises(SystemExit, match="onnxruntime"):
        packaging.check_desktop_backends(sorted(packaging.REQUIRED_BACKENDS - {"onnxruntime"}))


def test_new_setup_modules_are_automatically_collected():
    cmd = packaging.pyinstaller_cmd(Path("entry.py"), False, [])
    assert cmd[cmd.index("--collect-submodules") + 1] == "lahza_engine"


def test_cli_and_first_run_model_pins_match():
    from lahza_engine.models import local_llm

    llm_spec = importlib.util.spec_from_file_location("setup_local_llm", ROOT / "scripts/setup_local_llm.py")
    cli = importlib.util.module_from_spec(llm_spec)
    llm_spec.loader.exec_module(cli)
    for name in ("MODEL_REPO", "MODEL_REVISION", "MODEL_FILE", "MODEL_SIZE", "MODEL_SHA256", "MODEL_ID"):
        assert getattr(cli, name) == getattr(local_llm, name), name


def test_tauri_uses_generated_catalog():
    config = json.loads((ROOT / "app/src-tauri/tauri.conf.json").read_text())
    assert config["bundle"]["resources"]["../../build/sidecar/catalog/"] == "catalog/"


@pytest.mark.skipif(not os.environ.get("LAHZA_TEST_SIDECAR"), reason="opt-in frozen binary smoke")
def test_frozen_sidecar_health_and_catalog(tmp_path):
    binary = Path(os.environ["LAHZA_TEST_SIDECAR"]).resolve()
    isolated_env = {k: v for k, v in os.environ.items() if not k.startswith("DYLD_")}
    if os.name != "nt":
        # macOS hardware discovery uses the OS-provided /usr/sbin/sysctl.
        isolated_env["PATH"] = "/usr/bin:/bin:/usr/sbin:/sbin"
    imported = subprocess.run([str(binary), "--packaging-check"], cwd=tmp_path,
                              env=isolated_env, capture_output=True, text=True, timeout=90, check=True)
    diagnostics = json.loads(imported.stdout)
    child = subprocess.run([str(binary), "--packaging-mp-check"], cwd=tmp_path,
                           env=isolated_env, capture_output=True, text=True, timeout=90, check=True)
    assert json.loads(child.stdout)["shared_memory"] is True
    assert not child.stderr.strip(), child.stderr
    backends = diagnostics["imported_backends"]
    assert {"Inter.ttf", "OFL.txt"} <= set(diagnostics["fonts"])
    if os.environ.get("LAHZA_TEST_REQUIRE_ASR") == "1":
        assert {"faster_whisper", "ctranslate2", "tokenizers"} <= set(backends)
    assert "av" not in backends and diagnostics["av_guard"] is True
    catalog_dir = Path(os.environ.get("LAHZA_TEST_CATALOG", ROOT / "build/sidecar/catalog"))
    env = {**isolated_env, "LAHZA_DEV": "0", "LAHZA_TOKEN": "packaging-smoke-token",
           "LAHZA_DATA_DIR": str(tmp_path / "data"),
           "LAHZA_CATALOG": str(catalog_dir / "catalog.json"),
           "LAHZA_CATALOG_PUBKEY": (catalog_dir / "catalog.pub").read_text().strip()}
    registry = os.environ.get("LAHZA_TEST_MODEL_REGISTRY")
    if registry:
        models = tmp_path / "data/Models"
        models.mkdir(parents=True)
        shutil.copy2(registry, models / "installed.json")
    log_path = tmp_path / "sidecar.log"
    with log_path.open("w+") as log:
        process = subprocess.Popen([str(binary), "serve", "--port", "0"], env=env,
                                   cwd=tmp_path, stdout=log, stderr=log)
        try:
            deadline = time.monotonic() + 90
            while time.monotonic() < deadline:
                text = log_path.read_text()
                match = re.search(r"LAHZA_READY port=(\d+)", text)
                if match:
                    base = f"http://127.0.0.1:{match[1]}"
                    try:
                        with httpx.Client(base_url=base, timeout=10, trust_env=False) as client:
                            headers = {"Authorization": "Bearer packaging-smoke-token"}
                            health = client.get("/v1/health", headers=headers)
                            assert health.status_code == 200, health.text
                            assert health.json()["ok"] is True
                            assert client.get("/v1/health").status_code == 401
                            catalog = client.get("/v1/catalog/bundle", headers=headers)
                            assert catalog.status_code == 200, catalog.text
                            consent = client.post("/v1/models:bootstrap", headers=headers,
                                                  json={"consent": False})
                            assert consent.status_code == 400, consent.text
                            interop = client.post("/v1/interop/inspect", headers=headers,
                                                  json={"path": str(tmp_path / "missing.xml")})
                            assert interop.status_code == 400, interop.text
                            if registry:
                                installed = client.get("/v1/models", headers=headers)
                                installed.raise_for_status()
                                model_id = installed.json()["defaults"]["asr"]
                                tested = client.post(f"/v1/models/{model_id}:test",
                                                     headers=headers, timeout=90)
                                assert tested.status_code == 200, tested.text
                                assert tested.json()["ok"] is True, tested.text
                                audio = os.environ.get("LAHZA_TEST_ASR_AUDIO")
                                if audio:
                                    model = next(m for m in installed.json()["models"]
                                                 if m["id"] == model_id)
                                    result = subprocess.run(
                                        [str(binary), "--packaging-asr-check", model["path"], audio],
                                        cwd=tmp_path, capture_output=True, text=True,
                                        timeout=180, check=True,
                                    )
                                    assert json.loads(result.stdout)["words"] > 0
                        return
                    except httpx.ConnectError:
                        pass
                assert process.poll() is None, text
                time.sleep(0.2)
            pytest.fail(f"sidecar startup timed out: {log_path.read_text()}")
        finally:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=10)


@pytest.mark.skipif(not os.environ.get("LAHZA_TEST_RUNTIME"), reason="opt-in bundled FFmpeg smoke")
def test_bundled_ffmpeg_without_homebrew(tmp_path):
    runtime = Path(os.environ["LAHZA_TEST_RUNTIME"]).resolve()
    fonts = tmp_path / "fonts"
    fonts.mkdir()
    shutil.copy2(ROOT / "engine/src/lahza_engine/subtitle/fonts/Inter.ttf", fonts / "Inter.ttf")
    (tmp_path / "smoke.ass").write_text(
        "[Script Info]\nScriptType: v4.00+\nPlayResX: 128\nPlayResY: 128\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, "
        "BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, "
        "BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
        "Style: Default,Inter,18,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,"
        "0,0,0,0,100,100,0,0,1,1,0,2,4,4,4,1\n"
        "[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
        "Dialogue: 0,0:00:00.00,0:00:01.00,Default,,0,0,0,,Oʻzbekcha gʻoya\n",
        encoding="utf-8",
    )
    env = {k: v for k, v in os.environ.items() if not k.startswith("DYLD_")}
    env.update(PATH="/usr/bin:/bin", DYLD_PRINT_LIBRARIES="1")
    run = subprocess.run(
        [str(runtime / "ffmpeg"), "-v", "error", "-f", "lavfi", "-i",
         "color=c=black:s=128x128:d=0.2", "-vf", "ass=smoke.ass:fontsdir=fonts",
         "-f", "null", "-"],
        env=env, cwd=tmp_path, capture_output=True, text=True, timeout=30,
    )
    assert run.returncode == 0, run.stderr
    assert str(runtime / "lib/libass") in run.stderr, run.stderr
    assert "/opt/homebrew/" not in run.stderr, run.stderr
    assert "/usr/local/" not in run.stderr, run.stderr
    assert str(ROOT / "build/local-runtime") not in run.stderr, run.stderr
