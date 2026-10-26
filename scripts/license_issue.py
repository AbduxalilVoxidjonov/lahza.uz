"""Oflayn litsenziya kalitlari (V1-3, ADR-0016, docs/litsenziya-kaliti.md).

Kalit juftini yaratish (bir marta; maxfiy kalit REPOZITORIYGA KIRMAYDI):

    python scripts/license_issue.py keygen --out ~/.lahza-keys [--embed]

`--embed` ochiq kalitni `engine/src/lahza_engine/licensing/keys.py` dagi PRODUCTION_PUBLIC_KEYS
ga qo'shadi (eskilari saqlanadi). Kalit chiqarish:

    python scripts/license_issue.py issue --key ~/.lahza-keys/license_signing.key \\
        --licensee "Mijoz MChJ" --edition pro --expires 2027-12-31 \\
        [--perpetual] [--max-devices 3] [--device ABCD-EFGH-IJKL-MNOP] \\
        [--min-version 1.0.0] [--max-version 1.99.99] [--id L-2026-0001] [--log issued.jsonl]

Tekshirish: `python scripts/license_issue.py verify "LAHZA-..." [--pub <base64>]`.
Joriy qurilma barmoq izi: `python scripts/license_issue.py device`.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys
import uuid
from datetime import UTC, date, datetime
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
    PublicFormat,
)

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "engine" / "src"))

from lahza_engine.licensing import keyformat as kf  # noqa: E402
from lahza_engine.licensing import keys  # noqa: E402

KEYS_PY = ROOT / "engine" / "src" / "lahza_engine" / "licensing" / "keys.py"
BLOCK_RE = re.compile(r"(# --- PRODUCTION KEYS BEGIN[^\n]*\n)(.*?)(# --- PRODUCTION KEYS END ---)", re.S)


def embed_public_key(pub: str, path: Path | None = None) -> None:
    path = path or KEYS_PY  # chaqiruv vaqtida (testlar KEYS_PY ni almashtiradi)
    src = path.read_text(encoding="utf-8")
    m = BLOCK_RE.search(src)
    existing = re.findall(r'"([A-Za-z0-9+/=]{44})"', m.group(2)) if m else []
    if pub in existing:
        return
    items = "".join(f'    "{k}",\n' for k in [*existing, pub])
    body = f"PRODUCTION_PUBLIC_KEYS: tuple[str, ...] = (\n{items})\n"
    new, n = BLOCK_RE.subn(lambda m: m.group(1) + body + m.group(3), src)
    if n != 1:
        raise SystemExit(f"{path}: PRODUCTION KEYS bloki topilmadi")
    path.write_text(new, encoding="utf-8")


def cmd_keygen(a: argparse.Namespace) -> None:
    a.out.mkdir(parents=True, exist_ok=True)
    priv_path = a.out / "license_signing.key"
    if priv_path.exists() and not a.force:
        raise SystemExit(f"{priv_path} allaqachon bor (--force bilan qayta yozing - eski kalitlar yaroqsizlanmaydi)")
    try:
        if priv_path.resolve().is_relative_to(ROOT.resolve()):
            print("OGOHLANTIRISH: maxfiy kalit repozitoriy ichida - `.gitignore` (*.key) "
                  "uni chetlaydi, lekin uni tashqarida saqlang.", file=sys.stderr)
    except OSError:
        pass
    key = Ed25519PrivateKey.generate()
    priv = base64.b64encode(key.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption())).decode()
    pub = base64.b64encode(key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)).decode()
    fd = os.open(priv_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(priv + "\n")
    (a.out / "license_signing.pub").write_text(pub + "\n", encoding="utf-8")
    print(f"maxfiy kalit: {priv_path}\nochiq kalit: {pub}")
    if a.embed:
        embed_public_key(pub)
        print(f"ochiq kalit qo'shildi: {KEYS_PY}")


def load_private(path: Path) -> bytes:
    raw = base64.b64decode(path.read_text(encoding="utf-8").strip(), validate=True)
    if len(raw) != 32:
        raise SystemExit("maxfiy kalit 32 bayt (base64) bo'lishi kerak")
    return raw


def build_payload(a: argparse.Namespace) -> kf.LicensePayload:
    if a.perpetual == bool(a.expires):
        raise SystemExit("--expires YYYY-MM-DD yoki --perpetual dan aynan bittasi kerak")
    return kf.LicensePayload(
        id=a.id or f"L-{datetime.now(UTC):%Y%m%d}-{uuid.uuid4().hex[:6].upper()}",
        licensee=a.licensee, edition=a.edition,
        issued=date.fromisoformat(a.issued) if a.issued else datetime.now(UTC).date(),
        expires=date.fromisoformat(a.expires) if a.expires else None,
        max_devices=a.max_devices, devices=a.device or [],
        min_version=a.min_version, max_version=a.max_version,
    )


def cmd_issue(a: argparse.Namespace) -> None:
    payload = build_payload(a)
    priv = load_private(a.key)
    text = kf.sign(payload, priv)
    pub = Ed25519PrivateKey.from_private_bytes(priv).public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    kf.verify(text, [pub])  # o'z-o'zini tekshirish
    if a.log:
        with a.log.open("a", encoding="utf-8") as f:  # jurnal: kalit matnisiz, faqat payload
            f.write(json.dumps(payload.model_dump(mode="json"), ensure_ascii=False) + "\n")
    print(text)


def cmd_verify(a: argparse.Namespace) -> None:
    pubs = [keys.decode_key(a.pub)] if a.pub else keys.trusted_keys()
    try:
        p = kf.verify(a.text, pubs)
    except kf.LicenseError as e:
        raise SystemExit(f"yaroqsiz ({e.code}): {e}") from e
    print(json.dumps(p.model_dump(mode="json"), ensure_ascii=False, indent=2))


def cmd_device(_: argparse.Namespace) -> None:
    from lahza_engine.licensing.device import device_fingerprint

    print(device_fingerprint())


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("keygen", help="Ed25519 kalit jufti")
    g.add_argument("--out", required=True, type=Path)
    g.add_argument("--embed", action="store_true", help="ochiq kalitni keys.py ga qo'shish")
    g.add_argument("--force", action="store_true")
    g.set_defaults(fn=cmd_keygen)
    i = sub.add_parser("issue", help="kalit chiqarish")
    i.add_argument("--key", required=True, type=Path, help="maxfiy kalit fayli (base64)")
    i.add_argument("--licensee", required=True)
    i.add_argument("--edition", required=True)
    i.add_argument("--expires")
    i.add_argument("--perpetual", action="store_true")
    i.add_argument("--issued", help="standart: bugun (UTC)")
    i.add_argument("--max-devices", type=int)
    i.add_argument("--device", action="append", help="qurilma barmoq izi (takrorlanadi)")
    i.add_argument("--min-version")
    i.add_argument("--max-version")
    i.add_argument("--id")
    i.add_argument("--log", type=Path, help="chiqarilgan kalitlar jurnali (JSONL)")
    i.set_defaults(fn=cmd_issue)
    v = sub.add_parser("verify", help="kalitni tekshirish")
    v.add_argument("text")
    v.add_argument("--pub", help="ochiq kalit (base64); standart - keys.py dagilar")
    v.set_defaults(fn=cmd_verify)
    d = sub.add_parser("device", help="joriy qurilma barmoq izi")
    d.set_defaults(fn=cmd_device)
    a = ap.parse_args(argv)
    a.fn(a)


if __name__ == "__main__":
    main()
