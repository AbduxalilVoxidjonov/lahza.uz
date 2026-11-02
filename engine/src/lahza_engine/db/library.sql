-- Kutubxona bazasi: Library/library.db - shoular, spikerlar, lug'at, shablonlar, montajlar (TZ 12-bo'lim)
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

-- v3: montaj (docs/11, docs/05). Timeline - `lahza.timeline/1` JSON, shablon - `lahza.template/1` JSON.
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

-- v4: partiyaviy tahlil navbati (PRO-5). Holat engine qayta ishga tushganda shu jadvaldan tiklanadi.
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

-- v5: shaxsiy lug'at (PRO-1) va real natijalardan ball vaznlarini o'rganish (PRO-6).
CREATE TABLE IF NOT EXISTS personal_dictionary (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  wrong TEXT NOT NULL,
  right TEXT NOT NULL,
  kind TEXT NOT NULL DEFAULT 'soz' CHECK (kind IN ('ism','atama','soz')),
  count INTEGER NOT NULL DEFAULT 1 CHECK (count >= 1),
  last_episode_id TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now')),
  UNIQUE (wrong, right)
);
CREATE TABLE IF NOT EXISTS clip_metrics (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  episode_id TEXT NOT NULL REFERENCES episodes(id) ON DELETE CASCADE,
  show_id TEXT REFERENCES shows(id) ON DELETE CASCADE,
  clip_id TEXT NOT NULL,
  views INTEGER NOT NULL CHECK (views >= 0),
  likes INTEGER CHECK (likes IS NULL OR likes >= 0),
  features_json TEXT NOT NULL DEFAULT '{}',
  score REAL,
  source TEXT,
  recorded_at TEXT NOT NULL DEFAULT (datetime('now')),
  UNIQUE (episode_id, clip_id)
);
CREATE INDEX IF NOT EXISTS idx_clip_metrics_show ON clip_metrics(show_id);
CREATE TABLE IF NOT EXISTS highlight_weights (
  scope TEXT PRIMARY KEY,
  weights_json TEXT,
  n_samples INTEGER NOT NULL DEFAULT 0,
  since_id INTEGER NOT NULL DEFAULT 0,
  updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
