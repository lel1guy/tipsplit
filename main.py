"""TipSplit — weekly staff tips splitter for bars/restaurants.

Mirrors the classic Excel sheet: each staff member logs hours for the week,
the tip pool is divided proportionally, and vales (cash advances) are
deducted from each share.

    share = pool × (hours / total_hours) − vales

Money math lives in splitting.py and runs SERVER-side only — the browser
renders what the server returns (preview endpoint), so there is one formula.
Vales live in a dated ledger (db.vales), never in the week's entry rows.

Run:  uvicorn main:app --reload   then open http://127.0.0.1:8001
"""
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

import db
import splitting

app = FastAPI(title="TipSplit")

BASE_DIR = Path(__file__).resolve().parent
db.init_db()


# ---------- Pydantic models ----------

class StaffIn(BaseModel):
    name: str
    position: str = ""

class WeekIn(BaseModel):
    start_date: str          # ISO "2024-07-29" (the Monday)

class EntryIn(BaseModel):
    """Hours only — vales are ledger rows, not part of a save."""
    staff_id: int
    mon: float = 0.0
    tue: float = 0.0
    wed: float = 0.0
    thu: float = 0.0
    fri: float = 0.0
    sat: float = 0.0
    sun: float = 0.0

class WeekSaveIn(BaseModel):
    pool_eur: float = 0.0
    entries: list[EntryIn] = []

class ValeIn(BaseModel):
    staff_id: int
    amount: float
    note: str = ""
    week_id: int | None = None      # None = open week, -1 = standalone
    date: str | None = None


def _lang(lang: str) -> str:
    return "pt" if (lang or "pt").lower().startswith("pt") else "en"


def _preview(pool_eur: float, entries: list[dict], lang: str) -> dict:
    """Everything the UI needs to render a split — computed, never stored."""
    total_hours = splitting.total_hours(entries)
    shares = splitting.compute_shares(pool_eur, entries)
    gross = splitting.gross_shares(pool_eur, entries)
    shortfall = round(sum(splitting.vale_debt(gross.get(e["staff_id"], 0.0),
                                              float(e.get("vales") or 0))
                          for e in entries), 2)
    return {
        "shares": shares,
        "gross_shares": gross,
        "total_hours": total_hours,
        "rate_per_hour": splitting.rate_per_hour(pool_eur, total_hours),
        "vale_shortfall": shortfall,
        "statement": splitting.statement(pool_eur, total_hours, lang),
    }


# ---------- Pages ----------

@app.get("/")
def index():
    return FileResponse(BASE_DIR / "static" / "index.html")


# ---------- Staff ----------

@app.get("/api/staff")
def list_staff(include_archived: bool = True):
    return db.get_staff(include_archived=include_archived)

@app.post("/api/staff")
def create_staff(s: StaffIn):
    name = s.name.strip()
    if not name:
        raise HTTPException(400, "Name needed")
    return db.create_staff(name, s.position.strip())

@app.post("/api/staff/{staff_id}/archive")
def archive_staff(staff_id: int, archived: bool = True):
    out = db.archive_staff(staff_id, archived)
    if out is None:
        raise HTTPException(404, "Staff not found")
    return out

@app.delete("/api/staff/{staff_id}")
def delete_staff(staff_id: int):
    ok = db.delete_staff(staff_id)
    if not ok:
        raise HTTPException(400, "Staff has history — archive instead")
    return {"ok": True}


# ---------- Vales ledger ----------

@app.get("/api/vales")
def list_vales(staff_id: int | None = None, week_id: int | None = None):
    return db.get_vales(staff_id=staff_id, week_id=week_id)

@app.post("/api/vales")
def create_vale(v: ValeIn):
    row = db.record_vale(v.staff_id, v.amount, v.note, v.week_id, v.date)
    if row is None:
        raise HTTPException(400, "Amount must be positive and staff must exist")
    return row

@app.delete("/api/vales/{vale_id}")
def delete_vale(vale_id: int):
    if not db.delete_vale(vale_id):
        raise HTTPException(404, "Vale not found")
    return {"ok": True}


# ---------- Team + dashboard ----------

@app.get("/api/team")
def team():
    return db.get_team()

@app.get("/api/dashboard")
def dash():
    return db.dashboard()


# ---------- Weeks ----------

@app.get("/api/weeks")
def list_weeks():
    return db.get_weeks()

@app.post("/api/weeks")
def create_week(w: WeekIn):
    return db.create_week(w.start_date)

@app.get("/api/weeks/{week_id}")
def get_week(week_id: int, lang: str = "pt"):
    wk = db.get_week(week_id)
    if not wk:
        raise HTTPException(404, "Week not found")
    wk["statement"] = splitting.statement(wk["pool_eur"], wk["total_hours"], _lang(lang))
    return wk

@app.put("/api/weeks/{week_id}")
def update_week(week_id: int, w: WeekIn):
    ok = db.update_week(week_id, w.start_date)
    if not ok:
        raise HTTPException(404, "Week not found")
    return {"ok": True}

@app.delete("/api/weeks/{week_id}")
def delete_week(week_id: int):
    db.delete_week(week_id)
    return {"ok": True}


# ---------- Entries (hours per staff per week) ----------

@app.put("/api/weeks/{week_id}/save")
def save_week(week_id: int, data: WeekSaveIn):
    """Save the whole week in one round-trip: pool + every entry's hours.
    The UI edits the full grid and saves once — no per-cell churn."""
    wk = db.get_week(week_id)
    if not wk:
        raise HTTPException(404, "Week not found")
    try:
        return db.save_week(week_id, data.pool_eur, [e.model_dump() for e in data.entries])
    except PermissionError:
        raise HTTPException(403, "Week is locked — unlock it first")

@app.post("/api/weeks/{week_id}/preview")
def preview_week(week_id: int, data: WeekSaveIn, lang: str = "pt"):
    """Live split preview for the edit grid — same math as saving, but
    nothing is written. Keeps the browser free of a second formula."""
    wk = db.get_week(week_id)
    if not wk:
        raise HTTPException(404, "Week not found")
    entries = [e.model_dump() for e in data.entries]
    # the week's vales come from the ledger, so the preview matches a save
    vales = {e["staff_id"]: e["vales"] for e in wk["entries"]}
    for e in entries:
        e["vales"] = vales.get(e["staff_id"], 0.0)
    return _preview(data.pool_eur, entries, _lang(lang))

@app.post("/api/weeks/{week_id}/lock")
def lock_week(week_id: int, closed_by: str = ""):
    """Close the week — money agreed. Unlocking (with a reason) is 004."""
    if not db.get_week(week_id):
        raise HTTPException(404, "Week not found")
    return db.lock_week(week_id, closed_by)
