# TipSplit

Weekly staff tips splitter for bars and restaurants. Each staff member logs
**hours worked per day (Mon–Sun)**; the week's total hours drive the split,
and vales (cash advances) come off each share.

    share = pool × (person's hours ÷ total hours) − vales

Sister app to BarSpec — same stack, same design language.

## Run it

```bash
cd tipsplit
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8001
```

Open http://127.0.0.1:8001

First run seeds one demo week with **fictional staff and random hours** —
the real names from any bar get added through the UI. The seed is only
there so you can play with the split immediately.

## Tests

```bash
pip install pytest
python -m pytest tests/ -q
```

Regression suite for the split math: hours drive shares proportionally,
gross always balances to the cent (largest-remainder rounding), vales
deduct, nets never go negative, and demo data can't break the invariants.

## What it does

- Day grid per staff member (Mon–Sun, 0.5h steps) with auto-totaled hours.
- Staff roster shared across all weeks. Staff with history can't be
  deleted — that would corrupt old splits.
- One screen per week: pool in, hours + vales per person, net share out.
- Live share preview while you type, with a pool check that reads
  "fully split" or "split + €X in vales" before you save.
- Week history — no more one-tab-per-week Excel file.
- New weeks default to the current Monday.

## API

| Method | Path | What |
|--------|------|------|
| GET | `/api/staff` | roster |
| POST | `/api/staff` | add staff |
| DELETE | `/api/staff/{id}` | delete (only if no history) |
| GET | `/api/weeks` | week list |
| POST | `/api/weeks` | create week by Monday date (ISO) |
| GET | `/api/weeks/{id}` | week + entries (per-day hours) + shares |
| PUT | `/api/weeks/{id}/save` | save pool + all entries in one shot |
| DELETE | `/api/weeks/{id}` | delete week |

## Roadmap (not started)

- Edit/remove staff that have history (recompute old weeks)
- Export week as PDF/pay-slip printout for staff to sign
- Weekend shift multiplier for hours
- PWA so it works offline on a phone behind the bar
