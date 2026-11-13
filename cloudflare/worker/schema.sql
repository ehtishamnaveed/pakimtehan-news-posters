-- D1 schema for the pakimtehan-posters Worker. Apply with:
--   wrangler d1 execute pakimtehan-posters --remote --file schema.sql
-- Safe to run again (IF NOT EXISTS).

-- One row per poster waiting for review. Rows are deleted when the poster is approved
-- (the Pak Imtehan server copies the image first) or rejected.
CREATE TABLE IF NOT EXISTS posters (
  id          TEXT PRIMARY KEY,               -- "2026-11-13_1247-01" (date _ batch time - number)
  date        TEXT NOT NULL,                  -- YYYY-MM-DD (Pakistan time)
  rev         INTEGER NOT NULL DEFAULT 1,     -- +1 on every re-render after an edit
  state       TEXT NOT NULL DEFAULT 'ready',  -- ready | editing
  data        TEXT NOT NULL,                  -- JSON: every value the poster was rendered from
  edit        TEXT,                           -- JSON: changes the admin asked for (while editing)
  error       TEXT,                           -- why the last edit could not be applied
  created_at  TEXT NOT NULL,
  updated_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_posters_date ON posters(date);
CREATE INDEX IF NOT EXISTS idx_posters_state ON posters(state);

-- Files as base64 text, one per row (D1 rows are capped at 2 MB, so each file stays separate).
-- kind: image (the rendered poster JPEG), photo (background photo used), edit_photo (admin upload)
CREATE TABLE IF NOT EXISTS files (
  poster_id  TEXT NOT NULL,
  kind       TEXT NOT NULL,
  b64        TEXT NOT NULL,
  PRIMARY KEY (poster_id, kind)
);

-- Small pipeline state, e.g. "seen" (links already used) and "last_run" (date of the last batch).
CREATE TABLE IF NOT EXISTS state (
  k TEXT PRIMARY KEY,
  v TEXT NOT NULL
);
