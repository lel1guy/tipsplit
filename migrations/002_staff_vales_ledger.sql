-- 002: staff positions + archive flag, and the vales ledger.
-- Vales stop being a per-week column and become dated rows (money law: one
-- source). entries.vales is backfilled then dropped, so no two places can
-- disagree about what someone took.
ALTER TABLE staff ADD COLUMN position TEXT NOT NULL DEFAULT '';
ALTER TABLE staff ADD COLUMN archived INTEGER NOT NULL DEFAULT 0;

CREATE TABLE IF NOT EXISTS vales (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    staff_id   INTEGER NOT NULL REFERENCES staff(id) ON DELETE CASCADE,
    date       TEXT NOT NULL,
    week_id    INTEGER REFERENCES weeks(id) ON DELETE CASCADE,
    amount     REAL NOT NULL,
    note       TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_vales_staff ON vales(staff_id);
CREATE INDEX IF NOT EXISTS idx_vales_week ON vales(week_id);

-- History preserved: every week that carried vales becomes dated ledger rows.
INSERT INTO vales (staff_id, date, week_id, amount, note)
SELECT e.staff_id, w.start_date, e.week_id, e.vales, 'importado'
FROM entries e JOIN weeks w ON w.id = e.week_id
WHERE e.vales > 0;

ALTER TABLE entries DROP COLUMN vales;
