"""Katalog imzosi uchun Ed25519 kalitlar juftligi.

    python scripts/catalog_keygen.py --out ~/.lahza-keys

Maxfiy kalit repozitoriyga KIRMAYDI (CI sirida yoki xavfsiz joyda saqlanadi).
Ochiq kalit build vaqtida LAHZA_CATALOG_PUBKEY sifatida beriladi (docs/06).
"""

from __future__ import annotations

import argparse
import base64
import os
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
    PublicFormat,
)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True, type=Path)
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    key = Ed25519PrivateKey.generate()
    priv = base64.b64encode(key.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption())).decode()
    pub = base64.b64encode(key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)).decode()
    priv_path = a.out / "catalog_signing.key"
    priv_path.write_text(priv + "\n", encoding="utf-8")
    os.chmod(priv_path, 0o600)
    (a.out / "catalog_signing.pub").write_text(pub + "\n", encoding="utf-8")
    print(f"maxfiy kalit: {priv_path}\nochiq kalit (LAHZA_CATALOG_PUBKEY): {pub}")


if __name__ == "__main__":
    main()
