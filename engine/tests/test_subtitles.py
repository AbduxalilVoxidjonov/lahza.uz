import re

from conftest import make_words

from lahza_engine.subtitle.ass import ass_time, build_ass, build_srt
from lahza_engine.subtitle.layout import chunk_words
from lahza_engine.subtitle.style import StyleTemplate, ass_color
from lahza_engine.text.orthography import Orthography
from lahza_engine.timeline import Timeline


def test_timeline_with_cuts() -> None:
    tl = Timeline(10_000, 20_000, cuts=[(12_000, 13_000), (15_000, 16_000)])
    assert tl.duration_ms == 8_000
    assert tl.to_out(10_000) == 0
    assert tl.to_out(12_500) is None
    assert tl.to_out(13_000) == 2_000
    assert tl.to_out(20_000) == 8_000
    assert tl.clamp_to_out(15_500) == tl.to_out(16_000)


def test_ass_time_and_color() -> None:
    assert ass_time(3_723_450) == "1:02:03.45"
    assert ass_color("#FFD400") == "&H0000D4FF"
    assert ass_color("#000000", 0.5) == "&H80000000"


def test_chunking_keeps_number_with_unit() -> None:
    w = make_words("Bizda 25 foiz o'sish bo'ldi", 0)
    chunks = chunk_words(w, max_words=2, max_lines=1, max_chars=30)
    texts = [" ".join(x.text for x in c.words) for c in chunks]
    assert any("25 foiz" in t for t in texts)


def test_chunking_breaks_on_pause() -> None:
    w = make_words("bir ikki", 0) + make_words("uch", 5_000)
    chunks = chunk_words(w, max_words=4, max_lines=2, max_chars=30)
    assert len(chunks) == 2


def test_build_ass_karaoke_and_safe_zone() -> None:
    w = make_words("o'zbek tilida gaplashamiz", 1_000)
    tl = Timeline(1_000, 5_000)
    style = StyleTemplate(max_words=3, orthography=Orthography.NEW)
    doc = build_ass(w, tl, style)
    assert "PlayResX: 1080" in doc and "PlayResY: 1920" in doc
    # pastki 35% xavfsiz zona: MarginV = 672
    assert re.search(r"Style: Default,.*,2,64,64,672,1$", doc, flags=re.M)
    events = [x for x in doc.splitlines() if x.startswith("Dialogue:")]
    assert len(events) == 3  # har so'z uchun bitta faol holat
    assert events[0].startswith("Dialogue: 0,0:00:00.00,")
    assert "özbek" in doc  # yangi alifbo render paytida qo'llandi
    assert "\\c&H0000D4FF" in events[1]


def test_words_inside_cut_are_dropped() -> None:
    w = make_words("bir ikki uch tort", 0, word_ms=900, gap_ms=100)
    tl = Timeline(0, 4_000, cuts=[(1_000, 2_000)])
    doc = build_ass(w, tl, StyleTemplate(max_words=4, animation="none"))
    assert "ikki" not in doc and "bir" in doc and "uch" in doc


def test_srt() -> None:
    w = make_words("salom dunyo bu test", 0)
    srt = build_srt(w, Timeline(0, 2_000))
    assert srt.startswith("1\n00:00:00,000 --> ")
