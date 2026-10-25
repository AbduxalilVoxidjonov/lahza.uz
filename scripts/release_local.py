"""Lokal reliz (Apple Silicon): versiya -> testlar -> `.app` -> `versiyalar/<versiya>/`.

    python scripts/release_local.py 0.2.0          # yoki patch|minor|major
    python scripts/release_local.py 0.2.0 --dry-run

Qadamlar (birortasi yiqilsa to'xtaydi):
  1. `versiyalar/<versiya>/` hali yo'qligini tekshiradi (ustidan yozilmaydi).
  2. `scripts/bump_version.py` - versiya hamma manifestlarda.
  3. `make test-engine test-ui typecheck lint check-licenses`.
  4. `make build-local` (sidecar + `tauri build` + ad-hoc imzo).
  5. `versiyalar/<versiya>/`: ikki marta bosib ochiladigan `Lahza Studio.app` (`ditto` nusxa,
     `codesign --verify --deep --strict` bilan tekshiriladi), uning `ditto` zip nusxasi,
     `NOTES.md`, `SHA256SUMS` (zip + `Contents/MacOS/*`);
     `versiyalar/CHANGELOG.md` dagi "## [Kelgusi]" bo'limi shu versiya sarlavhasiga o'tkaziladi.

Build yiqilsa ham papka va hujjatlar yoziladi (NOTES'da "yig'ilmadi"), chiqish kodi 2.
Faqat standart kutubxona. Commit va git teg qo'yilmaydi - bu qo'lda qilinadi.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import platform
import re
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from bump_version import resolve  # noqa: E402
from check_versions import PYPROJECT, ROOT, collect  # noqa: E402

VERSIONS_DIR = Path("versiyalar")
APP_BUNDLE = Path("app/src-tauri/target/release/bundle/macos/Lahza Studio.app")
TEST_TARGETS = ["test-engine", "test-ui", "typecheck", "lint", "check-licenses"]
UNRELEASED = "## [Kelgusi]"


def run(cmd: list[str], root: Path) -> tuple[int, str, float]:
    """Buyruqni chiqishini jonli ko'rsatib bajaradi; (kod, to'liq chiqish, soniya)."""
    print(f"\n$ {' '.join(cmd)}", flush=True)
    t0 = time.monotonic()
    proc = subprocess.Popen(cmd, cwd=root, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True, encoding="utf-8", errors="replace")
    assert proc.stdout is not None
    chunks: list[str] = []
    for line in proc.stdout:
        sys.stdout.write(line)
        chunks.append(line)
    return proc.wait(), "".join(chunks), time.monotonic() - t0


def summarize(target: str, code: int, out: str) -> str:
    if target == "test-engine":
        m = re.findall(r"^[= ]*(\d+ (?:passed|failed|error).*?) in [\d.]+s", out, re.M)
        if m:
            return m[-1]
    if target == "test-ui":
        # TAP ("# pass N") yoki spec reporter ("ℹ pass N").
        p = re.findall(r"^(?:#|ℹ) pass (\d+)", out, re.M)
        f = re.findall(r"^(?:#|ℹ) fail (\d+)", out, re.M)
        if p:
            return f"{p[-1]} passed, {f[-1] if f else 0} failed"
    return "ok" if code == 0 else f"XATO (kod {code})"


def git(root: Path, *args: str) -> str:
    try:
        return subprocess.run(["git", *args], cwd=root, capture_output=True, text=True,
                              check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return ""


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def du(path: Path) -> int:
    if path.is_file():
        return path.stat().st_size
    return sum(p.lstat().st_size for p in path.rglob("*") if p.is_file() and not p.is_symlink())


def copy_app(app: Path, dest: Path) -> None:
    """`.app` ni `ditto` bilan nusxalaydi (symlink, atributlar, imzo saqlanadi) va imzoni tekshiradi."""
    subprocess.run(["ditto", str(app), str(dest)], check=True)
    subprocess.run(["codesign", "--verify", "--deep", "--strict", str(dest)], check=True)


def app_sums(app: Path) -> list[tuple[str, str]]:
    """`.app` ichidagi `Contents/MacOS/*` bajariladigan fayllar: (sha256, nisbiy yo'l)."""
    macos = app / "Contents" / "MacOS"
    return [(sha256(p), f"{app.name}/{p.relative_to(app).as_posix()}")
            for p in sorted(macos.iterdir()) if p.is_file() and not p.is_symlink()]


def mb(n: int) -> str:
    return f"{n / 1_000_000:.1f} MB"


def _section(lines: list[str], match) -> tuple[int, int] | None:  # type: ignore[no-untyped-def]
    """`match(sarlavha)` mos keladigan "## " bo'limi: (sarlavha indeksi, keyingi bo'lim indeksi)."""
    for i, s in enumerate(lines):
        if s.startswith("## ") and match(s.strip()):
            j = i + 1
            while j < len(lines) and not lines[j].startswith("## "):
                j += 1
            return i, j
    return None


def _is_version(version: str):  # type: ignore[no-untyped-def]
    return lambda s: s.startswith(f"## [{version}]")


def take_changes(changelog: Path, version: str) -> list[str]:
    """"## [Kelgusi]" bo'limi qatorlari; u bo'sh bo'lsa - shu versiyaning avvalgi yozuvi
    (build yiqilgandan keyin qayta urinishda o'zgarishlar yo'qolmasin)."""
    if not changelog.exists():
        return []
    lines = changelog.read_text(encoding="utf-8").splitlines()
    for match in (lambda s: s == UNRELEASED, _is_version(version)):
        sec = _section(lines, match)
        if not sec:
            continue
        body = [s for s in lines[sec[0] + 1:sec[1]] if not s.startswith("Tafsilotlar: ")]
        while body and not body[0].strip():
            body.pop(0)
        while body and not body[-1].strip():
            body.pop()
        if body:
            return body
    return []


def write_changelog(changelog: Path, version: str, date: str, body: list[str], built: bool) -> None:
    text = changelog.read_text(encoding="utf-8") if changelog.exists() else (
        "# O'zgarishlar tarixi\n\nEng yangisi tepada. Keyingi reliz o'zgarishlari "
        f"`{UNRELEASED}` bo'limiga yoziladi.\n\n{UNRELEASED}\n")
    lines = text.splitlines()
    head = f"## [{version}] — {date}" + ("" if built else " (binar yig'ilmadi)")
    entry = [head, "", *(body or ["- (o'zgarishlar ro'yxati kiritilmagan)"]), "",
             f"Tafsilotlar: [`{version}/NOTES.md`]({version}/NOTES.md)", ""]
    old = _section(lines, _is_version(version))  # qayta urinish: eski yozuv almashtiriladi
    if old:
        del lines[old[0]:old[1]]
    sec = _section(lines, lambda s: s == UNRELEASED)
    if not sec:
        lines += ["", UNRELEASED]
        sec = (len(lines) - 1, len(lines))
    lines[sec[0] + 1:sec[1]] = ["", *entry]
    changelog.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def app_notes(app_name: str, app_size: int, zip_name: str, zip_size: int) -> list[str]:
    """NOTES.md "## Binar" bo'limidagi `.app` va zip qatorlari."""
    return [
        f"- `{app_name}`: {mb(app_size)} - shu papkada, ikki marta bosib ochiladi "
        "(ad-hoc imzo, notarizatsiyasiz - faqat lokal sinov; `codesign --verify --deep --strict`: ok)",
        f"- `{zip_name}`: {mb(zip_size)} - o'sha `.app` ning `ditto` arxivi (boshqa Mac'ga ko'chirish uchun; "
        "ochish: `ditto -x -k <zip> /Applications`)",
        "- Xeshlar: `SHA256SUMS` (zip va `.app/Contents/MacOS/*`)",
        "- Birinchi ochishda Gatekeeper to'xtatsa: o'ng tugma -> Open.",
    ]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Lokal reliz: bump -> test -> build -> versiyalar/<V>/")
    ap.add_argument("version", help="yangi versiya (0.2.0) yoki patch|minor|major")
    ap.add_argument("--dry-run", action="store_true", help="faqat rejani ko'rsatish")
    ap.add_argument("--root", type=Path, default=ROOT, help=argparse.SUPPRESS)
    a = ap.parse_args(argv)
    root: Path = a.root

    current = collect(root)[str(PYPROJECT)] or "0.0.0"
    version = resolve(a.version, current)
    out_dir = root / VERSIONS_DIR / version
    if out_dir.exists():
        print(f"XATO: {out_dir.relative_to(root)} allaqachon bor - ustidan yozilmaydi.", file=sys.stderr)
        return 1
    if a.dry_run:
        arch = platform.machine() or "unknown"
        print(f"[dry-run] {current} -> {version}; make {' '.join(TEST_TARGETS)}; make build-local; "
              f"-> {out_dir.relative_to(root)}/{{{APP_BUNDLE.name}, "
              f"LahzaStudio-{version}-macos-{arch}.zip, NOTES.md, SHA256SUMS}}; "
              f"codesign --verify --deep --strict")
        return 0

    started = dt.datetime.now().astimezone()
    code, _, _ = run([sys.executable, "scripts/bump_version.py", version], root)
    if code:
        print("XATO: versiyani o'zgartirib bo'lmadi", file=sys.stderr)
        return 1

    tests: list[tuple[str, str]] = []
    for target in TEST_TARGETS:
        code, out, secs = run(["make", target], root)
        tests.append((target, f"{summarize(target, code, out)} ({secs:.0f} s)"))
        if code:
            print(f"\nXATO: `make {target}` yiqildi - reliz to'xtatildi (versiya {version} "
                  "manifestlarda qoldi).", file=sys.stderr)
            return 1

    code, out, build_secs = run(["make", "build-local"], root)
    app = root / APP_BUNDLE
    built = code == 0 and app.is_dir()
    build_error = ""
    if not built:
        tail = [s for s in out.splitlines() if s.strip()][-15:]
        build_error = "\n".join(tail)
        print(f"\nOGOHLANTIRISH: `make build-local` yiqildi (kod {code}) - binar yig'ilmadi.",
              file=sys.stderr)

    out_dir.mkdir(parents=True)
    arch = platform.machine() or "unknown"
    artifacts: list[Path] = []
    app_size = zip_size = 0
    app_copy = out_dir / APP_BUNDLE.name
    if built:
        app_size = du(app)
        copy_app(app, app_copy)
        zip_path = out_dir / f"LahzaStudio-{version}-macos-{arch}.zip"
        # ditto: kengaytirilgan atributlar, symlink va imzo saqlanadi.
        subprocess.run(["ditto", "-c", "-k", "--sequesterRsrc", "--keepParent", str(app), str(zip_path)],
                       check=True)
        zip_size = zip_path.stat().st_size
        artifacts.append(zip_path)
        sums = [(sha256(p), p.name) for p in artifacts] + app_sums(app_copy)
        (out_dir / "SHA256SUMS").write_text("".join(f"{h}  {n}\n" for h, n in sums), encoding="utf-8")

    commit = git(root, "rev-parse", "HEAD") or "-"
    subject = git(root, "log", "-1", "--format=%s")
    dirty = bool(git(root, "status", "--porcelain"))
    date = started.strftime("%Y-%m-%d")
    changelog = root / VERSIONS_DIR / "CHANGELOG.md"
    changes = take_changes(changelog, version)

    notes = [
        f"# Lahza Studio {version}",
        "",
        f"- **Sana:** {started.strftime('%Y-%m-%d %H:%M %Z')}",
        f"- **Git commit:** `{commit[:12]}` ({subject})"
        + (" + commit qilinmagan o'zgarishlar (working tree toza emas)" if dirty else ""),
        f"- **Platforma:** macOS {platform.mac_ver()[0] or '-'}, {arch}",
        f"- **Oldingi versiya:** {current}",
        "",
        "## O'zgarishlar",
        "",
        *(changes or ["- (o'zgarishlar ro'yxati kiritilmagan)"]),
        "",
        "## Testlar",
        "",
        "| Tekshiruv | Natija |",
        "|---|---|",
        *(f"| `make {t}` | {r} |" for t, r in tests),
        "",
        "## Binar",
        "",
    ]
    if built:
        notes += [
            f"- `make build-local`: muvaffaqiyatli ({build_secs / 60:.1f} daqiqa)",
            *app_notes(app_copy.name, app_size, artifacts[0].name, zip_size),
            "- Binar git'ga kirmaydi (`.gitignore`).",
        ]
    else:
        notes += [
            f"- **Yig'ilmadi:** `make build-local` kod {code} bilan yiqildi ({build_secs / 60:.1f} daqiqa).",
            "- Qayta urinish: muammoni tuzatib, bu papkani o'chiring va `make release-local` ni qayta ishga "
            "tushiring (versiya allaqachon o'rnatilgan).",
            "",
            "Oxirgi chiqish qatorlari:",
            "",
            "```",
            build_error or "-",
            "```",
        ]
    (out_dir / "NOTES.md").write_text("\n".join(notes).rstrip() + "\n", encoding="utf-8")
    write_changelog(changelog, version, date, changes, built)

    rel = out_dir.relative_to(root)
    print(f"\n{rel}/: NOTES.md" + (f", SHA256SUMS, {app_copy.name}, {artifacts[0].name}" if built else ""))
    if not built:
        print("Binar yig'ilmadi - NOTES.md ga qarang.", file=sys.stderr)
        return 2
    print(f"ok: Lahza Studio {version} -> {rel}/ (commit va teg qo'lda)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
