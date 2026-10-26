"""Litsenziya imzosini tekshiruvchi ochiq kalitlar (Ed25519, raw 32 bayt, base64).

* `PRODUCTION_PUBLIC_KEYS` - relizda tekshiriladigan kalitlar. Ro'yxat bo'sh bo'lsa, litsenziyalash
  "sozlanmagan" holatda qoladi va hech narsani bloklamaydi (docs/litsenziya-kaliti.md).
  Kalit `python scripts/license_issue.py keygen --out ~/.lahza-keys --embed` bilan qo'shiladi.
  Kalitni almashtirishda eskisini ro'yxatda qoldiring - avval chiqarilgan kalitlar ishlashda davom etadi.
* `TEST_PUBLIC_KEY` - faqat testlar uchun. Uning maxfiy kaliti ochiq urug'dan olinadi
  (`testing_private_key()`), shuning uchun u HECH QACHON `trusted_keys()` ga avtomatik qo'shilmaydi.
"""

from __future__ import annotations

import base64
import hashlib

# --- PRODUCTION KEYS BEGIN (scripts/license_issue.py keygen --embed shu blokni yangilaydi) ---
PRODUCTION_PUBLIC_KEYS: tuple[str, ...] = ()
# --- PRODUCTION KEYS END ---

TEST_KEY_SEED = b"lahza-license-TEST-ONLY-seed/1"
TEST_PUBLIC_KEY = "zb+UZ7i6lC0hPNUmqdWxWOtUMhTRjF0x9uHiF1H31XM="


def decode_key(b64: str) -> bytes:
    raw = base64.b64decode(b64.strip(), validate=True)
    if len(raw) != 32:
        raise ValueError("Ed25519 kaliti 32 bayt bo'lishi kerak")
    return raw


def trusted_keys() -> list[bytes]:
    """Ilova ishonadigan ochiq kalitlar (faqat production; test kaliti bu yerga kirmaydi)."""
    return [decode_key(k) for k in PRODUCTION_PUBLIC_KEYS]


def testing_private_key() -> bytes:
    """Test maxfiy kaliti (32 bayt urug'). Faqat testlar va hujjatdagi namunalar uchun."""
    return hashlib.sha256(TEST_KEY_SEED).digest()
