"""SQLite layer for TipSplit.

Plain sqlite3, no ORM — same style as BarSpec so both codebases read alike.
DB file: tipsplit.db (created on first run, gitignored).

Schema history lives in migrations/*.sql, applied in order and tracked with
PRAGMA user_version — a fresh install runs the same path as an upgraded one.

Money math lives in splitting.py (single source of truth); this module only
reads/writes rows.

Hours are the points: each staff member logs hours per day (Mon-Sun), the
week total drives the split:

    gross_share = pool × (week_hours / Σ week_hours)
    net_share   = gross_share − vales   (never below zero)
"""
import random
import sqlite3
from pathlib import Path

import splitting

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "tipsplit.db"
MIGRATIONS_DIR = BASE_DIR / "migrations"

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

DAYS = splitting.DAYS      # one source of truth for the day columns

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


# ---------- migrations ----------

def _version(conn) -> int:
    return conn.execute("PRAGMA user_version").fetchone()[0]


def migrate(conn):
    """Apply migrations/*.sql with a higher number than the current user_version."""
    current = _version(conn)
    for f in sorted(MIGRATIONS_DIR.glob("*.sql")):
        ver = int(f.name.split("_", 1)[0])
        if ver <= current:
            continue
        conn.executescript(f.read_text(encoding="utf-8"))
        conn.execute(f"PRAGMA user_version = {ver}")
        conn.commit()


def init_db():
    conn = _conn()
    # Base schema belongs only on a v0 database: it is the OLD shape, so
    # migration 001 exercises on every install, fresh or upgraded. Re-running
    # it on a migrated DB would re-add columns that already exist.
    if _version(conn) == 0:
        conn.executescript(SCHEMA)
    migrate(conn)
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
    wk.setdefault("status", "open")           # pre-001 rows
    wk.setdefault("closed_at", None)
    wk.setdefault("closed_by", None)
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
    wk["shares"] = splitting.compute_shares(wk["pool_eur"], entries)
    wk["gross_shares"] = splitting.gross_shares(wk["pool_eur"], entries)
    wk["rate_per_hour"] = splitting.rate_per_hour(wk["pool_eur"], wk["total_hours"])
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
    per-day hours and vales. A locked week is money agreed — refuse."""
    conn = _conn()
    row = conn.execute("SELECT status FROM weeks WHERE id=?", (week_id,)).fetchone()
    if row and row["status"] == "locked":
        conn.close()
        raise PermissionError("week is locked")
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


# ---------- Week lifecycle ----------

def lock_week(week_id: int, closed_by: str = ""):
    """Close a week: status locked + timestamp. Idempotent."""
    conn = _conn()
    conn.execute(
        "UPDATE weeks SET status='locked', "
        "closed_at=COALESCE(closed_at, datetime('now')), closed_by=? WHERE id=?",
        (closed_by, week_id),
    )
    conn.commit()
    conn.close()
    return get_week(week_id)
