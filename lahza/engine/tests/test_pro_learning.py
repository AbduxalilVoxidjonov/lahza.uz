"""PRO-1 (shaxsiy lug'at) va PRO-6 (real natijalardan ball vaznlari)."""

from __future__ import annotations

import json
import random
import sqlite3
from pathlib import Path

import pytest
from _api_helpers import make_client, seed_episode, wait_job

from lahza_engine.asr.base import dedupe_overlaps
from lahza_engine.config import HighlightConfig
from lahza_engine.db import store as db
from lahza_engine.highlight import learning as hl
from lahza_engine.text import personal_dict as pd
from lahza_engine.types import Clip, ClipSource, Word


def W(text: str, conf: float | None = 0.5, t: int = 0, edited: bool = False) -> Word:
    return Word(text=text, start_ms=t, end_ms=t + 300, conf=conf, edited=edited)


# ---- Lug'at yig'ish ---------------------------------------------------------------------------


def test_diff_pairs_word_level() -> None:
    assert pd.diff_pairs("Bugun laxza haqida.", "Bugun Lahza haqida.") == [("laxza", "Lahza")]
    # tinish belgisi o'zgarishi - juftlik emas; faqat bosh harf - juftlik
    assert pd.diff_pairs("salom, dunyo", "salom dunyo!") == []
    assert pd.diff_pairs("men toshkentdan", "men Toshkentdan") == [("toshkentdan", "Toshkentdan")]
    # qo'shish/o'chirish - ASR manbasi yo'q
    assert pd.diff_pairs("bir ikki", "bir yangi ikki") == []
    assert pd.diff_pairs("bir ikki uch", "bir uch") == []
    # ko'p so'zli (<= 3) va juda uzun oraliqlar
    assert pd.diff_pairs("abdu xalil keldi", "Abduxalil keldi") == [("abdu xalil", "Abduxalil")]
    assert pd.diff_pairs("a b c d e", "x y z w v") == []


def test_resolve_requires_repetition_and_majority() -> None:
    rows = [pd.DictEntry("laxza", "Lahza", 3, "ism"), pd.DictEntry("laxza", "Lahsa", 1, "ism"),
            pd.DictEntry("bir", "bor", 1), pd.DictEntry("kod", "kot", 2), pd.DictEntry("kod", "god", 2)]
    act = {(e.wrong, e.right) for e in pd.resolve(rows)}
    assert ("laxza", "Lahza") not in act  # 3/4 = 0.75 < 0.8 - ziddiyatli
    assert pd.resolve(rows, min_share=0.7)[0].right == "Lahza"
    assert not any(w == "bir" for w, _ in act)  # bir marta - takrorlanmagan
    assert not any(w == "kod" for w, _ in act)  # 50/50 - ziddiyat
    # zanjir A->B, B->C qo'llanmaydi; bosh harf tuzatish qo'llanadi
    chain = pd.resolve([pd.DictEntry("a1", "b1", 2), pd.DictEntry("b1", "c1", 2),
                        pd.DictEntry("toshkent", "Toshkent", 2, "ism")])
    assert {(e.wrong, e.right) for e in chain} == {("b1", "c1"), ("toshkent", "Toshkent")}


def test_hotwords_only_names_and_terms() -> None:
    es = [pd.DictEntry("laxza", "Lahza", 5, "ism"), pd.DictEntry("bor", "bir", 9, "soz"),
          pd.DictEntry("ai", "sun'iy intellekt", 2, "atama")]
    assert pd.hotwords(es) == ["Lahza", "sun'iy intellekt"]


# ---- Qo'llash chegaralari ---------------------------------------------------------------------


ENTRIES = [pd.DictEntry("laxza", "Lahza", 3, "ism"), pd.DictEntry("abdu xalil", "Abduxalil", 2, "ism"),
           pd.DictEntry("toshkent", "Toshkent", 2, "ism"), pd.DictEntry("ai", "sun'iy intellekt", 2, "atama")]


def _texts(ws: list[Word]) -> list[str]:
    return [w.text for w in ws]


def test_apply_exact_word_boundaries_only() -> None:
    out = pd.apply_dictionary([W("laxzaxon"), W("xlaxza"), W("laxza,"), W("(Laxza)")], ENTRIES)
    assert _texts(out) == ["laxzaxon", "xlaxza", "Lahza,", "(Lahza)"]
    assert out[2].original_text == "laxza,"


def test_apply_respects_confidence_and_user_edits() -> None:
    ws = [W("laxza", conf=0.95), W("laxza", conf=0.3), W("laxza", conf=None), W("laxza", edited=True)]
    assert _texts(pd.apply_dictionary(ws, ENTRIES)) == ["laxza", "Lahza", "Lahza", "laxza"]
    assert _texts(pd.apply_dictionary(ws, ENTRIES, conf_threshold=0.2)) == ["laxza", "laxza", "Lahza", "laxza"]


def test_apply_multiword_and_capitalization() -> None:
    ws = [W("Abdu", t=0), W("xalil", t=400), W("keldi.", t=800)]
    out = pd.apply_dictionary(ws, ENTRIES)
    assert _texts(out) == ["Abduxalil", "keldi."]
    assert out[0].start_ms == 0 and out[0].end_ms == 700 and out[0].original_text == "Abdu xalil"
    # gap chegarasidan o'tmaydi
    assert _texts(pd.apply_dictionary([W("abdu."), W("xalil")], ENTRIES)) == ["abdu.", "xalil"]
    # 1 -> 2 so'z: vaqt teng bo'linadi, uzluksiz
    out = pd.apply_dictionary([W("Ai", t=1000)], ENTRIES)
    assert _texts(out) == ["Sun'iy", "intellekt"]
    assert out[0].start_ms == 1000 and out[0].end_ms == out[1].start_ms and out[1].end_ms == 1300
    assert _texts(pd.apply_dictionary([W("Toshkent")], ENTRIES)) == ["Toshkent"]
    assert pd.apply_dictionary([], ENTRIES) == [] and _texts(pd.apply_dictionary([W("x")], [])) == ["x"]


def test_asr_hook_only_inside_active_context() -> None:
    ws = [W("laxza", t=0), W("salom", t=400)]
    assert _texts(dedupe_overlaps(ws)) == ["laxza", "salom"]
    with pd.use_dictionary(ENTRIES):
        assert _texts(dedupe_overlaps(ws)) == ["Lahza", "salom"]
    assert _texts(dedupe_overlaps(ws)) == ["laxza", "salom"]


# ---- Vaznlarni o'rganish ----------------------------------------------------------------------


def _samples(n: int, seed: int = 1, signal_matters: bool = True) -> list[hl.Sample]:
    rng = random.Random(seed)
    out = []
    for _ in range(n):
        llm, sig = rng.uniform(30, 90), rng.uniform(30, 90)
        base = sig if signal_matters else llm
        views = int(10 ** (2 + base / 30 + rng.gauss(0, 0.2)))
        out.append(hl.Sample({"llm": llm, "signal": sig}, views, views // 20))
    return out


def test_weights_need_min_samples() -> None:
    res = hl.fit_weights(_samples(hl.MIN_SAMPLES - 1))
    assert not res.learned and res.weights == hl.default_weights()
    # LLM komponenti yo'q (Lite) namunalar hisobga olinmaydi
    lite = [hl.Sample({"signal": 50.0 + i}, 100 * i) for i in range(30)]
    assert not hl.fit_weights(lite).learned
    const = [hl.Sample({"llm": 50.0, "signal": 50.0}, 100 * i) for i in range(30)]
    assert hl.fit_weights(const).reason == "xususiyatlar o'zgarmas"


def test_weights_move_cautiously_in_right_direction() -> None:
    d = hl.default_weights()
    res = hl.fit_weights(_samples(12))
    assert res.learned and res.weights["weight_signals"] > d["weight_signals"]
    assert abs(sum(res.weights.values()) - sum(d.values())) < 1e-3
    # kam namunada standartga yaqin (Bayes qisqartirish), ko'p namunada kuchliroq, lekin chegarada
    many = hl.fit_weights(_samples(400))
    assert many.weights["weight_signals"] > res.weights["weight_signals"]
    assert hl.BOUNDS[0] - 1e-6 <= min(many.weights.values()) and max(many.weights.values()) <= hl.BOUNDS[1] + 1e-6
    assert res.weights["weight_signals"] - d["weight_signals"] < 0.5
    other = hl.fit_weights(_samples(400, signal_matters=False))
    assert other.weights["weight_llm"] > d["weight_llm"]


def test_weights_stable_order_and_outlier() -> None:
    s = _samples(40, seed=7)
    a = hl.fit_weights(s).weights
    assert hl.fit_weights(list(reversed(s))).weights == a  # tartibga bog'liq emas, siljish yo'q
    outlier = [*s, hl.Sample({"llm": 95.0, "signal": 5.0}, 10**9, 10**7)]
    b = hl.fit_weights(outlier).weights
    assert all(abs(a[k] - b[k]) < 0.15 for k in a)  # bitta g'ayrioddiy natija vaznni ag'darmaydi


def test_apply_weights_to_config() -> None:
    cfg = hl.apply_weights(HighlightConfig(), {"weight_llm": 0.4, "weight_signals": 0.6, "boshqa": 1})
    assert (cfg.weight_llm, cfg.weight_signals) == (0.4, 0.6)
    assert hl.apply_weights(HighlightConfig(), None) == HighlightConfig()
    assert hl.features_of({"llm": 60, "signal": 40, "x": 1}) == {"llm": 60.0, "signal": 40.0}


# ---- Migratsiya v4 -> v5 ----------------------------------------------------------------------


def test_library_v4_to_v5(tmp_path: Path) -> None:
    conn = db.open_library(tmp_path)
    with conn:
        conn.executescript("DROP TABLE personal_dictionary; DROP TABLE clip_metrics;"
                           " DROP TABLE highlight_weights; UPDATE schema_version SET version = 4;"
                           " INSERT INTO shows(id, name) VALUES ('s1', 'Shou');"
                           " INSERT INTO episodes(id, show_id, title, project_dir) VALUES ('e1','s1','E','/x');")
    conn.close()
    conn = db.open_library(tmp_path)
    assert db.schema_version(conn) == db.LIBRARY_SCHEMA_VERSION == 5
    assert (tmp_path / "library.v4.bak").exists()
    with conn:
        conn.execute("INSERT INTO personal_dictionary(wrong, right) VALUES ('a', 'b')")
        conn.execute("INSERT INTO clip_metrics(episode_id, show_id, clip_id, views) VALUES ('e1','s1','c1',5)")
        conn.execute("INSERT INTO highlight_weights(scope) VALUES ('global')")
    with pytest.raises(sqlite3.IntegrityError), conn:
        conn.execute("INSERT INTO personal_dictionary(wrong, right) VALUES ('a', 'b')")
    with pytest.raises(sqlite3.IntegrityError), conn:
        conn.execute("INSERT INTO clip_metrics(episode_id, clip_id, views) VALUES ('e1','c2',-1)")
    with conn:
        conn.execute("DELETE FROM shows WHERE id = 's1'")
    assert conn.execute("SELECT count(*) FROM clip_metrics").fetchone()[0] == 0
    conn.close()


# ---- API ------------------------------------------------------------------------------------


def _edit(c, eid: str, sid: int, text: str) -> None:
    r = c.patch(f"/v1/episodes/{eid}/words", json={"sentence_id": sid, "ord": 0, "text": text})
    assert r.status_code == 200


def test_dictionary_api_and_analysis_wiring(tmp_path: Path, monkeypatch) -> None:
    c, st = make_client(tmp_path, monkeypatch)
    sid, eid, pdir = seed_episode(st, tmp_path)
    for s in (0, 1):
        _edit(c, eid, s, "laxza")
        _edit(c, eid, s, "Lahza")
    d = c.get("/v1/dictionary").json()
    by = {(e["wrong"], e["right"]): e for e in d["entries"]}
    e = by[("laxza", "Lahza")]
    assert e["count"] == 2 and e["active"] and e["kind"] == "ism" and d["min_count"] == 2
    assert not any(x["active"] for k, x in by.items() if k != ("laxza", "Lahza"))
    assert c.get("/v1/dictionary:export").json()["format"] == "lahza.dictionary/1"

    seen: dict = {}

    def fake_analyze(ctx, settings):
        seen["hotwords"] = ctx.services["hotwords"]
        seen["post"] = [w.text for w in dedupe_overlaps([W("laxza", conf=0.4)])]
        seen["settings"] = settings
        return {"highlight": {"mode": "lite", "clips": []}}

    monkeypatch.setattr("lahza_engine.core.analyze.analyze", fake_analyze)
    job = wait_job(st, c.post(f"/v1/episodes/{eid}:reanalyze", json={"force_lite": True}).json()["id"])
    assert job.status == "done"
    assert "Lahza" in seen["hotwords"] and seen["post"] == ["Lahza"]
    assert seen["settings"] is st.settings  # o'rganilgan vazn yo'q - standart sozlama

    # fine-tune manifesti: 2 ta tuzatilgan gap, audio yo'l + vaqt, yakuniy matn
    lines = [json.loads(x) for x in c.get("/v1/dictionary/finetune-manifest").text.splitlines()]
    assert [x["sentence_id"] for x in lines] == [0, 1]
    assert lines[0]["text"].startswith("Lahza") and not lines[0]["asr_text"].startswith("Lahza")
    assert lines[0]["audio"] == str(pdir / "cache" / "audio16k.wav") and lines[0]["audio_exists"]
    assert lines[0]["end_ms"] > lines[0]["start_ms"] and lines[0]["project_id"] == sid
    assert c.get("/v1/dictionary/finetune-manifest?project_id=yoq").text == ""
    r = c.post("/v1/dictionary/finetune-manifest:export", json={"out_path": str(tmp_path / "m")}).json()
    assert r["segments"] == 2 and Path(r["path"]).name == "m.jsonl"
    assert len(Path(r["path"]).read_text(encoding="utf-8").splitlines()) == 2
    assert c.post("/v1/dictionary/finetune-manifest:export",
                  json={"out_path": str(tmp_path / "yoq" / "m.jsonl")}).status_code == 400

    r = c.post("/v1/dictionary:export", json={"out_path": str(tmp_path)}).json()
    assert Path(r["path"]).name == "lahza-dictionary.json" and r["entries"] == len(by)
    saved = json.loads(Path(r["path"]).read_text(encoding="utf-8"))
    assert saved["format"] == "lahza.dictionary/1" and len(saved["entries"]) == len(by)

    assert c.delete(f"/v1/dictionary/{e['id']}").json()["ok"]
    assert c.delete(f"/v1/dictionary/{e['id']}").status_code == 404
    assert ("laxza", "Lahza") not in {(x["wrong"], x["right"]) for x in c.get("/v1/dictionary").json()["entries"]}


def _seed_clips(pdir: Path, eid: str, n: int) -> list[str]:
    conn = db.open_project(pdir)
    clips = [Clip(id=f"k{i}", media_id=eid, start_ms=i * 1000, end_ms=i * 1000 + 900,
                  start_sentence_id=0, end_sentence_id=0, score=50,
                  scores={"llm": 30 + (i * 37) % 60, "signal": 30 + (i * 53) % 60},
                  source=ClipSource.AI_LLM) for i in range(n)]
    db.save_clips(conn, clips)
    conn.close()
    return [c.id for c in clips]


def test_metrics_learn_and_reset(tmp_path: Path, monkeypatch) -> None:
    c, st = make_client(tmp_path, monkeypatch)
    sid, eid, pdir = seed_episode(st, tmp_path)
    ids = _seed_clips(pdir, eid, 12)
    url = f"/v1/episodes/{eid}/clips"
    assert c.put(f"{url}/yoq/metrics", json={"views": 1}).status_code == 404
    assert c.put(f"{url}/k0/metrics", json={"views": -1}).status_code == 422
    w0 = c.get(f"/v1/highlight/weights?project_id={sid}").json()
    assert w0["source"] == "default" and not w0["learned"] and w0["min_samples"] == hl.MIN_SAMPLES

    conn = db.open_project(pdir)
    clips = {k.id: k for k in db.load_clips(conn, eid)}
    conn.close()
    for i, cid in enumerate(ids):
        sig = clips[cid].scores["signal"]
        r = c.put(f"{url}/{cid}/metrics", json={"views": int(10 ** (2 + sig / 30)), "likes": i}).json()
        assert r["metrics"]["clip_id"] == cid
        assert r["weights"]["learned"] == (i + 1 >= hl.MIN_SAMPLES)
    w = c.get(f"/v1/highlight/weights?project_id={sid}").json()
    assert w["source"] == "project" and w["n_samples"] == 12
    assert w["weights"]["weight_signals"] > w["defaults"]["weight_signals"]
    assert c.get("/v1/highlight/weights").json()["source"] == "global"
    m = c.get(f"/v1/episodes/{eid}/clip-metrics").json()
    assert set(m) == set(ids) and m["k1"]["likes"] == 1

    seen: dict = {}

    def fake_analyze(ctx, settings):
        seen["h"] = settings.highlight
        return {"highlight": {"mode": "llm", "clips": []}}

    monkeypatch.setattr("lahza_engine.core.analyze.analyze", fake_analyze)
    wait_job(st, c.post(f"/v1/episodes/{eid}:reanalyze", json={}).json()["id"])
    assert seen["h"].weight_signals == pytest.approx(w["weights"]["weight_signals"])
    assert st.settings.highlight.weight_signals == HighlightConfig().weight_signals  # global o'zgarmaydi

    # Loyiha vaznini tiklash -> global vaznga qaytadi; global ham tiklansa - standart
    r = c.post("/v1/highlight/weights:reset", json={"project_id": sid}).json()
    assert r["source"] == "global" and not r["learned"] and r["n_samples"] == 0
    r = c.post("/v1/highlight/weights:reset", json={}).json()
    assert r["source"] == "default" and r["weights"] == r["defaults"]
    # Tiklashdan keyin eski namunalar hisobga olinmaydi: bitta yangi kiritish o'rgatmaydi
    r = c.put(f"{url}/k0/metrics", json={"views": 5}).json()
    assert not r["weights"]["learned"] and r["weights"]["n_samples"] == 1
    assert c.delete(f"{url}/k0/metrics").json()["ok"]
    assert c.delete(f"{url}/k0/metrics").status_code == 404
    assert c.post("/v1/highlight/weights:reset", json={"project_id": "yoq"}).status_code == 404
