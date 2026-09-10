-- 006: vales always belong to a week (V, 2026-09-10) — no more "standalone" advances.
-- Defensive backfill for any install that still has orphans: attach the advance to
-- the week it was taken in (the last week that started on/before its date), else to
-- the earliest week. Nothing is deleted — money records don't disappear.
UPDATE vales SET week_id = (
    SELECT w.id FROM weeks w WHERE w.start_date <= vales.date
    ORDER BY w.start_date DESC LIMIT 1
) WHERE week_id IS NULL;

UPDATE vales SET week_id = (SELECT MIN(id) FROM weeks) WHERE week_id IS NULL;

CREATE INDEX IF NOT EXISTS idx_vales_week ON vales(week_id);
