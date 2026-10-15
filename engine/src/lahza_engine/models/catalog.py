"""Model katalogi: imzolangan JSON, kompyuterga mos to'plamni avtomatik tanlash (TZ 13-bo'lim, ADR-0002).

* Imzo: Ed25519, kanonik JSON ("signature" maydonisiz, kalitlar saralangan, bo'shliqsiz).
* Avto-tanlov faqat `status == "approved"` (R0 baholashidan o'tgan, sha256 ma'lum) yozuvlardan.
  "candidate" yozuvlar - hali baholanmagan; ular o'rnatilmaydi.
"""

from __future__ import annotations

import base64
import json
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from lahza_engine.models.hardware import HardwareProfile, Tier


class Task(StrEnum):
    ASR = "asr"
    ALIGN = "align"
    VAD = "vad"
    DIARIZATION = "diarization"
    VISION = "vision"  # yuz aniqlash + ASD
    LLM = "llm"


MANDATORY_TASKS = (Task.ASR, Task.VAD, Task.ALIGN, Task.DIARIZATION, Task.VISION)
"""ASR to'plamisiz dastur ishlamaydi; LLM yo'q bo'lsa - Lite rejim (TZ 7, 13-bo'lim)."""


class ModelFile(BaseModel):
    path: str = Field(description="Model papkasi ichidagi nisbiy yo'l")
    urls: list[str] = Field(default_factory=list, description="Asosiy + zaxira manzillar")
    sha256: str | None = None
    size_bytes: int | None = None


class CatalogEntry(BaseModel):
    id: str
    task: Task
    name: str
    version: str
    backend: Literal["whisper.cpp", "faster-whisper", "nemo-onnx", "llama.cpp", "onnxruntime",
                     "pyannote", "silero", "ctc-aligner"]
    files: list[ModelFile]
    platforms: list[Literal["darwin-arm64", "win32-x86_64", "linux-x86_64"]]
    tiers: list[Tier]
    min_ram_gb: float | None = None
    min_vram_gb: float | None = None
    license: str
    license_url: str | None = None
    source_url: str
    attribution: str | None = None
    status: Literal["candidate", "approved", "deprecated"] = "candidate"
    eval: dict[str, float] | None = None
    notes: str | None = None

    @model_validator(mode="after")
    def _approved_needs_hashes(self) -> CatalogEntry:
        if self.status == "approved":
            for f in self.files:
                if not f.sha256 or not f.size_bytes or not f.urls:
                    raise ValueError(f"{self.id}: approved yozuvda sha256, hajm va URL majburiy")
        return self

    @property
    def size_bytes(self) -> int | None:
        sizes = [f.size_bytes for f in self.files]
        return None if any(s is None for s in sizes) else sum(s for s in sizes if s)


class Catalog(BaseModel):
    schema_version: int = 1
    catalog_version: str
    entries: list[CatalogEntry]
    signature: str | None = None

    def canonical_bytes(self) -> bytes:
        data = self.model_dump(mode="json", exclude={"signature"})
        return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


class SignatureError(RuntimeError):
    pass


def verify(catalog: Catalog, public_key_b64: str) -> None:
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

    if not catalog.signature:
        raise SignatureError("katalog imzolanmagan")
    key = Ed25519PublicKey.from_public_bytes(base64.b64decode(public_key_b64))
    try:
        key.verify(base64.b64decode(catalog.signature), catalog.canonical_bytes())
    except InvalidSignature as e:
        raise SignatureError("katalog imzosi yaroqsiz") from e


def sign(catalog: Catalog, private_key_b64: str) -> Catalog:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    key = Ed25519PrivateKey.from_private_bytes(base64.b64decode(private_key_b64))
    sig = key.sign(catalog.canonical_bytes())
    return catalog.model_copy(update={"signature": base64.b64encode(sig).decode()})


def platform_key(hw: HardwareProfile) -> str:
    return f"{hw.os}-{hw.arch}"


class Compat(StrEnum):
    RECOMMENDED = "recommended"  # "Tavsiya etiladi"
    SLOW = "slow"  # "Ishlaydi, lekin sekin"
    INCOMPATIBLE = "incompatible"  # "Mos emas"


class BundleItem(BaseModel):
    task: Task
    entry: CatalogEntry | None
    compat: Compat | None = None
    reason: str = ""
    mandatory: bool = False


_TIER_ORDER = [Tier.LITE, Tier.STANDARD, Tier.PRO]


def compatibility(entry: CatalogEntry, hw: HardwareProfile, tier: Tier) -> tuple[Compat, str]:
    if platform_key(hw) not in entry.platforms:
        return Compat.INCOMPATIBLE, f"{platform_key(hw)} platformasi qo'llanmaydi"
    if entry.min_ram_gb and hw.ram_gb < entry.min_ram_gb:
        return Compat.INCOMPATIBLE, f"{entry.min_ram_gb:.0f} GB RAM kerak, sizda {hw.ram_gb:.0f} GB"
    if entry.min_vram_gb and not hw.apple_silicon:
        g = hw.best_gpu()
        vram = g.vram_gb if g else None
        if vram is None or vram < entry.min_vram_gb:
            have = f"{vram:.0f} GB" if vram is not None else "yo'q"
            return Compat.INCOMPATIBLE, f"{entry.min_vram_gb:.0f} GB VRAM kerak, sizda {have}"
    size = entry.size_bytes
    if size and hw.free_disk_gb * 1024**3 < size * 1.1:
        return Compat.INCOMPATIBLE, "diskda joy yetarli emas"
    if tier in entry.tiers:
        return Compat.RECOMMENDED, "darajangizga mos"
    lowest = min((_TIER_ORDER.index(t) for t in entry.tiers if t in _TIER_ORDER), default=0)
    if tier in _TIER_ORDER and _TIER_ORDER.index(tier) < lowest:
        return Compat.SLOW, "ishlaydi, lekin sekin bo'lishi mumkin"
    return Compat.RECOMMENDED, "darajangizdan past model - tez ishlaydi"


def select_bundle(catalog: Catalog, hw: HardwareProfile, tier: Tier) -> list[BundleItem]:
    """Har vazifa uchun: darajaga mos approved yozuvlar ichidan R0 eval bali eng yuqorisi."""
    items: list[BundleItem] = []
    for task in Task:
        mandatory = task in MANDATORY_TASKS
        candidates = [e for e in catalog.entries if e.task == task and e.status == "approved"]
        ranked: list[tuple[int, float, CatalogEntry, Compat, str]] = []
        for e in candidates:
            compat, why = compatibility(e, hw, tier)
            if compat is Compat.INCOMPATIBLE:
                continue
            rank = 0 if compat is Compat.RECOMMENDED and tier in e.tiers else 1
            score = (e.eval or {}).get("score", 0.0)
            ranked.append((rank, -score, e, compat, why))
        if ranked:
            ranked.sort(key=lambda r: (r[0], r[1]))
            _, _, e, compat, why = ranked[0]
            items.append(BundleItem(task=task, entry=e, compat=compat, reason=why, mandatory=mandatory))
        else:
            why = "katalogda tasdiqlangan mos model yo'q"
            if task is Task.LLM:
                why += " - highlight Lite rejimda ishlaydi"
            items.append(BundleItem(task=task, entry=None, reason=why, mandatory=mandatory))
    return items


def load_catalog(path: str) -> Catalog:
    with open(path, encoding="utf-8") as f:
        return Catalog.model_validate_json(f.read())
