# TipSplit

**English** · [Português (PT-PT)](README.pt-PT.md)

A weekly tip splitter for small bars, cafés and restaurants. Staff hours go in,
everyone sees the same provable number, **vales** (cash advances) come off each
person's share, and payday prints payslips you can hand out with a pen.

    share = pool × (horas da pessoa ÷ horas totais) − vales

No money moves through the app. It's the calculator and the receipt, not the till.

Sister app to [BarSpec](https://github.com/lel1guy/barspec) — same stack, same design
language, separate product.

---

## Who it's for

Venues with **5–30 staff** in Portugal/EU where tips are pooled and split by hours.
It replaces the spreadsheet the manager rebuilds every Monday — and, more importantly,
answers the question that starts every argument: *"why is my number that number?"*

The differentiator isn't the arithmetic. It's **proof**: a fairness statement on every
screen, payslips that survive a pocket calculator, advances that always belong to a
week, and an owner audit trail with no silent edits.

## What it does

- **Week grid** — hours per day (Mon–Sun, 0.5 h steps), auto-totaled, live share
  preview while you type. Pool enters in one field.
- **Provable split** — the split math lives server-side in `splitting.py`; the browser
  only displays it. Printed proof shows the unrounded formula
  (`470,40 € × 32 h ÷ 448 h = 33,60 €`), never a rounded rate multiplied back out.
- **Vales (advances)** — always attached to a week; grouped per week with subtotals in
  *Equipa*; the week shows its own advances. Nobody needs hours or a motivo to take one,
  and an advance alone puts that person in the week's table (tagged *sem horas*).
- **Vale máximo** — optional ceiling per advance (*Definições*, `0` = no limit),
  enforced server-side.
- **Payday** — signed payslips per person (print view), a cash sheet for the till,
  week export (Excel/CSV) and an annual export. Printing an unlocked week is refused.
- **Weeks lock** — a locked week can only be reopened with a **reason**, which is
  recorded.
- **The team's own page** — each person gets a PIN and sees *their* numbers and the
  week's table. Nothing else. Filtered server-side.
- **Owner PIN gate** — one login field: the owner PIN opens management, a staff PIN
  opens that person's page.
- **Audit trail** — settings changes, week saves, locks, unlocks, advances, PINs.

## Run it

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --port 8001
```

Open http://127.0.0.1:8001 — the first run asks you to define the owner PIN, then seeds
one demo week with **fictional staff and random hours**. Real names get added in the UI;
the seed only exists so you can play with the split immediately.

Deployment on this network: systemd unit `tipsplit`, live on `192.168.1.77:8778`.
The DB is plain SQLite (`tipsplit.db`); migrations run on startup.

## Tests

```bash
python -m pytest tests/ -q      # 76 tests, the split math + money rules
node e2e/smoke.mjs              # 59 browser assertions across the full ritual
```

The unit suite covers proportional splits, largest-remainder cent balancing, vales,
zero-hour weeks, migrations from a legacy DB, auth (PIN hashing, token tampering,
expiry), per-staff isolation and the vale ceiling. The browser suite drives the real
UI against a throwaway DB: new week → hours → advance → lock → payslips → exports →
unlock with a reason → staff login → 403s on management endpoints.

## Data model

| Table | Holds |
|-------|-------|
| `weeks` | one row per week (Monday date, status open/locked) |
| `week_pools` | the pool per week |
| `entries` | hours per person per week (mon…sun) |
| `staff` | roster: name, position label, archived flag, `pin_hash` |
| `vales` | one row per advance: person, date, **week**, amount, note |
| `settings` | venue name, language, `vale_max` |
| `audit_log` | who did what, when |

Migrations in `migrations/*.sql` with `PRAGMA user_version`. Base schema is the old
shape on purpose, so `001` exercises on every install.

## API

All endpoints except `/api/auth/*` and `/` require a session cookie.

| Method | Path | What |
|--------|------|------|
| GET | `/api/auth/status` | is a PIN set, what role is this session |
| POST | `/api/auth/setup` | define the first owner PIN |
| POST | `/api/auth/login` | owner PIN or staff PIN |
| POST | `/api/auth/logout` | clear the session |
| POST | `/api/auth/pin` | change the owner PIN |
| GET/POST | `/api/staff` | roster / add a person |
| POST | `/api/staff/{id}/archive` | archive or reactivate (history is kept) |
| POST | `/api/staff/{id}/pin` | give or clear a person's PIN |
| DELETE | `/api/staff/{id}` | delete — only someone with no history |
| GET | `/api/team` | roster + this week's advances + PIN state |
| GET | `/api/dashboard` | the numbers on the Semana view |
| GET | `/api/vales` | advances (`?week_id=` filters, `?staff_id=` filters) |
| GET | `/api/vales/grouped` | the ledger grouped per week, with subtotals |
| POST | `/api/vales` | record an advance (week required; ceiling enforced) |
| DELETE | `/api/vales/{id}` | remove an advance |
| GET/POST | `/api/weeks` | list / create a week by Monday date |
| GET/PUT/DELETE | `/api/weeks/{id}` | read / edit the date / delete |
| PUT | `/api/weeks/{id}/save` | pool + all entries in one shot |
| POST | `/api/weeks/{id}/preview` | recompute shares without saving |
| POST | `/api/weeks/{id}/lock` | close the week |
| POST | `/api/weeks/{id}/unlock` | reopen — **requires a motivo** |
| GET | `/print/payslips/{id}` | signed payslips (HTML print view) |
| GET | `/print/cashsheet/{id}` | cash sheet for the till |
| GET | `/api/export/week/{id}` | week export (xlsx/csv) |
| GET | `/api/export/annual/{year}` | annual export |
| GET | `/api/settings` · PUT | venue name, language, vale ceiling |
| GET | `/api/audit` | recent changes |
| GET | `/api/me` | **staff session only** — own numbers, week table, own advances |
| GET | `/print/me/{week_id}` | **staff session only** — own payslip |

A staff session reaches `/api/me`, `/print/me/{week}` and logout. Everything else
answers **403** — verified in the browser suite against 8 endpoints.

## Security model

- PINs are `pbkdf2_hmac`-SHA256 (260k iterations, per-PIN salt). A cookie is
  HMAC-signed and carries **role + staff id + expiry**: a staff cookie cannot be
  edited into an owner one (unit-tested, including id and expiry tampering).
- Sharing a PIN is refused both ways — a duplicate means reading someone else's money.
- The staff page never receives the roster; the server filters to that person's id.
- `/api/*` and `/print/*` are `Cache-Control: no-store` — a cached 401 once made the
  app look broken right after setup.

## What it deliberately does not do

- **No money movement.** No payments, no bank, no POS, no payroll integration.
- **No position weights.** v1 splits by hours only; position is a label, not a
  multiplier. (A weekend/shift multiplier is on the roadmap.)
- **No multi-currency.** EUR, Portuguese UI, PT date and number formats.
- **It is not a payroll system.** It tells you what to pay and prints the proof.

## Roadmap

| | |
|---|---|
| ✅ | Weeks, hours, pool, provable split, payslips, cash sheet, exports |
| ✅ | Vales ledger per week, optional advance, per-advance ceiling |
| ✅ | PIN gate, audit trail, unlock-with-reason, mobile layout |
| ✅ | Staff page (own numbers + the week's table), real navigation |
| ⏭ | Demo bundle: a fictional bar with 8 weeks of history |
| ⏭ | English UI toggle (the interface is PT-PT) |
| 💭 | Edit/remove staff that have history (recompute old weeks) |
| 💭 | Shift/weekend multiplier for hours |
| 💭 | PWA so it works offline on a phone behind the bar |

## Stack

FastAPI + plain `sqlite3` (no ORM) + one HTML file with vanilla JS, system font stacks
(no webfonts — it runs on a venue LAN with no internet). `openpyxl` for Excel exports.
Default UI language: Portuguese (PT-PT).

---

Private repo. Bar-tech venture: `TipSplit` (this) + `BarSpec` (public).
