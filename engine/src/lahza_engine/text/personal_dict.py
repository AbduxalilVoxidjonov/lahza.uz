"""Shaxsiy lug'at (PRO-1): muharrir tuzatishlaridan "xato -> to'g'ri" juftliklarini yig'ish va
keyingi transkripsiyada qo'llash.

* `diff_pairs` - gapning oldingi/keyingi matnidan so'z darajasidagi almashtirishlar (1..3 so'z);
  qo'shilgan yoki o'chirilgan so'zlar juftlik emas (ASR manbasi yo'q).
* `resolve` - bazadagi yozuvlardan faol to'plam: juftlik kamida `min_count` marta takrorlangan va
  shu "xato" uchun ustun (>= `min_share`) bo'lgan "to'g'ri" variant.
* `apply_dictionary` - faqat butun so'z chegarasida (so'z ichidagi qism almashtirilmaydi), ASR
  ishonchi `conf_threshold` dan past so'zlarga qo'llanadi; foydalanuvchi tahrirlagan so'z tegilmaydi.
* `use_dictionary` / `apply_active` - tahlil vazifasi davomida faol lug'at (contextvar): ASR
  bosqichi `asr.base.dedupe_overlaps` orqali bitta chaqiruv bilan qo'llaydi.
"""

from __future__ import annotations

import difflib
import unicodedata
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass

from lahza_engine.text.orthography import normalize
from lahza_engine.types import Word

MAX_SPAN = 3  # bir juftlikda ko'pi bilan 3 so'z
MAX_CHARS = 60
DEFAULT_MIN_COUNT = 2  # "takrorlanuvchi": kamida 2 marta
DEFAULT_MIN_SHARE = 0.8
DEFAULT_CONF_THRESHOLD = 0.85
MAX_HOTWORDS = 40

_WORD_CATS = {"Lu", "Ll", "Lt", "Lo", "Lm", "Nd", "Nl", "No"}


def split_token(tok: str) -> tuple[str, str, str]:
    """"(salom," -> ("(", "salom", ","). O'zbek apostrofi (ʻ ʼ ') so'z ichida qoladi."""
    a, b = 0, len(tok)
    while a < b and unicodedata.category(tok[a]) not in _WORD_CATS:
        a += 1
    while b > a and unicodedata.category(tok[b - 1]) not in _WORD_CATS:
        b -= 1
    return tok[:a], tok[a:b], tok[b:]


def _cores(text: str) -> list[str]:
    out = []
    for tok in normalize(text).split():
        core = split_token(tok)[1]
        if core:
            out.append(core)
    return out


def classify(right: str) -> str:
    """'ism' (bosh harf), 'atama' (bir necha so'z yoki uzun), aks holda 'soz'."""
    if right[:1].isupper():
        return "ism"
    if " " in right or len(right) >= 12:
        return "atama"
    return "soz"


def diff_pairs(before: str, after: str, max_span: int = MAX_SPAN) -> list[tuple[str, str]]:
    """Gap matnlari farqidan (xato, to'g'ri) juftliklari. `xato` kichik harfda saqlanadi."""
    a, b = _cores(before), _cores(after)
    pairs: list[tuple[str, str]] = []
    sm = difflib.SequenceMatcher(a=a, b=b, autojunk=False)
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op != "replace":
            continue
        if not (1 <= i2 - i1 <= max_span and 1 <= j2 - j1 <= max_span):
            continue
        wrong, right = " ".join(a[i1:i2]), " ".join(b[j1:j2])
        if wrong == right or len(wrong) > MAX_CHARS or len(right) > MAX_CHARS:
            continue
        pairs.append((wrong.lower(), right))
    return pairs


@dataclass(frozen=True)
class DictEntry:
    wrong: str  # kichik harf, bo'shliq bilan ajratilgan so'zlar
    right: str
    count: int = 1
    kind: str = "soz"

    @property
    def tokens(self) -> list[str]:
        return self.wrong.split()


def resolve(rows: Sequence[DictEntry], min_count: int = DEFAULT_MIN_COUNT,
            min_share: float = DEFAULT_MIN_SHARE) -> list[DictEntry]:
    """Faol yozuvlar: har "xato" uchun ko'pi bilan bitta, ishonchli "to'g'ri" variant.

    Ziddiyatli tuzatishlar (bir xato -> turli to'g'ri) ulushi `min_share` dan past bo'lsa qo'llanmaydi.
    Zanjirlar (A->B, B->C) ham qo'llanmaydi: "to'g'ri" boshqa yozuvning "xato"si bo'lsa - o'tkaziladi.
    """
    by_wrong: dict[str, list[DictEntry]] = {}
    for r in rows:
        by_wrong.setdefault(r.wrong, []).append(r)
    out: list[DictEntry] = []
    for wrong, group in by_wrong.items():
        total = sum(g.count for g in group)
        best = max(group, key=lambda g: (g.count, g.right))
        # Faqat bosh harf tuzatilishi ham juftlik ("toshkent" -> "Toshkent").
        if best.count >= min_count and best.count / total >= min_share and best.right != wrong:
            out.append(best)
    wrongs = {e.wrong for e in out}
    out = [e for e in out if e.right.lower() not in wrongs or e.right.lower() == e.wrong]
    return sorted(out, key=lambda e: (-len(e.tokens), -e.count, e.wrong))


def hotwords(entries: Sequence[DictEntry], limit: int = MAX_HOTWORDS) -> list[str]:
    """Whisper prompt/hotwords: faqat ismlar va atamalar (oddiy so'zlar promptni buzadi)."""
    out: list[str] = []
    for e in sorted(entries, key=lambda x: (-x.count, x.right)):
        if e.kind in ("ism", "atama") and e.right not in out:
            out.append(e.right)
        if len(out) >= limit:
            break
    return out


def _cased(right: str, original_core: str) -> str:
    if original_core[:1].isupper() and right[:1].islower():
        return right[:1].upper() + right[1:]
    return right


def apply_dictionary(words: list[Word], entries: Sequence[DictEntry],
                     conf_threshold: float = DEFAULT_CONF_THRESHOLD) -> list[Word]:
    """So'zlar ro'yxatiga lug'atni qo'llaydi (yangi ro'yxat; kirish o'zgarmaydi).

    Mos kelish - so'z yadrosi (tinish belgilarisiz, kichik harf) to'liq teng bo'lishi; birinchi
    so'zning oldingi va oxirgi so'zning keyingi tinish belgilari saqlanadi. `conf` ma'lum bo'lsa va
    `>= conf_threshold` bo'lsa - ASR ishonchli, tegilmaydi. `edited` so'zlar tegilmaydi.
    """
    if not entries or not words:
        return list(words)
    index: dict[str, list[DictEntry]] = {}
    for e in entries:
        if e.tokens:
            index.setdefault(e.tokens[0], []).append(e)
    for group in index.values():
        group.sort(key=lambda e: -len(e.tokens))
    parts = [split_token(normalize(w.text)) for w in words]
    out: list[Word] = []
    i = 0
    while i < len(words):
        hit = None
        for e in index.get(parts[i][1].lower(), []):
            n = len(e.tokens)
            span = words[i:i + n]
            if len(span) < n:
                continue
            if [parts[i + k][1].lower() for k in range(n)] != e.tokens:
                continue
            if any(w.edited for w in span):
                continue
            if any(w.conf is not None and w.conf >= conf_threshold for w in span):
                continue
            # Ichki so'zlarda tinish belgisi bo'lsa (gap chegarasi) - qo'llanmaydi.
            if any(parts[i + k][2] for k in range(n - 1)) or any(parts[i + k][0] for k in range(1, n)):
                continue
            hit = e
            break
        if hit is None:
            out.append(words[i])
            i += 1
            continue
        n = len(hit.tokens)
        span = words[i:i + n]
        lead, trail = parts[i][0], parts[i + n - 1][2]
        new_toks = _cased(hit.right, parts[i][1]).split()
        new_toks[0] = lead + new_toks[0]
        new_toks[-1] = new_toks[-1] + trail
        orig = " ".join(w.text for w in span)
        confs = [w.conf for w in span if w.conf is not None]
        conf = min(confs) if confs else None
        if len(new_toks) == n:
            for w, t in zip(span, new_toks, strict=True):
                out.append(w.model_copy(update={"text": t, "original_text": w.text}))
        else:
            a, b = span[0].start_ms, span[-1].end_ms
            step = (b - a) / len(new_toks)
            for k, t in enumerate(new_toks):
                out.append(span[0].model_copy(update={
                    "text": t, "start_ms": int(a + k * step),
                    "end_ms": b if k == len(new_toks) - 1 else int(a + (k + 1) * step),
                    "conf": conf, "original_text": orig}))
        i += n
    return out


_ACTIVE: ContextVar[tuple[tuple[DictEntry, ...], float] | None] = ContextVar(
    "lahza_personal_dictionary", default=None)


@contextmanager
def use_dictionary(entries: Sequence[DictEntry],
                   conf_threshold: float = DEFAULT_CONF_THRESHOLD) -> Iterator[None]:
    """Shu blok (shu oqim) davomida ASR natijasiga lug'at qo'llanadi."""
    token = _ACTIVE.set((tuple(entries), conf_threshold))
    try:
        yield
    finally:
        _ACTIVE.reset(token)


def apply_active(words: list[Word]) -> list[Word]:
    """Faol lug'at bo'lmasa - o'zgarishsiz (ASR ulash nuqtasi)."""
    active = _ACTIVE.get()
    if not active or not active[0]:
        return words
    return apply_dictionary(words, active[0], active[1])
