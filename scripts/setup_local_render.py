#!/usr/bin/env python3
"""Build a local LGPL FFmpeg with libass; never replace a system executable."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION = "7.1.1"
SHA256 = "733984395e0dbbe5c046abda2dc49a5544e7e0e1e2366bba849222ae9e3a03b1"
URL = f"https://ffmpeg.org/releases/ffmpeg-{VERSION}.tar.xz"


def run(args: list[str], **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(args, check=True, **kwargs)


def validate(binary: Path) -> dict[str, str]:
    """Reject GPL/nonfree builds and missing subtitle filters, including on reuse."""
    config = run([str(binary), "-hide_banner", "-buildconf"], capture_output=True,
                 text=True).stdout
    flags = shlex.split(config)
    for flag in ("--enable-gpl", "--enable-nonfree", "--enable-version3"):
        if flag in flags:
            raise RuntimeError(f"Refusing FFmpeg configuration: {flag}")
    license_text = run([str(binary), "-L"], capture_output=True, text=True).stdout
    if "GNU Lesser General Public License" not in " ".join(license_text.split()):
        raise RuntimeError("FFmpeg did not report an LGPL license")
    filters = run([str(binary), "-hide_banner", "-filters"], capture_output=True,
                  text=True).stdout
    names = {p[1] for line in filters.splitlines()
             if len(p := line.split()) >= 3 and "->" in p[2]}
    if not {"ass", "subtitles"} <= names:
        raise RuntimeError("FFmpeg requires both ass and subtitles filters")
    return {"buildconf": config, "license": license_text}


def smoke_test(prefix: Path) -> None:
    """Decode real output and prove subtitle pixels differ from the blank source."""
    work = prefix / "smoke"
    work.mkdir(exist_ok=True)
    fonts = ROOT / "engine/src/lahza_engine/subtitle/fonts"
    shutil.copy2(fonts / "Inter.ttf", work / "Inter.ttf")
    (work / "sample.srt").write_text(
        "1\n00:00:00,000 --> 00:00:01,000\nOʻzbekiston gʻururi Ўў Ққ Ғғ Ҳҳ Öö Ğğ Şş Çç\n",
        encoding="utf-8",
    )
    ffmpeg = str(prefix / "bin/ffmpeg")
    source = [ffmpeg, "-hide_banner", "-v", "error", "-f", "lavfi", "-i",
              "color=c=black:s=640x360:r=5:d=1"]
    run([ffmpeg, "-v", "error", "-y", "-i", "sample.srt", "sample.ass"], cwd=work)
    ass = work / "sample.ass"
    ass.write_text(ass.read_text().replace("Arial", "Inter"), encoding="utf-8")
    # Relative filter paths keep spaces/colons in the repository path safe.
    run([*source, "-y", "-vf",
         "subtitles=sample.srt:fontsdir=.:force_style='FontName=Inter,FontSize=26'",
         "-c:v", "mpeg4", "-q:v", "3", "subtitled.mp4"], cwd=work)
    pixels = run([ffmpeg, "-v", "error", "-i", "subtitled.mp4", "-frames:v", "1",
                  "-f", "rawvideo", "-pix_fmt", "gray", "-"],
                 cwd=work, capture_output=True).stdout
    if len(pixels) != 640 * 360 or sum(v > 100 for v in pixels) < 100:
        raise RuntimeError("Subtitle smoke test produced no visible text")
    ass_pixels = run([*source, "-vf", "ass=sample.ass:fontsdir=.", "-frames:v", "1",
                      "-f", "rawvideo", "-pix_fmt", "gray", "-"],
                     cwd=work, capture_output=True).stdout
    if len(ass_pixels) != 640 * 360 or sum(v > 100 for v in ass_pixels) < 100:
        raise RuntimeError("ASS smoke test produced no visible text")
    run([str(prefix / "bin/ffprobe"), "-v", "error", "-show_streams",
         str(work / "subtitled.mp4")], capture_output=True)


def dylib_dependencies(binary: Path) -> list[str]:
    lines = run(["otool", "-L", str(binary)], capture_output=True, text=True).stdout.splitlines()[1:]
    dependencies = [line.strip().split(" (compatibility version", 1)[0] for line in lines]
    # A dylib's first entry is its own install ID, not a dependency.
    return dependencies[1:] if binary.suffix == ".dylib" else dependencies


def system_library(path: str) -> bool:
    return path.startswith(("/usr/lib/", "/System/Library/"))


def rpaths(binary: Path) -> list[str]:
    commands = run(["otool", "-l", str(binary)], capture_output=True, text=True).stdout
    return re.findall(r"cmd LC_RPATH\s+cmdsize \d+\s+path (.*?) \(offset", commands)


def resolve_dependency(binary: Path, dependency: str) -> Path:
    candidates = [dependency]
    if dependency.startswith("@rpath/"):
        candidates = [p + "/" + dependency.removeprefix("@rpath/") for p in rpaths(binary)]
    for candidate in candidates:
        candidate = candidate.replace("@loader_path", str(binary.parent))
        path = Path(candidate)
        if path.is_absolute() and path.is_file():
            return path.resolve()
    raise RuntimeError(f"Unresolved dependency of {binary}: {dependency}")


def stage_macos(prefix: Path, destination: Path) -> None:
    """Copy the dylib closure, rewrite load commands, ad-hoc sign and test relocation."""
    if sys.platform != "darwin":
        raise RuntimeError("--stage currently supports macOS only")
    with tempfile.TemporaryDirectory(prefix="stage-", dir=prefix) as temporary:
        stage = Path(temporary) / "bin"
        (stage / "lib").mkdir(parents=True)
        pending = [prefix / "bin" / name for name in ("ffmpeg", "ffprobe")]
        libraries: dict[str, Path] = {}
        copied: dict[Path, Path] = {}
        links: dict[Path, list[str]] = {}
        while pending:
            source = pending.pop().resolve()
            if source in copied:
                continue
            target = stage / ("lib" if source.suffix == ".dylib" else "") / source.name
            shutil.copy2(source, target)
            target.chmod(target.stat().st_mode | 0o200)
            copied[source] = target
            links[source] = dylib_dependencies(source)
            for dependency in links[source]:
                if system_library(dependency):
                    continue
                library = resolve_dependency(source, dependency)
                previous = libraries.setdefault(library.name, library)
                if previous != library:
                    raise RuntimeError(f"Dylib basename collision: {previous}, {library}")
                pending.append(library)
        inventory = []
        notices = stage / "licenses/local-render"
        notices.mkdir(parents=True)
        for source, target in copied.items():
            command = ["install_name_tool"]
            if target.suffix == ".dylib":
                command += ["-id", f"@loader_path/{target.name}"]
            for dependency in links[source]:
                if not system_library(dependency):
                    relative = "" if target.suffix == ".dylib" else "lib/"
                    command += ["-change", dependency,
                                f"@loader_path/{relative}{resolve_dependency(source, dependency).name}"]
            for path in rpaths(source):
                command += ["-delete_rpath", path]
            if len(command) > 1:
                run([*command, str(target)], capture_output=True)
            load_commands = run(["otool", "-l", str(target)], capture_output=True, text=True).stdout
            inventory.append({"file": str(target.relative_to(stage)), "source": str(source),
                              "minos": re.findall(r"\bminos\s+(\S+)", load_commands),
                              "architectures": run(["lipo", "-archs", str(target)],
                                                   capture_output=True, text=True).stdout.strip()})
            if target.suffix == ".dylib":
                # Homebrew bottle notices and provenance; full source obligations still apply.
                formula_root = source.parent.parent
                notice_dir = notices / formula_root.parent.name
                notice_dir.mkdir(exist_ok=True)
                for item in formula_root.rglob("*"):
                    if item.is_file() and (
                        item.name.upper().startswith(("LICENSE", "COPYING", "FTL", "GPL"))
                        or item.name in ("INSTALL_RECEIPT.json", "sbom.spdx.json")
                    ):
                        out = notice_dir / item.relative_to(formula_root)
                        out.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(item, out)
        for name in ("COPYING.LGPLv2.1", "LICENSE.md", "manifest.json"):
            shutil.copy2(prefix / name, notices / name)
        # install_name_tool invalidates ARM signatures. Final release signing is separate.
        for target in sorted(copied.values(), key=lambda p: p.suffix != ".dylib"):
            run(["codesign", "--force", "--sign", "-", str(target)], capture_output=True)
            run(["codesign", "--verify", "--strict", str(target)], capture_output=True)
            for dependency in dylib_dependencies(target):
                if system_library(dependency):
                    continue
                if not dependency.startswith("@loader_path/"):
                    raise RuntimeError(f"Nonrelocatable dependency: {dependency}")
                resolved = target.parent / dependency.removeprefix("@loader_path/")
                if not resolved.is_file():
                    raise RuntimeError(f"Missing staged dependency: {resolved}")
        # Move to a different directory before execution, checking relative lookup survives.
        relocated = Path(temporary) / "relocated runtime"
        shutil.copytree(stage, relocated / "bin")
        validate(relocated / "bin/ffmpeg")
        smoke_test(relocated)
        loaded = run([str(relocated / "bin/ffmpeg"), "-version"],
                     env={**os.environ, "DYLD_PRINT_LIBRARIES": "1"},
                     capture_output=True, text=True).stderr
        if "/opt/homebrew/" in loaded or "/usr/local/" in loaded:
            raise RuntimeError("Relocated runtime still loads external Homebrew libraries")
        (notices / "dyld-loaded.txt").write_text(loaded)
        (notices / "dylibs.json").write_text(json.dumps(inventory, indent=2) + "\n")
        destination.mkdir(parents=True, exist_ok=True)
        shutil.copytree(stage, destination, dirs_exist_ok=True)
    print(f"Relocatable macOS runtime staged: {destination} (ad-hoc signed)")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--install-deps", action="store_true",
                        help="Install libass, pkgconf and nasm using Homebrew (macOS)")
    parser.add_argument("--jobs", type=int, default=min(os.cpu_count() or 2, 8))
    parser.add_argument("--rebuild", action="store_true", help="Reconfigure and rebuild FFmpeg")
    parser.add_argument("--stage", nargs="?", type=Path,
                        const=ROOT / "app/src-tauri/resources/bin", metavar="BIN_DIR",
                        help="macOS: stage FFmpeg plus relocated dylibs (default: app resources/bin)")
    args = parser.parse_args()
    if not hasattr(tarfile, "data_filter"):
        parser.error("Python with tarfile.data_filter is required (use Python 3.12+)")
    if args.jobs < 1:
        parser.error("--jobs must be positive")
    prefix = ROOT / "build/local-runtime"
    prefix.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    if args.install_deps:
        if sys.platform != "darwin" or not shutil.which("brew"):
            parser.error("--install-deps requires macOS and Homebrew")
        run(["brew", "install", "libass", "pkgconf", "nasm"])
    if shutil.which("brew"):
        brew_prefix = run(["brew", "--prefix"], capture_output=True, text=True).stdout.strip()
        env["PATH"] = f"{brew_prefix}/bin:" + env.get("PATH", "")
        env["PKG_CONFIG_PATH"] = f"{brew_prefix}/lib/pkgconfig:" + env.get("PKG_CONFIG_PATH", "")
    if args.rebuild or not (prefix / "bin/ffmpeg").exists():
        run(["pkg-config", "--exists", "libass"], env=env)
        downloads = prefix / "downloads"
        downloads.mkdir(exist_ok=True)
        archive = downloads / f"ffmpeg-{VERSION}.tar.xz"
        if not archive.exists():
            partial = archive.with_suffix(".part")
            with urllib.request.urlopen(URL, timeout=60) as response, partial.open("wb") as out:
                shutil.copyfileobj(response, out)
            partial.replace(archive)
        if hashlib.sha256(archive.read_bytes()).hexdigest() != SHA256:
            raise RuntimeError(f"Checksum mismatch; remove {archive} and retry")
        source = prefix / f"ffmpeg-{VERSION}"
        if not source.exists():
            with tarfile.open(archive) as tar:
                tar.extractall(prefix, filter="data")
        flags = [f"--prefix={prefix}", "--disable-autodetect", "--disable-gpl",
                 "--disable-nonfree", "--disable-version3", "--disable-doc",
                 "--disable-debug", "--disable-ffplay", "--enable-libass",
                 "--enable-zlib"]
        if sys.platform == "darwin":
            flags += ["--enable-videotoolbox", "--enable-audiotoolbox"]
        log = prefix / "build.log"
        print(f"Building FFmpeg {VERSION}; log: {log}", flush=True)
        with log.open("w") as output:
            run(["./configure", *flags], cwd=source, env=env, stdout=output,
                stderr=subprocess.STDOUT)
            run(["make", f"-j{args.jobs}"], cwd=source, env=env, stdout=output,
                stderr=subprocess.STDOUT)
            run(["make", "install"], cwd=source, env=env, stdout=output,
                stderr=subprocess.STDOUT)
        for name in ("COPYING.LGPLv2.1", "LICENSE.md"):
            shutil.copy2(source / name, prefix / name)
    metadata = validate(prefix / "bin/ffmpeg")
    smoke_test(prefix)
    metadata.update(source=URL, sha256=SHA256)
    metadata["binary_sha256"] = hashlib.sha256((prefix / "bin/ffmpeg").read_bytes()).hexdigest()
    (prefix / "manifest.json").write_text(json.dumps(metadata, indent=2) + "\n")
    activation = (f"export LAHZA_BIN_DIR={shlex.quote(str(prefix / 'bin'))}\n"
                  'export PATH="$LAHZA_BIN_DIR:$PATH"\n'
                  "export LAHZA_REQUIRE_LIBASS=1\n")
    (prefix / "activate.sh").write_text(activation)
    if args.stage is not None:
        stage_macos(prefix, args.stage.resolve())
    print(f"Subtitle render passed: {prefix / 'smoke/subtitled.mp4'}")
    print(f"Activate: source {shlex.quote(str(prefix / 'activate.sh'))}")


if __name__ == "__main__":
    main()
