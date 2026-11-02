"""O'zbek lotin imlosi: normallashtirish va uch rejim o'rtasida o'girish.

Ichki saqlash har doim RASMIY (amaldagi) imloda: oʻ/gʻ uchun U+02BB, tutuq uchun U+02BC.
Boshqa rejimlar faqat ko'rsatish/render paytida qo'llanadi (ADR-0008).

Manbalar (docs/08-ozbek-imlosi.md):
* Oʻ/Gʻ = harf + U+02BB; U+2018/U+2019 o'zbek lotinida qo'shtirnoq vazifasini bajaradi.
* Yangi alifbo (Senat, 2026-09-10): Gʻ->Ğ, Oʻ->Ö, Sh->Ş, Ch->Ç. Qonun rasmiy e'lon qilingach,
  qoidalar uning matni bo'yicha qayta tekshiriladi (TZ 19-bo'lim).
"""

from __future__ import annotations

import re
import unicodedata
from enum import StrEnum

TURNED_COMMA = "ʻ"  # ʻ  (oʻ, gʻ)
APOSTROPHE = "ʼ"  # ʼ  (tutuq belgisi)

# Klaviatura va ASR chiqaradigan barcha apostrof variantlari.
_APOS_VARIANTS = "'`‘’ʻʼ´ʹ"
_APOS_CLASS = "[" + re.escape(_APOS_VARIANTS) + "]"

_OG_RE = re.compile(r"([oOgG])" + _APOS_CLASS)
# o/g dan keyingisi allaqachon U+02BB; qolgan "harf + apostrof + harf" -> tutuq.
_TUTUQ_RE = re.compile(r"(?<=[^\W\d_])(?<![oOgG])" + _APOS_CLASS + r"(?=[^\W\d_])")


class Orthography(StrEnum):
    OFFICIAL = "official"  # oʻzbek, togʻ, maʼno
    ASCII = "ascii"  # o'zbek, tog', ma'no
    NEW = "new"  # özbek, toğ, şahar, çiroy


def normalize(text: str) -> str:
    """Matnni ichki (rasmiy) ko'rinishga keltiradi.

    * Unicode NFC.
    * o/O/g/G dan keyingi har qanday apostrof varianti -> U+02BB.
    * Ikki harf orasidagi qolgan apostroflar -> tutuq U+02BC.
    * So'z chegarasidagi apostroflar (qo'shtirnoq) o'zgarmaydi.
    """
    text = unicodedata.normalize("NFC", text)
    text = _OG_RE.sub(lambda m: m.group(1) + TURNED_COMMA, text)
    text = _TUTUQ_RE.sub(APOSTROPHE, text)
    return text


def to_ascii(text: str) -> str:
    return text.replace(TURNED_COMMA, "'").replace(APOSTROPHE, "'")


_NEW_MAP = [
    ("o" + TURNED_COMMA, "ö"),
    ("O" + TURNED_COMMA, "Ö"),
    ("g" + TURNED_COMMA, "ğ"),
    ("G" + TURNED_COMMA, "Ğ"),
]
_DIGRAPH_RE = re.compile(r"([sScC])([hH])")


def _digraph(m: re.Match[str]) -> str:
    first = m.group(1)
    upper = first.isupper()
    if first in "sS":
        return "Ş" if upper else "ş"
    return "Ç" if upper else "ç"


def to_new_alphabet(text: str) -> str:
    """Rasmiy imlodan yangi alifboga.

    Tutuq bilan ajratilgan s+ʼ+h (masalan, Isʼhoq) digraf hisoblanmaydi, chunki
    orada U+02BC turadi va regex faqat yonma-yon s/h ni ushlaydi.
    """
    text = normalize(text)
    for src, dst in _NEW_MAP:
        text = text.replace(src, dst)
    return _DIGRAPH_RE.sub(_digraph, text)


def convert(text: str, mode: Orthography) -> str:
    text = normalize(text)
    if mode is Orthography.OFFICIAL:
        return text
    if mode is Orthography.ASCII:
        return to_ascii(text)
    return to_new_alphabet(text)


def fold_for_match(text: str) -> str:
    """Qidiruv va qoidalarni solishtirish uchun: kichik harf, apostroflar bir xil."""
    return to_ascii(normalize(text)).lower()


REQUIRED_GLYPHS = TURNED_COMMA + APOSTROPHE + "ÖöĞğŞşÇç" + "ЎўҚқҒғҲҳ"
"""Shrift glif testida tekshiriladigan belgilar (TZ 9-bo'lim)."""
