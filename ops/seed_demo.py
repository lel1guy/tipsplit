#!/usr/bin/env python3
"""Fictional venue for demos and screenshots — deterministic and rerun-safe.

    TIPSPLIT_DB=/tmp/tipsplit-demo.db .venv/bin/python ops/seed_demo.py --weeks 8
    TIPSPLIT_DB=/tmp/tipsplit-demo.db .venv/bin/python -m uvicorn main:app --port 8791

Nothing here comes from a real venue: the bar, the names and every euro are invented.
The same seed always produces the same weeks, so screenshots and demos don't drift.

Owner PIN 1234 · one staff PIN 2468 (see DEMO_SCRIPT).
"""
import argparse
import datetime
import pathlib
import random
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import auth  # noqa: E402
import db  # noqa: E402

VENUE = "Bar Onda"
OWNER_PIN = "1234"
STAFF_PIN = "2468"
STAFF_PIN_NAME = "Ana Teixeira"

# fixed roster — a demo that looks the same every time
STAFF = [
    ("Ana Teixeira", "Bartender"),
    ("Bruno Ferreira", "Bartender"),
    ("Carla Rocha", "Empregado de mesa"),
    ("David Sousa", "Cozinha"),
    ("Eva Ferreira", "Bartender"),
    ("Filipe Almeida", "Barback"),
    ("Gonçalo Martins", "Empregado de mesa"),
    ("Helena Rocha", "Bartender"),
    ("Ivo Lopes", "Cozinha"),
    ("Joana Pereira", "Empregado de mesa"),
    ("Kátia Gomes", "Bartender"),
    ("Luís Carvalho", "Barback"),
]
SHIFTS = [4, 4.5, 5, 5.5, 6, 6.5, 7, 7.5, 8, 9]
VALE_NOTES = ["adiantamento", "gasolina", "transportes", "jantar", "tabaco"]


def monday_back(weeks_ago: int) -> str:
    today = datetime.date.today()
    monday = today - datetime.timedelta(days=today.weekday())
    return (monday - datetime.timedelta(weeks=weeks_ago)).isoformat()


def wipe():
    conn = db._conn()
    for table in ("vales", "entries", "week_pools", "weeks", "staff", "audit_log"):
        conn.execute(f"DELETE FROM {table}")
    conn.commit()
    conn.close()


def seed(weeks: int, hired_late: bool = True) -> dict:
    """Build the venue. `hired_late` leaves one person out of the oldest weeks, so the
    history shows a real roster change instead of a perfectly flat past."""
    rng = random.Random(7)          # fixed seed: same venue every run
    db.init_db()                    # schema + migrations (and its own throwaway seed)
    wipe()

    db.set_setting("venue_name", VENUE)
    db.set_setting("lang", "pt")
    db.set_setting("vale_max", "50")
    auth.set_pin(OWNER_PIN)

    people = []
    for name, position in STAFF:
        row = db.create_staff(name, position)
        people.append(row["id"])
    latecomer = people[-1]
    db.set_staff_pin(people[0], auth.hash_pin(STAFF_PIN))

    stats = {"weeks": [], "vales": 0, "paid": 0.0}
    for i in range(weeks):
        weeks_ago = weeks - 1 - i
        wk = db.create_week(monday_back(weeks_ago))
        if wk is None:
            continue
        pool = round(520.0 + 55.0 * i + rng.uniform(-40, 40), 2)
        roster = [p for p in people if not (hired_late and weeks_ago >= 4 and p == latecomer)]
        entries = []
        is_current = weeks_ago == 0        # the open week is fully filled: it's the hero
        for staff_id in roster:
            if not is_current and rng.random() < 0.12:   # someone was off all week
                hours = {d: 0.0 for d in db.DAYS}
            else:
                days = rng.sample(db.DAYS, rng.randint(4, 6))
                hours = {d: (rng.choice(SHIFTS) if d in days else 0.0) for d in db.DAYS}
            entries.append({"staff_id": staff_id, **hours})
        db.save_week(wk["id"], pool, entries)

        # advances: a handful of people, never everyone
        for staff_id in rng.sample(roster, rng.randint(2, 4)):
            amount = round(rng.choice([5, 7.5, 10, 12.5, 15, 20, 25, 30, 40]), 2)
            date = (datetime.date.fromisoformat(wk["start_date"])
                    + datetime.timedelta(days=rng.randint(0, 6))).isoformat()
            try:
                db.record_vale(staff_id, amount, rng.choice(VALE_NOTES),
                               week_id=wk["id"], date=date)
                stats["vales"] += 1
            except ValueError:
                pass                                    # above the demo ceiling: skip

        locked = i < weeks - 1                          # everything but the current week
        if locked:
            db.lock_week(wk["id"], "demo")
        full = db.get_week(wk["id"])
        stats["weeks"].append((wk["start_date"], full["total_hours"], full["pool_eur"],
                               "fechada" if locked else "aberta"))
        if locked:
            stats["paid"] += sum(full["shares"].values())
    return stats


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--weeks", type=int, default=8, help="how many weeks of history")
    args = ap.parse_args()

    print(f"seeding {VENUE} → {db.DB_PATH}")
    stats = seed(args.weeks)
    print(f"  {len(stats['weeks'])} semanas · {len(STAFF)} pessoas · "
          f"{stats['vales']} vales · {stats['paid']:.2f} € pagos")
    for start, hours, pool, status in stats["weeks"]:
        print(f"  {start}  {hours:>6} h  pool {pool:>8.2f} €  {status}")
    print(f"\nPIN do dono {OWNER_PIN} · PIN de {STAFF_PIN_NAME} {STAFF_PIN}")


if __name__ == "__main__":
    main()
