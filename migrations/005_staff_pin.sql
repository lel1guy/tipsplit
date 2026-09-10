-- 005: per-staff PINs — each person signs in and sees only their own numbers,
-- plus the week's table (the venue chose transparent sharing). An empty string
-- means "no PIN issued yet"; the owner sets/clears it in Equipa.
ALTER TABLE staff ADD COLUMN pin_hash TEXT NOT NULL DEFAULT '';
