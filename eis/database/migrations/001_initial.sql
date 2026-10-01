-- E.I.S. Core SQLite schema (version 1)
-- Applied by eis.database.schema.apply_migrations()

CREATE TABLE IF NOT EXISTS schema_migrations (
    version     INTEGER PRIMARY KEY,
    name        TEXT NOT NULL,
    applied_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS customers (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    phone       TEXT NOT NULL DEFAULT '',
    email       TEXT NOT NULL DEFAULT '',
    notes       TEXT NOT NULL DEFAULT '',
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS devices (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id     INTEGER REFERENCES customers(id) ON DELETE CASCADE,
    device_type     TEXT NOT NULL DEFAULT 'laptop',   -- laptop|desktop|phone|tablet|other
    brand           TEXT NOT NULL DEFAULT '',
    model           TEXT NOT NULL DEFAULT '',
    serial          TEXT NOT NULL DEFAULT '',
    os              TEXT NOT NULL DEFAULT '',
    specs           TEXT NOT NULL DEFAULT '',          -- free-form CPU/RAM/storage summary
    password_notes  TEXT NOT NULL DEFAULT '',          -- stored locally only; see SECURITY.md
    notes           TEXT NOT NULL DEFAULT '',
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS jobs (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id     INTEGER NOT NULL REFERENCES devices(id) ON DELETE CASCADE,
    title         TEXT NOT NULL,
    status        TEXT NOT NULL DEFAULT 'open',        -- open|diagnosing|waiting_parts|repairing|done|cancelled
    priority      TEXT NOT NULL DEFAULT 'normal',      -- low|normal|high
    problem       TEXT NOT NULL DEFAULT '',
    diagnosis     TEXT NOT NULL DEFAULT '',
    solution      TEXT NOT NULL DEFAULT '',
    cost          REAL NOT NULL DEFAULT 0,
    received_at   TEXT NOT NULL DEFAULT (datetime('now')),
    finished_at   TEXT,
    created_at    TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS job_notes (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id      INTEGER NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    body        TEXT NOT NULL,
    kind        TEXT NOT NULL DEFAULT 'note',          -- note|diagnostic|action|result
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS command_history (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    action      TEXT NOT NULL,
    command     TEXT NOT NULL DEFAULT '',
    result      TEXT NOT NULL DEFAULT 'ok',
    error       TEXT NOT NULL DEFAULT '',
    details     TEXT NOT NULL DEFAULT '{}',            -- JSON
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS kb_feedback (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    kb_id       TEXT NOT NULL,
    helpful     INTEGER NOT NULL DEFAULT 0,            -- 1 helped, 0 did not
    note        TEXT NOT NULL DEFAULT '',
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_devices_customer   ON devices(customer_id);
CREATE INDEX IF NOT EXISTS idx_jobs_device        ON jobs(device_id);
CREATE INDEX IF NOT EXISTS idx_jobs_status        ON jobs(status);
CREATE INDEX IF NOT EXISTS idx_job_notes_job      ON job_notes(job_id);
CREATE INDEX IF NOT EXISTS idx_command_history_at ON command_history(created_at);
