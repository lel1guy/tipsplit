"""TipSplit — weekly staff tips splitter for bars/restaurants.

Mirrors the classic Excel sheet: each staff member gets points for the week,
the tip pool is divided proportionally, and vales (cash advances) are
deducted from each share.

share = pool × (points / total_points) − vales

Run:  uvicorn main:app --reload   then open http://127.0.0.1:8001
"""
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

import db

app = FastAPI(title="TipSplit")

BASE_DIR = Path(__file__).resolve().parent
db.init_db()


# ---------- Pydantic models ----------

class StaffIn(BaseModel):
    name: str

class WeekIn(BaseModel):
    start_date: str          # ISO "2024-07-29" (the Monday)

class EntryIn(BaseModel):
    staff_id: int
    points: float = 0.0
    vales: float = 0.0

class WeekSaveIn(BaseModel):
    pool_eur: float = 0.0
    entries: list[EntryIn] = []


# ---------- Pages ----------

@app.get("/")
def index():
    return FileResponse(BASE_DIR / "static" / "index.html")


# ---------- Staff ----------

@app.get("/api/staff")
def list_staff():
    return db.get_staff()

@app.post("/api/staff")
def create_staff(s: StaffIn):
    name = s.name.strip()
    if not name:
        raise HTTPException(400, "Name needed")
    return db.create_staff(name)

@app.delete("/api/staff/{staff_id}")
def delete_staff(staff_id: int):
    ok = db.delete_staff(staff_id)
    if not ok:
        raise HTTPException(400, "Staff has history — deactivate instead")
    return {"ok": True}


# ---------- Weeks ----------

@app.get("/api/weeks")
def list_weeks():
    return db.get_weeks()

@app.post("/api/weeks")
def create_week(w: WeekIn):
    return db.create_week(w.start_date)

@app.get("/api/weeks/{week_id}")
def get_week(week_id: int):
    wk = db.get_week(week_id)
    if not wk:
        raise HTTPException(404, "Week not found")
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


# ---------- Entries (points + vales per staff per week) ----------

@app.put("/api/weeks/{week_id}/save")
def save_week(week_id: int, data: WeekSaveIn):
    """Save the whole week in one round-trip: pool + every entry.
    The UI edits the full grid and saves once — no per-cell churn."""
    wk = db.get_week(week_id)
    if not wk:
        raise HTTPException(404, "Week not found")
    return db.save_week(week_id, data.pool_eur, [e.model_dump() for e in data.entries])
