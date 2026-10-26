"""scripts/gen_licenses.py (V1-5): oflayn generator, kesh va Markdown belgilari. Faqat tmp fayllar."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("gen_licenses", ROOT / "scripts/gen_licenses.py")
gen = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gen)


class _Meta(dict):
    def get_all(self, key):
        v = self.get(key)
        return v if isinstance(v, list) else None


@pytest.mark.parametrize(("meta", "expected"), [
    ({"License-Expression": "MIT OR Apache-2.0"}, "MIT OR Apache-2.0"),
    ({"License": "Apache 2.0"}, "Apache-2.0"),
    ({"License": "x" * 200, "Classifier": ["License :: OSI Approved :: BSD License"]}, "BSD"),
    ({}, "ANIQLANSIN"),
])
def test_python_license(meta, expected):
    assert gen.python_license(_Meta(meta)) == expected


@pytest.mark.parametrize(("name", "base"), [
    ("libx264.165.dylib", "x264"),
    ("libavcodec.62.11.100.dylib", "avcodec"),
    ("avcodec-62.dll", "avcodec"),
    ("libvpx-1a2b3c4d.so.9", "vpx"),
    ("libSvtAv1Enc.3.1.2.dylib", "SvtAv1Enc"),
])
def test_native_base(name, base):
    assert gen.native_base(name) == base


def test_gpl_native_libs_are_known():
    assert gen.NATIVE_KNOWN["x264"].startswith("GPL")
    assert gen.NATIVE_KNOWN["avcodec"].startswith("LGPL")


def test_texts_deduplicated_and_normalized(tmp_path):
    texts = gen.Texts()
    (tmp_path / "LICENSE").write_text("MIT  \r\nCopyright\r\n", encoding="utf-8")
    (tmp_path / "COPYING").write_text("MIT\nCopyright\n", encoding="utf-8")
    (tmp_path / "license.js").write_text("code", encoding="utf-8")
    (tmp_path / "README.md").write_text("readme", encoding="utf-8")
    ids = texts.add_dir(tmp_path)
    assert len(ids) == 1 and texts.items[ids[0]]["body"] == "MIT\nCopyright\n"


def _lock(tmp_path, monkeypatch, *pkgs):
    lock = tmp_path / "Cargo.lock"
    body = "version = 4\n\n[[package]]\nname = \"app\"\nversion = \"0.1.0\"\n"
    for name, version in pkgs:
        body += (f"\n[[package]]\nname = \"{name}\"\nversion = \"{version}\"\n"
                 "source = \"registry+https://github.com/rust-lang/crates.io-index\"\n")
    lock.write_text(body, encoding="utf-8")
    monkeypatch.setattr(gen, "CARGO_LOCK", lock)


def test_rust_from_registry_unknown_and_cache(tmp_path, monkeypatch):
    _lock(tmp_path, monkeypatch, ("serde", "1.0.0"), ("windows-sys", "0.59.0"), ("syn", "1.0.0"), ("syn", "2.0.0"))
    reg = tmp_path / "registry"
    for name, ver in [("serde", "1.0.0"), ("syn", "2.0.0")]:
        crate = reg / f"{name}-{ver}"
        crate.mkdir(parents=True)
        (crate / "Cargo.toml").write_text(f'[package]\nname = "{name}"\nlicense = "MIT OR Apache-2.0"\n', encoding="utf-8")
        (crate / "LICENSE-MIT").write_text(f"MIT {name}\n", encoding="utf-8")
    texts = gen.Texts()
    comps = {c["id"]: c for c in gen.rust_components(texts, gen.Cache(None), [reg])}
    assert comps["rust:serde@1.0.0"]["license"] == "MIT OR Apache-2.0"
    assert comps["rust:serde@1.0.0"]["texts"]
    assert comps["rust:windows-sys@0.59.0"]["license"] == "ANIQLANSIN"
    assert "2.0.0" in comps["rust:syn@1.0.0"]["notes"]  # boshqa versiya ko'rsatiladi, litsenziya taxmin qilinmaydi
    assert comps["rust:syn@1.0.0"]["license"] == "ANIQLANSIN"

    # Registry yo'q (CI): oldingi natija o'zgarishsiz qayta ishlatiladi.
    previous = {"components": list(comps.values()), "texts": texts.items}
    again = gen.rust_components(gen.Texts(), gen.Cache(previous), [])
    assert again == sorted(comps.values(), key=lambda c: (c["name"].lower(), c["version"]))


def test_runtime_staged_sbom_and_cache(tmp_path, monkeypatch):
    rt = tmp_path / "runtimes.toml"
    rt.write_text('[ffmpeg]\nref = ""\nconfigure_common = ["--enable-shared"]\n[whisper_cpp]\nref = ""\n', encoding="utf-8")
    monkeypatch.setattr(gen, "RUNTIMES", rt)
    staged = tmp_path / "licenses"
    lib = staged / "local-render" / "libass"
    lib.mkdir(parents=True)
    (lib / "COPYING").write_text("ISC License\n", encoding="utf-8")
    (lib / "sbom.spdx.json").write_text(json.dumps({"packages": [
        {"name": "libass", "versionInfo": "0.17.5", "licenseConcluded": "ISC"}]}), encoding="utf-8")
    (staged / "local-render" / "COPYING.LGPLv2.1").write_text("GNU LESSER GENERAL PUBLIC LICENSE\n", encoding="utf-8")
    (staged / "local-render" / "dav1d.COPYING").write_text("Copyright © 2018-2019, VideoLAN and dav1d authors\n",
                                                          encoding="utf-8")
    texts = gen.Texts()
    comps = gen.runtime_components(texts, gen.Cache(None), staged)
    by = {c["name"]: c for c in comps}
    assert by["FFmpeg"]["license"] == "LGPL-2.1-or-later"
    assert by["FFmpeg"]["version"] == gen._pin(gen.SETUP_RENDER, "VERSION")
    assert by["FFmpeg"]["texts"]
    assert "--enable-shared" in by["FFmpeg"]["notes"]
    assert by["libass"]["license"] == "ISC" and by["libass"]["category"] == "native"
    assert by["whisper.cpp (ggml)"]["version"] == "ANIQLANSIN"
    # dav1d: statik (FFmpeg ichida), native/Homebrew emas; versiya setup_local_render.py pinidan.
    assert by["dav1d"]["license"] == "BSD-2-Clause" and by["dav1d"]["category"] == "runtime"
    assert by["dav1d"]["version"] == gen._pin(gen.SETUP_RENDER, "DAV1D_VERSION") != ""
    assert "VideoLAN" in texts.items[by["dav1d"]["texts"][0]]["body"]
    assert "dav1d.COPYING" not in by  # fayl - Homebrew bottle katalogi sifatida sanalmaydi

    previous = {"components": comps, "texts": texts.items}
    again = gen.runtime_components(gen.Texts(), gen.Cache(previous), tmp_path / "yoq")
    assert {c["id"]: c for c in again} == {c["id"]: c for c in comps}


def test_fonts_and_models_from_repo():
    texts = gen.Texts()
    fonts = gen.font_components(texts)
    assert fonts and fonts[0]["name"] == "Inter" and fonts[0]["license"] == "OFL-1.1"
    assert "SIL OPEN FONT LICENSE" in texts.items[fonts[0]["texts"][0]]["body"].upper()
    entries = json.loads(gen.CATALOG.read_text(encoding="utf-8"))["entries"]
    models = gen.model_components()
    assert len(models) == len(entries)
    attributed = [m for m in models if m["license"] == "CC-BY-4.0"]
    assert attributed and all(m["attribution"] for m in attributed)


def test_render_markers():
    text = "a\n<!-- gen_licenses:x:start -->\nold\n<!-- gen_licenses:x:end -->\nb\n"
    assert "new" in gen.render(text, {"x": "new"}) and "old" not in gen.render(text, {"x": "new"})
    with pytest.raises(SystemExit):
        gen.render(text, {"y": "z"})


def test_committed_files_consistent():
    """Kesh-only qayta generatsiya aynan joriy JSON'ni beradi va MD'da barcha belgilar bor."""
    previous = gen.load_previous()
    assert previous is not None
    assert gen.collect(gen.GROUPS, previous) == previous
    md = gen.OUT.read_text(encoding="utf-8")
    for name in gen.sections(previous):
        assert f"<!-- gen_licenses:{name}:start -->" in md
    for c in previous["components"]:
        assert all(t in previous["texts"] for t in c["texts"]), c["id"]
