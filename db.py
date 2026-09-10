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

Vales are dated ledger rows (migration 002) — never a stored week total.
"""
import os
import random
import sqlite3
from pathlib import Path

import splitting

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = Path(os.environ.get("TIPSPLIT_DB", BASE_DIR / "tipsplit.db"))
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
DEMO_POSITIONS = ["Bartender", "Barback", "Empregado de mesa", "Cozinha", ""]


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


def _today():
    import datetime
    return datetime.date.today().isoformat()


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
    # migration 001 (and 002) exercise on every install, fresh or upgraded.
    # Re-running it on a migrated DB would re-add columns that already exist.
    if _version(conn) == 0:
        conn.executescript(SCHEMA)
    migrate(conn)
    # Seed one random demo week if the DB is empty.
    if conn.execute("SELECT COUNT(*) FROM weeks").fetchone()[0] == 0:
        _seed_demo(conn)
    conn.close()


def _seed_demo(conn):
    """One fictional week: staff, hours, pool, and a couple of vales.
    Writes through the NEW schema (vales are ledger rows, not a column)."""
    start = _current_monday()
    cur = conn.execute("INSERT INTO weeks (start_date) VALUES (?)", (start,))
    week_id = cur.lastrowid
    pool = round(random.uniform(400, 900), 0)
    conn.execute("INSERT INTO week_pools (week_id, pool_eur) VALUES (?,?)",
                 (week_id, pool))
    seeded = []
    for name in _demo_staff():
        conn.execute("INSERT INTO staff (name, position) VALUES (?,?)",
                     (name, random.choice(DEMO_POSITIONS)))
        srow = conn.execute("SELECT id FROM staff WHERE name=?", (name,)).fetchone()
        seeded.append((srow["id"], _demo_hours()))
    total_hours = sum(sum(h.values()) for _, h in seeded)
    for staff_id, hours in seeded:
        week_hours = sum(hours.values())
        gross = pool * (week_hours / total_hours) if total_hours else 0
        conn.execute(
            f"""INSERT INTO entries (week_id, staff_id, {", ".join(DAYS)})
                VALUES (?,?,{", ".join(["?"] * len(DAYS))})""",
            (week_id, staff_id, *[hours[d] for d in DAYS]),
        )
        if random.random() < 0.35:              # ~1 in 3 took an advance
            max_vale = max(5.0, gross * 0.5)    # demo keeps vales below gross
            conn.execute(
                "INSERT INTO vales (staff_id, date, week_id, amount, note) VALUES (?,?,?,?,?)",
                (staff_id, start, week_id, round(random.uniform(5.0, max_vale), 2), "seed"),
            )
    conn.commit()


# ---------- Staff ----------

def get_staff(include_archived: bool = True):
    conn = _conn()
    sql = "SELECT * FROM staff"
    if not include_archived:
        sql += " WHERE archived = 0"
    rows = conn.execute(sql + " ORDER BY archived, name").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def create_staff(name: str, position: str = ""):
    conn = _conn()
    try:
        cur = conn.execute("INSERT INTO staff (name, position) VALUES (?,?)",
                           (name, position))
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        return None
    new_id = cur.lastrowid
    conn.close()
    return {"id": new_id, "name": name, "position": position}


def archive_staff(staff_id: int, archived: bool = True):
    """Soft flag, not delete — churn happens and history has to survive."""
    conn = _conn()
    cur = conn.execute("UPDATE staff SET archived=? WHERE id=?",
                       (1 if archived else 0, staff_id))
    conn.commit()
    conn.close()
    return None if cur.rowcount == 0 else {"id": staff_id, "archived": bool(archived)}


def delete_staff(staff_id: int) -> bool:
    """Hard delete only for someone with no history at all (typo cleanup).
    Everyone else gets archived — old splits must keep their names."""
    conn = _conn()
    n = conn.execute("SELECT COUNT(*) FROM entries WHERE staff_id=?", (staff_id,)).fetchone()[0]
    if n > 0:
        conn.close()
        return False
    conn.execute("DELETE FROM staff WHERE id=?", (staff_id,))
    conn.commit()
    conn.close()
    return True


# ---------- Per-staff access (the /equipa view) ----------

def staff_pin_hash(staff_id: int) -> str:
    conn = _conn()
    row = conn.execute("SELECT pin_hash FROM staff WHERE id=?", (staff_id,)).fetchone()
    conn.close()
    return (row["pin_hash"] or "") if row else ""


def set_staff_pin(staff_id: int, pin_hash: str):
    conn = _conn()
    cur = conn.execute("UPDATE staff SET pin_hash=? WHERE id=?", (pin_hash, staff_id))
    conn.commit()
    conn.close()
    return None if cur.rowcount == 0 else {"id": staff_id, "has_pin": bool(pin_hash)}


def staff_with_pins():
    """Active staff who already have a PIN — used to resolve a login, so the hash
    comes back with the row (never leaves the server)."""
    conn = _conn()
    rows = conn.execute(
        "SELECT id, name, pin_hash FROM staff WHERE archived=0 AND pin_hash <> '' "
        "ORDER BY name").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def staff_view(staff_id: int, weeks: int = 12):
    """Everything one person may see and nothing else: their line for the week that
    concerns them, the week's table (transparent sharing — the venue's call), their
    own advances and their own locked history.

    "Their week" = the most recent week they actually worked, open or locked. Payday
    is when a week is locked and a fresh empty week may already exist — nobody wants
    to open their page and see zeros.
    """
    person = next((s for s in get_staff() if s["id"] == staff_id), None)
    if person is None:
        return None
    out = {"staff": {"id": person["id"], "name": person["name"],
                     "position": person["position"],
                     "archived": bool(person["archived"])},
           "week": None, "mine": None, "team": [], "vales": [], "history": []}

    history, current, current_line = [], None, None
    for w in get_weeks()[:weeks]:
        full = get_week(w["id"])
        line = next((x for x in full["entries"] if x["staff_id"] == staff_id), None)
        worked = bool(line and line["hours"])
        if worked and current is None:
            current, current_line = full, line             # newest week they worked
            continue
        if worked and w["status"] == "locked":
            history.append({"week_id": w["id"], "start_date": w["start_date"],
                            "hours": line["hours"], "vales": line["vales"],
                            "net": full["shares"].get(staff_id, 0.0)})

    if current is None:                                    # no hours anywhere yet
        ws = get_weeks()[:weeks]
        current = get_week(ws[0]["id"]) if ws else None
        if current:
            current_line = next((x for x in current["entries"]
                                 if x["staff_id"] == staff_id), None)

    if current:
        out["week"] = {
            "id": current["id"], "start_date": current["start_date"],
            "status": current["status"], "pool_eur": current["pool_eur"],
            "total_hours": current["total_hours"],
            "rate_per_hour": current["rate_per_hour"],
            "statement": splitting.statement(current["pool_eur"], current["total_hours"]),
        }
        if current_line:
            out["mine"] = {"hours": current_line["hours"], "vales": current_line["vales"],
                           "gross": current["gross_shares"].get(staff_id, 0.0),
                           "net": current["shares"].get(staff_id, 0.0)}
        out["team"] = [{"name": e["name"], "hours": e["hours"],
                        "vales": e["vales"],
                        "gross": current["gross_shares"].get(e["staff_id"], 0.0),
                        "net": current["shares"].get(e["staff_id"], 0.0),
                        "me": e["staff_id"] == staff_id}
                       for e in current["entries"] if e["hours"] or e["vales"]]

    out["vales"] = vales_by_week(staff_id=staff_id)     # grouped per week, own only
    out["history"] = history
    return out


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
        f"""SELECT e.id, e.staff_id, s.name, s.position, s.archived, {", ".join(DAYS)}
            FROM entries e JOIN staff s ON s.id = e.staff_id
            WHERE e.week_id=? ORDER BY s.name""",
        (week_id,),
    ).fetchall()
    vales = _week_vales(conn, week_id)
    entries = []
    for r in estaff:
        e = dict(r)
        e["hours"] = round(_hours_of(r), 1)
        e["vales"] = vales.get(e["staff_id"], 0.0)   # derived from the ledger
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
    """Replace the week's pool + hours wholesale. Vales are NOT here — they
    live in the ledger and are read back. A locked week is money agreed — refuse."""
    conn = _conn()
    row = conn.execute("SELECT status FROM weeks WHERE id=?", (week_id,)).fetchone()
    if row and row["status"] == "locked":
        conn.close()
        raise PermissionError("week is locked")
    conn.execute("DELETE FROM entries WHERE week_id=?", (week_id,))
    conn.execute("UPDATE week_pools SET pool_eur=? WHERE week_id=?", (pool_eur, week_id))
    for e in entries:
        conn.execute(
            f"""INSERT INTO entries (week_id, staff_id, {", ".join(DAYS)})
                VALUES (?,?,{", ".join(["?"] * len(DAYS))})""",
            (week_id, e["staff_id"], *[float(e.get(d, 0) or 0) for d in DAYS]),
        )
    conn.commit()
    conn.close()
    return get_week(week_id)


# ---------- Vales ledger ----------

def _week_vales(conn, week_id: int) -> dict:
    """Σ vales per staff for one week (0 for anyone with none)."""
    rows = conn.execute(
        "SELECT staff_id, ROUND(SUM(amount),2) AS total FROM vales "
        "WHERE week_id=? GROUP BY staff_id", (week_id,)).fetchall()
    return {r["staff_id"]: float(r["total"] or 0) for r in rows}


def open_week_id():
    """Latest week that is still open — where a new advance belongs."""
    conn = _conn()
    row = conn.execute(
        "SELECT id FROM weeks WHERE status='open' ORDER BY start_date DESC LIMIT 1").fetchone()
    conn.close()
    return row["id"] if row else None


def record_vale(staff_id: int, amount: float, note: str = "",
                week_id: int | None = None, date: str | None = None):
    """One dated advance, always attached to a week (V, 2026-09-10).

    week_id None → the open week. With no week at all there is nothing to deduct
    from, so that raises instead of creating an orphan. Returns the row, or None
    for a bad amount or an unknown person.
    """
    amount = round(float(amount), 2)
    if amount <= 0:
        return None
    if week_id is None:
        week_id = open_week_id()
    if week_id is None:
        raise ValueError("no week to attach the advance to")
    conn = _conn()
    if not conn.execute("SELECT 1 FROM staff WHERE id=?", (staff_id,)).fetchone():
        conn.close()
        return None
    if not conn.execute("SELECT 1 FROM weeks WHERE id=?", (week_id,)).fetchone():
        conn.close()
        raise ValueError("unknown week")
    cur = conn.execute(
        "INSERT INTO vales (staff_id, date, week_id, amount, note) VALUES (?,?,?,?,?)",
        (staff_id, date or _today(), week_id, amount, note))
    conn.commit()
    vid = cur.lastrowid
    conn.close()
    return get_vale(vid)


def vales_by_week(staff_id: int | None = None, limit: int = 12):
    """The ledger grouped the way it is now read: per week. Each bucket carries its
    own subtotal, newest week first."""
    rows = get_vales(staff_id=staff_id)
    weeks = {w["id"]: w for w in get_weeks()}
    buckets: dict[int | None, dict] = {}
    for v in rows:
        b = buckets.setdefault(v["week_id"], {
            "week_id": v["week_id"],
            "start_date": (weeks.get(v["week_id"]) or {}).get("start_date"),
            "status": (weeks.get(v["week_id"]) or {}).get("status"),
            "rows": [], "total": 0.0})
        b["rows"].append(v)
        b["total"] = round(b["total"] + v["amount"], 2)
    out = sorted(buckets.values(),
                 key=lambda b: (b["start_date"] or "", b["week_id"] or 0), reverse=True)
    return out[:limit]


def get_vale(vale_id: int):
    conn = _conn()
    row = conn.execute(
        "SELECT v.*, s.name FROM vales v JOIN staff s ON s.id = v.staff_id WHERE v.id=?",
        (vale_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_vales(staff_id: int | None = None, week_id: int | None = None):
    conn = _conn()
    sql = ("SELECT v.*, s.name FROM vales v JOIN staff s ON s.id = v.staff_id")
    where, args = [], []
    if staff_id is not None:
        where.append("v.staff_id=?"); args.append(staff_id)
    if week_id is not None:
        where.append("v.week_id=?"); args.append(week_id)
    if where:
        sql += " WHERE " + " AND ".join(where)
    rows = conn.execute(sql + " ORDER BY v.date DESC, v.id DESC", args).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_vale(vale_id: int) -> bool:
    conn = _conn()
    cur = conn.execute("DELETE FROM vales WHERE id=?", (vale_id,))
    conn.commit()
    conn.close()
    return cur.rowcount > 0


# ---------- Team + dashboard ----------

def get_team():
    """Roster with vale balances: this week (open week) + lifetime."""
    conn = _conn()
    wk = conn.execute(
        "SELECT id FROM weeks WHERE status='open' ORDER BY start_date DESC LIMIT 1").fetchone()
    week_id = wk["id"] if wk else None
    this_week = _week_vales(conn, week_id) if week_id else {}
    totals = {r["staff_id"]: float(r["total"] or 0) for r in conn.execute(
        "SELECT staff_id, ROUND(SUM(amount),2) AS total FROM vales GROUP BY staff_id")}
    rows = conn.execute("SELECT * FROM staff ORDER BY archived, name").fetchall()
    conn.close()
    out = []
    for r in rows:
        s = dict(r)
        s["vales_week"] = this_week.get(s["id"], 0.0)
        s["vales_total"] = totals.get(s["id"], 0.0)
        s["has_pin"] = bool(s.pop("pin_hash", ""))     # the hash never leaves the server
        out.append(s)
    return {"week_id": week_id, "staff": out}


def dashboard():
    """Doors-of-the-venue numbers. Deliberately no month-per-staff here —
    that is a trend, and trends wait until there's history worth charting."""
    conn = _conn()
    row = conn.execute(
        "SELECT id FROM weeks WHERE status='open' ORDER BY start_date DESC LIMIT 1").fetchone()
    open_week = get_week(row["id"]) if row else None
    last_closed_row = conn.execute(
        "SELECT id FROM weeks WHERE status='locked' ORDER BY start_date DESC LIMIT 1").fetchone()
    last_closed = get_week(last_closed_row["id"]) if last_closed_row else None
    conn.close()

    warnings = []
    if open_week:
        for e in open_week["entries"]:
            gross = open_week["gross_shares"].get(e["staff_id"], 0.0)
            if e["vales"] > gross > 0:
                warnings.append({"staff_id": e["staff_id"], "name": e["name"],
                                 "vales": e["vales"], "gross": gross})
    return {
        "week": None if not open_week else {
            "id": open_week["id"], "start_date": open_week["start_date"],
            "pool_eur": open_week["pool_eur"], "status": open_week["status"],
            "total_hours": open_week["total_hours"],
            "net_total": round(sum(open_week["shares"].values()), 2),
            "vales_total": round(sum(e["vales"] for e in open_week["entries"]), 2),
        },
        "open_week_id": open_week["id"] if open_week else None,
        "vale_warnings": warnings,
        "last_closed": None if not last_closed else {
            "start_date": last_closed["start_date"],
            "net_total": round(sum(last_closed["shares"].values()), 2),
            "staff": len(last_closed["entries"]),
        },
        "staff_active": len(get_staff(include_archived=False)),
    }


# ---------- Settings ----------

def get_setting(key: str, default: str = "") -> str:
    conn = _conn()
    row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    conn.close()
    return row["value"] if row else default


def set_setting(key: str, value: str) -> None:
    conn = _conn()
    conn.execute("INSERT INTO settings (key, value) VALUES (?,?) "
                 "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, value))
    conn.commit()
    conn.close()


# ---------- Annual report (payday paperwork for the tax return) ----------

def annual(year: int) -> dict:
    """Per-staff tip totals for a year: month buckets + gross/vales/net.
    Derived from the weeks every time — nothing stored, nothing to rot."""
    conn = _conn()
    weeks = conn.execute(
        "SELECT id FROM weeks WHERE start_date LIKE ? ORDER BY start_date",
        (f"{year}-%",)).fetchall()
    conn.close()
    months, staff = set(), {}
    for r in weeks:
        w = get_week(r["id"])
        m = int(w["start_date"][5:7])
        months.add(m)
        for e in w["entries"]:
            sid = e["staff_id"]
            s = staff.setdefault(sid, {
                "staff_id": sid, "name": e["name"], "position": e.get("position") or "",
                "monthly": {}, "gross": 0.0, "vales": 0.0, "net": 0.0})
            net = w["shares"].get(sid, 0.0)
            s["monthly"][m] = round(s["monthly"].get(m, 0.0) + net, 2)
            s["gross"] = round(s["gross"] + w["gross_shares"].get(sid, 0.0), 2)
            s["vales"] = round(s["vales"] + e["vales"], 2)
            s["net"] = round(s["net"] + net, 2)
    return {"year": year, "weeks": len(weeks), "months": sorted(months),
            "staff": list(staff.values())}


# ---------- Audit log ----------

def audit(action: str, detail: str = "", actor: str = "") -> None:
    conn = _conn()
    conn.execute("INSERT INTO audit_log (actor, action, detail) VALUES (?,?,?)",
                 (actor, action, detail))
    conn.commit()
    conn.close()


def get_audit(limit: int = 50):
    conn = _conn()
    rows = conn.execute("SELECT * FROM audit_log ORDER BY id DESC LIMIT ?",
                        (max(1, min(limit, 200)),)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def unlock_week(week_id: int, reason: str, actor: str = ""):
    """Reopen a locked week. The reason is mandatory — that's the point."""
    reason = (reason or "").strip()
    if not reason:
        raise ValueError("reason required")
    conn = _conn()
    cur = conn.execute(
        "UPDATE weeks SET status='open', closed_at=NULL, closed_by='' WHERE id=?",
        (week_id,))
    conn.commit()
    conn.close()
    if cur.rowcount == 0:
        return None
    audit("week.unlock", f"week={week_id} motivo={reason}", actor)
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
