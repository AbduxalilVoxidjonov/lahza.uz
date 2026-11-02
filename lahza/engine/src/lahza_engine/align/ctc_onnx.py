"""ONNX CTC akustik model bilan so'z vaqtlarini aniqlash (M1-ALN-1, R0-ALN-2).

Model: wav2vec2 uslubidagi CTC (kirish 16 kHz float32 [1, N], chiqish logits [1, T, V]).
Lug'at: `vocab.json` ({token: id}, HF wav2vec2) yoki `tokens.txt` ("token id" qatorlari,
sherpa-onnx/onnx-asr). Blank - `<pad>`/`<blank>`, so'z ajratgich - `|` (yoki bo'shliq).
Standart model - Omnilingual ASR CTC 300M v2 (int8); uning sozlamalari `aligner.json` da:
`vocab`, `blank`, `separator`, `apostrophe`, `frame_ms`, `max_chunk_ms`, `end_pad_ms`.
Matn gaplar bo'yicha <= 30 s bo'laklarga bo'linadi (atrofga 200 ms), har bo'lak alohida
tekislanadi (`align.ctc.forced_align`). ASR so'z vaqtlari taxminiy bo'lsa (AsrOptions.timestamps
"ctc": bo'lak ichida proporsional) `windows` - ASR bo'laklari chegaralari beriladi: so'zlar o'z
bo'lagining audiosida tekislanadi, taxminiy vaqt xatosi bo'lakdan tashqariga chiqmaydi. Bo'lakni
tekislab bo'lmasa - o'sha bo'lakda ASR vaqtlari qoladi. Torch kerak emas.
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


def load_vocab(path: Path) -> dict[str, int]:
    """`vocab.json` ({token: id}) yoki `tokens.txt` ("token id"; token bo'shliq bo'lishi mumkin)."""
    path = Path(path)
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".json":
        return {str(t): int(i) for t, i in json.loads(text).items()}
    vocab: dict[str, int] = {}
    for line in text.splitlines():
        if not line.strip():
            continue
        token, _, ident = line.rpartition(" ")
        vocab[token] = int(ident)
    return vocab


def _log_softmax(x: np.ndarray) -> np.ndarray:
    # float32 yetarli (Viterbi faqat taqqoslaydi); katta lug'atda (~10k token) xotirani 2x tejaydi.
    x = np.asarray(x, dtype=np.float32)
    m = x.max(axis=-1, keepdims=True)
    return x - m - np.log(np.exp(x - m).sum(axis=-1, keepdims=True))


class Tokenizer:
    """Belgi darajasidagi CTC lug'ati uchun o'zbekcha matn -> token ID'lar."""

    def __init__(self, vocab: dict[str, int], blank: int | None = None,
                 separator: str | None = None, apostrophe: str | None = None) -> None:
        self.vocab = vocab
        if blank is None:
            name = next((b for b in _BLANKS if b in vocab), None)
            blank = vocab[name] if name is not None else 0
        self.blank = blank
        self._sep_char = separator if separator is not None else _SEP
        self.sep = vocab.get(self._sep_char)
        # Lug'atdagi apostrof varianti (oʻ/gʻ va tutuq uchun); `apostrophe` - model o'qitilgan belgi.
        forced = apostrophe if apostrophe in vocab else None
        self._apos = {c: forced or self._pick_apos(c) for c in _APOS}
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
            elif ch.isalnum():
                # Tinish/defis tashlanadi: talaffuz qilinmaydi, majburiy kadr esa vaqtni suradi.
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
            if ch in self.vocab and ch != self._sep_char:
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
                 session: Any | None = None, normalize_input: bool = True, *,
                 blank: int | None = None, separator: str | None = None,
                 apostrophe: str | None = None, frame_ms: float | None = None,
                 max_chunk_ms: int = MAX_CHUNK_MS, end_pad_ms: int = 0) -> None:
        if session is None:
            if model_path is None:
                raise ValueError("model_path yoki session kerak")
            import onnxruntime as ort

            session = ort.InferenceSession(str(model_path), providers=["CPUExecutionProvider"])
        self.session = session
        self.input_name = session.get_inputs()[0].name
        self.tok = Tokenizer(vocab, blank=blank, separator=separator, apostrophe=apostrophe)
        self.normalize_input = normalize_input
        self.frame_ms = frame_ms
        self.max_chunk_ms = max(2 * PAD_MS + 1000, int(max_chunk_ms))
        # CTC "cho'qqili": oxirgi harf akustik tugashdan oldin chiqadi; oxir keyingi so'zgacha cho'ziladi.
        self.end_pad_ms = max(0, int(end_pad_ms))

    @classmethod
    def from_dir(cls, model_dir: Path) -> CtcAligner:
        root = Path(model_dir)
        onnx = root if root.suffix == ".onnx" else next(iter(sorted(root.rglob("*.onnx"))), None)
        if onnx is None:
            raise FileNotFoundError(f"{root}: .onnx topilmadi")
        dirs = list(dict.fromkeys((onnx.parent, root if root.is_dir() else onnx.parent)))

        def find(*names: str) -> Path | None:
            return next((d / n for n in names for d in dirs if (d / n).is_file()), None)

        conf_path = find("aligner.json")
        conf = json.loads(conf_path.read_text(encoding="utf-8")) if conf_path else {}
        vocab_path = find(*([conf["vocab"]] if conf.get("vocab") else []), "vocab.json", "tokens.txt")
        if vocab_path is None:
            raise FileNotFoundError(f"{root}: vocab.json/tokens.txt topilmadi")
        normalize = bool(conf.get("normalize", True))
        pre = find("preprocessor_config.json")
        if pre is not None:
            normalize = bool(json.loads(pre.read_text(encoding="utf-8")).get("do_normalize", normalize))
        blank = conf.get("blank")
        return cls(load_vocab(vocab_path), model_path=onnx, normalize_input=normalize,
                   blank=None if blank is None else int(blank), separator=conf.get("separator"),
                   apostrophe=conf.get("apostrophe"), frame_ms=conf.get("frame_ms"),
                   max_chunk_ms=int(conf.get("max_chunk_ms", MAX_CHUNK_MS)),
                   end_pad_ms=int(conf.get("end_pad_ms", 0)))

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

    def _align_chunk(self, words: list[Word], audio: np.ndarray, offset_ms: int,
                     score: bool = False) -> list[Word]:
        """`audio` offset_ms dan boshlanadi. Xatoda ASR vaqtlari qaytadi.

        `score` - so'z ishonchi CTC bilan aniqlanadi (`word_conf`): ASR ishonchi segment darajasida
        bo'lganda (timestamp'siz dekodlash) so'zlar orasidagi farqni CTC beradi."""
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
        frame_ms = self.frame_ms or len(audio) * 1000 / SAMPLE_RATE / lp.shape[0]
        first: dict[int, int] = {}
        last: dict[int, int] = {}
        probs: dict[int, list[float]] = {}
        for sp, wi in zip(spans, owner, strict=True):
            if wi < 0:
                continue
            first.setdefault(wi, sp.start_frame)
            last[wi] = sp.end_frame
            probs.setdefault(wi, []).append(sp.score)
        out = []
        for i, w in enumerate(words):
            if i not in first:
                out.append(w)
                continue
            a = offset_ms + int(round(first[i] * frame_ms))
            b = offset_ms + int(round(last[i] * frame_ms))
            upd: dict[str, Any] = {"start_ms": a, "end_ms": max(b, a + 1)}
            if score:
                upd["conf"] = word_conf(w.conf, float(np.mean(probs[i])))
            out.append(w.model_copy(update=upd))
        return _fix_unaligned(out, [i in first for i in range(len(words))])

    def align_words(self, words: list[Word], wav_path: Path, start_ms: int, end_ms: int) -> list[Word]:
        """Bitta oraliqdagi (odatda bitta gap) so'zlarni qayta tekislaydi."""
        if not words:
            return words
        if end_ms - start_ms > self.max_chunk_ms:
            return self(words, wav_path)
        a = max(0, start_ms - PAD_MS)
        audio = read_wav_segment(Path(wav_path), a, end_ms + PAD_MS)
        return _pad_ends(self._align_chunk(words, audio, a), self.end_pad_ms, end_ms)

    def __call__(self, words: list[Word], wav_path: Path | str,
                 windows: list[tuple[int, int]] | None = None) -> list[Word]:
        """Butun fayl. `windows` - ASR bo'laklari [a, b) (ms): so'z o'rtasi tushgan oynada tekislanadi;
        qo'shni oynalar `max_chunk_ms` gacha bitta ONNX chaqiruviga birlashtiriladi."""
        if windows:
            out = self._align_windows(words, Path(wav_path), windows)
        else:
            out = self._align_grouped(words, Path(wav_path))
        return _pad_ends(out, self.end_pad_ms, out[-1].end_ms + self.end_pad_ms if out else 0)

    def _align_grouped(self, words: list[Word], wav_path: Path, score: bool = False) -> list[Word]:
        """So'zlar ASR vaqtlari bo'yicha gaplarga/bo'laklarga guruhlanadi (aniq ASR vaqtlari uchun)."""
        out: list[Word] = []
        for idx in group_words(words, max_ms=self.max_chunk_ms - 2 * PAD_MS):
            chunk = [words[i] for i in idx]
            a = max(0, chunk[0].start_ms - PAD_MS)
            b = chunk[-1].end_ms + PAD_MS
            audio = read_wav_segment(wav_path, a, b)
            out.extend(self._align_chunk(chunk, audio, a, score=score))
        return out

    def _align_windows(self, words: list[Word], wav_path: Path,
                       windows: list[tuple[int, int]]) -> list[Word]:
        out = list(words)
        for (a, b), idx in window_groups(words, windows, self.max_chunk_ms):
            chunk = [words[i] for i in idx]
            if b - a > self.max_chunk_ms:  # bitta oyna juda uzun - matn bo'yicha guruhlash
                got = self._align_grouped(chunk, wav_path, score=True)
            else:
                got = self._align_chunk(chunk, read_wav_segment(wav_path, a, b), a, score=True)
            for i, w in zip(idx, got, strict=True):
                out[i] = w
        return out


def word_conf(asr_conf: float | None, ctc_score: float) -> float:
    """So'z ishonchi = ASR segment ishonchi x CTC so'z bali (token ehtimollari o'rtachasi).

    FLEURS uz (40 gap) bo'yicha xato so'zni ajratish: faqat segment - AUC 0.78, < 0.6 belgisi hech
    qaerda; CTC - 0.86/0.81; ko'paytma - 0.87/0.83 (base/small), < 0.6 belgisi so'zlarning ~15-17%
    ida, ularning 45-60% i haqiqiy xato. Shkala UI'dagi word.probability bilan bir xil (0..1).
    """
    c = max(0.0, min(1.0, ctc_score))
    return round(c if asr_conf is None else max(0.0, min(1.0, asr_conf)) * c, 4)


def window_groups(words: list[Word], windows: list[tuple[int, int]],
                  max_ms: int) -> list[tuple[tuple[int, int], list[int]]]:
    """So'z indekslarini oynalarga taqsimlaydi: ((a, b), [indekslar]) ro'yxati, vaqt tartibida.

    * kesishgan oynalar (bo'lak padding'i) kesishma o'rtasidan ajratiladi - oynalar ustma-ust tushmaydi;
    * so'z o'rtasi (start+end)/2 tushgan oynaga, hech biriga tushmasa - eng yaqiniga;
    * bo'sh oynalar tashlanadi; ketma-ket oynalar umumiy uzunlik <= max_ms bo'lsa birlashtiriladi.
    """
    import bisect

    ws = sorted((int(a), int(b)) for a, b in windows if b > a)
    if not ws or not words:
        return []
    cut: list[list[int]] = [list(ws[0])]
    for a, b in ws[1:]:
        prev = cut[-1]
        if a < prev[1]:
            if b <= prev[1]:
                continue  # to'liq ichida
            m = (a + prev[1]) // 2
            prev[1] = m
            a = m
        cut.append([a, b])
    starts = [a for a, _ in cut]
    members: list[list[int]] = [[] for _ in cut]
    for i, w in enumerate(words):
        mid = (w.start_ms + w.end_ms) / 2
        k = max(0, bisect.bisect_right(starts, mid) - 1)
        if mid >= cut[k][1] and k + 1 < len(cut) and cut[k + 1][0] - mid < mid - cut[k][1]:
            k += 1
        members[k].append(i)
    groups: list[tuple[tuple[int, int], list[int]]] = []
    for (a, b), idx in zip(cut, members, strict=True):
        if not idx:
            continue
        if groups and b - groups[-1][0][0] <= max_ms:
            (ga, _), gi = groups[-1]
            groups[-1] = ((ga, b), gi + idx)
        else:
            groups.append(((a, b), idx))
    return groups


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


def _pad_ends(words: list[Word], pad_ms: int, limit_ms: int) -> list[Word]:
    """So'z oxirini `pad_ms` gacha uzaytiradi: keyingi so'z boshidan va bo'lak oxiridan oshmaydi."""
    if pad_ms <= 0:
        return words
    out = list(words)
    for i, w in enumerate(out):
        hi = out[i + 1].start_ms if i + 1 < len(out) else limit_ms
        end = min(w.end_ms + pad_ms, max(w.end_ms, hi))
        if end > w.end_ms:
            out[i] = w.model_copy(update={"end_ms": end})
    return out
