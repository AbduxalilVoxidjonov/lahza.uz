import base64
import json
import zipfile
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from lahza_engine.models.catalog import Task
from lahza_engine.models.lzpack import PackError, export_pack, import_pack
from lahza_engine.models.store import InstalledModel, ModelStore


def _store(root: Path) -> ModelStore:
    st = ModelStore(root)
    d = root / "asr" / "w1"
    d.mkdir(parents=True)
    (d / "model.bin").write_bytes(b"weights" * 1000)
    (d / "sub").mkdir()
    (d / "sub" / "vocab.json").write_text("{}", encoding="utf-8")
    (root / "llm").mkdir()
    (root / "llm" / "q.gguf").write_bytes(b"GGUF" + b"\x00" * 100)
    st.register([InstalledModel(id="w1", task=Task.ASR, version="1", path=str(d)),
                 InstalledModel(id="custom:q", task=Task.LLM, version="custom",
                                path=str(root / "llm" / "q.gguf"), source="custom", verified=False)])
    return st


def _keys() -> tuple[str, str]:
    k = Ed25519PrivateKey.generate()
    priv = k.private_bytes(serialization.Encoding.Raw, serialization.PrivateFormat.Raw,
                           serialization.NoEncryption())
    pub = k.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    return base64.b64encode(priv).decode(), base64.b64encode(pub).decode()


def _rewrite(src: Path, dst: Path, edit) -> None:
    with zipfile.ZipFile(src) as zi, zipfile.ZipFile(dst, "w") as zo:
        items = {n: zi.read(n) for n in zi.namelist()}
        for n, data in edit(items).items():
            zo.writestr(n, data)


def test_roundtrip_signed(tmp_path: Path) -> None:
    priv, pub = _keys()
    src = _store(tmp_path / "a")
    progress: list[float] = []
    res = export_pack(src, tmp_path / "m.lzpack", private_key_b64=priv, progress=progress.append)
    assert res["models"] == ["custom:q", "w1"] and res["files"] == 3 and progress[-1] == 1.0
    with zipfile.ZipFile(tmp_path / "m.lzpack") as z:
        man = json.loads(z.read("manifest.json"))
        assert "signature" in z.namelist()
    assert all(f["path"].startswith("Models/") and len(f["sha256"]) == 64 for f in man["files"])
    assert {m["path"] for m in man["registry"]["models"]} == {"Models/asr/w1", "Models/llm/q.gguf"}

    dst = ModelStore(tmp_path / "b")
    out = import_pack(dst, tmp_path / "m.lzpack", pubkey_b64=pub, dev=False)
    assert sorted(out["imported"]) == ["custom:q", "w1"]
    m = dst.get("w1")
    assert m is not None and Path(m.path) == (tmp_path / "b").resolve() / "asr" / "w1"
    assert (Path(m.path) / "sub" / "vocab.json").exists()
    assert dst.default_for(Task.ASR).id == "w1"
    assert not list((tmp_path / "b").glob(".lzpack-*"))  # vaqtinchalik papka tozalandi


def test_signature_rules(tmp_path: Path) -> None:
    priv, pub = _keys()
    _, other_pub = _keys()
    src = _store(tmp_path / "a")
    export_pack(src, tmp_path / "s.lzpack", private_key_b64=priv)
    export_pack(src, tmp_path / "u.lzpack")
    with pytest.raises(PackError, match="imzosi"):
        import_pack(ModelStore(tmp_path / "b"), tmp_path / "s.lzpack", pubkey_b64=other_pub, dev=False)
    with pytest.raises(PackError, match="imzolanmagan"):
        import_pack(ModelStore(tmp_path / "c"), tmp_path / "u.lzpack", pubkey_b64=pub, dev=False)
    # dev rejimi: imzosiz qabul, lekin sha256 baribir tekshiriladi
    assert import_pack(ModelStore(tmp_path / "d"), tmp_path / "u.lzpack", pubkey_b64=pub, dev=True)
    # kalit sozlanmagan: sha256 tekshiruvi bilan qabul
    assert import_pack(ModelStore(tmp_path / "e"), tmp_path / "u.lzpack", pubkey_b64=None, dev=False)


@pytest.mark.parametrize("case", ["tamper", "slip", "abs", "exe_magic", "exe_ext", "extra", "missing"])
def test_import_rejects_bad_packs(tmp_path: Path, case: str) -> None:
    src = _store(tmp_path / "a")
    export_pack(src, tmp_path / "ok.lzpack")
    bad = tmp_path / "bad.lzpack"

    def edit(items: dict) -> dict:
        man = json.loads(items["manifest.json"])
        if case == "tamper":
            items["Models/asr/w1/model.bin"] = b"boshqa" * 1000
        elif case in ("slip", "abs", "exe_ext"):
            name = {"slip": "Models/../../evil.txt", "abs": "/etc/evil",
                    "exe_ext": "Models/asr/w1/run.sh"}[case]
            items[name] = b"x"
            man["files"].append({"path": name, "sha256": "0" * 64, "size": 1})
        elif case == "exe_magic":
            data = b"\x7fELF" + b"\x00" * 10
            items["Models/asr/w1/model.bin"] = data
            import hashlib

            for f in man["files"]:
                if f["path"] == "Models/asr/w1/model.bin":
                    f.update(sha256=hashlib.sha256(data).hexdigest(), size=len(data))
        elif case == "extra":
            items["Models/asr/w1/extra.bin"] = b"x"
        elif case == "missing":
            del items["Models/asr/w1/sub/vocab.json"]
        items["manifest.json"] = json.dumps(man).encode()
        return items

    _rewrite(tmp_path / "ok.lzpack", bad, edit)
    dst = ModelStore(tmp_path / "b")
    with pytest.raises(PackError):
        import_pack(dst, bad, pubkey_b64=None, dev=False)
    assert dst.load().models == []
    assert not (tmp_path / "evil.txt").exists()
    assert not (tmp_path / "b" / "asr").exists()


def test_not_a_zip(tmp_path: Path) -> None:
    p = tmp_path / "x.lzpack"
    p.write_bytes(b"emas")
    with pytest.raises(PackError):
        import_pack(ModelStore(tmp_path / "s"), p)
    with pytest.raises(PackError):
        export_pack(ModelStore(tmp_path / "e"), tmp_path / "y.lzpack")


def test_store_remove_switches_default(tmp_path: Path) -> None:
    st = _store(tmp_path / "a")
    d2 = tmp_path / "a" / "asr" / "w2"
    d2.mkdir()
    (d2 / "model.bin").write_bytes(b"x")
    st.register([InstalledModel(id="w2", task=Task.ASR, version="1", path=str(d2))])
    assert st.default_for(Task.ASR).id == "w1"
    st.remove("w1")
    assert st.default_for(Task.ASR).id == "w2" and not (tmp_path / "a" / "asr" / "w1").exists()
    st.remove("w2")
    assert st.default_for(Task.ASR) is None and "asr" not in st.load().defaults
    # Models/ dan tashqaridagi fayl o'chirilmaydi
    outside = tmp_path / "tashqi.gguf"
    outside.write_bytes(b"GGUF")
    st.register([InstalledModel(id="t", task=Task.LLM, version="1", path=str(outside))])
    st.remove("t")
    assert outside.exists()
    with pytest.raises(KeyError):
        st.remove("yoq")
