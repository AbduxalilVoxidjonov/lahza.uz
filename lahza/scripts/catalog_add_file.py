"""Katalog yozuviga yuklangan faylning sha256 va hajmini yozadi (qo'lda kiritish xatosiz).

    python scripts/catalog_add_file.py asr-piyola-v2 ./model.onnx --url https://.../model.onnx [--url zaxira]

Yozuvdagi `files[].path` fayl nomi bilan moslashtiriladi. Imzo o'chiriladi - keyin catalog_sign.py.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        while b := f.read(8 * 1024 * 1024):
            h.update(b)
    return h.hexdigest()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("entry_id")
    ap.add_argument("file", type=Path)
    ap.add_argument("--url", action="append", required=True)
    ap.add_argument("--catalog", type=Path, default=ROOT / "catalog" / "catalog.json")
    a = ap.parse_args()

    data = json.loads(a.catalog.read_text(encoding="utf-8"))
    entry = next((e for e in data["entries"] if e["id"] == a.entry_id), None)
    if entry is None:
        raise SystemExit(f"yozuv topilmadi: {a.entry_id}")
    target = next((f for f in entry["files"] if Path(f["path"]).name == a.file.name), None)
    if target is None:
        raise SystemExit(f"{a.entry_id} ichida {a.file.name} nomli fayl yo'q")
    target["sha256"] = sha256(a.file)
    target["size_bytes"] = a.file.stat().st_size
    target["urls"] = a.url
    data["signature"] = None
    a.catalog.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{a.entry_id}/{target['path']}: {target['size_bytes']} bayt, sha256 {target['sha256'][:16]}…")


if __name__ == "__main__":
    main()
