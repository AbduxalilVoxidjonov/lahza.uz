-- Kutubxona bazasi: Library/library.db - shoular, spikerlar, lug'at, shablonlar (TZ 12-bo'lim)
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL);

CREATE TABLE IF NOT EXISTS shows (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS episodes (
  id TEXT PRIMARY KEY,
  show_id TEXT NOT NULL REFERENCES shows(id) ON DELETE CASCADE,
  title TEXT NOT NULL,
  project_dir TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'new',
  highlight_mode TEXT CHECK (highlight_mode IN ('llm','lite')),  -- v2
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS show_speakers (
  id TEXT PRIMARY KEY,
  show_id TEXT NOT NULL REFERENCES shows(id) ON DELETE CASCADE,
  display_name TEXT NOT NULL,
  voice_embedding BLOB
);

CREATE TABLE IF NOT EXISTS lexicon (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  show_id TEXT REFERENCES shows(id) ON DELETE CASCADE,
  term TEXT NOT NULL,
  variants_json TEXT NOT NULL DEFAULT '[]',
  kind TEXT NOT NULL CHECK (kind IN ('ism','brend','atama'))
);
CREATE INDEX IF NOT EXISTS idx_lexicon_show ON lexicon(show_id);  -- v2

CREATE TABLE IF NOT EXISTS style_templates (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  json TEXT NOT NULL,
  updated_at TEXT  -- v2
);

CREATE TABLE IF NOT EXISTS settings (
  key TEXT PRIMARY KEY,
  value_json TEXT NOT NULL
);
