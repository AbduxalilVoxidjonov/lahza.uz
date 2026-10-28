"""ADR-0015: ASR yo'li PyAV'siz - LGPL FFmpeg dekodi, `av` qo'riqchisi, qadoqlash/litsenziya darvozalari."""
from __future__ import annotations

import importlib.metadata as md
import importlib.util
import math
import os
import re
import subprocess
import sys
import tomllib
import wave
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from conftest import requires_ffmpeg

from lahza_engine.asr import fw_compat
from lahza_engine.asr.base import AsrOptions
from lahza_engine.media.pcm import AudioDecodeError, decode_pcm_f32

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "engine" / "src"


def _load(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _write_stereo_wav(path: Path, rate: int = 8000, seconds: float = 0.5, hz: float = 440.0) -> None:
    n = int(rate * seconds)
    t = np.arange(n) / rate
    tone = (0.5 * np.sin(2 * math.pi * hz * t) * 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(np.column_stack([tone, tone]).tobytes())


# ------------------------------------------------------------------ dekod (haqiqiy ffmpeg)

@requires_ffmpeg
def test_decode_resamples_to_16k_mono_float32(tmp_path):
    src = tmp_path / "tone.wav"
    _write_stereo_wav(src)
    audio = decode_pcm_f32(src)
    assert audio.dtype == np.float32 and audio.ndim == 1
    assert abs(len(audio) - 8000) <= 64  # 0.5 s @ 16 kHz
    assert 0.4 < float(np.max(np.abs(audio))) <= 1.0
    assert audio.flags.writeable  # faster-whisper massivni o'zgartirishi mumkin


@requires_ffmpeg
def test_decode_failure_is_explicit(tmp_path):
    bad = tmp_path / "not-audio.wav"
    bad.write_bytes(b"not a media file")
    with pytest.raises(AudioDecodeError):
        decode_pcm_f32(bad)
    with pytest.raises(AudioDecodeError):
        decode_pcm_f32(tmp_path / "missing.wav")


def test_decode_uses_given_ffmpeg_without_shell(tmp_path, monkeypatch):
    seen = {}

    def fake_run(args, **kw):
        seen["args"], seen["kw"] = args, kw
        return SimpleNamespace(returncode=0, stdout=np.array([0.25, -0.5], "<f4").tobytes() + b"\x00",
                               stderr=b"")

    monkeypatch.setattr("lahza_engine.media.pcm.subprocess.run", fake_run)
    audio = decode_pcm_f32(tmp_path / "a b.wav", ffmpeg=tmp_path / "ffmpeg")
    assert audio.tolist() == [0.25, -0.5]  # to'liq bo'lmagan oxirgi namuna tashlanadi
    args = seen["args"]
    assert args[0] == str(tmp_path / "ffmpeg") and "shell" not in seen["kw"]
    assert args[args.index("-i") + 1] == str(tmp_path / "a b.wav")
    assert args[args.index("-ar") + 1] == "16000" and args[args.index("-ac") + 1] == "1"
    assert args[-3:] == ["-f", "f32le", "pipe:1"]


# ------------------------------------------------------------------ `av` qo'riqchisi

def test_guard_satisfies_import_but_blocks_use(monkeypatch):
    monkeypatch.setitem(sys.modules, "av", None)  # PyAV o'rnatilmagan/to'sib qo'yilgan
    assert fw_compat.install_av_guard() is True
    import av

    assert fw_compat.av_guard_active()
    with pytest.raises(fw_compat.PyAvBlocked, match="ADR-0015"):
        av.open("x.wav")
    with pytest.raises(AttributeError):
        av.__path__  # noqa: B018 - submodul importi ham ishlamaydi
    assert fw_compat.install_av_guard() is True  # idempotent


def test_asr_path_without_pyav(monkeypatch, tmp_path):
    """`av` yo'q: backend massivni dekod qilib beradi, fayl yo'li faster-whisper'ga bormaydi."""
    monkeypatch.setitem(sys.modules, "av", None)
    from lahza_engine.asr import faster_whisper_backend as fwb

    wav = tmp_path / "chunk.wav"
    decoded = np.linspace(-0.1, 0.1, 16000, dtype=np.float32)
    monkeypatch.setattr(fwb, "decode_pcm_f32", lambda path, sr: decoded if (path, sr) == (wav, 16000) else None)
    seen = {}

    def transcribe(audio, **kw):
        seen["audio"] = audio
        word = SimpleNamespace(word="salom", start=0.1, end=0.4, probability=0.9)
        return iter([SimpleNamespace(words=[word])]), None

    backend = object.__new__(fwb.FasterWhisperBackend)
    backend.model = SimpleNamespace(transcribe=transcribe)
    words = backend.transcribe_chunk(wav, 1000, AsrOptions(timestamps="whisper"))
    assert seen["audio"] is decoded
    assert [(w.text, w.start_ms) for w in words] == [("salom", 1100)]
    assert sys.modules["av"] is None  # backend `av` ga tegmadi


def test_backend_init_installs_guard(monkeypatch, tmp_path):
    monkeypatch.setitem(sys.modules, "av", None)
    monkeypatch.setitem(sys.modules, "faster_whisper",
                        SimpleNamespace(WhisperModel=lambda *a, **kw: SimpleNamespace()))
    from lahza_engine.asr.faster_whisper_backend import FasterWhisperBackend

    FasterWhisperBackend(tmp_path, "m", device="cpu")
    assert fw_compat.av_guard_active()


@pytest.mark.skipif(importlib.util.find_spec("faster_whisper") is None, reason="faster-whisper o'rnatilmagan")
def test_real_faster_whisper_imports_without_pyav(tmp_path):
    """Toza jarayon: PyAV to'sib qo'yilgan, haqiqiy faster_whisper import bo'ladi va PyAV yuklanmaydi."""
    code = (
        "import sys\n"
        "sys.modules['av'] = None\n"
        "from lahza_engine.asr.fw_compat import import_faster_whisper, PyAvBlocked\n"
        "fw = import_faster_whisper()\n"
        "assert fw.WhisperModel\n"
        "import lahza_engine.asr.faster_whisper_backend\n"
        "assert getattr(sys.modules['av'], '__lahza_av_guard__', False)\n"
        "try:\n"
        "    fw.decode_audio('x.wav')\n"
        "except PyAvBlocked:\n"
        "    print('blocked')\n"
    )
    run = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=120,
                         cwd=tmp_path, env={"PYTHONPATH": str(SRC), "PATH": "/usr/bin:/bin",
                              # Windows: SYSTEMROOT'siz asyncio (_overlapped) yuklanmaydi
                              **({"SYSTEMROOT": os.environ["SYSTEMROOT"]} if sys.platform == "win32" else {})})
    assert run.returncode == 0, run.stderr
    assert run.stdout.strip() == "blocked"


def test_engine_never_imports_pyav_directly():
    pat = re.compile(r"^\s*(import av\b|from av\b)", re.M)
    offenders = [p.relative_to(SRC).as_posix() for p in SRC.rglob("*.py") if pat.search(p.read_text(encoding="utf-8"))]
    assert offenders == []
    direct = re.compile(r"^\s*from faster_whisper import|^\s*import faster_whisper\b", re.M)
    users = [p.relative_to(SRC).as_posix() for p in SRC.rglob("*.py")
             if direct.search(p.read_text(encoding="utf-8"))]
    assert users == ["lahza_engine/asr/fw_compat.py"]  # boshqalar import_faster_whisper() orqali


# ------------------------------------------------------------------ o'rnatish va litsenziya darvozalari

def _pyproject():
    with (ROOT / "engine/pyproject.toml").open("rb") as f:
        return tomllib.load(f)["project"]


def test_desktop_extra_installs_no_pyav():
    from packaging.requirements import Requirement

    desktop = {Requirement(r).name.lower() for r in _pyproject()["optional-dependencies"]["desktop"]}
    assert "av" not in desktop and "faster-whisper" not in desktop
    gl = _load("gen_licenses_nopyav", "scripts/gen_licenses.py")
    assert gl.nodeps_requirements() == ["faster-whisper"]
    try:
        reqs = md.distribution("faster-whisper").requires or []
    except md.PackageNotFoundError:
        pytest.skip("faster-whisper o'rnatilmagan")
    runtime = {Requirement(r).name.lower() for r in reqs if "extra ==" not in r}
    # faster-whisper'ning PyAV'dan boshqa barcha runtime bog'liqliklari desktop ekstrasida.
    assert runtime - {"av"} <= desktop


def test_forbidden_lists_match():
    gl = _load("gen_licenses_nopyav2", "scripts/gen_licenses.py")
    bs = _load("build_sidecar_nopyav", "scripts/build_sidecar.py")
    assert gl.FORBIDDEN_PYTHON == set(bs.FORBIDDEN_MODULES) == {"av"}


def test_license_gate_rejects_gpl_components():
    gl = _load("gen_licenses_nopyav3", "scripts/gen_licenses.py")

    def comp(name, lic, category="python", risk=""):
        return gl.component("python", name, "1", lic, basis="t", category=category, risk=risk)

    clean = {"components": [
        comp("numpy", "BSD-3-Clause"),
        comp("PyInstaller bootloader", "GPL-2.0-or-later WITH Bootloader-exception"),
        comp("avcodec", "LGPL-3.0-or-later", category="python-native"),
        comp("FreeType", "FTL OR GPL-2.0", category="runtime"),  # runtime: alohida tekshiriladi
    ]}
    assert gl.gpl_violations(clean) == []
    for bad in (comp("av", "BSD-3-Clause"), comp("x264", "GPL-2.0-or-later", "python-native", "GPL"),
                comp("somepkg", "GPL-3.0-only")):
        assert len(gl.gpl_violations({"components": [*clean["components"], bad]})) == 1


def test_license_closure_skips_nodeps_dependencies(monkeypatch):
    gl = _load("gen_licenses_nopyav4", "scripts/gen_licenses.py")
    dists = {
        "lahza-dummy": ("MIT", ["faster-whisper"]),
        "faster-whisper": ("MIT", ["av>=11", "tqdm"]),
        "tqdm": ("MPL-2.0 AND MIT", []),
        "av": ("BSD-3-Clause", []),
    }

    class Dist:
        def __init__(self, name):
            lic, reqs = dists[name]
            self.metadata = {"Name": name, "Version": "1", "License-Expression": lic}
            self.requires = reqs
            self.files = []

    monkeypatch.setattr(gl, "root_requirements", lambda: ["tqdm"])
    monkeypatch.setattr(gl, "nodeps_requirements", lambda: ["faster-whisper"])
    monkeypatch.setattr(md, "distribution", lambda n: Dist(n) if n in dists else (_ for _ in ()).throw(
        md.PackageNotFoundError(n)))
    names = {c["name"] for c in gl.python_components(gl.Texts()) if c["category"] == "python"}
    assert {"faster-whisper", "tqdm"} <= names and "av" not in names
