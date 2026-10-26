"""Litsenziya holati: kalitni tekshirish, saqlash, soat orqaga surilishiga qarshi himoya.

Bayroq (`Settings.licensing_enabled`) o'chiq bo'lsa - holat `disabled`, `allows()` doim True:
ilova hozirgidek bepul ishlaydi va hech narsa bloklanmaydi. Tarmoq ishlatilmaydi (NFR-01).

Soat himoyasi (oddiy): ko'rilgan eng katta vaqt (`last_seen`) saqlanadi. Muddatli kalitda joriy
vaqt `last_seen` dan `CLOCK_TOLERANCE` dan ko'proq orqada bo'lsa - holat `clock_rollback`.
Abadiy kalitga soat ta'sir qilmaydi.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from typing import Any, Protocol

from lahza_engine.licensing import keyformat as kf

STORE_KEY = "license"
CLOCK_KEY = "license_clock"
CLOCK_TOLERANCE = timedelta(hours=48)

# Holatlar (UI tarjimasi shu kodlar bo'yicha)
DISABLED = "disabled"  # bayroq o'chiq - hech narsa tekshirilmaydi
NOT_CONFIGURED = "not_configured"  # ochiq kalit build'ga kiritilmagan - bloklamaydi
UNLICENSED = "unlicensed"
VALID = "valid"
EXPIRED = "expired"
NOT_YET_VALID = "not_yet_valid"
WRONG_VERSION = "wrong_version"
WRONG_DEVICE = "wrong_device"
CLOCK_ROLLBACK = "clock_rollback"
INVALID = "invalid"  # saqlangan kalit imzosi/formati buzilgan

NON_BLOCKING = {DISABLED, NOT_CONFIGURED, VALID}


class KeyValueStore(Protocol):
    def get(self, key: str) -> dict[str, Any] | None: ...
    def set(self, key: str, value: dict[str, Any]) -> None: ...
    def delete(self, key: str) -> None: ...


class MemoryStore:
    def __init__(self) -> None:
        self.data: dict[str, dict[str, Any]] = {}

    def get(self, key: str) -> dict[str, Any] | None:
        return self.data.get(key)

    def set(self, key: str, value: dict[str, Any]) -> None:
        self.data[key] = value

    def delete(self, key: str) -> None:
        self.data.pop(key, None)


def _utcnow() -> datetime:
    return datetime.now(UTC)


class LicenseManager:
    def __init__(self, store: KeyValueStore, *, enabled: bool, public_keys: list[bytes],
                 app_version: str, device_id: Callable[[], str],
                 now: Callable[[], datetime] = _utcnow) -> None:
        self.store = store
        self.enabled = enabled
        self.public_keys = public_keys
        self.app_version = app_version
        self.device_id = device_id
        self.now = now

    # ---- soat -------------------------------------------------------------
    def _observe_clock(self) -> tuple[datetime, bool]:
        """(joriy vaqt, orqaga surilganmi). `last_seen` faqat oldinga siljiydi."""
        now = self.now()
        rec = self.store.get(CLOCK_KEY) or {}
        last = None
        if rec.get("last_seen"):
            try:
                last = datetime.fromisoformat(rec["last_seen"])
            except ValueError:
                last = None
        rolled_back = last is not None and now + CLOCK_TOLERANCE < last
        if last is None or now > last:
            self.store.set(CLOCK_KEY, {"last_seen": now.isoformat()})
        return now, rolled_back

    # ---- baholash ---------------------------------------------------------
    def evaluate(self, payload: kf.LicensePayload, now: datetime, rolled_back: bool = False) -> str:
        today: date = now.date()
        if payload.devices and kf.normalize_device(self.device_id()) not in payload.devices:
            return WRONG_DEVICE
        if not kf.version_in_range(self.app_version, payload.min_version, payload.max_version):
            return WRONG_VERSION
        if payload.expires is not None:
            if rolled_back:
                return CLOCK_ROLLBACK
            if today > payload.expires:
                return EXPIRED
        if payload.issued > (now + CLOCK_TOLERANCE).date():
            return NOT_YET_VALID
        return VALID

    def _public(self, payload: kf.LicensePayload) -> dict[str, Any]:
        return {
            "id": payload.id,
            "licensee": payload.licensee,
            "edition": payload.edition,
            "issued": payload.issued.isoformat(),
            "expires": payload.expires.isoformat() if payload.expires else None,
            "perpetual": payload.expires is None,
            "max_devices": payload.max_devices,
            "device_locked": bool(payload.devices),
            "min_version": payload.min_version,
            "max_version": payload.max_version,
        }

    def status(self) -> dict[str, Any]:
        base: dict[str, Any] = {"enabled": self.enabled, "device_id": None, "license": None,
                                "reason": None, "app_version": self.app_version}
        if not self.enabled:
            return {**base, "state": DISABLED}
        base["device_id"] = self.device_id()
        if not self.public_keys:
            return {**base, "state": NOT_CONFIGURED}
        now, rolled_back = self._observe_clock()
        rec = self.store.get(STORE_KEY)
        if not rec or not rec.get("key"):
            return {**base, "state": UNLICENSED}
        try:
            payload = kf.verify(rec["key"], self.public_keys)
        except kf.LicenseError as e:
            return {**base, "state": INVALID, "reason": e.code}
        return {**base, "state": self.evaluate(payload, now, rolled_back),
                "license": self._public(payload), "activated_at": rec.get("activated_at")}

    def allows(self) -> bool:
        """Pullik imkoniyatga ruxsat. Bayroq o'chiq bo'lsa - doim True (hech narsa bloklanmaydi)."""
        if not self.enabled:
            return True
        return self.status()["state"] in NON_BLOCKING

    # ---- amallar ----------------------------------------------------------
    def activate(self, text: str) -> dict[str, Any]:
        """Kalitni tekshirib saqlaydi. Yaroqsiz bo'lsa `LicenseError` (saqlanmaydi)."""
        if not self.enabled:
            raise kf.LicenseError(DISABLED, "litsenziyalash o'chiq")
        payload = kf.verify(text, self.public_keys)
        now, rolled_back = self._observe_clock()
        state = self.evaluate(payload, now, rolled_back)
        if state != VALID:
            raise kf.LicenseError(state, f"kalit bu qurilmada yaroqsiz: {state}")
        canonical = kf.encode(kf.decode_text(text))  # bir xil ko'rinishda saqlanadi
        self.store.set(STORE_KEY, {"key": canonical, "activated_at": now.isoformat()})
        return self.status()

    def deactivate(self) -> dict[str, Any]:
        """Saqlangan kalitni o'chiradi (`last_seen` saqlanib qoladi - soat himoyasi uchun)."""
        self.store.delete(STORE_KEY)
        return self.status()
