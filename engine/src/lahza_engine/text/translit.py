"""Lotin o'zbekcha -> kirill o'zbekcha transliteratsiya (PRO-4, TZ 9-bo'lim "Kirill (v1.1)").

Kirish avval rasmiy imloga keltiriladi (`normalize`), so'ng so'zma-so'z o'giriladi:

* oʻ->ў, gʻ->ғ, sh->ш, ch->ч, q->қ, h->ҳ, x->х, j->ж, y->й; ng -> нг (alohida harf emas).
* ye/yo/yu/ya -> е/ё/ю/я (lekin yoʻ -> йў: yoʻl -> йўл).
* e so'z boshida va unlidan keyin -> э, qolgan joyda -> е.
* ts so'z boshida/oxirida va "tsi"+unli/y oldidan -> ц (operatsiya -> операция);
  qolgan joyda т+с, chunki o'zbek fe'llarida t+s qo'shimcha chegarasi (ketsa -> кетса).
* Tutuq ʼ -> ъ (maʼno -> маъно); s/c bilan h ni ajratgan tutuq tushib qoladi (Isʼhoq -> Исҳоқ).
* Bir ma'noli bo'lmagan holatlar (ь, ц, ruscha o'zlashmalar) - `data/cyrillic.json` lug'ati.

Raqamlar, URL/e-pochta/@nomlar va lotin brendlar (c/w harfli, ichida katta harfli - iPhone,
YouTube - yoki `keep` ro'yxatidagi) o'zgarmaydi. Kirill matn ham tegilmaydi.
"""

from __future__ import annotations

import json
import os
import re
import unicodedata
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from functools import lru_cache
from pathlib import Path

from lahza_engine.text.orthography import APOSTROPHE, TURNED_COMMA, Orthography, convert, normalize

LEXICON_PATH = Path(__file__).parent / "data" / "cyrillic.json"


class Script(StrEnum):
    LATIN = "latin"
    CYRILLIC = "cyrillic"


_MAP = {
    "a": "а", "b": "б", "d": "д", "f": "ф", "g": "г", "h": "ҳ", "i": "и", "j": "ж", "k": "к",
    "l": "л", "m": "м", "n": "н", "o": "о", "p": "п", "q": "қ", "r": "р", "s": "с", "t": "т",
    "u": "у", "v": "в", "x": "х", "y": "й", "z": "з",
    # Yangi alifbo harflari ham qabul qilinadi (matn shu rejimda saqlangan bo'lsa).
    "ö": "ў", "ğ": "ғ", "ş": "ш", "ç": "ч",
}
_IOTATED = {"e": "е", "o": "ё", "u": "ю", "a": "я"}
_VOWELS = frozenset("aeiouö")
_UZ_LATIN = frozenset(_MAP) | {"e", "c"}

# Himoyalangan bo'laklar (URL, e-pochta, @nom, domen) va lotin so'zlar.
_TOKEN_RE = re.compile(
    r"(?P<keep>(?:https?://|www\.)\S+"
    r"|[\w.+-]+@[\w-]+(?:\.[\w-]+)+"
    r"|@\w+"
    r"|\b[\w-]+(?:\.[\w-]+)*\.(?:uz|com|ru|org|net|io|me|app|tv)\b(?:/\S*)?)"
    r"|(?P<word>[^\W\d_]+)"
)
_MIXED_CASE_RE = re.compile(r"[a-z][A-Z]")


@dataclass(frozen=True)
class CyrillicLexicon:
    """Istisnolar lug'ati. Kalitlar rasmiy imloda va kichik harfda saqlanadi."""

    words: Mapping[str, str] = field(default_factory=dict)
    stems: Mapping[str, str] = field(default_factory=dict)
    keep: frozenset[str] = frozenset()

    @classmethod
    def from_dict(cls, data: Mapping) -> CyrillicLexicon:
        return cls(
            words={_key(k): v for k, v in (data.get("words") or {}).items()},
            stems={_key(k): v for k, v in (data.get("stems") or {}).items()},
            keep=frozenset(_key(k) for k in (data.get("keep") or ())),
        )

    def merged(self, other: CyrillicLexicon | Mapping) -> CyrillicLexicon:
        """Foydalanuvchi lug'ati bilan kengaytirish (`other` ustun)."""
        o = other if isinstance(other, CyrillicLexicon) else CyrillicLexicon.from_dict(other)
        return CyrillicLexicon(
            words={**self.words, **o.words},
            stems={**self.stems, **o.stems},
            keep=self.keep | o.keep,
        )

    def stem_for(self, key: str) -> str | None:
        """So'z boshiga mos eng uzun stem (so'zning o'zidan qisqa bo'lmasa ham bo'ladi)."""
        best = None
        for s in self.stems:
            if key.startswith(s) and (best is None or len(s) > len(best)):
                best = s
        return best


def _key(word: str) -> str:
    return normalize(word.strip()).lower()


def load_lexicon(path: str | os.PathLike[str] | None = None,
                 extra: Iterable[CyrillicLexicon | Mapping] = ()) -> CyrillicLexicon:
    """JSON lug'atni o'qiydi (standart: paket ichidagi `data/cyrillic.json`) va `extra` bilan kengaytiradi."""
    data = json.loads(Path(path or LEXICON_PATH).read_text(encoding="utf-8"))
    lex = CyrillicLexicon.from_dict(data)
    for e in extra:
        lex = lex.merged(e)
    return lex


@lru_cache(maxsize=1)
def default_lexicon() -> CyrillicLexicon:
    return load_lexicon()


def _cased(out: str, upper: bool) -> str:
    return out.upper() if upper else out


def _apply_case(src: str, dst: str) -> str:
    """Lug'atdan olingan so'zga manbaning registr ko'rinishini beradi."""
    cased = [c for c in src if c.isupper() or c.islower()]
    if not cased:
        return dst
    if len(cased) > 1 and all(c.isupper() for c in cased):
        return dst.upper()
    if cased[0].isupper():
        return dst[:1].upper() + dst[1:]
    return dst


def _is_foreign(word: str) -> bool:
    """Lotin brend/xorijiy so'z: c (ch emas), w, o'zbek lotinida yo'q harf yoki ichida katta harf."""
    low = word.lower()
    for i, c in enumerate(low):
        if c in (TURNED_COMMA, APOSTROPHE):
            continue
        if c == "c" and low[i + 1:i + 2] != "h":
            return True
        if c.isascii() and c not in _UZ_LATIN:
            return True  # w
        if not c.isascii() and c not in _UZ_LATIN and "a" <= _fold_latin(c) <= "z":
            return True  # é, ü, ñ ...
    return bool(_MIXED_CASE_RE.search(word))


def _fold_latin(c: str) -> str:
    base = unicodedata.normalize("NFD", c)[0]
    return base.lower()


def _translit_word(word: str, prev: str = "start") -> str:
    """Bitta so'z (faqat harflar va ʻ/ʼ). prev: "start" | "vowel" | "cons" | "tutuq"."""
    out: list[str] = []
    n = len(word)
    low = word.lower()
    i = 0
    while i < n:
        ch, lc = word[i], low[i]
        up = ch.isupper()
        nxt = low[i + 1] if i + 1 < n else ""
        if lc in "og" and nxt == TURNED_COMMA:
            out.append(_cased("ў" if lc == "o" else "ғ", up))
            prev = "vowel" if lc == "o" else "cons"
            i += 2
            continue
        if lc in "sc" and nxt == "h":
            out.append(_cased("ш" if lc == "s" else "ч", up))
            prev, i = "cons", i + 2
            continue
        if lc == "t" and nxt == "s":
            after = low[i + 2:i + 4]
            if prev == "start" or i + 2 == n or (after[:1] == "i" and after[1:2] in _VOWELS | {"y"}):
                out.append(_cased("ц", up))
                prev, i = "cons", i + 2
                continue
        if lc == "y" and nxt in _IOTATED and not (nxt == "o" and low[i + 2:i + 3] == TURNED_COMMA):
            out.append(_cased(_IOTATED[nxt], up))
            prev, i = "vowel", i + 2
            continue
        if lc == "e":
            out.append(_cased("э" if prev in ("start", "vowel") else "е", up))
            prev, i = "vowel", i + 1
            continue
        if ch == APOSTROPHE:
            if 0 < i < n - 1:
                if low[i - 1] in "sc" and nxt == "h":
                    pass  # Isʼhoq -> Исҳоқ: tutuq faqat sh/ch emasligini bildiradi
                else:
                    out.append(_cased("ъ", word[i - 1].isupper() and word[i + 1].isupper()))
                prev = "tutuq"
            else:
                out.append(ch)
            i += 1
            continue
        mapped = _MAP.get(lc)
        if mapped is None:
            out.append(ch)  # kirill yoki boshqa belgi - o'zgarmaydi
            prev = "cons"
        else:
            out.append(_cased(mapped, up))
            prev = "vowel" if lc in _VOWELS else "cons"
        i += 1
    return "".join(out)


def _prev_after(latin: str) -> str:
    last = latin[-1:].lower()
    if last == TURNED_COMMA:
        return "vowel" if latin[-2:-1].lower() == "o" else "cons"
    if last == APOSTROPHE:
        return "tutuq"
    return "vowel" if last in _VOWELS else "cons"


def _word(word: str, lex: CyrillicLexicon) -> str:
    key = word.lower()
    # Brend + tutuqli qo'shimcha (Instagramʼda) - butun so'z lotinda qoladi.
    head = word.split(APOSTROPHE, 1)[0]
    if key in lex.keep or head.lower() in lex.keep or _is_foreign(head):
        return word
    if key in lex.words:
        return _apply_case(word, lex.words[key])
    stem = lex.stem_for(key)
    if stem:
        head, tail = word[:len(stem)], word[len(stem):]
        return _apply_case(head, lex.stems[stem]) + _translit_word(tail, _prev_after(stem))
    return _translit_word(word)


def to_cyrillic(text: str, lexicon: CyrillicLexicon | None = None) -> str:
    """Lotin o'zbekcha matnni kirillga o'giradi (istisnolar lug'ati bilan)."""
    lex = lexicon or default_lexicon()
    text = normalize(text)

    def sub(m: re.Match[str]) -> str:
        w = m.group("word")
        return m.group(0) if w is None else _word(w, lex)

    return _TOKEN_RE.sub(sub, text)


def display_text(text: str, orthography: Orthography, script: Script | str = Script.LATIN) -> str:
    """Subtitr/eksport matni: kirill tanlansa transliteratsiya, aks holda imlo rejimi."""
    if script == Script.CYRILLIC:
        return to_cyrillic(text)
    return convert(text, orthography)
