import pytest

from lahza_engine.text.orthography import (
    APOSTROPHE,
    TURNED_COMMA,
    Orthography,
    convert,
    fold_for_match,
    normalize,
)

TC, AP = TURNED_COMMA, APOSTROPHE


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("o'zbek", f"o{TC}zbek"),
        ("O`zbekiston", f"O{TC}zbekiston"),
        ("tog’", f"tog{TC}"),
        ("g‘oya", f"g{TC}oya"),
        ("ma'no", f"ma{AP}no"),
        ("ta’lim", f"ta{AP}lim"),
        ("san'at", f"san{AP}at"),
        ("maʻno", f"ma{AP}no"),  # noto'g'ri U+02BB tutuq o'rnida
        (f"o{TC}qituvchi", f"o{TC}qituvchi"),  # allaqachon to'g'ri - o'zgarmaydi
        ("'salom' dedi", "'salom' dedi"),  # qo'shtirnoq tegilmaydi
    ],
)
def test_normalize(raw: str, expected: str) -> None:
    assert normalize(raw) == expected


def test_normalize_idempotent() -> None:
    s = "O'zbekiston ma'naviyati va g'oyalari"
    assert normalize(normalize(s)) == normalize(s)


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("o'zbek tili", "özbek tili"),
        ("tog' va shahar", "toğ va şahar"),
        ("Choyxona", "Çoyxona"),
        ("SHAHAR", "ŞAHAR"),
        ("G'afur O'g'li", "Ğafur Öğli"),
        ("Is'hoq", f"Is{AP}hoq"),  # tutuq bilan ajratilgan s+h digraf emas
        ("ma'no", f"ma{AP}no"),
    ],
)
def test_new_alphabet(raw: str, expected: str) -> None:
    assert convert(raw, Orthography.NEW) == expected


def test_ascii_mode() -> None:
    assert convert(f"o{TC}zbek ma{AP}no", Orthography.ASCII) == "o'zbek ma'no"


def test_fold_for_match() -> None:
    assert fold_for_match("O‘ZBEK") == "o'zbek"
