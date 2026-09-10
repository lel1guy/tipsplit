-- 001: week lifecycle (open/locked) + settings table.
-- Locked week = money agreed: save is refused server-side; unlocking (with a
-- reason) arrives in 004 alongside the audit log.
ALTER TABLE weeks ADD COLUMN status TEXT NOT NULL DEFAULT 'open';
ALTER TABLE weeks ADD COLUMN closed_at TEXT;
ALTER TABLE weeks ADD COLUMN closed_by TEXT;

CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
