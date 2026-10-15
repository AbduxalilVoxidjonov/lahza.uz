"""M3-SUB-3: yetkaziladigan shriftlar papkasi va o'zbek glif testi (fontTools)."""

from pathlib import Path

from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen

from lahza_engine.subtitle.fonts import REQUIRED_GLYPHS, default_fonts_dir, has_fonts, list_fonts


def _make_font(path: Path, family: str, chars: str) -> Path:
    names = [".notdef"] + [f"uni{ord(c):04X}" for c in chars]
    fb = FontBuilder(1000, isTTF=True)
    fb.setupGlyphOrder(names)
    fb.setupCharacterMap({ord(c): f"uni{ord(c):04X}" for c in chars})
    pen = TTGlyphPen(None)
    pen.moveTo((0, 0))
    pen.lineTo((0, 500))
    pen.lineTo((500, 0))
    pen.closePath()
    g = pen.glyph()
    fb.setupGlyf({n: g for n in names})
    fb.setupHorizontalMetrics({n: (600, 0) for n in names})
    fb.setupHorizontalHeader(ascent=800, descent=-200)
    fb.setupNameTable({"familyName": family, "styleName": "Regular"})
    fb.setupOS2()
    fb.setupPost()
    fb.save(str(path))
    return path


def test_glyph_check(tmp_path) -> None:
    latin = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ'"
    _make_font(tmp_path / "Tola.ttf", "Tola", latin + REQUIRED_GLYPHS)
    (tmp_path / "sub").mkdir()
    _make_font(tmp_path / "sub" / "Kam.ttf", "Kam", latin + "ÖöĞğ")
    (tmp_path / "buzuq.otf").write_bytes(b"emas")
    (tmp_path / "izoh.txt").write_text("x")
    fonts = {f.family: f for f in list_fonts(tmp_path)}
    assert set(fonts) == {"Tola", "Kam"}
    assert fonts["Tola"].ok and fonts["Tola"].missing == []
    kam = fonts["Kam"]
    assert not kam.ok
    assert "ʻ" in kam.missing and "Ş" in kam.missing and "Ö" not in kam.missing
    assert kam.path.endswith("Kam.ttf")


def test_fonts_dir_env_and_missing_dir(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("LAHZA_FONTS_DIR", str(tmp_path / "f"))
    assert default_fonts_dir() == tmp_path / "f"
    assert list_fonts() == [] and not has_fonts()
    (tmp_path / "f").mkdir()
    _make_font(tmp_path / "f" / "A.ttf", "A", "a")
    assert has_fonts() and [f.family for f in list_fonts()] == ["A"]
    monkeypatch.delenv("LAHZA_FONTS_DIR")
    assert default_fonts_dir().name == "fonts" and default_fonts_dir().parent.name == "subtitle"
