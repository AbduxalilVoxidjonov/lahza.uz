"""library.db v2 -> v3 (montaj jadvallari) migratsiyasi."""

import sqlite3
from pathlib import Path

import pytest

from lahza_engine.db import store as db


def _v2_library(path: Path) -> None:
    """Haqiqiy v2 baza: v1 sxemasi + v2 migratsiyasi (library.sql'ning v3 qismisiz)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(path)
    c.execute("PRAGMA journal_mode = WAL")
    c.executescript("""
CREATE TABLE schema_version (version INTEGER NOT NULL);
CREATE TABLE shows (id TEXT PRIMARY KEY, name TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT (datetime('now')));
CREATE TABLE episodes (id TEXT PRIMARY KEY, show_id TEXT NOT NULL REFERENCES shows(id) ON DELETE CASCADE,
  title TEXT NOT NULL, project_dir TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'new',
  created_at TEXT NOT NULL DEFAULT (datetime('now')));
CREATE TABLE lexicon (id INTEGER PRIMARY KEY AUTOINCREMENT, show_id TEXT, term TEXT NOT NULL,
  variants_json TEXT NOT NULL DEFAULT '[]', kind TEXT NOT NULL CHECK (kind IN ('ism','brend','atama')));
CREATE TABLE style_templates (id TEXT PRIMARY KEY, name TEXT NOT NULL, json TEXT NOT NULL);
""")
    c.executescript(db.LIBRARY_MIGRATIONS[2])
    c.executescript("INSERT INTO schema_version VALUES (2);"
                    "INSERT INTO shows(id, name) VALUES ('s1', 'Shou');")
    c.commit()
    c.close()


def _cols(conn, table: str) -> set[str]:
    return {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}


def test_library_v2_to_v3(tmp_path: Path) -> None:
    _v2_library(tmp_path / "library.db")
    conn = db.open_library(tmp_path)
    assert db.schema_version(conn) == 3
    assert {"id", "project_id", "name", "template_id", "sources_json", "overrides_json", "timeline_json",
            "status", "error", "user_edited", "created_at", "updated_at"} <= _cols(conn, "montages")
    assert {"id", "json", "created_at", "updated_at"} <= _cols(conn, "user_templates")
    assert {"id", "montage_id", "job_id", "path", "status", "created_at",
            "finished_at"} <= _cols(conn, "montage_exports")
    bak = tmp_path / "library.v2.bak"
    assert bak.exists()
    old = sqlite3.connect(bak)
    assert old.execute("SELECT version FROM schema_version").fetchone()[0] == 2
    assert "montages" not in {r[0] for r in old.execute("SELECT name FROM sqlite_master")}
    old.close()

    # CHECK va FK: status cheklangan; shou o'chirilsa montaj qoladi (project_id = NULL),
    # montaj o'chirilsa uning eksportlari ham o'chadi.
    with conn:
        conn.execute("INSERT INTO montages(id, project_id, name, template_id, sources_json)"
                     " VALUES ('m1', 's1', 'M', 't', '[]')")
        conn.execute("INSERT INTO montage_exports(id, montage_id) VALUES ('x1', 'm1')")
    with pytest.raises(sqlite3.IntegrityError), conn:
        conn.execute("UPDATE montages SET status = 'boshqa' WHERE id = 'm1'")
    with conn:
        conn.execute("DELETE FROM shows WHERE id = 's1'")
    assert conn.execute("SELECT project_id FROM montages WHERE id='m1'").fetchone()[0] is None
    with conn:
        conn.execute("DELETE FROM montages WHERE id = 'm1'")
    assert conn.execute("SELECT count(*) FROM montage_exports").fetchone()[0] == 0
    conn.close()
    db.open_library(tmp_path).close()
    assert not (tmp_path / "library.v3.bak").exists()
