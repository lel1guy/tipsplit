# TipSplit

Weekly staff tips splitter for bars and restaurants. The Excel workflow,
rebuilt: each staff member earns points for the week, the tip pool is
divided proportionally, and vales (cash advances) come off each share.

share = pool × (points ÷ total points) − vales

Sister app to BarSpec — same stack, same design language.

## Run it

```bash
cd tipsplit
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8001
```

Open http://127.0.0.1:8001

First run seeds one real sample week (29 Jul 2024, from the actual
Tips_2024.xlsx sheet): 12 staff, pool €555, shares match the original
spreadsheet exactly — use it to verify the math against Excel.

## Tests

```bash
pip install pytest
python -m pytest tests/ -q
```

Regression suite for the split math: shares must match the source
spreadsheet, always balance to the cent (largest-remainder rounding),
deduct vales, and never go negative.

## What it does

- Staff roster (shared across all weeks). Staff with history can't be
  deleted — that would corrupt old splits.
- One screen per week: pool in, points + vales per person, net share out.
- Live share preview while you type, with a pool check ("fully split"
  or "€X over/under") before you save.
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
| GET | `/api/weeks/{id}` | week + entries + shares |
| PUT | `/api/weeks/{id}/save` | save pool + all entries in one shot |
| DELETE | `/api/weeks/{id}` | delete week |

## Roadmap (not started)

- Per-day tip entry (Mon–Sun columns like the sheet) that sums to the pool
- Edit/remove staff that have history (recompute old weeks)
- Export week as PDF/pay-slip printout for staff to sign
- Weighted points presets (weekend multiplier)
- PWA so it works offline on a phone behind the bar
