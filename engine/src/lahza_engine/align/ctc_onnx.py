"""ONNX CTC akustik model bilan so'z vaqtlarini aniqlash (M1-ALN-1, R0-ALN-2).

Model: wav2vec2 uslubidagi CTC (kirish 16 kHz float32 [1, N], chiqish logits [1, T, V]) va
`vocab.json` (token -> id). Blank - `<pad>` yoki `<blank>`, so'z ajratgich - `|`.
Matn gaplar bo'yicha <= 30 s bo'laklarga bo'linadi (atrofga 200 ms), har bo'lak alohida
tekislanadi (`align.ctc.forced_align`). Bo'lakni tekislab bo'lmasa - o'sha bo'lakda ASR vaqtlari
qoladi. Torch kerak emas.
"""

from __future__ import annotations

import json
import logging
import unicodedata
import wave
from pathlib import Path
from typing import Any

import numpy as np

from lahza_engine.align.ctc import forced_align
from lahza_engine.types import Word

log = logging.getLogger(__name__)

SAMPLE_RATE = 16000
MAX_CHUNK_MS = 30_000
PAD_MS = 200
_BLANKS = ("<pad>", "<blank>", "[PAD]", "<eps>")
_SEP = "|"
_APOS = "ʻʼ'’‘`´"
_TERMINAL = (".", "?", "!", "…")


def read_wav_segment(path: Path, start_ms: int, end_ms: int) -> np.ndarray:
    """16-bit PCM WAV'dan faqat kerakli oraliqni o'qiydi -> float32 mono."""
    with wave.open(str(path), "rb") as w:
        if w.getsampwidth() != 2:
            raise ValueError("faqat 16-bit PCM WAV qo'llanadi")
        rate, ch, n = w.getframerate(), w.getnchannels(), w.getnframes()
        a = max(0, min(n, int(start_ms * rate / 1000)))
        b = max(a, min(n, int(end_ms * rate / 1000)))
        w.setpos(a)
        raw = w.readframes(b - a)
    pcm = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
    if ch > 1:
        pcm = pcm.reshape(-1, ch).mean(axis=1)
    if rate != SAMPLE_RATE and len(pcm):
        m = int(round(len(pcm) * SAMPLE_RATE / rate))
        pcm = np.interp(np.arange(m) / SAMPLE_RATE, np.arange(len(pcm)) / rate, pcm).astype(np.float32)
    return pcm


def _log_softmax(x: np.ndarray) -> np.ndarray:
    x = x.astype(np.float64)
    m = x.max(axis=-1, keepdims=True)
    return x - m - np.log(np.exp(x - m).sum(axis=-1, keepdims=True))


class Tokenizer:
    """Belgi darajasidagi CTC lug'ati uchun o'zbekcha matn -> token ID'lar."""

    def __init__(self, vocab: dict[str, int]) -> None:
        self.vocab = vocab
        blank = next((b for b in _BLANKS if b in vocab), None)
        self.blank = vocab[blank] if blank is not None else 0
        self.sep = vocab.get(_SEP)
        # Lug'atdagi apostrof varianti (oʻ/gʻ va tutuq uchun).
        self._apos = {c: self._pick_apos(c) for c in _APOS}
        self._multi = sorted((t for t in vocab if len(t) > 1 and not t.startswith(("<", "["))),
                             key=len, reverse=True)

    def _pick_apos(self, c: str) -> str | None:
        if c in self.vocab:
            return c
        order = "ʼ'’ʻ‘`" if c == "ʼ" else "ʻ'‘’ʼ`"
        return next((v for v in order if v in self.vocab), None)

    def _clean(self, word: str) -> str:
        t = unicodedata.normalize("NFC", word).lower()
        out = []
        for ch in t:
            if ch in self._apos:
                rep = self._apos[ch]
                if rep is not None:
                    out.append(rep)
            else:
                out.append(ch)
        return "".join(out)

    def word_tokens(self, word: str) -> list[int]:
        """So'z tokenlari; lug'atda yo'q belgilar tashlanadi."""
        t = self._clean(word)
        ids: list[int] = []
        i = 0
        while i < len(t):
            hit = next((m for m in self._multi if t.startswith(m, i)), None)
            if hit is not None:
                ids.append(self.vocab[hit])
                i += len(hit)
                continue
            ch = t[i]
            if ch in self.vocab and ch != _SEP:
                ids.append(self.vocab[ch])
            i += 1
        return ids


def group_words(words: list[Word], max_ms: int = MAX_CHUNK_MS - 2 * PAD_MS,
                gap_ms: int = 1000) -> list[list[int]]:
    """So'z indekslarini gaplarga, gaplarni esa <= max_ms bo'laklarga yig'adi."""
    sentences: list[list[int]] = []
    cur: list[int] = []
    for i, w in enumerate(words):
        if cur and (w.start_ms - words[cur[-1]].end_ms >= gap_ms
                    or w.end_ms - words[cur[0]].start_ms > max_ms):
            sentences.append(cur)
            cur = []
        cur.append(i)
        if w.text.rstrip().endswith(_TERMINAL):
            sentences.append(cur)
            cur = []
    if cur:
        sentences.append(cur)
    chunks: list[list[int]] = []
    for s in sentences:
        if chunks and words[s[-1]].end_ms - words[chunks[-1][0]].start_ms <= max_ms:
            chunks[-1].extend(s)
        else:
            chunks.append(list(s))
    return chunks


class CtcAligner:
    """`align_words` (bitta gap/oraliq) va `__call__` (butun fayl) - shartnoma 1-band."""

    method = "ctc"

    def __init__(self, vocab: dict[str, int], model_path: Path | None = None,
                 session: Any | None = None, normalize_input: bool = True) -> None:
        if session is None:
            if model_path is None:
                raise ValueError("model_path yoki session kerak")
            import onnxruntime as ort

            session = ort.InferenceSession(str(model_path), providers=["CPUExecutionProvider"])
        self.session = session
        self.input_name = session.get_inputs()[0].name
        self.tok = Tokenizer(vocab)
        self.normalize_input = normalize_input

    @classmethod
    def from_dir(cls, model_dir: Path) -> CtcAligner:
        root = Path(model_dir)
        onnx = root if root.suffix == ".onnx" else next(iter(sorted(root.rglob("*.onnx"))), None)
        if onnx is None:
            raise FileNotFoundError(f"{root}: .onnx topilmadi")
        base = onnx.parent
        vocab_path = next((p for p in (base / "vocab.json", root / "vocab.json") if p.exists()), None)
        if vocab_path is None:
            raise FileNotFoundError(f"{root}: vocab.json topilmadi")
        vocab = json.loads(vocab_path.read_text(encoding="utf-8"))
        normalize = True
        pre = base / "preprocessor_config.json"
        if pre.exists():
            normalize = bool(json.loads(pre.read_text(encoding="utf-8")).get("do_normalize", True))
        return cls(vocab, model_path=onnx, normalize_input=normalize)

    # --- emissiyalar -------------------------------------------------------------------------

    def log_probs(self, audio: np.ndarray) -> np.ndarray:
        x = audio.astype(np.float32)
        if self.normalize_input and len(x):
            x = (x - x.mean()) / np.sqrt(x.var() + 1e-7)
        (logits, *_) = self.session.run(None, {self.input_name: x[None, :]})
        logits = np.asarray(logits)
        if logits.ndim == 3:
            logits = logits[0]
        return _log_softmax(logits)

    # --- tekislash ---------------------------------------------------------------------------

    def _align_chunk(self, words: list[Word], audio: np.ndarray, offset_ms: int) -> list[Word]:
        """`audio` offset_ms dan boshlanadi. Xatoda ASR vaqtlari qaytadi."""
        per_word = [self.tok.word_tokens(w.text) for w in words]
        targets: list[int] = []
        owner: list[int] = []  # har target tokenning so'z indeksi (-1: ajratgich)
        for i, ids in enumerate(per_word):
            if not ids:
                continue
            if targets and self.tok.sep is not None:
                targets.append(self.tok.sep)
                owner.append(-1)
            targets.extend(ids)
            owner.extend([i] * len(ids))
        if not targets or len(audio) == 0:
            return words
        try:
            lp = self.log_probs(audio)
            spans = forced_align(lp, targets, blank=self.tok.blank)
        except ValueError:
            log.info("bo'lakni tekislab bo'lmadi (%d so'z) - ASR vaqtlari qoldi", len(words))
            return words
        frame_ms = len(audio) * 1000 / SAMPLE_RATE / lp.shape[0]
        first: dict[int, int] = {}
        last: dict[int, int] = {}
        for sp, wi in zip(spans, owner, strict=True):
            if wi < 0:
                continue
            first.setdefault(wi, sp.start_frame)
            last[wi] = sp.end_frame
        out = []
        for i, w in enumerate(words):
            if i not in first:
                out.append(w)
                continue
            a = offset_ms + int(round(first[i] * frame_ms))
            b = offset_ms + int(round(last[i] * frame_ms))
            out.append(w.model_copy(update={"start_ms": a, "end_ms": max(b, a + 1)}))
        return _fix_unaligned(out, [i in first for i in range(len(words))])

    def align_words(self, words: list[Word], wav_path: Path, start_ms: int, end_ms: int) -> list[Word]:
        """Bitta oraliqdagi (odatda bitta gap) so'zlarni qayta tekislaydi."""
        if not words:
            return words
        if end_ms - start_ms > MAX_CHUNK_MS:
            return self(words, wav_path)
        a = max(0, start_ms - PAD_MS)
        audio = read_wav_segment(Path(wav_path), a, end_ms + PAD_MS)
        return self._align_chunk(words, audio, a)

    def __call__(self, words: list[Word], wav_path: Path | str) -> list[Word]:
        out: list[Word] = []
        for idx in group_words(words):
            chunk = [words[i] for i in idx]
            a = max(0, chunk[0].start_ms - PAD_MS)
            b = chunk[-1].end_ms + PAD_MS
            audio = read_wav_segment(Path(wav_path), a, b)
            out.extend(self._align_chunk(chunk, audio, a))
        return out


def _fix_unaligned(words: list[Word], aligned: list[bool]) -> list[Word]:
    """Tekislanmagan so'zlar (masalan, faqat raqam) qo'shnilari orasiga siqiladi."""
    out = list(words)
    for i, ok in enumerate(aligned):
        if ok:
            continue
        lo = max((out[j].end_ms for j in range(i) if aligned[j]), default=None)
        hi = min((out[j].start_ms for j in range(i + 1, len(out)) if aligned[j]), default=None)
        a, b = out[i].start_ms, out[i].end_ms
        if lo is not None:
            a = max(a, lo)
        if hi is not None:
            b = min(b, hi)
        if b <= a:
            continue
        out[i] = out[i].model_copy(update={"start_ms": a, "end_ms": b})
    return out

