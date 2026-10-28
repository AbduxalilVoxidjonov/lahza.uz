"""Windows: bin/ dagi exe/DLL'lar uchun kerakli VC++ runtime DLL'larini yoniga (app-local) qo'yadi
va har bir importni tekshiradi - toza Windows (hech narsa o'rnatilmagan) kompyuterida ham ishlashi uchun.

    python scripts/stage_windows_dlls.py [--bin-dir DIR] [--runtime-dir DIR] [--check-only]
                                         [--check EXE ...]

* `--bin-dir` (standart: app/src-tauri/resources/bin) - llama-server, ffmpeg/ffprobe va ularning DLL'lari.
* `--runtime-dir` (standart: engine/.venv/Scripts) - `msvc-runtime` paketidagi yangi VC++ DLL'lari.
  Tizimdagi eski runtime (masalan 14.28) yangi msvcp140 bilan aralashsa llama/ggml qulaydi, shuning
  uchun bin/ dagi kerakli runtime DLL'lari doim shu manbadagi nusxa bilan bir xil qilinadi.
* `--check` - qo'shimcha exe'lar (lahza-studio.exe, sidecar): faqat tizim DLL'lari yoki yonidagi
  fayllarni import qilishi shart.

Har bir import uch xil bo'ladi: papkaning o'zida bor; Windows tizim DLL'i (KERNEL32, api-ms-win-crt-*
Win10+ UCRT, ...); qayta tarqatiladigan runtime (msvcp140*, vcruntime140*, libomp, MinGW runtime...) -
u bin/ da bo'lishi yoki --runtime-dir dan ko'chirilishi shart. Yechilmagan import - xato (exit 1).
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BIN_DIR = ROOT / "app" / "src-tauri" / "resources" / "bin"
RUNTIME_DIR = ROOT / "engine" / ".venv" / "Scripts"

# Tizimda bo'lishi kafolatlanmagan (yoki eski versiyasi bo'lishi mumkin) runtime'lar: System32'da
# topilsa ham tizimniki hisoblanmaydi. msvcrt.dll (tizimniki) bunga kirmaydi.
REDIST_RE = re.compile(r"^(msvcp\d+.*|vcruntime\d+.*|concrt\d+|vcomp\d+.*|vccorlib\d+|vcamp\d+|msvcr\d+.*"
                       r"|ucrtbased|libomp.*|libiomp.*|libgcc.*|libstdc\+\+.*|libwinpthread.*)\.dll$")
# API set'lar (api-ms-win-crt-* = UCRT) Win10+ da tizimning bir qismi.
API_SET_RE = re.compile(r"^(api|ext)-ms-win-.*\.dll$")
PE_SUFFIXES = (".exe", ".dll")


def _rva_to_offset(sections: list[tuple[int, int, int, int]], rva: int) -> int | None:
    for va, vsize, raw, rsize in sections:
        if va <= rva < va + min(vsize or rsize, rsize):  # faqat fayldagi (raw) qism
            return raw + rva - va
    return None


def _cstr(data: bytes, off: int) -> str:
    end = data.index(b"\0", off)
    return data[off:end].decode("ascii", "replace")


def pe_imports(data: bytes) -> list[str]:
    """PE faylning import va delay-load import DLL nomlari (fayldagi tartibda, takrorsiz)."""
    if data[:2] != b"MZ":
        raise ValueError("PE emas (MZ yo'q)")
    pe = struct.unpack_from("<I", data, 0x3C)[0]
    if data[pe:pe + 4] != b"PE\0\0":
        raise ValueError("PE emas (PE imzosi yo'q)")
    nsec, opt_size = struct.unpack_from("<H", data, pe + 6)[0], struct.unpack_from("<H", data, pe + 20)[0]
    opt = pe + 24
    magic = struct.unpack_from("<H", data, opt)[0]
    dd = opt + (112 if magic == 0x20B else 96)  # PE32+ / PE32
    ndirs = struct.unpack_from("<I", data, dd - 4)[0]
    sec0 = opt + opt_size
    sections = []  # (VirtualAddress, VirtualSize, PointerToRawData, SizeOfRawData)
    for i in range(nsec):
        vsize, va, rsize, raw = struct.unpack_from("<IIII", data, sec0 + 40 * i + 8)
        sections.append((va, vsize, raw, rsize))

    names: list[str] = []
    for index, desc_size, name_field in ((1, 20, 12), (13, 32, 4)):  # import, delay-load import
        if index >= ndirs:
            continue
        rva = struct.unpack_from("<I", data, dd + 8 * index)[0]
        off = _rva_to_offset(sections, rva) if rva else None
        while off is not None and off + desc_size <= len(data):
            desc = data[off:off + desc_size]
            if not any(desc):
                break
            name_off = _rva_to_offset(sections, struct.unpack_from("<I", desc, name_field)[0])
            if name_off is not None:
                name = _cstr(data, name_off)
                if name.lower() not in (n.lower() for n in names):
                    names.append(name)
            off += desc_size
    return names


def is_system_dll(name: str, system_names: set[str]) -> bool:
    """Windows'ning o'z DLL'i: API set yoki System32'da bor va qayta tarqatiladigan runtime emas."""
    low = name.lower()
    if API_SET_RE.match(low):
        return True
    return low in system_names and not REDIST_RE.match(low)


def plan(imports: dict[str, list[str]], present: set[str], available: dict[str, list[str]],
         system_names: set[str]) -> tuple[list[str], dict[str, list[str]]]:
    """Ko'chirish kerak bo'lgan runtime DLL'lar va yechilmagan importlar (fayl -> DLL'lar).

    `imports` - papkadagi fayllar importlari; `present` - papkadagi fayl nomlari; `available` -
    --runtime-dir dagi DLL -> uning importlari (ko'chirilgan DLL'ning bog'liqliklari ham yechiladi).
    Hamma nomlar kichik harfda solishtiriladi; natija kichik harfda."""
    have = {n.lower() for n in present}
    avail = {k.lower(): v for k, v in available.items()}
    queue = [(f.lower(), deps) for f, deps in sorted(imports.items())]
    copy: list[str] = []
    missing: dict[str, list[str]] = {}
    while queue:
        owner, deps = queue.pop(0)
        for dep in deps:
            low = dep.lower()
            if low in have or is_system_dll(low, system_names):
                continue
            if low in avail and REDIST_RE.match(low):
                copy.append(low)
                have.add(low)
                queue.append((low, avail[low]))
                continue
            missing.setdefault(owner, []).append(low)
    return copy, missing


def stale_runtime(present: set[str], available: dict[str, list[str]], same) -> list[str]:
    """bin/ da bor, lekin --runtime-dir dagi nusxadan farq qiladigan runtime DLL'lar (eski versiya)."""
    avail = {k.lower() for k in available}
    return sorted(n.lower() for n in present if n.lower() in avail and REDIST_RE.match(n.lower())
                  and not same(n))


def _pe_files(folder: Path) -> list[Path]:
    return sorted(p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in PE_SUFFIXES)


def _system_names() -> set[str]:
    sysdir = Path(os.environ.get("SYSTEMROOT", r"C:\Windows")) / "System32"
    return {p.name.lower() for p in sysdir.iterdir()} if sysdir.is_dir() else set()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--bin-dir", type=Path, default=BIN_DIR)
    ap.add_argument("--runtime-dir", type=Path, default=RUNTIME_DIR)
    ap.add_argument("--check-only", action="store_true", help="hech narsa ko'chirmaslik, faqat tekshirish")
    ap.add_argument("--check", type=Path, action="append", default=[], help="qo'shimcha exe (yonidagi fayllar bilan)")
    a = ap.parse_args(argv)
    if sys.platform != "win32":
        print("faqat Windows uchun - o'tkazib yuborildi")
        return 0

    system_names = _system_names()
    files = _pe_files(a.bin_dir)
    imports = {p.name: pe_imports(p.read_bytes()) for p in files}
    available = ({p.name: pe_imports(p.read_bytes()) for p in _pe_files(a.runtime_dir)
                  if REDIST_RE.match(p.name.lower())} if a.runtime_dir.is_dir() else {})
    src = {k.lower(): a.runtime_dir / k for k in available}
    present = {p.name for p in files}

    copy, missing = plan(imports, present, available, system_names)
    stale = stale_runtime(present, available, lambda n: (a.bin_dir / n).read_bytes() == src[n.lower()].read_bytes())
    for name in sorted(set(copy) | set(stale)):
        action = "yangilanadi" if name in stale else "ko'chiriladi"
        print(f"{name}: {action} <- {src[name]}")
        if not a.check_only:
            shutil.copy2(src[name], a.bin_dir / src[name].name)

    for exe in a.check:
        sib = {p.name for p in _pe_files(exe.parent)}
        _, bad = plan({exe.name: pe_imports(exe.read_bytes())}, sib, {}, system_names)
        missing.update({str(exe): v for v in bad.values()})
        print(f"{exe.name}: " + ", ".join(pe_imports(exe.read_bytes())))

    if a.check_only and (copy or stale):
        missing.setdefault("(runtime)", []).extend(sorted(set(copy) | set(stale)))
    if missing:
        for owner, deps in sorted(missing.items()):
            print(f"XATO: {owner}: yechilmagan import(lar): {', '.join(deps)}", file=sys.stderr)
        return 1
    print(f"ok: {len(files)} ta fayl ({a.bin_dir}) - hamma importlar yechildi")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
