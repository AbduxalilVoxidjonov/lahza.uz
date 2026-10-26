"""Standart CTC aligner: Omnilingual lug'ati/sozlamalari, qat'iy o'rnatuvchi, setup va services."""
import hashlib
import json
import wave
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import onnxruntime
import pytest

from lahza_engine.align.ctc_onnx import CtcAligner, Tokenizer, load_vocab
from lahza_engine.core import services as services_mod
from lahza_engine.models import local_aligner
from lahza_engine.models.catalog import Task
from lahza_engine.models.setup import Setup
from lahza_engine.models.store import InstalledModel, ModelStore
from lahza_engine.types import Word

FRAME = 320  # 20 ms @ 16 kHz
# Omnilingual uslubi: blank `<s>`=0, `<pad>` ham bor, bo'shliq - ajratgich, "|" - oddiy belgi.
TOKENS = ["<s>", "<pad>", "</s>", "<unk>", " ", *"abcdefghijklmnopqrstuvwxyz", "|", "'", "ʻ"]
VOCAB = {t: i for i, t in enumerate(TOKENS)}


class _Inp:
    name = "x"


class FakeSession:
    """Har 20 ms kadrdagi o'rtacha qiymat*100 = token ID (test_ml_align bilan bir xil g'oya)."""

    def __init__(self, *_args, **_kwargs) -> None:
        pass

    def get_inputs(self):
        return [_Inp()]

    def run(self, _outs, feeds):
        x = feeds["x"][0]
        T = len(x) // FRAME
        ids = np.rint(x[: T * FRAME].reshape(T, -1).mean(axis=1) * 100).astype(int)
        logits = np.full((1, T, len(VOCAB)), -10.0, dtype=np.float32)
        logits[0, np.arange(T), np.clip(ids, 0, len(VOCAB) - 1)] = 10.0
        return [logits]


def _write_wav(path: Path, frames: dict[int, int], total: int) -> None:
    sig = np.zeros(total * FRAME, dtype=np.float32)
    for k, tok in frames.items():
        sig[k * FRAME:(k + 1) * FRAME] = tok / 100
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(np.rint(sig * 32768).astype("<i2").tobytes())


def _speak(frames: dict[int, int], start: int, word: str) -> None:
    for i, c in enumerate(word):
        frames[start + i] = VOCAB[c]


def _tokens_txt(path: Path) -> None:
    path.write_text("".join(f"{t} {i}\n" for t, i in VOCAB.items()), encoding="utf-8")


def _model_dir(root: Path, **conf) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "model.int8.onnx").write_bytes(b"onnx")
    _tokens_txt(root / "tokens.txt")
    (root / "aligner.json").write_text(json.dumps({**local_aligner.ALIGNER_CONFIG, **conf}))
    return root


def test_tokens_txt_keeps_space_token(tmp_path: Path) -> None:
    _tokens_txt(tmp_path / "tokens.txt")
    vocab = load_vocab(tmp_path / "tokens.txt")
    assert vocab == VOCAB and vocab[" "] == 4


def test_tokenizer_omnilingual_settings() -> None:
    tok = Tokenizer(VOCAB, blank=0, separator=" ", apostrophe="'")
    assert tok.blank == 0 and tok.sep == VOCAB[" "]
    # ʻ/ʼ/’ modelning ASCII apostrofiga; tinish, defis va "|" (bu lug'atda ajratgich emas) tashlanadi.
    assert tok.word_tokens("Oʻzbek,") == [VOCAB[c] for c in "o'zbek"]
    assert tok.word_tokens("ma’no") == [VOCAB[c] for c in "ma'no"]
    assert tok.word_tokens("ketma-ket.") == [VOCAB[c] for c in "ketmaket"]
    assert tok.word_tokens("a|b") == [VOCAB["a"], VOCAB["b"]]
    # Standart (wav2vec2) xatti-harakat saqlanadi: blank `<pad>`, ajratgich `|`.
    legacy = Tokenizer(VOCAB)
    assert legacy.blank == VOCAB["<pad>"] and legacy.sep == VOCAB["|"]
    assert legacy.word_tokens("oʻ") == [VOCAB["o"], VOCAB["ʻ"]]


def test_from_dir_reads_aligner_json_and_aligns(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(onnxruntime, "InferenceSession", FakeSession)
    al = CtcAligner.from_dir(_model_dir(tmp_path / "m"))
    assert al.tok.blank == 0 and al.tok.sep == VOCAB[" "]
    assert (al.frame_ms, al.max_chunk_ms, al.end_pad_ms) == (20, 15000, 60)
    frames: dict[int, int] = {}
    _speak(frames, 30, "salom")
    frames[40] = VOCAB[" "]
    _speak(frames, 60, "do'st")
    wav = tmp_path / "a.wav"
    _write_wav(wav, frames, 150)
    words = [Word(text="Salom,", start_ms=400, end_ms=1000), Word(text="doʻst.", start_ms=1100, end_ms=1700)]
    out = al(words, wav)
    # boshlar CTC'dan; oxir +60 ms (keyingi so'z boshidan oshmaydi)
    assert [(w.start_ms, w.end_ms) for w in out] == [(600, 760), (1200, 1360)]
    assert [w.text for w in out] == ["Salom,", "doʻst."]


def test_end_padding_never_crosses_next_word(tmp_path: Path) -> None:
    frames: dict[int, int] = {}
    _speak(frames, 20, "ab")
    frames[22] = VOCAB[" "]
    _speak(frames, 23, "cd")
    wav = tmp_path / "b.wav"
    _write_wav(wav, frames, 60)
    al = CtcAligner(VOCAB, session=FakeSession(), normalize_input=False, blank=0, separator=" ",
                    frame_ms=20, end_pad_ms=200)
    out = al([Word(text="ab", start_ms=300, end_ms=500), Word(text="cd", start_ms=500, end_ms=600)], wav)
    assert out[0].end_ms == out[1].start_ms == 460
    assert out[1].end_ms == 500 + 200  # oxirgi so'z: to'liq pad
    one = al.align_words([Word(text="ab", start_ms=300, end_ms=480)], wav, 300, 480)
    assert one[0].end_ms == 480  # bitta gap oynasi: gap oxiridan oshmaydi


def test_installer_requires_consent_before_network(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(local_aligner, "download", lambda *a, **k: pytest.fail("network"))
    with pytest.raises(ValueError, match="consent"):
        local_aligner.install_model(ModelStore(tmp_path))


def _fake_files(monkeypatch) -> dict[str, bytes]:
    blobs = {name: f"payload-{name}".encode() for name, _, _ in local_aligner.FILES}
    pinned = tuple((n, len(b), hashlib.sha256(b).hexdigest()) for n, b in blobs.items())
    monkeypatch.setattr(local_aligner, "FILES", pinned)
    monkeypatch.setattr(local_aligner, "MODEL_SIZE", sum(len(b) for b in blobs.values()))
    return blobs


def test_installer_pinned_download_provenance_and_offline_reuse(tmp_path: Path, monkeypatch) -> None:
    blobs = _fake_files(monkeypatch)
    calls = []

    def fake_download(urls, dest, digest, size, progress=None, **_):
        calls.append((urls[0], digest, size))
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(blobs[dest.name])
        if progress:
            progress(size, size)
        return dest

    monkeypatch.setattr(local_aligner, "download", fake_download)
    store = ModelStore(tmp_path)
    seen = []
    model = local_aligner.install_model(store, consent=True, progress=lambda h, t: seen.append((h, t)))
    assert model.id == local_aligner.MODEL_ID and model.task == Task.ALIGN
    assert all(local_aligner.REVISION in url for url, _, _ in calls) and len(calls) == len(blobs)
    assert seen[-1] == (local_aligner.MODEL_SIZE, local_aligner.MODEL_SIZE)
    target = Path(model.path)
    assert json.loads((target / "aligner.json").read_text()) == local_aligner.ALIGNER_CONFIG
    prov = json.loads((target / "provenance.json").read_text())
    assert prov["license"] == "Apache-2.0" and {r["path"] for r in prov["files"]} >= set(blobs)
    local_aligner.verify_installation(target)
    assert store.get(model.id) is not None
    # Sog'lom o'rnatma - tarmoqsiz qayta ishlatiladi.
    monkeypatch.setattr(local_aligner, "download", lambda *a, **k: pytest.fail("network"))
    assert local_aligner.install_model(store, consent=True).id == model.id
    # Buzilgan fayl aniqlanadi.
    (target / "tokens.txt").write_bytes(b"tampered")
    with pytest.raises(ValueError, match="tokens.txt"):
        local_aligner.verify_installation(target)


def test_setup_validates_align_component(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(onnxruntime, "InferenceSession", FakeSession)
    store = ModelStore(tmp_path / "store")
    setup = Setup(store, SimpleNamespace(jobs={}))
    good = _model_dir(store.root / "align" / "mine")
    setup._validate_model(InstalledModel(id="mine", task=Task.ALIGN, version="1", path=str(good)), good)
    bad = tmp_path / "cyr"
    bad.mkdir()
    (bad / "model.onnx").write_bytes(b"onnx")
    (bad / "vocab.json").write_text(json.dumps({"<pad>": 0, "|": 1, "а": 2}))
    with pytest.raises(ValueError, match="lotin"):
        setup._validate_model(InstalledModel(id="cyr", task=Task.ALIGN, version="1", path=str(bad)), bad)
    # Qat'iy model ID - sha256/sozlama ham tekshiriladi.
    pinned = InstalledModel(id=local_aligner.MODEL_ID, task=Task.ALIGN, version="1", path=str(good))
    with pytest.raises(ValueError, match="mos emas"):
        setup._validate_model(pinned, good)


def test_setup_status_lists_align_with_download_size(tmp_path: Path) -> None:
    store = ModelStore(tmp_path)
    setup = Setup(store, SimpleNamespace(jobs={}))
    setup._runtime = lambda names: (True, None)
    comp = {c["id"]: c for c in setup.status()["components"]}
    assert comp["align"]["required"] and not comp["align"]["ready"]
    assert comp["align"]["download_bytes"] == local_aligner.MODEL_SIZE
    assert local_aligner.MODEL_SIZE == sum(size for _, size, _ in local_aligner.FILES) < 400_000_000


def test_services_use_installed_aligner_without_explicit_default(tmp_path: Path, monkeypatch) -> None:
    import lahza_engine.align.ctc_onnx as ctc_onnx

    monkeypatch.setattr(ctc_onnx.CtcAligner, "from_dir", classmethod(lambda cls, p: ("al", p.name)))
    store = ModelStore(tmp_path)
    path = store.model_dir(Task.ALIGN, local_aligner.MODEL_FOLDER)
    path.mkdir(parents=True)
    store.register([InstalledModel(id=local_aligner.MODEL_ID, task=Task.ALIGN, version="1", path=str(path))])
    reg = store.load()
    reg.defaults.pop(Task.ALIGN.value, None)
    store._save(reg)
    s = services_mod.build_services(store)
    assert s.aligner == ("al", local_aligner.MODEL_FOLDER)
    assert s.aligner_model_id == local_aligner.MODEL_ID


def test_real_pinned_config_matches_catalog_entry() -> None:
    catalog = json.loads((Path(__file__).resolve().parents[2] / "catalog" / "catalog.json").read_text())
    entry = next(e for e in catalog["entries"] if e["id"] == "align-omnilingual-ctc")
    pinned = {n: (size, digest) for n, size, digest in local_aligner.FILES}
    for f in entry["files"]:
        assert (f["size_bytes"], f["sha256"]) == pinned[f["path"]]
        assert all(local_aligner.REVISION in u for u in f["urls"])
    assert entry["license"] == local_aligner.LICENSE
