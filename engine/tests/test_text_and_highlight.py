import json

from conftest import make_sentences, make_words

from lahza_engine.config import HighlightConfig
from lahza_engine.highlight.boundaries import snap
from lahza_engine.highlight.finder import find_highlights, iou, lite_candidates, nms
from lahza_engine.highlight.llm import Window, make_windows, parse_response, render_prompt
from lahza_engine.highlight.rules import is_question, start_penalty
from lahza_engine.highlight.schema import json_schema
from lahza_engine.highlight.signals import SignalReport, compute_signals, loudness_db
from lahza_engine.text.sentences import build_sentences


def test_sentences_split_on_punct_pause_and_speaker() -> None:
    w = make_words("Salom do'stlar. Bugun mavzu", 0) + make_words("muhim", 5000)
    w += make_words("Ha albatta", 6000, speaker="B")
    for x in w[:5]:
        x.speaker = "A"
    s = build_sentences(w, max_gap_ms=700)
    texts = [x.text for x in s]
    assert texts[0] == "Salom do'stlar."
    assert texts[1] == "Bugun mavzu"  # uzun pauzadan oldin
    assert texts[-1] == "Ha albatta"  # spiker almashdi
    assert [x.id for x in s] == list(range(len(s)))


def test_snap_never_cuts_words_and_respects_bounds() -> None:
    sents = make_sentences(20)
    cfg = HighlightConfig(min_clip_ms=30_000, max_clip_ms=60_000)
    span = snap(sents, 3, 6, cfg)
    assert 30_000 <= span.duration_ms <= 60_000
    first, last = sents[span.start_id], sents[span.end_id]
    assert span.start_ms <= first.start_ms and span.end_ms >= last.end_ms
    if span.start_id > 0:
        assert span.start_ms > sents[span.start_id - 1].end_ms
    if span.end_id + 1 < len(sents):
        assert span.end_ms < sents[span.end_id + 1].start_ms


def test_snap_shrinks_too_long() -> None:
    sents = make_sentences(30)
    cfg = HighlightConfig(min_clip_ms=15_000, max_clip_ms=30_000)
    span = snap(sents, 0, 20, cfg)
    assert span.duration_ms <= 30_000


def test_start_penalty_rules() -> None:
    assert start_penalty("Va keyin u ketdi")[0] > 0
    assert start_penalty("Lekin bu boshqa gap")[0] > 0
    assert start_penalty("Shuning uchun men aytdim")[0] > 0
    assert start_penalty("U juda yaxshi odam")[0] > 0
    assert start_penalty("Uchinchi qoida shunday")[0] == 0  # "u" so'z emas, prefiks
    assert start_penalty("Biznesda eng katta xato")[0] == 0


def test_is_question() -> None:
    assert is_question("Nega bunday bo'ldi")
    assert is_question("Siz rozimisiz?")
    assert not is_question("Men roziman.")


def test_loudness_and_signals() -> None:
    import numpy as np

    sr = 16000
    pcm = np.concatenate([np.zeros(sr * 6), 0.5 * np.ones(sr * 6)]).astype(np.float32)
    db = loudness_db(pcm, sr)
    assert db[-1] > db[0]
    sents = make_sentences(2, dur_ms=5000, pause_ms=1000)
    rep = compute_signals(sents, pcm, sr)
    assert rep.sentences[1].loudness_z > rep.sentences[0].loudness_z


def test_windows_cover_everything_with_overlap() -> None:
    sents = make_sentences(200, dur_ms=6000)
    cfg = HighlightConfig(llm_window_ms=120_000, llm_window_overlap_ms=30_000)
    ws = make_windows(sents, cfg)
    assert ws[0].first_id == 0 and ws[-1].last_id == len(sents) - 1
    for a, b in zip(ws, ws[1:], strict=False):
        assert b.first_id <= a.last_id  # ustma-ust
        assert b.first_id > a.first_id  # oldinga siljiydi


def test_prompt_contains_ids_and_rules() -> None:
    sents = make_sentences(5)
    p = render_prompt(sents, Window(0, 4), HighlightConfig(), focus="ta'lim")
    assert "0 | - |" in p and "4 | - |" in p and "ta'lim" in p


def _cand(**kw):
    base = {"start_id": 2, "end_id": 6, "hook_id": 3, "turi": "maslahat", "mustaqil": True,
            "ballar": {"hook": 8, "mustaqillik": 9, "hissiyot": 6, "foyda": 9, "aniqlik": 8},
            "sarlavha": "Eng katta xato", "sabab": "aniq xulosa", "izoh_matni": "...",
            "heshteglar": ["podkast", "#biznes"]}
    base.update(kw)
    return base


def test_parse_response_validates_window_and_schema() -> None:
    w = Window(0, 10)
    raw = json.dumps({"nomzodlar": [_cand(), _cand(end_id=50), _cand(hook_id=99), _cand(turi="yo'q")]})
    out = parse_response(raw, w)
    assert len(out) == 1
    assert out[0].heshteglar == ["#podkast", "#biznes"]
    assert parse_response("bu JSON emas", w) == []


def test_json_schema_is_valid_object() -> None:
    s = json_schema()
    assert s["type"] == "object" and "nomzodlar" in s["properties"]


def test_find_highlights_lite_mode() -> None:
    sents = make_sentences(40)
    cfg = HighlightConfig(clip_count=5)
    clips = find_highlights("m", sents, SignalReport(), cfg)
    assert 0 < len(clips) <= 5
    for c in clips:
        assert c.source == "ai_lite" and c.title
    spans = lite_candidates(sents, cfg)
    assert all(cfg.min_clip_ms * 0.8 <= s.duration_ms <= cfg.max_clip_ms for s in spans)


def test_find_highlights_llm_mode_uses_llm_fields() -> None:
    from lahza_engine.highlight.schema import LlmCandidate

    sents = make_sentences(40)
    c = LlmCandidate.model_validate(_cand(start_id=10, end_id=14, hook_id=11))
    clips = find_highlights("m", sents, SignalReport(), HighlightConfig(), [c], "qwen")
    assert len(clips) == 1
    assert clips[0].title == "Eng katta xato" and clips[0].llm_model_id == "qwen"
    assert clips[0].hook_sentence_id == 11


def test_nms_removes_overlaps() -> None:
    from lahza_engine.highlight.boundaries import ClipSpan
    from lahza_engine.highlight.finder import Scored

    a = Scored(ClipSpan(0, 1, 0, 10_000), 90)
    b = Scored(ClipSpan(0, 1, 1_000, 11_000), 80)
    c = Scored(ClipSpan(5, 6, 50_000, 60_000), 70)
    kept = nms([a, b, c], 0.3, 10)
    assert kept == [a, c]
    assert iou(a.span, b.span) > 0.8
