# TipSplit — Dev Guide

For whoever touches the code next (probably you, six months from now, at 1am).

## Layout

| File | Responsibility |
|---|---|
| `main.py` | FastAPI app: every route, the owner/staff PIN gate, the security headers, print pages |
| `splitting.py` | **all money math** — hours, shares, largest-remainder rounding, the statement text |
| `db.py` | SQLite access (no ORM), migrations runner, weeks/entries/staff/vales/settings/audit |
| `auth.py` | PIN hashing (pbkdf2), the signed session cookie (role + staff id + expiry), brute-force brake |
| `exporters.py` | payslips, cash sheet, week + annual xlsx/csv. **Formats only — never decides money** |
| `static/index.html` | the whole UI: one file, vanilla JS, inline CSS, system fonts |
| `migrations/*.sql` | schema steps, applied by `PRAGMA user_version` |
| `ops/seed_demo.py` | the fictional venue (demos, screenshots) |
| `tests/`, `e2e/smoke.mjs` | unit suite + browser journey |

Rule of the house: **money math lives in `splitting.py` and nowhere else.** The browser
renders what the server computed; `exporters.py` only formats it. If you ever need a
number in two places, send it from the server.

## Data model

```
weeks(id, start_date UNIQUE, status open|locked, closed_at, closed_by)
week_pools(week_id, pool_eur)
entries(week_id, staff_id, mon..sun)
staff(id, name, position, archived, pin_hash)          -- pin_hash '' = no PIN issued
vales(id, staff_id, date, week_id, amount, note)       -- week_id is always set
settings(key, value)                                   -- venue_name, lang, vale_max
audit_log(id, ts, actor, action, detail)
```

Migrations: add `migrations/00N_name.sql`, and bump `LATEST` in
`tests/test_migrations.py`. The base schema is deliberately the **old** shape so `001`
exercises on every fresh install.

## Running it

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m uvicorn main:app --reload --port 8778
```

`TIPSPLIT_DB` overrides the database path (used by tests, e2e and the demo).

## Tests

```bash
.venv/bin/python -m pytest tests/ -q      # 76 unit tests (~1 min)
node e2e/smoke.mjs                        # 60 browser assertions against a throwaway DB
```

The unit suite covers the split math (proportional shares, cent balancing, zero-hour
weeks), vales (week required, ceiling, grouping, auto-listing), migrations from a legacy
DB, auth (hashing, token tampering, expiry, per-staff isolation) and the printed
statement's arithmetic.

The browser suite boots the real app and drives the whole ritual: first-run PIN → new
week → hours → advance → ceiling → lock → payslips → exports → unlock with a motivo →
staff login → the staff page → 403s on management endpoints → phone layouts.

`e2e/smoke.mjs` reuses `playwright-core` from the BarSpec checkout
(`/home/vitor/dev/barspec/node_modules`) and a Chromium from `~/.cache/ms-playwright`.
No install needed on this machine.

**Never point tests at the live DB.** They copy or override `TIPSPLIT_DB`.

## Deploy (this network)

```bash
sudo systemctl restart tipsplit && sleep 15 && systemctl is-active tipsplit
```

Live on `192.168.1.77:8778`, DB at `/home/vitor/dev/tipsplit/tipsplit.db`, migrations run
on startup. Before a restart that touches schema: copy the DB first.

## Backup and restore

```bash
cp tipsplit.db "tipsplit-$(date +%F).db"     # backup: the whole app is this file
```

Restore = stop the service, put the file back, start it. There is no other state.

## PIN recovery (forgotten owner PIN)

There is no email reset — no cloud, no accounts. On the machine:

```bash
sqlite3 tipsplit.db "DELETE FROM settings WHERE key='pin_hash'"
```

The gate then asks to define a PIN on the next visit. Staff PINs live in
`staff.pin_hash`; clear one per person from *Equipa → limpar*, or in SQL.

## Adding a feature without breaking trust

1. Money change? Reproduce the arithmetic in a test **first**, off a real payslip page if
   you can. A rounding bug is invisible until payday.
2. New endpoint? Decide who may reach it: owner, staff, or nobody without a cookie. Add it
   to the e2e 403 list if it's owner-only.
3. New field on a week or a person? It probably belongs in the week payload from the
   server, not in client state.
4. UI change? Run `node e2e/smoke.mjs`. Unit tests were green through five real UI bugs
   during the design port; only the browser caught them.
5. Anything that writes money records (advances, locks) deserves an `audit()` call.

## Regenerating the screenshots

```bash
rm -f /tmp/tipsplit-demo.db
TIPSPLIT_DB=/tmp/tipsplit-demo.db .venv/bin/python ops/seed_demo.py --weeks 8
```

Then drive the app with a small playwright script and save into `docs/screenshots/`. The
seed is deterministic, so the numbers in the README stay true.

## Known sharp edges

- The interface is PT-PT only, by decision. English strings in the UI are bugs — they were
  found twice (`Payslips`/`Cash sheet`, `Mon…Sun`), so check for them when adding copy.
- `#gate` must keep `display:none !important` when hidden; an id selector beat the class
  once and left the app dead behind an invisible overlay.
- Any refresh that re-renders a `<select>` must preserve the user's choice, and concurrent
  refreshes are coalesced in `loadTeam()` — a stale render once re-pointed an advance at
  the wrong person.
- `/api/*` and `/print/*` must stay `Cache-Control: no-store`: a cached 401 made the app
  look broken right after setup.
