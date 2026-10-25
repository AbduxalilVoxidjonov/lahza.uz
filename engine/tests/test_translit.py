import json
from pathlib import Path

import pytest
from _api_helpers import make_client, seed_episode
from conftest import make_words

import lahza_engine.core.export as export_mod
from lahza_engine.subtitle.ass import build_ass, build_srt, build_vtt, text_item_events
from lahza_engine.subtitle.style import StyleTemplate, template_from_dict
from lahza_engine.text.orthography import Orthography
from lahza_engine.text.translit import (
    CyrillicLexicon,
    Script,
    default_lexicon,
    display_text,
    load_lexicon,
    to_cyrillic,
)
from lahza_engine.timeline import Timeline


@pytest.mark.parametrize(
    "latin, cyrillic",
    [
        # Asosiy harflar va digraflar
        ("salom", "салом"),
        ("Toshkent", "Тошкент"),
        ("choy", "чой"),
        ("shahar", "шаҳар"),
        ("qishloq", "қишлоқ"),
        ("xabar", "хабар"),
        ("jahon", "жаҳон"),
        ("tong", "тонг"),  # ng -> нг
        ("bayram", "байрам"),
        # oʻ / gʻ - turli apostrof variantlari
        ("oʻzbek", "ўзбек"),
        ("o'zbek", "ўзбек"),
        ("o‘zbek", "ўзбек"),
        ("o’zbek", "ўзбек"),
        ("o`zbek", "ўзбек"),
        ("gʻoya", "ғоя"),
        ("tog'", "тоғ"),
        ("o’g’il", "ўғил"),
        # ye / yo / yu / ya
        ("yer", "ер"),
        ("yaxshi", "яхши"),
        ("dunyo", "дунё"),
        ("yulduz", "юлдуз"),
        ("Qayerda", "Қаерда"),
        ("sayyora", "сайёра"),
        ("yoʻl", "йўл"),  # yoʻ -> йў, ё emas
        ("yo'q", "йўқ"),
        ("kiyim", "кийим"),
        # e: so'z boshida va unlidan keyin э
        ("ekran", "экран"),
        ("Erkin", "Эркин"),
        ("poeziya", "поэзия"),
        ("aeroport", "аэропорт"),
        ("kecha", "кеча"),
        ("teatr", "театр"),
        # ts
        ("operatsiya", "операция"),
        ("revolyutsiya", "революция"),
        ("ketsa", "кетса"),  # qo'shimcha chegarasi: т+с
        ("aytsin", "айтсин"),
        # tutuq belgisi
        ("maʼno", "маъно"),
        ("ma'no", "маъно"),
        ("san’at", "санъат"),
        ("taʼlim", "таълим"),
        ("Is'hoq", "Исҳоқ"),  # s+ʼ+h - sh emas, tutuq tushadi
        ("s'yezd", "съезд"),
    ],
)
def test_words(latin: str, cyrillic: str) -> None:
    assert to_cyrillic(latin) == cyrillic


@pytest.mark.parametrize(
    "latin, cyrillic",
    [
        ("sentyabr", "сентябрь"),
        ("sentabr", "сентябрь"),
        ("oktyabr", "октябрь"),
        ("Yanvar", "январь".capitalize()),
        ("iyul", "июль"),
        ("aktyor", "актёр"),
        ("kompyuter", "компьютер"),
        ("obyekt", "объект"),
        ("obyektlar", "объектлар"),  # stem + qo'shimcha
        ("kompyuterda", "компьютерда"),
        ("sirk", "цирк"),
        ("sirka", "сирка"),  # sirk faqat butun so'z - sirka (sirka) buzilmaydi
        ("stansiyaga", "станцияга"),
        ("intervyu", "интервью"),
    ],
)
def test_exceptions(latin: str, cyrillic: str) -> None:
    assert to_cyrillic(latin) == cyrillic


@pytest.mark.parametrize(
    "latin, cyrillic",
    [
        ("OʻZBEKISTON", "ЎЗБЕКИСТОН"),
        ("O'zbekiston", "Ўзбекистон"),
        ("SHAHAR", "ШАҲАР"),
        ("Shahar", "Шаҳар"),
        ("CHIROY", "ЧИРОЙ"),
        ("YOʻL", "ЙЎЛ"),
        ("Yoʻq", "Йўқ"),
        ("YANGI", "ЯНГИ"),
        ("E", "Э"),
        ("MAʼNO", "МАЪНО"),
        ("OKTYABR", "ОКТЯБРЬ"),
        ("Sentyabr", "Сентябрь"),
        ("OBYEKTLAR", "ОБЪЕКТЛАР"),
    ],
)
def test_case_preserved(latin: str, cyrillic: str) -> None:
    assert to_cyrillic(latin) == cyrillic


@pytest.mark.parametrize(
    "text",
    [
        "https://lahza.uz/klip?id=12",
        "www.example.com",
        "info@lahza.uz",
        "@lahza_studio",
        "lahza.uz",
        "iPhone",
        "YouTube",
        "TikTok",
        "Facebook",
        "Windows",
        "Instagram",
        "Café",
        "2026",
        "3.14",
    ],
)
def test_protected_unchanged(text: str) -> None:
    assert to_cyrillic(text) == text


def test_sentence_with_numbers_and_punctuation() -> None:
    src = "5-sentyabrda, 2026-yil: “Lahza” Instagram'da 25% o'sdi! Batafsil: https://lahza.uz"
    assert to_cyrillic(src) == (
        "5-сентябрда, 2026-йил: “Лаҳза” Instagramʼda 25% ўсди! Батафсил: https://lahza.uz"
    )


def test_cyrillic_and_mixed_input_untouched() -> None:
    assert to_cyrillic("Ўзбекистон") == "Ўзбекистон"
    assert to_cyrillic("Привет dunyo") == "Привет дунё"


def test_idempotent_on_cyrillic_output() -> None:
    once = to_cyrillic("Oʻzbekiston maʼnaviyati va gʻoyalari")
    assert once == "Ўзбекистон маънавияти ва ғоялари"
    assert to_cyrillic(once) == once


def test_new_alphabet_letters_accepted() -> None:
    assert to_cyrillic("özbek toğ şahar çiroy") == "ўзбек тоғ шаҳар чирой"


def test_lexicon_extendable(tmp_path: Path) -> None:
    lex = default_lexicon().merged({"words": {"lahza": "ЛАҲЗА!"}, "keep": ["Toshkent"],
                                    "stems": {"blog": "блог"}})
    assert to_cyrillic("Lahza Toshkent bloglar", lex) == "ЛАҲЗА! Toshkent блоглар"
    # Asl lug'at o'zgarmaydi
    assert to_cyrillic("Lahza Toshkent") == "Лаҳза Тошкент"

    p = tmp_path / "extra.json"
    p.write_text(json.dumps({"words": {"o'tov": "ЎТОВ"}}, ensure_ascii=False), encoding="utf-8")
    lex2 = load_lexicon(p, extra=[CyrillicLexicon(keep=frozenset({"salom"}))])
    assert to_cyrillic("Oʻtov salom", lex2) == "ЎТОВ salom"  # lug'atdagi registr saqlanadi


def test_bundled_lexicon_is_valid() -> None:
    lex = default_lexicon()
    assert lex.words and lex.stems and lex.keep
    assert all(k == k.lower() for k in [*lex.words, *lex.stems, *lex.keep])


def test_display_text_modes() -> None:
    assert display_text("o'zbek", Orthography.NEW) == "özbek"
    assert display_text("o'zbek", Orthography.ASCII, Script.LATIN) == "o'zbek"
    assert display_text("o'zbek", Orthography.NEW, Script.CYRILLIC) == "ўзбек"
    assert display_text("o'zbek", Orthography.OFFICIAL, "cyrillic") == "ўзбек"


# --- Subtitr eksporti -------------------------------------------------------------------------


def test_style_script_default_and_old_templates() -> None:
    assert StyleTemplate().script is Script.LATIN
    # Eski (maydonsiz) shablon fayli ham o'qiladi.
    assert template_from_dict({"version": 1, "template": {"name": "Eski"}}).script is Script.LATIN
    assert StyleTemplate.model_validate({"script": "cyrillic"}).script is Script.CYRILLIC
    with pytest.raises(ValueError):
        StyleTemplate.model_validate({"script": "arab"})


def test_srt_vtt_cyrillic_and_latin_default() -> None:
    w = make_words("Oʻzbekiston yoʻli sentyabr", 1_000)
    tl = Timeline(1_000, 3_000)
    latin = build_srt(w, tl, style=StyleTemplate())
    assert "Oʻzbekiston yoʻli sentyabr" in latin  # standart xulq o'zgarmagan
    cyr = StyleTemplate(script=Script.CYRILLIC)
    assert "Ўзбекистон йўли сентябрь" in build_srt(w, tl, style=cyr)
    assert "Ўзбекистон йўли сентябрь" in build_vtt(w, tl, style=cyr)


def test_ass_cyrillic_with_uppercase_and_mask() -> None:
    w = make_words("yaxshi ahmoq shahar", 0)
    style = StyleTemplate(animation="none", uppercase=True, script=Script.CYRILLIC,
                          mask_profanity=True, profanity_words=["ahmoq"])
    doc = build_ass(w, Timeline(0, 2_000), style)
    assert "ЯХШИ А**** ШАҲАР" in doc
    assert "yaxshi" not in doc.lower()


def test_text_items_cyrillic() -> None:
    class _Item:
        kind, position, animation, font_size = "title", "upper", "none", None
        text, start_ms, end_ms = "Yangi epizod", 0, 1_000

    _, events = text_item_events([_Item()], StyleTemplate(script=Script.CYRILLIC))
    assert events and events[0].endswith("Янги эпизод")


def test_preview_api_script_override(tmp_path: Path, monkeypatch) -> None:
    c, st = make_client(tmp_path, monkeypatch)
    _, eid, _ = seed_episode(st, tmp_path)
    clip = c.post(f"/v1/episodes/{eid}/clips", json={"start_sentence_id": 2, "end_sentence_id": 4}).json()
    url = f"/v1/episodes/{eid}/clips/{clip['id']}:preview"
    seen: list[str] = []

    def fake(conn, media_id, clip, t_out_ms, style, settings, out_jpg, detector=None):
        seen.append(style.script.value)
        out_jpg.write_bytes(b"\xff\xd8\xff\xe0fakejpeg")
        return out_jpg

    monkeypatch.setattr(export_mod, "render_preview_frame", fake, raising=False)
    assert c.post(url, json={"t_ms": 0}).status_code == 200
    assert c.post(url, json={"t_ms": 0, "script": "cyrillic"}).status_code == 200
    assert c.post(url, json={"t_ms": 0, "style": {"script": "cyrillic"}}).status_code == 200
    assert c.post(url, json={"t_ms": 0, "script": "arab"}).status_code == 422
    assert seen == ["latin", "cyrillic", "cyrillic"]
