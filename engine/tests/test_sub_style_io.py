"""M3-SUB-2: shablonni JSON fayl orqali almashish."""

import json

import pytest

from lahza_engine.subtitle.style import (
    TEMPLATE_VERSION,
    StyleTemplate,
    TemplateError,
    load_template,
    save_template,
)


def test_roundtrip_with_version(tmp_path) -> None:
    t = StyleTemplate(name="Brend", highlight_color="#ff0000", animation="pop", pop_scale=140,
                      keywords=["pul", " "], logo_position="bottom_left", logo_opacity=0.5)
    p = save_template(t, tmp_path / "s" / "brend.json")
    data = json.loads(p.read_text(encoding="utf-8"))
    assert data["version"] == TEMPLATE_VERSION and data["template"]["pop_scale"] == 140
    back = load_template(p)
    assert back == t
    assert back.highlight_color == "#FF0000" and back.keywords == ["pul"]


def test_bare_legacy_and_unknown_fields(tmp_path) -> None:
    p = tmp_path / "eski.json"
    p.write_text(json.dumps({"name": "Eski", "font_size": 64, "kelajak_maydoni": 1}), "utf-8")
    t = load_template(p)
    assert t.name == "Eski" and t.font_size == 64 and t.pop_scale == 115


def test_newer_version_and_invalid(tmp_path) -> None:
    p = tmp_path / "yangi.json"
    p.write_text(json.dumps({"version": TEMPLATE_VERSION + 1, "template": {}}), "utf-8")
    with pytest.raises(TemplateError, match="yangilang"):
        load_template(p)
    p.write_text(json.dumps({"version": 1, "template": {"pop_scale": 300}}), "utf-8")
    with pytest.raises(TemplateError, match="pop_scale"):
        load_template(p)
    p.write_text("{buzuq", "utf-8")
    with pytest.raises(TemplateError, match="JSON"):
        load_template(p)
    with pytest.raises(TemplateError, match="topilmadi"):
        load_template(tmp_path / "yoq.json")
