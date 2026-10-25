"""SQLite ombori: sxema, migratsiya va asosiy yozish/o'qish (TZ 12-bo'lim, ADR-0006)."""

from __future__ import annotations

import json
import sqlite3
from importlib import resources
from pathlib import Path

from lahza_engine.types import (
    Clip,
    ClipHook,
    ClipKind,
    ClipSource,
    ClipStatus,
    Sentence,
    Transcript,
    Word,
)

# Kutubxona (library.db) va epizod (project.db) sxemalari alohida versiyalanadi: bir bazadagi
# o'zgarish ikkinchisini migratsiyaga majburlamasligi uchun. Kutubxona v4 (v3 montaj, v4 tahlil
# navbati), loyiha v3 (v3 - klip hook'i, PRO-3).
LIBRARY_SCHEMA_VERSION = 4
PROJECT_SCHEMA_VERSION = 3
SCHEMA_VERSION = PROJECT_SCHEMA_VERSION  # orqaga moslik

# {yangi_versiya: "SQL"}; ochishdan oldin zaxira nusxa (<baza>.v<N>.bak) olinadi.
LIBRARY_MIGRATIONS: dict[int, str] = {
    2: """
ALTER TABLE episodes ADD COLUMN highlight_mode TEXT CHECK (highlight_mode IN ('llm','lite'));
ALTER TABLE style_templates ADD COLUMN updated_at TEXT;
CREATE INDEX IF NOT EXISTS idx_lexicon_show ON lexicon(show_id);
""",
    3: """
CREATE TABLE IF NOT EXISTS montages (
  id TEXT PRIMARY KEY,
  project_id TEXT REFERENCES shows(id) ON DELETE SET NULL,
  name TEXT NOT NULL,
  template_id TEXT NOT NULL,
  sources_json TEXT NOT NULL,
  overrides_json TEXT NOT NULL DEFAULT '{}',
  timeline_json TEXT,
  duration_ms INTEGER,
  status TEXT NOT NULL DEFAULT 'planning' CHECK (status IN ('planning','ready','failed')),
  error TEXT,
  job_id TEXT,
  user_edited INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_montages_project ON montages(project_id);
CREATE TABLE IF NOT EXISTS user_templates (
  id TEXT PRIMARY KEY,
  json TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS montage_exports (
  id TEXT PRIMARY KEY,
  montage_id TEXT NOT NULL REFERENCES montages(id) ON DELETE CASCADE,
  job_id TEXT,
  path TEXT,
  status TEXT NOT NULL DEFAULT 'queued',
  error TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  finished_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_montage_exports_montage ON montage_exports(montage_id);
""",
    4: """
CREATE TABLE IF NOT EXISTS analysis_queue (
  id TEXT PRIMARY KEY,
  show_id TEXT NOT NULL REFERENCES shows(id) ON DELETE CASCADE,
  episode_id TEXT REFERENCES episodes(id) ON DELETE SET NULL,
  path TEXT NOT NULL,
  title TEXT,
  options_json TEXT NOT NULL DEFAULT '{}',
  position INTEGER NOT NULL,
  status TEXT NOT NULL DEFAULT 'queued'
    CHECK (status IN ('queued','running','done','failed','cancelled')),
  error TEXT,
  job_id TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  started_at TEXT,
  finished_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_analysis_queue_status ON analysis_queue(status, position);
""",
}
PROJECT_MIGRATIONS: dict[int, str] = {
    2: """
ALTER TABLE exports ADD COLUMN job_id TEXT;
ALTER TABLE exports ADD COLUMN finished_at TEXT;
ALTER TABLE corrections ADD COLUMN media_id TEXT;
ALTER TABLE corrections ADD COLUMN sentence_id INTEGER;
""",
    3: """
ALTER TABLE clips ADD COLUMN hook_start_ms INTEGER;
ALTER TABLE clips ADD COLUMN hook_end_ms INTEGER;
""",
}
MIGRATIONS = PROJECT_MIGRATIONS  # orqaga moslik

_SCHEMAS: dict[str, tuple[int, dict[int, str]]] = {
    "library.sql": (LIBRARY_SCHEMA_VERSION, LIBRARY_MIGRATIONS),
    "project.sql": (PROJECT_SCHEMA_VERSION, PROJECT_MIGRATIONS),
}


def _connect(path: Path, schema_file: str) -> sqlite3.Connection:
    version, migrations = _SCHEMAS[schema_file]
    path.parent.mkdir(parents=True, exist_ok=True)
    existed = path.exists()
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    if not existed:
        sql = resources.files("lahza_engine.db").joinpath(schema_file).read_text(encoding="utf-8")
        conn.executescript(sql)
        conn.execute("INSERT INTO schema_version(version) VALUES (?)", (version,))
        conn.commit()
    else:
        _migrate(conn, path, version, migrations)
    return conn


def _migrate(conn: sqlite3.Connection, path: Path, target: int, migrations: dict[int, str]) -> None:
    row = conn.execute("SELECT version FROM schema_version").fetchone()
    current = row[0] if row else 0
    if current > target:
        raise RuntimeError("loyiha yangiroq dastur versiyasida yaratilgan")
    if current == target:
        return
    # WAL rejimida oddiy fayl nusxasi oxirgi yozuvlarni yo'qotishi mumkin - SQLite backup API.
    bak = sqlite3.connect(path.with_suffix(f".v{current}.bak"))
    try:
        conn.backup(bak)
    finally:
        bak.close()
    for v in range(current + 1, target + 1):
        conn.executescript(migrations[v])
        conn.execute("UPDATE schema_version SET version = ?", (v,))
    conn.commit()


def schema_version(conn: sqlite3.Connection) -> int:
    row = conn.execute("SELECT version FROM schema_version").fetchone()
    return int(row[0]) if row else 0


def open_project(project_dir: Path) -> sqlite3.Connection:
    return _connect(project_dir / "project.db", "project.sql")


def open_library(library_dir: Path) -> sqlite3.Connection:
    return _connect(library_dir / "library.db", "library.sql")


def save_transcript(conn: sqlite3.Connection, media_id: str, tr: Transcript) -> None:
    """Qo'lda tahrirlangan so'zlar (edited=1) qayta tahlilda ustiga yozilmaydi (TZ 12-bo'lim)."""
    edited = {
        (r["sentence_id"], r["ord"]): r
        for r in conn.execute(
            "SELECT * FROM words WHERE media_id = ? AND edited = 1", (media_id,)
        ).fetchall()
    }
    with conn:
        conn.execute("DELETE FROM words WHERE media_id = ?", (media_id,))
        conn.execute("DELETE FROM sentences WHERE media_id = ?", (media_id,))
        for s in tr.sentences:
            conn.execute(
                "INSERT INTO sentences(id, media_id, start_ms, end_ms, speaker_id, text) VALUES (?,?,?,?,?,?)",
                (s.id, media_id, s.start_ms, s.end_ms, s.speaker, s.text),
            )
            for i, w in enumerate(s.words):
                keep = edited.get((s.id, i))
                text = keep["text"] if keep else w.text
                conn.execute(
                    "INSERT INTO words(media_id, sentence_id, ord, text, start_ms, end_ms, confidence,"
                    " speaker_id, edited, original_text) VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (media_id, s.id, i, text, w.start_ms, w.end_ms, w.conf, w.speaker,
                     1 if keep else 0, keep["original_text"] if keep else None),
                )


def load_transcript(conn: sqlite3.Connection, media_id: str) -> Transcript:
    sentences: dict[int, Sentence] = {}
    for r in conn.execute(
        "SELECT * FROM sentences WHERE media_id = ? ORDER BY id", (media_id,)
    ).fetchall():
        sentences[r["id"]] = Sentence(id=r["id"], start_ms=r["start_ms"], end_ms=r["end_ms"],
                                      speaker=r["speaker_id"])
    for r in conn.execute(
        "SELECT * FROM words WHERE media_id = ? ORDER BY sentence_id, ord", (media_id,)
    ).fetchall():
        sentences[r["sentence_id"]].words.append(
            Word(text=r["text"], start_ms=r["start_ms"], end_ms=r["end_ms"], conf=r["confidence"],
                 speaker=r["speaker_id"], edited=bool(r["edited"]), original_text=r["original_text"])
        )
    return Transcript(sentences=list(sentences.values()))


def edit_word(conn: sqlite3.Connection, media_id: str, sentence_id: int, ord_: int, text: str) -> None:
    with conn:
        conn.execute(
            "UPDATE words SET original_text = COALESCE(original_text, text), text = ?, edited = 1 "
            "WHERE media_id = ? AND sentence_id = ? AND ord = ?",
            (text, media_id, sentence_id, ord_),
        )


def save_clips(conn: sqlite3.Connection, clips: list[Clip], replace_ai: bool = True) -> None:
    """AI nomzodlarini yangilaydi; foydalanuvchi tahrirlagan/qabul qilgan klipler saqlanadi."""
    with conn:
        if replace_ai and clips:
            conn.execute(
                "DELETE FROM clips WHERE media_id = ? AND status = 'nomzod' AND user_edited = 0 "
                "AND source != 'qolda'",
                (clips[0].media_id,),
            )
        for c in clips:
            conn.execute(
                "INSERT OR REPLACE INTO clips(id, media_id, start_ms, end_ms, start_sentence_id,"
                " end_sentence_id, hook_sentence_id, title, caption, hashtags_json, kind, score,"
                " scores_json, reason, status, source, llm_model_id, hook_start_ms, hook_end_ms)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (c.id, c.media_id, c.start_ms, c.end_ms, c.start_sentence_id, c.end_sentence_id,
                 c.hook_sentence_id, c.title, c.caption, json.dumps(c.hashtags, ensure_ascii=False),
                 c.kind.value if c.kind else None, c.score, json.dumps(c.scores), c.reason,
                 c.status.value, c.source.value, c.llm_model_id,
                 c.hook.start_ms if c.hook else None, c.hook.end_ms if c.hook else None),
            )
            conn.execute("DELETE FROM clip_cuts WHERE clip_id = ?", (c.id,))
            conn.executemany(
                "INSERT INTO clip_cuts(clip_id, start_ms, end_ms) VALUES (?,?,?)",
                [(c.id, a, b) for a, b in c.cuts],
            )


def load_clips(conn: sqlite3.Connection, media_id: str) -> list[Clip]:
    out = []
    for r in conn.execute(
        "SELECT * FROM clips WHERE media_id = ? ORDER BY start_ms", (media_id,)
    ).fetchall():
        cuts = [(a, b) for a, b in conn.execute(
            "SELECT start_ms, end_ms FROM clip_cuts WHERE clip_id = ? ORDER BY start_ms", (r["id"],))]
        out.append(
            Clip(
                id=r["id"], media_id=r["media_id"], start_ms=r["start_ms"], end_ms=r["end_ms"],
                start_sentence_id=r["start_sentence_id"], end_sentence_id=r["end_sentence_id"],
                hook_sentence_id=r["hook_sentence_id"], title=r["title"], caption=r["caption"],
                hashtags=json.loads(r["hashtags_json"]),
                kind=ClipKind(r["kind"]) if r["kind"] else None, score=r["score"],
                scores=json.loads(r["scores_json"]), reason=r["reason"],
                status=ClipStatus(r["status"]), source=ClipSource(r["source"]),
                llm_model_id=r["llm_model_id"], cuts=cuts,
                hook=ClipHook(start_ms=r["hook_start_ms"], end_ms=r["hook_end_ms"])
                if r["hook_start_ms"] is not None and r["hook_end_ms"] is not None else None,
            )
        )
    return out


def update_clip(conn: sqlite3.Connection, clip_id: str, **fields) -> None:
    allowed = {"start_ms", "end_ms", "title", "caption", "status", "style_template_id"}
    sets = {k: v for k, v in fields.items() if k in allowed and v is not None}
    if "hashtags" in fields and fields["hashtags"] is not None:
        sets["hashtags_json"] = json.dumps(fields["hashtags"], ensure_ascii=False)
    if not sets:
        return
    cols = ", ".join(f"{k} = ?" for k in sets) + ", user_edited = 1"
    with conn:
        conn.execute(f"UPDATE clips SET {cols} WHERE id = ?", (*sets.values(), clip_id))  # noqa: S608
        if "status" in sets and sets["status"] in ("qabul", "rad"):
            conn.execute("INSERT INTO feedback(clip_id, action) VALUES (?, ?)", (clip_id, sets["status"]))


def load_sentence(conn: sqlite3.Connection, media_id: str, sentence_id: int) -> Sentence | None:
    r = conn.execute("SELECT * FROM sentences WHERE media_id = ? AND id = ?",
                     (media_id, sentence_id)).fetchone()
    if r is None:
        return None
    s = Sentence(id=r["id"], start_ms=r["start_ms"], end_ms=r["end_ms"], speaker=r["speaker_id"])
    for w in conn.execute("SELECT * FROM words WHERE media_id = ? AND sentence_id = ? ORDER BY ord",
                          (media_id, sentence_id)).fetchall():
        s.words.append(Word(text=w["text"], start_ms=w["start_ms"], end_ms=w["end_ms"],
                            conf=w["confidence"], speaker=w["speaker_id"], edited=bool(w["edited"]),
                            original_text=w["original_text"]))
    return s


def replace_sentence(conn: sqlite3.Connection, media_id: str, s: Sentence) -> None:
    """Bitta gapning so'zlarini to'liq qayta yozadi (ord 0..n-1 qayta raqamlanadi)."""
    with conn:
        conn.execute("UPDATE sentences SET start_ms = ?, end_ms = ?, text = ? WHERE media_id = ? AND id = ?",
                     (s.start_ms, s.end_ms, s.text, media_id, s.id))
        conn.execute("DELETE FROM words WHERE media_id = ? AND sentence_id = ?", (media_id, s.id))
        conn.executemany(
            "INSERT INTO words(media_id, sentence_id, ord, text, start_ms, end_ms, confidence,"
            " speaker_id, edited, original_text) VALUES (?,?,?,?,?,?,?,?,?,?)",
            [(media_id, s.id, i, w.text, w.start_ms, w.end_ms, w.conf, w.speaker, int(w.edited),
              w.original_text) for i, w in enumerate(s.words)],
        )


def add_correction(conn: sqlite3.Connection, media_id: str, sentence_id: int, chunk: str,
                   before: str, after: str) -> None:
    with conn:
        conn.execute(
            "INSERT INTO corrections(audio_chunk_path, before_text, after_text, media_id, sentence_id)"
            " VALUES (?,?,?,?,?)", (chunk, before, after, media_id, sentence_id))


def insert_manual_clip(conn: sqlite3.Connection, clip: Clip) -> None:
    save_clips(conn, [clip], replace_ai=False)
    with conn:
        conn.execute("UPDATE clips SET user_edited = 1 WHERE id = ?", (clip.id,))


def get_clip(conn: sqlite3.Connection, media_id: str, clip_id: str) -> Clip | None:
    return next((c for c in load_clips(conn, media_id) if c.id == clip_id), None)


def set_cuts(conn: sqlite3.Connection, clip_id: str, cuts: list[tuple[int, int]]) -> None:
    with conn:
        conn.execute("DELETE FROM clip_cuts WHERE clip_id = ?", (clip_id,))
        conn.executemany("INSERT INTO clip_cuts(clip_id, start_ms, end_ms) VALUES (?,?,?)",
                         [(clip_id, a, b) for a, b in cuts])
        conn.execute("UPDATE clips SET user_edited = 1 WHERE id = ?", (clip_id,))
        conn.execute("INSERT INTO feedback(clip_id, action) VALUES (?, 'tahrir')", (clip_id,))


def set_hook(conn: sqlite3.Connection, clip_id: str, hook: ClipHook | None) -> None:
    """Hook oldinga (PRO-3): yoqish/o'zgartirish yoki o'chirish (None).

    Chiqish vaqti siljiydi, shuning uchun avtomatik kamera rejasi keshi (chiqish vaqtida) tashlanadi.
    """
    with conn:
        conn.execute("UPDATE clips SET hook_start_ms = ?, hook_end_ms = ?, user_edited = 1 WHERE id = ?",
                     (hook.start_ms if hook else None, hook.end_ms if hook else None, clip_id))
        conn.execute("DELETE FROM reframe_keyframes WHERE clip_id = ? AND source = 'avto'", (clip_id,))
        conn.execute("INSERT INTO feedback(clip_id, action) VALUES (?, 'tahrir')", (clip_id,))


KEYFRAME_LAYOUTS = ("focus", "split", "fit_blur", "manual")


def load_keyframes(conn: sqlite3.Connection, clip_id: str) -> list[dict]:
    return [dict(r) for r in conn.execute(
        "SELECT t_ms, layout, cx, cy, zoom, lane, source FROM reframe_keyframes WHERE clip_id = ?"
        " ORDER BY lane, t_ms", (clip_id,)).fetchall()]


def save_manual_keyframes(conn: sqlite3.Connection, clip_id: str, keyframes: list[dict]) -> None:
    """Klipning kalit kadrlarini to'liq almashtiradi; hammasi source='qolda'."""
    with conn:
        conn.execute("DELETE FROM reframe_keyframes WHERE clip_id = ?", (clip_id,))
        conn.executemany(
            "INSERT OR REPLACE INTO reframe_keyframes(clip_id, t_ms, layout, cx, cy, zoom, lane, source)"
            " VALUES (?,?,?,?,?,?,?,'qolda')",
            [(clip_id, k["t_ms"], k["layout"], k.get("cx"), k.get("cy"), k.get("zoom", 1.0),
              k.get("lane", "a")) for k in keyframes],
        )


def list_speakers(conn: sqlite3.Connection, media_id: str) -> list[dict]:
    labels = [r[0] for r in conn.execute(
        "SELECT DISTINCT speaker_id FROM sentences WHERE media_id = ? AND speaker_id IS NOT NULL"
        " ORDER BY speaker_id", (media_id,))]
    names = {r["label"]: r["display_name"] for r in conn.execute("SELECT label, display_name FROM speakers")}
    for lbl in names:
        if lbl not in labels:
            labels.append(lbl)
    return [{"label": lbl, "display_name": names.get(lbl)} for lbl in labels]


def set_speaker_name(conn: sqlite3.Connection, label: str, display_name: str | None) -> None:
    with conn:
        conn.execute(
            "INSERT INTO speakers(id, label, display_name) VALUES (?,?,?) "
            "ON CONFLICT(id) DO UPDATE SET display_name = excluded.display_name",
            (label, label, display_name))


def record_export(conn: sqlite3.Connection, export_id: str, clip_id: str, job_id: str,
                  profile: dict) -> None:
    with conn:
        conn.execute("INSERT INTO exports(id, clip_id, profile_json, status, job_id) VALUES (?,?,?,?,?)",
                     (export_id, clip_id, json.dumps(profile, ensure_ascii=False), "queued", job_id))


def finish_export(conn: sqlite3.Connection, export_id: str, status: str, path: str | None = None,
                  error: str | None = None) -> None:
    done = status in ("done", "failed", "cancelled")
    with conn:
        conn.execute(
            "UPDATE exports SET status = ?, path = COALESCE(?, path), error = ?,"
            " finished_at = CASE WHEN ? THEN datetime('now') ELSE finished_at END WHERE id = ?",
            (status, path, error, int(done), export_id))
