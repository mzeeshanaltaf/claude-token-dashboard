-- Claude Lens initial schema. Runs with search_path set to the target schema,
-- so table names are deliberately unqualified.

-- One row per JSONL record (user / assistant / ...). The dedup key for
-- streaming snapshots is (session_id, message_id), not uuid: see
-- collector/ingest.py.
CREATE TABLE messages (
  uuid                    TEXT PRIMARY KEY,
  parent_uuid             TEXT,
  session_id              TEXT NOT NULL,
  project_slug            TEXT NOT NULL,
  machine                 TEXT NOT NULL,
  cwd                     TEXT,
  git_branch              TEXT,
  cc_version              TEXT,
  entrypoint              TEXT,
  type                    TEXT NOT NULL,
  is_sidechain            BOOLEAN NOT NULL DEFAULT FALSE,
  agent_id                TEXT,
  timestamp               TIMESTAMPTZ NOT NULL,
  model                   TEXT,
  stop_reason             TEXT,
  prompt_id               TEXT,
  message_id              TEXT,
  input_tokens            BIGINT NOT NULL DEFAULT 0,
  output_tokens           BIGINT NOT NULL DEFAULT 0,
  cache_read_tokens       BIGINT NOT NULL DEFAULT 0,
  cache_create_5m_tokens  BIGINT NOT NULL DEFAULT 0,
  cache_create_1h_tokens  BIGINT NOT NULL DEFAULT 0,
  prompt_text             TEXT,
  prompt_chars            INTEGER,
  tool_calls_json         JSONB,
  -- Only the first 100k chars are indexed: a tsvector is capped at 1 MB and a
  -- huge pasted prompt would otherwise make the whole insert fail.
  prompt_tsv              tsvector GENERATED ALWAYS AS (
                            to_tsvector('english', left(coalesce(prompt_text, ''), 100000))
                          ) STORED
);
CREATE INDEX idx_messages_session   ON messages (session_id);
CREATE INDEX idx_messages_project   ON messages (project_slug);
CREATE INDEX idx_messages_timestamp ON messages (timestamp);
CREATE INDEX idx_messages_model     ON messages (model);
CREATE INDEX idx_messages_msgid     ON messages (session_id, message_id);
CREATE INDEX idx_messages_parent    ON messages (parent_uuid);
CREATE INDEX idx_messages_prompt_tsv ON messages USING GIN (prompt_tsv);

-- One row per tool_use block, plus one '_tool_result' row per tool_result
-- block. No natural key: the collector deletes a message's rows before
-- re-inserting them.
CREATE TABLE tool_calls (
  id             BIGSERIAL PRIMARY KEY,
  message_uuid   TEXT NOT NULL,
  session_id     TEXT NOT NULL,
  project_slug   TEXT NOT NULL,
  tool_name      TEXT NOT NULL,
  target         TEXT,
  tool_use_id    TEXT,
  result_tokens  INTEGER,
  is_error       INTEGER NOT NULL DEFAULT 0,
  timestamp      TIMESTAMPTZ NOT NULL
);
CREATE INDEX idx_tools_session ON tool_calls (session_id);
CREATE INDEX idx_tools_name    ON tool_calls (tool_name);
CREATE INDEX idx_tools_target  ON tool_calls (target);
CREATE INDEX idx_tools_message ON tool_calls (message_uuid);

-- Incremental-scan high-water marks, per machine. mtime is a float8 so the
-- collector's equality check against os.stat().st_mtime round-trips exactly.
CREATE TABLE files (
  machine     TEXT NOT NULL,
  path        TEXT NOT NULL,
  mtime       DOUBLE PRECISION NOT NULL,
  bytes_read  BIGINT NOT NULL,
  scanned_at  TIMESTAMPTZ NOT NULL,
  PRIMARY KEY (machine, path)
);

CREATE TABLE session_titles (
  session_id  TEXT PRIMARY KEY,
  title       TEXT NOT NULL
);

-- Key/value app settings (plan, timezone, ...).
CREATE TABLE settings (
  k  TEXT PRIMARY KEY,
  v  JSONB
);

CREATE TABLE dismissed_tips (
  tip_key       TEXT PRIMARY KEY,
  dismissed_at  TIMESTAMPTZ NOT NULL
);

-- SKILL.md sizes, uploaded by each machine's collector (the API can't see
-- the PC's filesystem).
CREATE TABLE skill_catalog (
  machine     TEXT NOT NULL,
  slug        TEXT NOT NULL,
  path        TEXT NOT NULL,
  chars       INTEGER NOT NULL,
  tokens      INTEGER NOT NULL,
  updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (machine, slug)
);

-- One row per collector run ("last synced ..." in the UI).
CREATE TABLE sync_runs (
  id           BIGSERIAL PRIMARY KEY,
  machine      TEXT NOT NULL,
  started_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  finished_at  TIMESTAMPTZ,
  files        INTEGER,
  messages     INTEGER,
  tools        INTEGER,
  titles       INTEGER,
  status       TEXT NOT NULL CHECK (status IN ('running', 'ok', 'error')),
  error        TEXT
);
CREATE INDEX idx_sync_runs_started ON sync_runs (started_at DESC);

CREATE TABLE users (
  id             BIGSERIAL PRIMARY KEY,
  username       TEXT NOT NULL UNIQUE,
  password_hash  TEXT NOT NULL,
  created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Server-side login sessions; only sha256(token) is stored.
CREATE TABLE auth_sessions (
  token_hash  TEXT PRIMARY KEY,
  user_id     BIGINT NOT NULL REFERENCES users (id) ON DELETE CASCADE,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  expires_at  TIMESTAMPTZ NOT NULL
);
CREATE INDEX idx_auth_sessions_user    ON auth_sessions (user_id);
CREATE INDEX idx_auth_sessions_expires ON auth_sessions (expires_at);
