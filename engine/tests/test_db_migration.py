import sqlite3
from pathlib import Path

import pytest
from conftest import make_sentences

from lahza_engine.db import store as db
from lahza_engine.types import Transcript

# v1 sxemalaridan migratsiya o'zgartiradigan jadvallar (asl v1 DDL).
V1_LIBRARY = """
CREATE TABLE schema_version (version INTEGER NOT NULL);
CREATE TABLE shows (id TEXT PRIMARY KEY, name TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT (datetime('now')));
CREATE TABLE episodes (id TEXT PRIMARY KEY, show_id TEXT NOT NULL REFERENCES shows(id) ON DELETE CASCADE,
  title TEXT NOT NULL, project_dir TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'new',
  created_at TEXT NOT NULL DEFAULT (datetime('now')));
CREATE TABLE lexicon (id INTEGER PRIMARY KEY AUTOINCREMENT, show_id TEXT, term TEXT NOT NULL,
  variants_json TEXT NOT NULL DEFAULT '[]', kind TEXT NOT NULL CHECK (kind IN ('ism','brend','atama')));
CREATE TABLE style_templates (id TEXT PRIMARY KEY, name TEXT NOT NULL, json TEXT NOT NULL);
INSERT INTO schema_version VALUES (1);
INSERT INTO shows(id, name) VALUES ('s1', 'Shou');
INSERT INTO episodes(id, show_id, title, project_dir) VALUES ('e1', 's1', 'Ep', '/x');
"""

V1_PROJECT = """
CREATE TABLE schema_version (version INTEGER NOT NULL);
CREATE TABLE exports (id TEXT PRIMARY KEY, clip_id TEXT NOT NULL, path TEXT, profile_json TEXT NOT NULL,
  status TEXT NOT NULL, error TEXT, created_at TEXT NOT NULL DEFAULT (datetime('now')));
CREATE TABLE corrections (id INTEGER PRIMARY KEY AUTOINCREMENT, audio_chunk_path TEXT NOT NULL,
  before_text TEXT NOT NULL, after_text TEXT NOT NULL, at TEXT NOT NULL DEFAULT (datetime('now')));
CREATE TABLE clips (id TEXT PRIMARY KEY, media_id TEXT NOT NULL, start_ms INTEGER NOT NULL,
  end_ms INTEGER NOT NULL);
INSERT INTO schema_version VALUES (1);
INSERT INTO corrections(audio_chunk_path, before_text, after_text) VALUES ('a', 'b', 'c');
"""


def _cols(conn, table: str) -> set[str]:
    return {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}


def _make(path: Path, sql: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(path)
    c.execute("PRAGMA journal_mode = WAL")
    c.executescript(sql)
    c.commit()
    c.close()


def test_library_v1_to_latest(tmp_path: Path) -> None:
    _make(tmp_path / "library.db", V1_LIBRARY)
    conn = db.open_library(tmp_path)
    assert db.schema_version(conn) == db.LIBRARY_SCHEMA_VERSION == 4
    assert "highlight_mode" in _cols(conn, "episodes") and "updated_at" in _cols(conn, "style_templates")
    assert conn.execute("SELECT title FROM episodes WHERE id='e1'").fetchone()[0] == "Ep"
    bak = tmp_path / "library.v1.bak"
    assert bak.exists()
    old = sqlite3.connect(bak)
    assert old.execute("SELECT version FROM schema_version").fetchone()[0] == 1
    assert "highlight_mode" not in _cols(old, "episodes")
    assert old.execute("SELECT count(*) FROM episodes").fetchone()[0] == 1  # WAL'dagi yozuvlar ham
    conn.close()
    db.open_library(tmp_path).close()  # qayta ochish - migratsiyasiz
    assert not any((tmp_path / f"library.v{v}.bak").exists() for v in (2, 3, 4))


def test_project_v1_to_v2(tmp_path: Path) -> None:
    _make(tmp_path / "project.db", V1_PROJECT)
    conn = db.open_project(tmp_path)
    assert db.schema_version(conn) == db.PROJECT_SCHEMA_VERSION == 3
    assert {"job_id", "finished_at"} <= _cols(conn, "exports")
    assert {"media_id", "sentence_id"} <= _cols(conn, "corrections")
    assert conn.execute("SELECT after_text FROM corrections").fetchone()[0] == "c"
    assert (tmp_path / "project.v1.bak").exists()


def test_newer_schema_refused(tmp_path: Path) -> None:
    _make(tmp_path / "project.db", "CREATE TABLE schema_version (version INTEGER NOT NULL);"
                                   " INSERT INTO schema_version VALUES (99);")
    with pytest.raises(RuntimeError, match="yangiroq"):
        db.open_project(tmp_path)


def test_fresh_dbs_are_v2_and_match_migrated_columns(tmp_path: Path) -> None:
    fresh = db.open_project(tmp_path / "f")
    _make(tmp_path / "m" / "project.db", V1_PROJECT)
    mig = db.open_project(tmp_path / "m")
    for t in ("exports", "corrections"):
        assert _cols(fresh, t) == _cols(mig, t)
    lib = db.open_library(tmp_path / "lf")
    _make(tmp_path / "lm" / "library.db", V1_LIBRARY)
    lib_m = db.open_library(tmp_path / "lm")
    for t in ("episodes", "style_templates", "lexicon", "montages", "user_templates", "montage_exports",
              "analysis_queue"):
        assert _cols(lib, t) == _cols(lib_m, t)
    assert db.schema_version(fresh) == db.PROJECT_SCHEMA_VERSION and db.schema_version(lib) == 4


def test_v2_helpers(tmp_path: Path) -> None:
    conn = db.open_project(tmp_path)
    with conn:
        conn.execute("INSERT INTO media(id, path, hash, duration_ms, fps, width, height, audio_channels)"
                     " VALUES ('m1','/x','h',1,25,1,1,2)")
    db.save_transcript(conn, "m1", Transcript(sentences=make_sentences(2)))
    s = db.load_sentence(conn, "m1", 1)
    s2 = s.model_copy(update={"words": s.words[1:]})
    db.replace_sentence(conn, "m1", s2)
    back = db.load_sentence(conn, "m1", 1)
    assert [w.text for w in back.words] == [w.text for w in s.words[1:]]
    assert conn.execute("SELECT text FROM sentences WHERE media_id='m1' AND id=1").fetchone()[0] == s2.text
    assert db.load_sentence(conn, "m1", 9) is None
    db.set_speaker_name(conn, "SPEAKER_00", "Ali")
    db.set_speaker_name(conn, "SPEAKER_00", "Vali")
    assert db.list_speakers(conn, "m1") == [{"label": "SPEAKER_00", "display_name": "Vali"}]
