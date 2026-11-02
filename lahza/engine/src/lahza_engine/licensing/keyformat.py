"""Litsenziya kaliti formati (V1-3, TZ 19-bo'lim): imzolangan payload + Ed25519 imzo.

Ikkilik ko'rinish::

    raw   = 0x01 || zlib(JSON payload)          # 0x01 - format versiyasi
    imzo  = Ed25519(maxfiy_kalit, DOMAIN || raw) # 64 bayt
    blob  = raw || imzo

Matn ko'rinishi: `LAHZA-` + base32(blob) (RFC 4648, `=` siz), 5 belgilik guruhlar, `-` bilan.
Base32 katta-kichik harfga sezgir emas; kiritishda bo'shliq/qator ko'chishi/`-` e'tiborsiz qoldiriladi,
o'xshash belgilar tuzatiladi (0->O, 1->I, 8->B). Imzo payload ochilishidan OLDIN tekshiriladi.
"""

from __future__ import annotations

import base64
import json
import re
import zlib
from datetime import date

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from pydantic import BaseModel, Field, ValidationError, field_validator

PREFIX = "LAHZA-"
FORMAT_VERSION = 1
DOMAIN = b"lahza-license/1\x00"
SIG_LEN = 64
MAX_PAYLOAD = 4096  # ochilgan JSON chegarasi (bayt)
GROUP = 5
_VERSION_RE = re.compile(r"^\d+(\.\d+){0,2}$")


class LicenseError(ValueError):
    """Kalit yaroqsiz. `code` - UI tarjimasi uchun barqaror kod."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class LicensePayload(BaseModel):
    v: int = FORMAT_VERSION
    id: str = Field(min_length=1, max_length=64)  # litsenziya raqami (chiqaruvchi jurnali uchun)
    licensee: str = Field(min_length=1, max_length=200)
    edition: str = Field(min_length=1, max_length=40)  # nashr/tarif (masalan "pro")
    issued: date
    expires: date | None = None  # None - abadiy
    max_devices: int | None = Field(default=None, ge=1)  # ma'lumot uchun (oflayn sanab bo'lmaydi)
    devices: list[str] = Field(default_factory=list)  # bo'sh emas bo'lsa - faqat shu qurilmalar
    min_version: str | None = None  # kiritilgan (inclusive)
    max_version: str | None = None  # kiritilgan (inclusive)

    @field_validator("min_version", "max_version")
    @classmethod
    def _ver(cls, v: str | None) -> str | None:
        if v is not None and not _VERSION_RE.match(v):
            raise ValueError("versiya X.Y.Z ko'rinishida bo'lishi kerak")
        return v

    @field_validator("devices")
    @classmethod
    def _devices(cls, v: list[str]) -> list[str]:
        return [normalize_device(d) for d in v]


def normalize_device(d: str) -> str:
    return re.sub(r"[^0-9A-Z]", "", d.upper())


def parse_version(v: str) -> tuple[int, int, int]:
    """'1.2.3', '1.2', '0.2.0-beta' -> (1, 2, 3); qo'shimcha (-beta, +build) e'tiborsiz."""
    core = re.split(r"[-+]", v.strip(), maxsplit=1)[0]
    parts = [int(p) if p.isdigit() else 0 for p in core.split(".")[:3]]
    while len(parts) < 3:
        parts.append(0)
    return parts[0], parts[1], parts[2]


def version_in_range(version: str, lo: str | None, hi: str | None) -> bool:
    cur = parse_version(version)
    if lo is not None and cur < parse_version(lo):
        return False
    return not (hi is not None and cur > parse_version(hi))


def _canonical(payload: LicensePayload) -> bytes:
    data = payload.model_dump(mode="json")
    return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def _group(s: str) -> str:
    return "-".join(s[i:i + GROUP] for i in range(0, len(s), GROUP))


def encode(blob: bytes) -> str:
    return PREFIX + _group(base64.b32encode(blob).decode().rstrip("="))


def decode_text(text: str) -> bytes:
    s = re.sub(r"[\s-]+", "", text).upper()
    if s.startswith(PREFIX[:-1]):  # "LAHZA" (blob 0x01 bilan boshlanadi -> base32 "AE"/"AF")
        s = s[len(PREFIX) - 1:]
    s = s.translate(str.maketrans("018", "OIB"))
    if not s or not re.fullmatch(r"[A-Z2-7]+", s):
        raise LicenseError("malformed", "kalit formati noto'g'ri")
    try:
        return base64.b32decode(s + "=" * (-len(s) % 8))
    except ValueError as e:  # binascii.Error ham ValueError
        raise LicenseError("malformed", "kalit formati noto'g'ri") from e


def sign(payload: LicensePayload, private_key: bytes) -> str:
    """Kalit chiqarish (faqat `scripts/license_issue.py` va testlar)."""
    raw = bytes([FORMAT_VERSION]) + zlib.compress(_canonical(payload), 9)
    sig = Ed25519PrivateKey.from_private_bytes(private_key).sign(DOMAIN + raw)
    return encode(raw + sig)


def verify(text: str, public_keys: list[bytes]) -> LicensePayload:
    """Imzo va tuzilmani tekshiradi (muddat/versiya/qurilma - `manager` da)."""
    blob = decode_text(text)
    if len(blob) <= SIG_LEN + 1:
        raise LicenseError("malformed", "kalit juda qisqa")
    raw, sig = blob[:-SIG_LEN], blob[-SIG_LEN:]
    if raw[0] != FORMAT_VERSION:
        raise LicenseError("unsupported", "kalit formati versiyasi qo'llanmaydi")
    if not public_keys:
        raise LicenseError("not_configured", "ochiq kalit sozlanmagan")
    for pk in public_keys:
        try:
            Ed25519PublicKey.from_public_bytes(pk).verify(sig, DOMAIN + raw)
            break
        except InvalidSignature:
            continue
    else:
        raise LicenseError("bad_signature", "imzo noto'g'ri")
    try:
        d = zlib.decompressobj()
        data = d.decompress(raw[1:], MAX_PAYLOAD)
        if d.unconsumed_tail:
            raise LicenseError("malformed", "payload juda katta")
        payload = LicensePayload.model_validate_json(data)
    except (zlib.error, ValidationError, UnicodeDecodeError) as e:
        raise LicenseError("malformed", "payload o'qilmadi") from e
    if payload.v != FORMAT_VERSION:
        raise LicenseError("unsupported", "payload versiyasi qo'llanmaydi")
    return payload
