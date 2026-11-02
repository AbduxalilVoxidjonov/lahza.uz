"""Video shablonlar: o'rnatilganlari, fayl import/eksport, validatsiya (templates/store.py)."""

from __future__ import annotations

import json
import types
from pathlib import Path

import pytest

from lahza_engine.templates import store
from lahza_engine.templates.model import Template
from lahza_engine.templates.store import (
    TemplateError,
    builtin_templates,
    get_builtin,
    load_template_file,
    parse_template,
    save_template_file,
    validate_template,
)

BUILTIN_IDS = {
    "uz.lahza.tpl.podcast-hook",
    "uz.lahza.tpl.event-rhythm",
    "uz.lahza.tpl.product-promo",
    "uz.lahza.tpl.interview-clean",
    "uz.lahza.tpl.course-announce",
    "uz.lahza.tpl.daily-story",
}


def test_builtin_ids_and_locales() -> None:
    ts = builtin_templates()
    assert {t.id for t in ts} >= BUILTIN_IDS
    for t in ts:
        assert t.builtin
        for lt in (t.name, t.description):
            assert lt is not None
            assert lt.uz and lt.uz_Cyrl and lt.ru and lt.en, t.id
        assert t.to_json()["schema"] == "lahza.template/1"


def test_builtin_recipes_match_contract() -> None:
    p = get_builtin("uz.lahza.tpl.podcast-hook")
    assert p.selection == "highlight" and p.captions and p.intro is None and p.outro is not None
    assert 30_000 <= p.target_duration_ms <= 45_000
    assert any(r.plugin == "uz.lahza.motion.punch-in" and r.trigger == "on_emphasis" and r.max_count == 3
               for r in p.fx)
    assert p.transition is not None and p.transition.plugin == "uz.lahza.tr.cut"
    assert p.caption_style is not None and p.caption_style.animation == "karaoke"

    e = get_builtin("uz.lahza.tpl.event-rhythm")
    assert e.selection == "scenes" and e.mute_sources and e.music and e.music.required
    assert 20_000 <= e.target_duration_ms <= 30_000 and (e.min_shot_ms, e.max_shot_ms) == (1200, 3000)
    assert e.transition is not None and (e.transition.plugin, e.transition.dur_ms) == ("uz.lahza.tr.dissolve", 300)
    assert any(r.plugin == "uz.lahza.motion.push-in" for r in e.fx)

    pr = get_builtin("uz.lahza.tpl.product-promo")
    assert pr.intro and pr.intro.kind == "card" and pr.outro and pr.color == "uz.lahza.color.vivid"

    i = get_builtin("uz.lahza.tpl.interview-clean")
    assert i.selection == "highlight" and i.captions and i.hook_text and i.hook_text.kind == "lower_third"
    assert i.transition is not None and i.transition.plugin == "uz.lahza.tr.fade"

    c = get_builtin("uz.lahza.tpl.course-announce")
    assert c.hook_text and c.captions and c.outro

    d = get_builtin("uz.lahza.tpl.daily-story")
    assert d.order == "xronologik" and d.selection == "scenes" and d.color == "uz.lahza.color.warm"
    assert d.transition is not None and d.transition.plugin == "uz.lahza.tr.slideup"
    assert d.music is not None and not d.music.required


def test_builtins_are_copies() -> None:
    a = get_builtin("uz.lahza.tpl.podcast-hook")
    a.target_duration_ms = 99_000
    assert get_builtin("uz.lahza.tpl.podcast-hook").target_duration_ms != 99_000
    with pytest.raises(KeyError):
        get_builtin("uz.lahza.tpl.yoq")


def test_builtins_pass_fx_registry() -> None:
    pytest.importorskip("lahza_engine.fx.registry")
    for t in builtin_templates():
        validate_template(t, check_fx=True)


def test_save_load_roundtrip(tmp_path: Path) -> None:
    t = get_builtin("uz.lahza.tpl.product-promo")
    p = save_template_file(t, tmp_path / "sub" / "promo.json")
    data = json.loads(p.read_text(encoding="utf-8"))
    assert data["schema"] == "lahza.template/1" and data["builtin"] is False
    assert data["name"]["uz-Cyrl"] == t.name.uz_Cyrl
    back = load_template_file(p)
    assert not back.builtin
    assert back.model_copy(update={"builtin": True}) == t


def _write(tmp_path: Path, data: object) -> Path:
    p = tmp_path / "t.json"
    p.write_text(json.dumps(data, ensure_ascii=False) if not isinstance(data, str) else data, encoding="utf-8")
    return p


def _base() -> dict:
    return get_builtin("uz.lahza.tpl.daily-story").model_copy(update={"id": "user.test-1"}).to_json()


@pytest.mark.parametrize(
    ("mutate", "match"),
    [
        (lambda d: d.update(schema="lahza.recipe/1"), "shabloni emas"),
        (lambda d: d.update(id="Yomon ID!"), "id"),
        (lambda d: d.update(target_duration_ms=1000), "target_duration_ms"),
        (lambda d: d.update(min_shot_ms=5000, max_shot_ms=2000), "max_shot_ms"),
        (lambda d: d.update(hook_text={"text": "{nomi}", "dur_ms": 2000}), "o'rinbosar"),
        (lambda d: d.update(hook_text={"text": "   ", "dur_ms": 2000}), "bo'sh"),
        (lambda d: d.update(intro={"text": "X", "dur_ms": 9000}, outro={"text": "Y", "dur_ms": 9000},
                            target_duration_ms=15_000), "intro va outro"),
        (lambda d: d.update(transition={"plugin": "uz.lahza.tr.fade", "dur_ms": 1000}), "o'tish"),
        (lambda d: d.update(fx=[{"plugin": "uz.lahza.motion.pan", "trigger": "every_n"}]), "every_n"),
        (lambda d: d.update(intro={"text": "X", "background": "qizil"}), "fon"),
    ],
)
def test_invalid_templates(tmp_path: Path, mutate, match: str) -> None:  # type: ignore[no-untyped-def]
    d = _base()
    mutate(d)
    with pytest.raises(TemplateError, match=match):
        load_template_file(_write(tmp_path, d))


def test_bad_files(tmp_path: Path) -> None:
    with pytest.raises(TemplateError, match="topilmadi"):
        load_template_file(tmp_path / "yoq.json")
    with pytest.raises(TemplateError, match="JSON emas"):
        load_template_file(_write(tmp_path, "{buzilgan"))
    with pytest.raises(TemplateError, match="obyekt"):
        load_template_file(_write(tmp_path, [1, 2]))
    big = tmp_path / "big.json"
    big.write_text(" " * (store.MAX_FILE_BYTES + 1))
    with pytest.raises(TemplateError, match="katta"):
        load_template_file(big)


class _FakeManifest:
    def __init__(self, pid: str, kind: str) -> None:
        self.id, self.kind = pid, kind


def _fake_registry(known: dict[str, str]) -> types.SimpleNamespace:
    def get_plugin(pid: str) -> _FakeManifest:
        if pid not in known:
            raise KeyError(pid)
        return _FakeManifest(pid, known[pid])

    def validate_params(m: _FakeManifest, params: dict) -> dict:
        if "yomon" in params:
            raise ValueError("noma'lum parametr 'yomon'")
        return params

    return types.SimpleNamespace(get_plugin=get_plugin, validate_params=validate_params)


def test_fx_validation_with_fake_registry(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    known = {"uz.lahza.tr.slideup": "transition", "uz.lahza.color.warm": "color",
             "uz.lahza.motion.push-in": "motion", "uz.lahza.tr.fade": "transition"}
    monkeypatch.setattr(store, "_registry", lambda: _fake_registry(known))
    assert load_template_file(_write(tmp_path, _base())).id == "user.test-1"

    d = _base()
    d["fx"] = [{"plugin": "uz.lahza.motion.yoq", "trigger": "on_cut"}]
    with pytest.raises(TemplateError, match="o'rnatilmagan"):
        load_template_file(_write(tmp_path, d))
    d = _base()
    d["color"] = "uz.lahza.tr.fade"
    with pytest.raises(TemplateError, match="turi"):
        load_template_file(_write(tmp_path, d))
    d = _base()
    d["transition"] = {"plugin": "uz.lahza.motion.push-in", "dur_ms": 300}
    with pytest.raises(TemplateError, match="turi"):
        load_template_file(_write(tmp_path, d))
    d = _base()
    d["fx"] = [{"plugin": "uz.lahza.motion.push-in", "trigger": "on_cut", "params": {"yomon": 1}}]
    with pytest.raises(TemplateError, match="parametr"):
        load_template_file(_write(tmp_path, d))


def test_fx_validation_skipped_without_registry(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(store, "_registry", lambda: None)
    d = _base()
    d["fx"] = [{"plugin": "uz.lahza.motion.kelajakda", "trigger": "on_cut"}]
    assert parse_template(d).fx[0].plugin == "uz.lahza.motion.kelajakda"


def test_real_registry_rejects_unknown_plugin() -> None:
    pytest.importorskip("lahza_engine.fx.registry")
    d = _base()
    d["fx"] = [{"plugin": "uz.lahza.motion.kelajakda", "trigger": "on_cut"}]
    with pytest.raises(TemplateError):
        parse_template(d)


def test_template_model_direct() -> None:
    t = Template(id="user.min", name={"uz": "Minimal"})
    assert validate_template(t, check_fx=False) is t
