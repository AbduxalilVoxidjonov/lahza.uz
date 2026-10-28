"""V1-3: oflayn litsenziya kaliti (Ed25519) - format, tekshiruv, holat, API, bayroq o'chiqligi."""

from __future__ import annotations

import socket
import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest
from _api_helpers import make_client
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from lahza_engine.api import routes_license
from lahza_engine.config import Settings
from lahza_engine.licensing import keyformat as kf
from lahza_engine.licensing import keys
from lahza_engine.licensing import manager as lm
from lahza_engine.licensing.device import fingerprint_of

PRIV = keys.testing_private_key()
PUB = keys.decode_key(keys.TEST_PUBLIC_KEY)
DEVICE = "ABCD-EFGH-IJKL-MNOP"
NOW = datetime(2026, 10, 26, 12, 0, tzinfo=UTC)


def payload(**kw) -> kf.LicensePayload:
    base = {"id": "L-0001", "licensee": "Test MChJ", "edition": "pro", "issued": date(2026, 10, 1)}
    return kf.LicensePayload(**{**base, **kw})


def make_key(**kw) -> str:
    return kf.sign(payload(**kw), PRIV)


class Clock:
    def __init__(self, t: datetime) -> None:
        self.t = t

    def __call__(self) -> datetime:
        return self.t


def mgr(enabled: bool = True, version: str = "0.2.3", clock: Clock | None = None,
        store: lm.MemoryStore | None = None, public_keys: list[bytes] | None = None) -> lm.LicenseManager:
    return lm.LicenseManager(store or lm.MemoryStore(), enabled=enabled,
                             public_keys=[PUB] if public_keys is None else public_keys,
                             app_version=version, device_id=lambda: DEVICE, now=clock or Clock(NOW))


# ---- format --------------------------------------------------------------------------------------
def test_test_key_pair_matches_constant() -> None:
    pub = Ed25519PrivateKey.from_private_bytes(PRIV).public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    assert pub == PUB
    assert PUB not in keys.trusted_keys()  # test kaliti hech qachon avtomatik ishonchli emas


def test_roundtrip_and_text_format() -> None:
    text = make_key(expires=date(2027, 10, 1), max_devices=2, min_version="0.2", max_version="1.99.99")
    assert text.startswith("LAHZA-")
    groups = text.removeprefix("LAHZA-").split("-")
    assert all(1 <= len(g) <= 5 for g in groups) and all(len(g) == 5 for g in groups[:-1])
    p = kf.verify(text, [PUB])
    assert p.licensee == "Test MChJ" and p.expires == date(2027, 10, 1) and p.max_devices == 2


def test_input_is_forgiving() -> None:
    text = make_key()
    low = text.lower()
    messy = "  " + low[:40].replace("-", " - ") + "\n" + low[40:].replace("-", "") + " "
    assert kf.verify(messy, [PUB]).id == "L-0001"
    # 0/1/8 base32'da yo'q - O/I/B ga tuzatiladi
    body = text.removeprefix("LAHZA-")
    swapped = body.replace("O", "0").replace("I", "1").replace("B", "8")
    assert kf.verify(swapped, [PUB]).id == "L-0001"
    assert kf.verify("LAHZA" + body.replace("-", ""), [PUB]).id == "L-0001"


def test_tampered_signature_and_payload_rejected() -> None:
    blob = kf.decode_text(make_key())
    bad_sig = blob[:-1] + bytes([blob[-1] ^ 1])
    with pytest.raises(kf.LicenseError) as e:
        kf.verify(kf.encode(bad_sig), [PUB])
    assert e.value.code == "bad_signature"
    bad_payload = blob[:5] + bytes([blob[5] ^ 1]) + blob[6:]
    with pytest.raises(kf.LicenseError) as e:
        kf.verify(kf.encode(bad_payload), [PUB])
    assert e.value.code == "bad_signature"


def test_other_key_rejected_and_rotation_supported() -> None:
    other = Ed25519PrivateKey.generate()
    other_pub = other.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    text = make_key()
    with pytest.raises(kf.LicenseError) as e:
        kf.verify(text, [other_pub])
    assert e.value.code == "bad_signature"
    assert kf.verify(text, [other_pub, PUB]).id == "L-0001"  # bir nechta kalit (almashtirish)


@pytest.mark.parametrize("text,code", [("", "malformed"), ("LAHZA-!!!", "malformed"),
                                       ("LAHZA-ABCDE", "malformed")])
def test_malformed(text: str, code: str) -> None:
    with pytest.raises(kf.LicenseError) as e:
        kf.verify(text, [PUB])
    assert e.value.code == code


def test_no_public_keys() -> None:
    with pytest.raises(kf.LicenseError) as e:
        kf.verify(make_key(), [])
    assert e.value.code == "not_configured"


def test_version_helpers() -> None:
    assert kf.parse_version("0.2.3-beta+1") == (0, 2, 3)
    assert kf.parse_version("1") == (1, 0, 0)
    assert kf.version_in_range("0.2.3", "0.2", "0.2.99")
    assert not kf.version_in_range("1.0.0", None, "0.9.9")
    assert not kf.version_in_range("0.1.9", "0.2.0", None)
    with pytest.raises(ValueError):
        payload(max_version="v1")


def test_device_fingerprint_shape() -> None:
    fp = fingerprint_of("machine-123")
    assert fp == fingerprint_of("machine-123") != fingerprint_of("machine-124")
    assert len(fp) == 19 and fp.count("-") == 3


# ---- holat ---------------------------------------------------------------------------------------
def test_valid_key_activation_and_status() -> None:
    m = mgr()
    assert m.status()["state"] == lm.UNLICENSED and not m.allows()
    st = m.activate(make_key(expires=date(2027, 1, 1), devices=[DEVICE.lower()]))
    assert st["state"] == lm.VALID and m.allows()
    assert st["license"]["licensee"] == "Test MChJ" and st["license"]["device_locked"] is True
    assert st["device_id"] == DEVICE


def test_perpetual_key() -> None:
    m = mgr()
    assert m.activate(make_key())["license"]["perpetual"] is True


def test_expired_key() -> None:
    m = mgr()
    with pytest.raises(kf.LicenseError) as e:
        m.activate(make_key(expires=date(2026, 10, 25)))
    assert e.value.code == lm.EXPIRED
    assert m.status()["state"] == lm.UNLICENSED  # yaroqsiz kalit saqlanmaydi
    # Faollashtirilgandan keyin muddat o'tsa
    clock = Clock(NOW)
    m = mgr(clock=clock)
    m.activate(make_key(expires=date(2026, 10, 26)))  # oxirgi kun ham yaroqli
    clock.t = NOW + timedelta(days=1)
    assert m.status()["state"] == lm.EXPIRED and not m.allows()


def test_wrong_version() -> None:
    with pytest.raises(kf.LicenseError) as e:
        mgr(version="2.0.0").activate(make_key(max_version="1.99.99"))
    assert e.value.code == lm.WRONG_VERSION
    with pytest.raises(kf.LicenseError) as e:
        mgr(version="0.1.0").activate(make_key(min_version="0.2.0"))
    assert e.value.code == lm.WRONG_VERSION
    # Ilova yangilangach saqlangan kalit versiyaga mos kelmay qoladi
    store = lm.MemoryStore()
    mgr(store=store).activate(make_key(max_version="0.2.99"))
    assert mgr(store=store, version="0.3.0").status()["state"] == lm.WRONG_VERSION


def test_wrong_device() -> None:
    with pytest.raises(kf.LicenseError) as e:
        mgr().activate(make_key(devices=["ZZZZ-ZZZZ-ZZZZ-ZZZZ"]))
    assert e.value.code == lm.WRONG_DEVICE


def test_not_yet_valid() -> None:
    with pytest.raises(kf.LicenseError) as e:
        mgr().activate(make_key(issued=date(2026, 12, 1)))
    assert e.value.code == lm.NOT_YET_VALID


def test_clock_rollback_guard() -> None:
    clock = Clock(NOW)
    m = mgr(clock=clock)
    m.activate(make_key(expires=date(2027, 1, 1)))
    clock.t = NOW + timedelta(days=30)
    assert m.status()["state"] == lm.VALID  # last_seen oldinga siljiydi
    clock.t = NOW + timedelta(days=29)  # tolerans ichida - normal
    assert m.status()["state"] == lm.VALID
    clock.t = NOW  # 30 kun orqaga
    assert m.status()["state"] == lm.CLOCK_ROLLBACK and not m.allows()
    clock.t = NOW + timedelta(days=31)
    assert m.status()["state"] == lm.VALID


def test_clock_rollback_does_not_affect_perpetual() -> None:
    clock = Clock(NOW + timedelta(days=100))
    m = mgr(clock=clock)
    m.activate(make_key())
    clock.t = NOW
    assert m.status()["state"] == lm.VALID


def test_stored_key_tampered_becomes_invalid() -> None:
    store = lm.MemoryStore()
    m = mgr(store=store)
    m.activate(make_key())
    rec = store.get(lm.STORE_KEY)
    blob = kf.decode_text(rec["key"])
    store.set(lm.STORE_KEY, {**rec, "key": kf.encode(blob[:-1] + bytes([blob[-1] ^ 1]))})
    st = m.status()
    assert st["state"] == lm.INVALID and st["reason"] == "bad_signature"


def test_deactivate() -> None:
    m = mgr()
    m.activate(make_key())
    assert m.deactivate()["state"] == lm.UNLICENSED


def test_disabled_flag_blocks_nothing() -> None:
    m = mgr(enabled=False)
    st = m.status()
    assert st["state"] == lm.DISABLED and st["enabled"] is False and st["device_id"] is None
    assert m.allows()
    with pytest.raises(kf.LicenseError) as e:
        m.activate(make_key())
    assert e.value.code == lm.DISABLED
    assert m.store.get(lm.CLOCK_KEY) is None  # o'chiq bo'lsa hech narsa yozilmaydi


def test_enabled_without_production_key_does_not_block() -> None:
    m = mgr(public_keys=[])
    assert m.status()["state"] == lm.NOT_CONFIGURED and m.allows()


def test_settings_flag_default_off(monkeypatch) -> None:
    monkeypatch.delenv("LAHZA_LICENSING", raising=False)
    assert Settings().licensing_enabled is False
    monkeypatch.setenv("LAHZA_LICENSING", "1")
    assert Settings().licensing_enabled is True


# ---- API -----------------------------------------------------------------------------------------
@pytest.fixture
def no_network(monkeypatch):
    real_connect = socket.socket.connect

    def deny(sock, address, *a, **k):
        # Windows'da asyncio socketpair'ni 127.0.0.1 orqali yasaydi; tashqi tarmoq taqiqlangan.
        if isinstance(address, tuple) and address[0] in ("127.0.0.1", "::1"):
            return real_connect(sock, address, *a, **k)
        raise AssertionError("litsenziya tarmoqqa murojaat qilmasligi kerak (NFR-01)")

    monkeypatch.setattr(socket.socket, "connect", deny)


def test_api_disabled_by_default(tmp_path: Path, monkeypatch, no_network) -> None:
    monkeypatch.delenv("LAHZA_LICENSING", raising=False)
    c, _ = make_client(tmp_path, monkeypatch)
    r = c.get("/v1/license").json()
    assert r["enabled"] is False and r["state"] == "disabled"
    r = c.put("/v1/license", json={"key": make_key()})
    assert r.status_code == 409 and r.json()["detail"].startswith("disabled: ")
    assert c.delete("/v1/license").status_code == 409
    # Boshqa endpointlar odatdagidek ishlaydi
    assert c.get("/v1/health").json()["ok"] is True


def test_api_enabled_flow(tmp_path: Path, monkeypatch, no_network) -> None:
    monkeypatch.setenv("LAHZA_LICENSING", "1")
    monkeypatch.setattr(routes_license.keys, "trusted_keys", lambda: [PUB])
    monkeypatch.setattr(routes_license, "device_fingerprint", lambda: DEVICE)
    c, st = make_client(tmp_path, monkeypatch)
    assert st.settings.licensing_enabled is True
    assert c.get("/v1/license").json()["state"] == "unlicensed"

    r = c.put("/v1/license", json={"key": "LAHZA-XXXXX"})
    assert r.status_code == 400 and r.json()["detail"].split(":")[0] == "malformed"
    blob = kf.decode_text(make_key())
    r = c.put("/v1/license", json={"key": kf.encode(blob[:-1] + bytes([blob[-1] ^ 1]))})
    assert r.json()["detail"].split(":")[0] == "bad_signature"
    r = c.put("/v1/license", json={"key": make_key(expires=date(2020, 1, 1), issued=date(2019, 1, 1))})
    assert r.json()["detail"].split(":")[0] == "expired"
    r = c.put("/v1/license", json={"key": make_key(max_version="0.0.1")})
    assert r.json()["detail"].split(":")[0] == "wrong_version"

    r = c.put("/v1/license", json={"key": make_key(edition="studio").lower()})
    assert r.status_code == 200 and r.json()["state"] == "valid"
    assert r.json()["license"]["edition"] == "studio"
    # Saqlangan (kutubxona `settings` jadvali) - yangi so'rovda ham
    assert c.get("/v1/license").json()["state"] == "valid"
    rows = st.lib("SELECT key FROM settings WHERE key IN ('license', 'license_clock') ORDER BY key")
    assert [r["key"] for r in rows] == ["license", "license_clock"]

    assert c.delete("/v1/license").json()["state"] == "unlicensed"
    assert c.get("/v1/license").json()["state"] == "unlicensed"


def test_api_requires_token(tmp_path: Path, monkeypatch) -> None:
    c, _ = make_client(tmp_path, monkeypatch)
    c.headers.pop("Authorization")
    assert c.get("/v1/license").status_code == 401


# ---- chiqarish skripti ---------------------------------------------------------------------------
def _script():
    import importlib.util

    path = Path(__file__).resolve().parents[2] / "scripts" / "license_issue.py"
    spec = importlib.util.spec_from_file_location("license_issue", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_issue_script_keygen_embed_issue(tmp_path: Path, capsys) -> None:
    mod = _script()
    keys_copy = tmp_path / "keys.py"
    real = mod.KEYS_PY.read_text(encoding="utf-8")
    keys_copy.write_text(real, encoding="utf-8")
    mod.KEYS_PY = keys_copy
    out = tmp_path / "k"
    mod.main(["keygen", "--out", str(out), "--embed"])
    priv = out / "license_signing.key"
    if sys.platform != "win32":  # Windows'da Unix ruxsat bitlari yo'q
        assert (priv.stat().st_mode & 0o777) == 0o600
    pub = (out / "license_signing.pub").read_text().strip()
    ns: dict = {}
    exec(compile(keys_copy.read_text(), str(keys_copy), "exec"), ns)  # noqa: S102
    assert ns["PRODUCTION_PUBLIC_KEYS"] == (pub,)
    assert Path(keys.__file__).read_text(encoding="utf-8") == real  # haqiqiy keys.py tegilmagan
    mod.main(["keygen", "--out", str(tmp_path / "k2"), "--embed"])  # rotatsiya: eskisi qoladi
    ns = {}
    exec(compile(keys_copy.read_text(), str(keys_copy), "exec"), ns)  # noqa: S102
    assert len(ns["PRODUCTION_PUBLIC_KEYS"]) == 2 and ns["PRODUCTION_PUBLIC_KEYS"][0] == pub
    with pytest.raises(SystemExit):  # qayta yozishdan himoya
        mod.main(["keygen", "--out", str(out)])
    capsys.readouterr()
    mod.main(["issue", "--key", str(priv), "--licensee", "X", "--edition", "pro", "--perpetual",
              "--device", "abcd-efgh-ijkl-mnop", "--log", str(tmp_path / "log.jsonl")])
    text = capsys.readouterr().out.strip()
    p = kf.verify(text, [keys.decode_key(pub)])
    assert p.expires is None and p.devices == ["ABCDEFGHIJKLMNOP"]
    assert text not in (tmp_path / "log.jsonl").read_text()  # jurnalda kalit matni yo'q
    with pytest.raises(SystemExit):  # --expires yoki --perpetual majburiy
        mod.main(["issue", "--key", str(priv), "--licensee", "X", "--edition", "pro"])
