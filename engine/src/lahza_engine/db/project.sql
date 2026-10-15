-- Epizod loyihasi bazasi: <Epizod>.lahza/project.db  (TZ 12-bo'lim)
-- Vaqt: butun son ms. Matn: Unicode NFC, rasmiy imlo.
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL);

CREATE TABLE IF NOT EXISTS media (
  id TEXT PRIMARY KEY,
  path TEXT NOT NULL,
  hash TEXT NOT NULL,
  duration_ms INTEGER NOT NULL,
  fps REAL NOT NULL,
  width INTEGER NOT NULL,
  height INTEGER NOT NULL,
  audio_channels INTEGER NOT NULL,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- stage_runs.media_id'da FK yo'q: ingest bosqichi 'media' qatorini o'zi yaratadi.
CREATE TABLE IF NOT EXISTS stage_runs (
  media_id TEXT NOT NULL,
  stage TEXT NOT NULL,
  version INTEGER NOT NULL,
  model_id TEXT,
  param_hash TEXT NOT NULL,
  cache_key TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('running','done','failed','cancelled')),
  result_path TEXT,
  error TEXT,
  started_at TEXT NOT NULL DEFAULT (datetime('now')),
  finished_at TEXT,
  PRIMARY KEY (media_id, stage)
);

-- id = diarizatsiya yorlig'i (masalan SPEAKER_00); display_name - foydalanuvchi bergan ism.
CREATE TABLE IF NOT EXISTS speakers (
  id TEXT PRIMARY KEY,
  show_id TEXT,
  label TEXT NOT NULL,
  display_name TEXT
);

CREATE TABLE IF NOT EXISTS sentences (
  id INTEGER NOT NULL,
  media_id TEXT NOT NULL REFERENCES media(id) ON DELETE CASCADE,
  start_ms INTEGER NOT NULL,
  end_ms INTEGER NOT NULL,
  speaker_id TEXT,
  text TEXT NOT NULL,
  confidence REAL,
  PRIMARY KEY (media_id, id)
);

CREATE TABLE IF NOT EXISTS words (
  media_id TEXT NOT NULL,
  sentence_id INTEGER NOT NULL,
  ord INTEGER NOT NULL,
  text TEXT NOT NULL,
  start_ms INTEGER NOT NULL,
  end_ms INTEGER NOT NULL,
  confidence REAL,
  speaker_id TEXT,
  edited INTEGER NOT NULL DEFAULT 0,
  original_text TEXT,
  PRIMARY KEY (media_id, sentence_id, ord),
  FOREIGN KEY (media_id, sentence_id) REFERENCES sentences(media_id, id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_words_time ON words(media_id, start_ms);

CREATE TABLE IF NOT EXISTS clips (
  id TEXT PRIMARY KEY,
  media_id TEXT NOT NULL REFERENCES media(id) ON DELETE CASCADE,
  start_ms INTEGER NOT NULL,
  end_ms INTEGER NOT NULL,
  start_sentence_id INTEGER NOT NULL,
  end_sentence_id INTEGER NOT NULL,
  hook_sentence_id INTEGER,
  title TEXT NOT NULL DEFAULT '',
  caption TEXT NOT NULL DEFAULT '',
  hashtags_json TEXT NOT NULL DEFAULT '[]',
  kind TEXT,
  score REAL NOT NULL DEFAULT 0,
  scores_json TEXT NOT NULL DEFAULT '{}',
  reason TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL DEFAULT 'nomzod'
    CHECK (status IN ('nomzod','qabul','rad','eksport_qilingan')),
  source TEXT NOT NULL CHECK (source IN ('ai_llm','ai_lite','qolda')),
  llm_model_id TEXT,
  style_template_id TEXT,
  user_edited INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS clip_cuts (
  clip_id TEXT NOT NULL REFERENCES clips(id) ON DELETE CASCADE,
  start_ms INTEGER NOT NULL,
  end_ms INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS reframe_keyframes (
  clip_id TEXT NOT NULL REFERENCES clips(id) ON DELETE CASCADE,
  t_ms INTEGER NOT NULL,
  layout TEXT NOT NULL CHECK (layout IN ('focus','split','fit_blur','manual')),
  cx REAL, cy REAL, zoom REAL NOT NULL DEFAULT 1.0,
  lane TEXT NOT NULL DEFAULT 'a',
  source TEXT NOT NULL DEFAULT 'avto' CHECK (source IN ('avto','qolda')),
  PRIMARY KEY (clip_id, lane, t_ms)
);

CREATE TABLE IF NOT EXISTS exports (
  id TEXT PRIMARY KEY,
  clip_id TEXT NOT NULL REFERENCES clips(id) ON DELETE CASCADE,
  path TEXT,
  profile_json TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('queued','running','done','failed','cancelled')),
  error TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  job_id TEXT,  -- v2: engine sessiyasidagi vazifa
  finished_at TEXT  -- v2
);

CREATE TABLE IF NOT EXISTS feedback (
  clip_id TEXT NOT NULL,
  action TEXT NOT NULL CHECK (action IN ('qabul','rad','tahrir')),
  at TEXT NOT NULL DEFAULT (datetime('now')),
  metrics_json TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS corrections (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  audio_chunk_path TEXT NOT NULL,
  before_text TEXT NOT NULL,
  after_text TEXT NOT NULL,
  at TEXT NOT NULL DEFAULT (datetime('now')),
  media_id TEXT,  -- v2
  sentence_id INTEGER  -- v2
);
