"""Katalogni tekshirib, Ed25519 bilan imzolaydi.

    python scripts/catalog_sign.py catalog/catalog.json --key ~/.lahza-keys/catalog_signing.key
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from lahza_engine.models.catalog import Catalog, sign


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("catalog", type=Path)
    ap.add_argument("--key", required=True, type=Path)
    a = ap.parse_args()
    cat = Catalog.model_validate_json(a.catalog.read_text(encoding="utf-8"))  # sxema tekshiruvi
    signed = sign(cat, a.key.read_text(encoding="utf-8").strip())
    a.catalog.write_text(
        json.dumps(signed.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    approved = sum(1 for e in signed.entries if e.status == "approved")
    print(f"imzolandi: {a.catalog} ({len(signed.entries)} yozuv, {approved} approved)")


if __name__ == "__main__":
    main()
