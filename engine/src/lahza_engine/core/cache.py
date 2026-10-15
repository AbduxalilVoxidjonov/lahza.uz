"""Bosqich natijasi kaliti (TZ 4-bo'lim): manba_hash + bosqich_versiyasi + model_id + parametr_hash.

Yuqori oqimdagi bosqichlar kalitlari ham qo'shiladi: biror parametr o'zgarsa, faqat undan
keyingi bosqichlar qayta hisoblanadi.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any


def param_hash(params: dict[str, Any]) -> str:
    blob = json.dumps(params, sort_keys=True, separators=(",", ":"), default=str, ensure_ascii=False)
    return hashlib.sha256(blob.encode()).hexdigest()[:16]


def stage_key(
    media_hash: str,
    stage: str,
    version: int,
    model_id: str | None,
    params: dict[str, Any],
    upstream: list[str] | None = None,
) -> str:
    parts = [media_hash, stage, str(version), model_id or "-", param_hash(params), *(upstream or [])]
    return hashlib.sha256("|".join(parts).encode()).hexdigest()
