"""SQLite layer for TipSplit.

Plain sqlite3, no ORM — same style as BarSpec so both codebases read alike.
DB file: tipsplit.db (created on first run, gitignored).

Points are HOURS worked: each staff member logs hours per day (Mon-Sun),
the week total drives the split:

    gross_share = pool × (week_hours / Σ week_hours)
    net_share   = gross_share − vales   (never below zero)
"""
import sqlite3
import math
import random
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "tipsplit.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS staff (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS weeks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    start_date TEXT NOT NULL UNIQUE   -- ISO Monday of the week
);

CREATE TABLE IF NOT EXISTS entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    week_id INTEGER NOT NULL REFERENCES weeks(id) ON DELETE CASCADE,
    staff_id INTEGER NOT NULL REFERENCES staff(id) ON DELETE CASCADE,
    mon REAL NOT NULL DEFAULT 0,
    tue REAL NOT NULL DEFAULT 0,
    wed REAL NOT NULL DEFAULT 0,
    thu REAL NOT NULL DEFAULT 0,
    fri REAL NOT NULL DEFAULT 0,
    sat REAL NOT NULL DEFAULT 0,
    sun REAL NOT NULL DEFAULT 0,
    vales REAL NOT NULL DEFAULT 0,
    UNIQUE (week_id, staff_id)
);

CREATE TABLE IF NOT EXISTS week_pools (
    week_id INTEGER PRIMARY KEY REFERENCES weeks(id) ON DELETE CASCADE,
    pool_eur REAL NOT NULL DEFAULT 0
);
"""

DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]

# Random demo names — deliberately NOT the real staff list from the
# spreadsheet V shared. The seed data is fictional so the app can be
# played with freely; real names get added through the UI.
DEMO_FIRST = ["Ana", "Bruno", "Carla", "David", "Eva", "Filipe", "Gonçalo",
              "Helena", "Ivo", "Joana", "Kátia", "Luís", "Marta", "Nuno"]
DEMO_LAST = ["", "Sousa", "Pereira", "Martins", "Rocha", "Teixeira", "Lopes",
             "Ferreira", "Almeida", "Ribeiro", "Carvalho", "Gomes"]


def _demo_staff():
    """Pick ~10-12 distinct fictional staff names."""
    random.shuffle(DEMO_FIRST)
    names = []
    for first in DEMO_FIRST[:random.randint(10, 12)]:
        last = random.choice(DEMO_LAST)
        names.append(f"{first} {last}".strip())
    return names


def _demo_hours():
    """A week of shifts for one person: mostly 5-6 days, 4-10 h/day.
    Returns (dict of day->hours, week total)."""
    worked_days = random.sample(DAYS, random.randint(4, 6))
    hours = {d: 0.0 for d in DAYS}
    for d in worked_days:
        # 0.5h granularity, realistic shift lengths
        hours[d] = random.choice([4, 4.5, 5, 5.5, 6, 6.5, 7, 7.5, 8, 9, 10])
    return hours


def _conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _current_monday():
    """ISO date of this week's Monday (seed data should look current)."""
    import datetime
    today = datetime.date.today()
    monday = today - datetime.timedelta(days=today.weekday())
    return monday.isoformat()


def init_db():
    conn = _conn()
    conn.executescript(SCHEMA)
    # Seed one random demo week if the DB is empty.
    if conn.execute("SELECT COUNT(*) FROM weeks").fetchone()[0] == 0:
        cur = conn.execute("INSERT INTO weeks (start_date) VALUES (?)",
                           (_current_monday(),))
        week_id = cur.lastrowid
        pool = round(random.uniform(400, 900), 0)
        conn.execute("INSERT INTO week_pools (week_id, pool_eur) VALUES (?,?)",
                     (week_id, pool))
        # Generate all staff + hours first so we can compute gross shares
        # and keep vales BELOW gross (a vale above gross = staff owes the pot,
        # which only confuses demo data).
        seeded = []
        for name in _demo_staff():
            conn.execute("INSERT INTO staff (name) VALUES (?)", (name,))
            srow = conn.execute("SELECT id FROM staff WHERE name=?", (name,)).fetchone()
            hours = _demo_hours()
            seeded.append((srow["id"], hours))
        total_hours = sum(sum(h.values()) for _, h in seeded)
        for staff_id, hours in seeded:
            week_hours = sum(hours.values())
            gross = pool * (week_hours / total_hours) if total_hours else 0
            vale = 0.0
            if random.random() < 0.35:          # ~1 in 3 took an advance
                max_vale = max(5.0, gross * 0.5)  # never above half their gross
                vale = round(random.uniform(5.0, max_vale), 2)
            conn.execute(
                f"""INSERT INTO entries
                    (week_id, staff_id, {", ".join(DAYS)}, vales)
                    VALUES (?,?,{", ".join(["?"] * len(DAYS))},?)""",
                (week_id, staff_id, *[hours[d] for d in DAYS], vale),
            )
        conn.commit()
    conn.close()


# ---------- Staff ----------

def get_staff():
    conn = _conn()
    rows = conn.execute("SELECT * FROM staff ORDER BY name").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def create_staff(name: str):
    conn = _conn()
    try:
        cur = conn.execute("INSERT INTO staff (name) VALUES (?)", (name,))
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        return None
    new_id = cur.lastrowid
    conn.close()
    return {"id": new_id, "name": name}


def delete_staff(staff_id: int) -> bool:
    """Only allow delete if the person has no history (would corrupt old splits)."""
    conn = _conn()
    n = conn.execute("SELECT COUNT(*) FROM entries WHERE staff_id=?", (staff_id,)).fetchone()[0]
    if n > 0:
        conn.close()
        return False
    conn.execute("DELETE FROM staff WHERE id=?", (staff_id,))
    conn.commit()
    conn.close()
    return True


# ---------- Weeks ----------

def _hours_of(row) -> float:
    return sum(float(row[d] or 0) for d in DAYS)


def _week_summary(conn, row) -> dict:
    wk = dict(row)
    wk["pool_eur"] = 0.0
    p = conn.execute("SELECT pool_eur FROM week_pools WHERE week_id=?", (wk["id"],)).fetchone()
    if p:
        wk["pool_eur"] = p["pool_eur"]
    return wk


def get_weeks():
    conn = _conn()
    rows = conn.execute("SELECT * FROM weeks ORDER BY start_date DESC").fetchall()
    out = [_week_summary(conn, r) for r in rows]
    conn.close()
    return out


def get_week(week_id: int):
    conn = _conn()
    row = conn.execute("SELECT * FROM weeks WHERE id=?", (week_id,)).fetchone()
    if not row:
        conn.close()
        return None
    wk = _week_summary(conn, row)
    estaff = conn.execute(
        f"""SELECT e.id, e.staff_id, s.name, {", ".join(DAYS)}, e.vales
            FROM entries e JOIN staff s ON s.id = e.staff_id
            WHERE e.week_id=? ORDER BY s.name""",
        (week_id,),
    ).fetchall()
    entries = []
    for r in estaff:
        e = dict(r)
        e["hours"] = round(_hours_of(r), 1)
        entries.append(e)
    wk["entries"] = entries
    wk["total_hours"] = round(sum(e["hours"] for e in entries), 1)
    wk["shares"] = _compute_shares(wk["pool_eur"], entries)
    conn.close()
    return wk


def create_week(start_date: str):
    conn = _conn()
    try:
        cur = conn.execute("INSERT INTO weeks (start_date) VALUES (?)", (start_date,))
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        return None
    week_id = cur.lastrowid
    conn.execute("INSERT INTO week_pools (week_id, pool_eur) VALUES (?,0)", (week_id,))
    conn.commit()
    conn.close()
    return get_week(week_id)


def update_week(week_id: int, start_date: str) -> bool:
    conn = _conn()
    cur = conn.execute("UPDATE weeks SET start_date=? WHERE id=?", (start_date, week_id))
    conn.commit()
    ok = cur.rowcount > 0
    conn.close()
    return ok


def delete_week(week_id: int):
    conn = _conn()
    conn.execute("DELETE FROM weeks WHERE id=?", (week_id,))
    conn.commit()
    conn.close()


def save_week(week_id: int, pool_eur: float, entries: list[dict]) -> dict:
    """Replace the week's pool + entries wholesale. Each entry carries
    per-day hours and vales."""
    conn = _conn()
    conn.execute("DELETE FROM entries WHERE week_id=?", (week_id,))
    conn.execute("UPDATE week_pools SET pool_eur=? WHERE week_id=?", (pool_eur, week_id))
    for e in entries:
        conn.execute(
            f"""INSERT INTO entries (week_id, staff_id, {", ".join(DAYS)}, vales)
                VALUES (?,?,{", ".join(["?"] * len(DAYS))},?)""",
            (week_id, e["staff_id"],
             *[float(e.get(d, 0) or 0) for d in DAYS],
             float(e.get("vales", 0) or 0)),
        )
    conn.commit()
    conn.close()
    return get_week(week_id)


# ---------- The split math ----------

def _compute_shares(pool_eur: float, entries: list[dict]) -> dict:
    """gross_i = pool × hours_i / Σhours, net = gross − vales (never < 0).

    Largest-remainder rounding on the GROSS shares so they always sum to
    exactly the pool. Without it, N shares rounded independently drift and
    the cash never balances.
    """
    total = sum(e["hours"] for e in entries)
    if total <= 0:
        return {e["staff_id"]: 0.0 for e in entries}

    exact = {e["staff_id"]: pool_eur * (e["hours"] / total) for e in entries}
    floored = {sid: math.floor(v * 100) / 100 for sid, v in exact.items()}
    leftover_cents = round((pool_eur - sum(floored.values())) * 100)

    order = sorted(floored.keys(), key=lambda sid: exact[sid] - floored[sid], reverse=True)
    for i in range(leftover_cents):
        floored[order[i % len(order)]] += 0.01

    vales = {e["staff_id"]: e["vales"] for e in entries}
    shares = {}
    for sid, gross in floored.items():
        shares[sid] = round(max(0.0, gross - vales.get(sid, 0.0)), 2)
    return shares
