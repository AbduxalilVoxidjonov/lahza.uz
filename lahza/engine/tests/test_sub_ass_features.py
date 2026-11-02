"""M3-SUB-1: pop animatsiyasi, kalit so'z, to'ldiruvchi so'zlar, so'kinish maskasi; VTT."""

from conftest import make_words

from lahza_engine.subtitle.ass import build_ass, build_srt, build_vtt, mask_word
from lahza_engine.subtitle.style import StyleTemplate
from lahza_engine.text.orthography import Orthography
from lahza_engine.timeline import Timeline


def _events(doc: str) -> list[str]:
    return [x for x in doc.splitlines() if x.startswith("Dialogue:")]


def _texts(doc: str) -> str:
    return " | ".join(e.split(",", 9)[9] for e in _events(doc))


def test_pop_animation_scales_from_pop_scale_to_100_at_word_start() -> None:
    w = make_words("bir ikki uch", 0)
    doc = build_ass(w, Timeline(0, 2_000), StyleTemplate(animation="pop", pop_scale=130))
    ev = _events(doc)
    assert len(ev) == 3
    assert "{\\c&H0000D4FF\\fscx130\\fscy130\\t(0,150,\\fscx100\\fscy100)}ikki" in ev[1]
    # faol bo'lmagan so'z animatsiyasiz
    assert ev[1].split(",", 9)[9].startswith("bir {")
    # har qator faol so'z boshida boshlanadi: \t vaqti shu qatorga nisbatan
    assert ev[1].startswith("Dialogue: 0,0:00:00.35,")


def test_karaoke_has_no_scale_and_pop_100_has_no_transform() -> None:
    w = make_words("bir ikki", 0)
    assert "\\fscx" not in build_ass(w, Timeline(0, 1_000), StyleTemplate())
    assert "\\t(" not in build_ass(w, Timeline(0, 1_000), StyleTemplate(animation="pop", pop_scale=100))


def test_keywords_highlighted_and_bold_regardless_of_case_and_punct() -> None:
    w = make_words("Bu juda MUHIM, gap", 0)
    style = StyleTemplate(animation="none", bold=False, max_words=4, keywords=["muhim"])
    doc = build_ass(w, Timeline(0, 2_000), style)
    text = _texts(doc)
    assert "{\\c&H0000D4FF\\b1}MUHIM,{\\c&H00FFFFFF\\b0}" in text
    assert text.startswith("Bu juda {")  # "Bu juda" oddiy


def test_keyword_matches_apostrophe_variants() -> None:
    w = make_words("o‘zbek tili", 0)
    doc = build_ass(w, Timeline(0, 1_000), StyleTemplate(animation="none", keywords=["o'zbek"]))
    assert "\\b1}oʻzbek" in doc  # rasmiy imlo saqlanadi


def test_remove_fillers_only_from_subtitles() -> None:
    w = make_words("ee salom mmm, dunyo Hmm", 0)
    style = StyleTemplate(animation="none", remove_fillers=True, max_words=8)
    text = _texts(build_ass(w, Timeline(0, 3_000), style))
    assert text == "salom | dunyo"  # o'chirilgan joyda pauza qoladi -> bo'linadi
    # o'chirilmaganda saqlanadi
    assert "mmm" in build_ass(w, Timeline(0, 3_000), StyleTemplate(animation="none", max_words=8))
    srt = build_srt(w, Timeline(0, 3_000), style=style)
    assert "mmm" not in srt and "salom" in srt


def test_mask_profanity_keeps_first_letter_and_punct() -> None:
    assert mask_word("ahmoq,") == "a****,"
    assert mask_word("«ahmoq»") == "«a****»"
    assert mask_word("a") == "a"
    w = make_words("sen Ahmoq!", 0)
    style = StyleTemplate(animation="none", mask_profanity=True, profanity_words=["ahmoq"])
    assert "A****!" in build_ass(w, Timeline(0, 1_000), style)
    off = StyleTemplate(animation="none", mask_profanity=False, profanity_words=["ahmoq"])
    assert "Ahmoq!" in build_ass(w, Timeline(0, 1_000), off)


def test_mask_and_uppercase_with_new_orthography() -> None:
    w = make_words("go'zal shahar", 0)
    style = StyleTemplate(animation="none", uppercase=True, orthography=Orthography.NEW,
                          mask_profanity=True, profanity_words=["shahar"])
    doc = build_ass(w, Timeline(0, 1_000), style)
    assert "GÖZAL" in doc.upper() and "Ş****" in doc  # şahar -> ş**** -> Ş****


def test_offset_drops_finished_lines_and_shifts() -> None:
    w = make_words("bir ikki uch tort besh olti", 0, word_ms=900, gap_ms=100)
    doc = build_ass(w, Timeline(0, 6_000), StyleTemplate(max_words=2), offset_ms=2_500)
    ev = _events(doc)
    assert ev and ev[0].startswith("Dialogue: 0,0:00:00.00,")
    assert "bir" not in "".join(ev)


def test_vtt_format_and_style() -> None:
    w = make_words("o'zbek tilida subtitr", 1_000)
    vtt = build_vtt(w, Timeline(1_000, 3_000), style=StyleTemplate(orthography=Orthography.ASCII))
    assert vtt.startswith("WEBVTT\n\n00:00:00.000 --> 00:00:01.")
    assert "o'zbek tilida subtitr" in vtt
    assert "," not in vtt.splitlines()[2]  # VTT'da millisekund nuqta bilan
    plain = build_vtt(w, Timeline(1_000, 3_000))
    assert "o'zbek" in plain
