"""scripts/stage_windows_dlls.py: PE import o'quvchi va app-local runtime DLL rejasi (sof mantiq)."""
from __future__ import annotations

import importlib.util
import struct
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("stage_windows_dlls", ROOT / "scripts/stage_windows_dlls.py")
stage = importlib.util.module_from_spec(spec)
spec.loader.exec_module(stage)

SYSTEM = {"kernel32.dll", "user32.dll", "msvcrt.dll", "vcruntime140.dll", "msvcp140.dll"}


def _pe(imports: list[str], delay: list[str] = ()) -> bytes:
    """Minimal PE32+: bitta bo'lim (VA 0x1000, fayl 0x200), import va delay-load jadvallari."""
    sec = bytearray(0x400)
    names_at = 0x200
    strings: list[int] = []
    for name in [*imports, *delay]:
        strings.append(0x1000 + names_at)
        sec[names_at:names_at + len(name) + 1] = name.encode() + b"\0"
        names_at += len(name) + 1
    for i, rva in enumerate(strings[:len(imports)]):  # IMAGE_IMPORT_DESCRIPTOR, Name +12
        struct.pack_into("<5I", sec, 20 * i, 0, 0, 0, rva, 0)
    for i, rva in enumerate(strings[len(imports):]):  # delay descriptor, DllNameRVA +4
        struct.pack_into("<8I", sec, 0x100 + 32 * i, 1, rva, 0, 0, 0, 0, 0, 0)
    head = bytearray(0x200)
    head[:2] = b"MZ"
    struct.pack_into("<I", head, 0x3C, 0x40)
    head[0x40:0x44] = b"PE\0\0"
    struct.pack_into("<HHIIIHH", head, 0x44, 0x8664, 1, 0, 0, 0, 240, 0x22)
    opt = 0x58
    struct.pack_into("<H", head, opt, 0x20B)
    struct.pack_into("<I", head, opt + 108, 16)
    struct.pack_into("<II", head, opt + 112 + 8, 0x1000, 20 * (len(imports) + 1))
    if delay:
        struct.pack_into("<II", head, opt + 112 + 8 * 13, 0x1100, 32 * (len(delay) + 1))
    struct.pack_into("<8sIIII", head, opt + 240, b".idata", 0x400, 0x1000, 0x400, 0x200)
    return bytes(head + sec)


def test_pe_imports_reads_import_and_delay_tables():
    assert stage.pe_imports(_pe(["KERNEL32.dll", "MSVCP140.dll"], ["WINMM.dll"])) == [
        "KERNEL32.dll", "MSVCP140.dll", "WINMM.dll"]
    assert stage.pe_imports(_pe(["a.dll", "A.DLL"])) == ["a.dll"]  # takrorsiz
    with pytest.raises(ValueError):
        stage.pe_imports(b"not a pe" * 10)


@pytest.mark.parametrize(("name", "system"), [
    ("KERNEL32.dll", True), ("api-ms-win-crt-runtime-l1-1-0.dll", True), ("msvcrt.dll", True),
    ("VCRUNTIME140.dll", False),  # System32'da eski nusxasi bo'lsa ham - app-local bo'lishi shart
    ("msvcp140.dll", False), ("libomp.dll", False), ("libwinpthread-1.dll", False), ("foo.dll", False),
])
def test_is_system_dll(name, system):
    assert stage.is_system_dll(name, SYSTEM) is system


def test_plan_copies_runtime_closure_and_reports_unknown():
    imports = {"llama-server.exe": ["llama.dll", "KERNEL32.dll", "VCRUNTIME140.dll"],
               "llama.dll": ["MSVCP140.dll", "ggml.dll", "api-ms-win-crt-heap-l1-1-0.dll"]}
    available = {"msvcp140.dll": ["VCRUNTIME140.dll", "VCRUNTIME140_1.dll", "KERNEL32.dll"],
                 "vcruntime140.dll": ["KERNEL32.dll"], "vcruntime140_1.dll": ["VCRUNTIME140.dll"]}
    copy, missing = stage.plan(imports, {"llama-server.exe", "llama.dll"}, available, SYSTEM)
    assert sorted(copy) == ["msvcp140.dll", "vcruntime140.dll", "vcruntime140_1.dll"]
    assert missing == {"llama.dll": ["ggml.dll"]}
    # Hammasi joyida bo'lsa - hech narsa ko'chirilmaydi.
    present = {"llama-server.exe", "llama.dll", "ggml.dll", "MSVCP140.dll", "vcruntime140.dll", "vcruntime140_1.dll"}
    assert stage.plan(imports, present, available, SYSTEM) == ([], {})


def test_stale_runtime_only_for_redistributables():
    available = {"msvcp140.dll": [], "vcruntime140.dll": [], "foo.dll": []}
    same = {"msvcp140.dll": False, "vcruntime140.dll": True, "foo.dll": False}
    assert stage.stale_runtime({"MSVCP140.dll", "vcruntime140.dll", "foo.dll", "x.dll"}, available,
                               lambda n: same[n.lower()]) == ["msvcp140.dll"]
