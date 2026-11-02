from pathlib import Path

from _api_helpers import make_client, seed_episode, wait_job

from lahza_engine.align.realign import distribute, realign_sentence
from lahza_engine.api.routes_episodes import lexicon_for
from lahza_engine.core.services import Services
from lahza_engine.db import store as db
from lahza_engine.types import Sentence, Word


def test_get_episode(tmp_path: Path, monkeypatch) -> None:
    c, st = make_client(tmp_path, monkeypatch)
    sid, eid, pdir = seed_episode(st, tmp_path)
    r = c.get(f"/v1/episodes/{eid}").json()
    assert r["id"] == eid and r["show_id"] == sid and r["status"] == "ready"
    assert r["media"]["width"] == 1920 and r["media"]["fps"] == 25.0
    assert r["highlight_mode"] is None
    assert c.get("/v1/episodes/yoq").status_code == 404


def test_word_replace_split_delete(tmp_path: Path, monkeypatch) -> None:
    c, st = make_client(tmp_path, monkeypatch)
    _, eid, pdir = seed_episode(st, tmp_path)
    url = f"/v1/episodes/{eid}/words"
    conn = db.open_project(pdir)
    orig = db.load_sentence(conn, eid, 2)
    assert orig is not None

    # 1) almashtirish: vaqtlar saqlanadi
    r = c.patch(url, json={"sentence_id": 2, "ord": 0, "text": "Salom"}).json()
    s = r["sentence"]
    assert r["ok"] and s["words"][0]["text"] == "Salom" and s["words"][0]["edited"]
    assert s["words"][0]["original_text"] == orig.words[0].text
    assert s["words"][0]["start_ms"] == orig.words[0].start_ms
    assert s["text"].startswith("Salom ")

    # 2) bo'linish: eski so'z oralig'i ichida taqsimlanadi, qolganlar o'zgarmaydi
    r = c.patch(url, json={"sentence_id": 2, "ord": 1, "text": "ikki so'z"}).json()["sentence"]
    assert len(r["words"]) == len(orig.words) + 1
    a, b = r["words"][1], r["words"][2]
    assert orig.words[1].start_ms == a["start_ms"] < a["end_ms"] <= b["start_ms"] < b["end_ms"]
    assert b["end_ms"] <= orig.words[1].end_ms
    assert r["words"][3]["start_ms"] == orig.words[2].start_ms

    # 3) o'chirish: ord qayta raqamlanadi
    r = c.patch(url, json={"sentence_id": 2, "ord": 0, "text": "  "}).json()["sentence"]
    assert len(r["words"]) == len(orig.words)
    assert r["words"][0]["text"] == "ikki"
    ords = [x[0] for x in conn.execute(
        "SELECT ord FROM words WHERE media_id = ? AND sentence_id = 2 ORDER BY ord", (eid,))]
    assert ords == list(range(len(orig.words)))
    text = conn.execute("SELECT text FROM sentences WHERE media_id = ? AND id = 2", (eid,)).fetchone()[0]
    assert text == r["text"]
    corr = conn.execute("SELECT audio_chunk_path, before_text, after_text, sentence_id FROM corrections"
                        " ORDER BY id").fetchall()
    assert len(corr) == 3 and corr[0]["before_text"] == orig.text
    assert corr[0]["audio_chunk_path"] == f"cache/audio16k.wav#{orig.start_ms}-{orig.end_ms}"
    assert corr[-1]["sentence_id"] == 2

    assert c.patch(url, json={"sentence_id": 99, "ord": 0, "text": "x"}).status_code == 404
    assert c.patch(url, json={"sentence_id": 2, "ord": 99, "text": "x"}).status_code == 404


class FakeAligner:
    def __init__(self) -> None:
        self.calls: list[tuple[int, int, int]] = []

    def align_words(self, words, wav_path, start_ms, end_ms):
        assert Path(wav_path).exists()
        self.calls.append((len(words), start_ms, end_ms))
        step = (end_ms - start_ms) // len(words)
        return [w.model_copy(update={"start_ms": start_ms + i * step,
                                     "end_ms": start_ms + (i + 1) * step - 1, "text": "X"})
                for i, w in enumerate(words)]


def test_word_edit_uses_aligner_for_that_sentence_only(tmp_path: Path, monkeypatch) -> None:
    c, st = make_client(tmp_path, monkeypatch)
    _, eid, pdir = seed_episode(st, tmp_path)
    al = FakeAligner()
    svc = Services()
    svc.aligner = al  # type: ignore[attr-defined]
    st._services = svc
    conn = db.open_project(pdir)
    before_other = db.load_sentence(conn, eid, 3)
    r = c.patch(f"/v1/episodes/{eid}/words", json={"sentence_id": 2, "ord": 0, "text": "Yangi"}).json()
    s2 = db.load_sentence(conn, eid, 2)
    assert len(al.calls) == 1 and al.calls[0][1:] == (s2.start_ms, s2.end_ms)
    assert r["sentence"]["words"][0]["text"] == "Yangi"  # aligner matnni o'zgartirmaydi
    assert r["sentence"]["words"][1]["start_ms"] == s2.start_ms + (s2.end_ms - s2.start_ms) // 12
    assert db.load_sentence(conn, eid, 3) == before_other


def test_realign_sentence_rules() -> None:
    words = [Word(text="bir", start_ms=0, end_ms=300), Word(text="ikkinchi", start_ms=400, end_ms=900)]
    s = Sentence(id=0, start_ms=0, end_ms=1000, words=words)
    assert realign_sentence(s, None, None).words == words  # soni o'zgarmadi -> saqlanadi
    out = realign_sentence(s, None, None, original_count=3)
    assert out.words[0].start_ms == 0 and out.words[-1].end_ms == 1000
    assert out.words[1].end_ms - out.words[1].start_ms > out.words[0].end_ms - out.words[0].start_ms
    zero = s.model_copy(update={"words": [*words, Word(text="yangi", start_ms=900, end_ms=900)]})
    assert all(w.end_ms > w.start_ms for w in realign_sentence(zero, None, None).words)
    assert distribute([], 0, 10) == []

    class Broken:
        def align_words(self, *a):
            raise RuntimeError("x")

    assert realign_sentence(s, Path(__file__), Broken()).words == words


def test_waveform(tmp_path: Path, monkeypatch) -> None:
    c, st = make_client(tmp_path, monkeypatch)
    _, eid, pdir = seed_episode(st, tmp_path, n=3)
    r = c.get(f"/v1/episodes/{eid}/waveform", params={"buckets": 100}).json()
    assert len(r["peaks"]) == 100 and max(r["peaks"]) == 1.0 and min(r["peaks"]) >= 0
    assert abs(r["duration_ms"] - (db.load_transcript(db.open_project(pdir), eid).sentences[-1].end_ms + 500)) <= 1
    assert list((pdir / "cache").glob("waveform-100-*.json"))
    assert c.get(f"/v1/episodes/{eid}/waveform", params={"buckets": 100}).json() == r
    assert c.get(f"/v1/episodes/{eid}/waveform", params={"buckets": 1}).status_code == 422
    _, eid2, _ = seed_episode(st, tmp_path, n=2, wav=False, show_name="B")
    assert c.get(f"/v1/episodes/{eid2}/waveform").status_code == 404


def test_speakers(tmp_path: Path, monkeypatch) -> None:
    c, st = make_client(tmp_path, monkeypatch)
    _, eid, _ = seed_episode(st, tmp_path)
    url = f"/v1/episodes/{eid}/speakers"
    assert c.get(url).json() == [{"label": "SPEAKER_00", "display_name": None},
                                 {"label": "SPEAKER_01", "display_name": None}]
    assert c.patch(f"{url}/SPEAKER_01", json={"display_name": " Aziza "}).json() == {"ok": True}
    assert c.get(url).json()[1] == {"label": "SPEAKER_01", "display_name": "Aziza"}
    c.patch(f"{url}/SPEAKER_01", json={"display_name": ""})
    assert c.get(url).json()[1]["display_name"] is None
    assert c.patch(f"{url}/SPEAKER_09", json={"display_name": "x"}).status_code == 404


def test_lexicon_feeds_analysis_and_reanalyze(tmp_path: Path, monkeypatch) -> None:
    c, st = make_client(tmp_path, monkeypatch)
    sid, eid, _ = seed_episode(st, tmp_path)
    c.post("/v1/lexicon", json={"show_id": sid, "term": "Lahza", "variants": ["laxza", "Lahsa"],
                                "kind": "brend"})
    c.post("/v1/lexicon", json={"term": "Toshkent", "variants": ["tashkent"], "kind": "atama"})
    other = c.post("/v1/projects", json={"name": "Boshqa"}).json()["id"]
    c.post("/v1/lexicon", json={"show_id": other, "term": "Begona", "kind": "ism"})
    hot, mp = lexicon_for(st, sid)
    assert hot == ["Lahza", "Toshkent"]
    assert mp["laxza"] == "Lahza" and mp["lahsa"] == "Lahza" and mp["tashkent"] == "Toshkent"
    assert "begona" not in mp

    seen: dict = {}

    def fake_analyze(ctx, settings):
        seen.update(ctx.services)
        return {"highlight": {"mode": "lite", "clips": ["a", "b"]}}

    monkeypatch.setattr("lahza_engine.core.analyze.analyze", fake_analyze)
    r = c.post(f"/v1/episodes/{eid}:reanalyze", json={"force_lite": True, "focus": "biznes"})
    assert r.status_code == 200 and r.json()["kind"] == "analyze"
    job = wait_job(st, r.json()["id"])
    assert job.status == "done" and job.result["clips"] == 2
    assert seen["hotwords"] == hot and seen["lexicon_map"]["laxza"] == "Lahza"
    assert seen["force_lite"] is True and seen["focus"] == "biznes" and "aligner" in seen
    ep = c.get(f"/v1/episodes/{eid}").json()
    assert ep["highlight_mode"] == "lite" and ep["status"] == "ready"
    assert c.post("/v1/episodes/yoq:reanalyze", json={}).status_code == 404


def test_reanalyze_failure_marks_failed(tmp_path: Path, monkeypatch) -> None:
    c, st = make_client(tmp_path, monkeypatch)
    _, eid, _ = seed_episode(st, tmp_path)

    def boom(ctx, settings):
        raise RuntimeError("yiqildi")

    monkeypatch.setattr("lahza_engine.core.analyze.analyze", boom)
    job = wait_job(st, c.post(f"/v1/episodes/{eid}:reanalyze").json()["id"])
    assert job.status == "failed"
    assert c.get(f"/v1/episodes/{eid}").json()["status"] == "failed"
