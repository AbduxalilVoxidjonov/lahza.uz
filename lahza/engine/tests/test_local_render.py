"""Local setup must prove visible output and keep the LGPL configuration gate."""

import importlib.util
import subprocess
from pathlib import Path

import pytest
from conftest import requires_ffmpeg, requires_libass, requires_symlink

from lahza_engine.media.tools import find_tool

SPEC = importlib.util.spec_from_file_location(
    "setup_local_render", Path(__file__).resolve().parents[2] / "scripts/setup_local_render.py"
)
setup = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(setup)


@pytest.mark.parametrize("flag", ["--enable-gpl", "--enable-nonfree", "--enable-version3"])
def test_setup_rejects_incompatible_build(monkeypatch, flag) -> None:
    def run(*args, **kwargs):
        return subprocess.CompletedProcess(args[0], 0, stdout=f"configuration: {flag}")

    monkeypatch.setattr(setup, "run", run)
    with pytest.raises(RuntimeError, match="Refusing FFmpeg configuration"):
        setup.validate(Path("ffmpeg"))


@pytest.mark.parametrize("license_text, filters, message", [
    ("GNU General Public License", "", "did not report an LGPL license"),
    ("GNU Lesser General Public\nLicense", " ... ass V->V Render ASS", "both ass and subtitles"),
])
def test_setup_requires_lgpl_and_both_filters(monkeypatch, license_text, filters, message) -> None:
    def run(args, **kwargs):
        output = {"-buildconf": "configuration: --enable-libass",
                  "-L": license_text, "-filters": filters}[args[-1]]
        return subprocess.CompletedProcess(args, 0, stdout=output)

    monkeypatch.setattr(setup, "run", run)
    with pytest.raises(RuntimeError, match=message):
        setup.validate(Path("ffmpeg"))


DECODERS_NO_DAV1D = " V....D av1                  Alliance for Open Media AV1\n"
DECODERS_DAV1D = DECODERS_NO_DAV1D + " V..... libdav1d             dav1d AV1 decoder by VideoLAN (codec av1)\n"


@pytest.mark.parametrize("buildconf, decoders", [
    ("configuration: --enable-libass", DECODERS_DAV1D),          # bayroq yo'q
    ("configuration: --enable-libass --enable-libdav1d", DECODERS_NO_DAV1D),  # dekoder yo'q
])
def test_setup_requires_dav1d(monkeypatch, buildconf, decoders) -> None:
    def run(args, **kwargs):
        output = {"-buildconf": buildconf, "-L": "GNU Lesser General Public License",
                  "-filters": " ... ass V->V Render ASS\n ... subtitles V->V Render text",
                  "-decoders": decoders}[args[-1]]
        return subprocess.CompletedProcess(args, 0, stdout=output)

    monkeypatch.setattr(setup, "run", run)
    with pytest.raises(RuntimeError, match="libdav1d"):
        setup.validate(Path("ffmpeg"))


def test_setup_accepts_lgpl_build_with_dav1d(monkeypatch) -> None:
    def run(args, **kwargs):
        output = {"-buildconf": "configuration: --disable-gpl --enable-libass --enable-libdav1d",
                  "-L": "GNU Lesser General Public License",
                  "-filters": " ... ass V->V Render ASS\n ... subtitles V->V Render text",
                  "-decoders": DECODERS_DAV1D}[args[-1]]
        return subprocess.CompletedProcess(args, 0, stdout=output)

    monkeypatch.setattr(setup, "run", run)
    assert "--enable-libdav1d" in setup.validate(Path("ffmpeg"))["buildconf"]


def test_dav1d_pin_matches_runtimes_toml() -> None:
    import tomllib
    rt = tomllib.loads((Path(__file__).resolve().parents[2] / "third_party/runtimes.toml").read_text())
    assert rt["dav1d"]["version"] == setup.DAV1D_VERSION
    assert rt["dav1d"]["sha256"] == setup.DAV1D_SHA256
    assert rt["dav1d"]["url"] == setup.DAV1D_URL
    assert rt["dav1d"]["license"] == "BSD-2-Clause"
    assert "--enable-libdav1d" in rt["ffmpeg"]["configure_common"]
    assert "--enable-gpl" not in rt["ffmpeg"]["configure_common"]


@requires_ffmpeg
@requires_libass
@pytest.mark.ffmpeg
@pytest.mark.libass
@requires_symlink
def test_local_setup_renders_visible_uzbek_with_both_filters(tmp_path) -> None:
    (tmp_path / "bin").mkdir()
    for name in ("ffmpeg", "ffprobe"):
        (tmp_path / "bin" / name).symlink_to(find_tool(name).resolve())
    setup.smoke_test(tmp_path)
    assert (tmp_path / "smoke/subtitled.mp4").stat().st_size > 1000


@pytest.mark.parametrize("reference", ["@loader_path/libdep.dylib", "@rpath/libdep.dylib"])
def test_resolve_staged_dependency_with_relative_rpath(tmp_path, monkeypatch, reference) -> None:
    library = tmp_path / "libdep.dylib"
    library.write_bytes(b"placeholder")
    monkeypatch.setattr(setup, "rpaths", lambda _: ["@loader_path/../" + tmp_path.name])
    assert setup.resolve_dependency(tmp_path / "consumer.dylib", reference) == library.resolve()


def test_unresolved_dylib_stops_staging(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(setup, "rpaths", lambda _: ["@loader_path"])
    with pytest.raises(RuntimeError, match="Unresolved dependency"):
        setup.resolve_dependency(tmp_path / "consumer.dylib", "@rpath/missing.dylib")
