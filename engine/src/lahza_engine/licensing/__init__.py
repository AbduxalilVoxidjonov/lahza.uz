"""Oflayn litsenziya kaliti (V1-3, TZ 19-bo'lim, ADR-0016).

Standart holatda O'CHIQ (`Settings.licensing_enabled = False`): ilova bepul ishlaydi, hech narsa
bloklanmaydi. Format va chiqarish tartibi: docs/litsenziya-kaliti.md.
"""

from lahza_engine.licensing.keyformat import LicenseError, LicensePayload, sign, verify
from lahza_engine.licensing.manager import KeyValueStore, LicenseManager, MemoryStore

__all__ = ["KeyValueStore", "LicenseError", "LicenseManager", "LicensePayload", "MemoryStore",
           "sign", "verify"]
