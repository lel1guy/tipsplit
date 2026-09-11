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
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
from pydantic import BaseModel

import auth
import db
import exporters
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


def _lang_setting() -> str:
    """The venue's language, as stored in Definições."""
    return "en" if (db.get_setting("lang", "pt") or "pt").lower().startswith("en") else "pt"


def _msg(pt: str, en: str) -> str:
    """User-facing API messages follow the same setting as the interface."""
    return en if _lang_setting() == "en" else pt


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
        raise HTTPException(400, _msg("Falta o nome", "Name needed"))
    return db.create_staff(name, s.position.strip())

@app.post("/api/staff/{staff_id}/archive")
def archive_staff(staff_id: int, archived: bool = True):
    out = db.archive_staff(staff_id, archived)
    if out is None:
        raise HTTPException(404, _msg("Pessoa não encontrada", "Staff not found"))
    db.audit("staff.arquivar" if archived else "staff.reativar", f"staff={staff_id}")
    return out

@app.delete("/api/staff/{staff_id}")
def delete_staff(staff_id: int):
    ok = db.delete_staff(staff_id)
    if not ok:
        raise HTTPException(400, _msg("Tem histórico — arquive em vez de apagar", "Has history — archive instead"))
    return {"ok": True}


# ---------- Vales ledger ----------

@app.get("/api/vales")
def list_vales(staff_id: int | None = None, week_id: int | None = None):
    return db.get_vales(staff_id=staff_id, week_id=week_id)

@app.post("/api/vales")
def create_vale(v: ValeIn):
    """An advance always belongs to a week — with no week there is nothing to
    deduct from, so that's a 400, not an orphan row."""
    try:
        row = db.record_vale(v.staff_id, v.amount, v.note, v.week_id, v.date)
    except ValueError as e:
        raise HTTPException(400, f"Semana inválida: {e}")
    if row is None:
        raise HTTPException(400, _msg("Valor tem de ser positivo e a pessoa tem de existir", "Amount must be positive and the person must exist"))
    db.audit("vale.add", f"{row['name']} {row['amount']}€ semana={row['week_id']}")
    return row


@app.get("/api/vales/grouped")
def vales_grouped(limit: int = 12):
    """The ledger read the way V reads it: one bucket per week."""
    return db.vales_by_week(limit=limit)

@app.delete("/api/vales/{vale_id}")
def delete_vale(vale_id: int):
    row = db.get_vale(vale_id)
    if not db.delete_vale(vale_id):
        raise HTTPException(404, "Vale not found")
    db.audit("vale.apagar", f"{row['name']} {row['amount']}€")
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
        out = db.save_week(week_id, data.pool_eur, [e.model_dump() for e in data.entries])
    except PermissionError:
        raise HTTPException(403, _msg("Semana fechada — desbloqueie primeiro", "Week is locked — unlock it first"))
    db.audit("week.guardar", f"semana={week_id} pool={data.pool_eur} linhas={len(data.entries)}")
    return out

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
    """Close the week — money agreed. Reopening needs a reason (T-D)."""
    if not db.get_week(week_id):
        raise HTTPException(404, "Week not found")
    out = db.lock_week(week_id, closed_by)
    db.audit("week.fechar", f"semana={week_id}")
    return out


class UnlockIn(BaseModel):
    reason: str = ""


@app.post("/api/weeks/{week_id}/unlock")
def unlock_week(week_id: int, u: UnlockIn):
    """Reopen a settled week — the reason is required and gets logged."""
    try:
        out = db.unlock_week(week_id, u.reason)
    except ValueError:
        raise HTTPException(400, _msg("Motivo obrigatório", "A reason is required"))
    if out is None:
        raise HTTPException(404, "Week not found")
    return out


# ---------- Payday: payslips, cash sheet, exports ----------

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _locked_week(week_id: int):
    """Payday paperwork belongs to a settled week — an open week prints 409."""
    wk = db.get_week(week_id)
    if not wk:
        raise HTTPException(404, "Week not found")
    if wk["status"] != "locked":
        raise HTTPException(409, _msg("Feche a semana primeiro", "Lock the week first"))
    return wk


def _download(body, media_type: str, filename: str):
    return Response(body, media_type=media_type,
                    headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@app.get("/print/payslips/{week_id}", response_class=HTMLResponse)
def print_payslips(week_id: int):
    return exporters.payslips_html(_locked_week(week_id), db.get_setting("venue_name"),
                                   _lang_setting())


@app.get("/print/cashsheet/{week_id}", response_class=HTMLResponse)
def print_cashsheet(week_id: int):
    return exporters.cashsheet_html(_locked_week(week_id), db.get_setting("venue_name"),
                                    _lang_setting())


@app.get("/api/export/week/{week_id}")
def export_week(week_id: int, fmt: str = "csv"):
    wk = db.get_week(week_id)
    if not wk:
        raise HTTPException(404, "Week not found")
    name = f"gorjetas-{wk['start_date']}"
    if fmt == "xlsx":
        return _download(exporters.week_xlsx(wk).getvalue(), XLSX, f"{name}.xlsx")
    return _download(exporters.week_csv(wk), "text/csv; charset=utf-8", f"{name}.csv")


@app.get("/api/export/annual/{year}")
def export_annual(year: int, fmt: str = "xlsx"):
    report = db.annual(year)
    if fmt == "csv":
        return _download(exporters.annual_csv(report), "text/csv; charset=utf-8",
                         f"gorjetas-{year}.csv")
    return _download(exporters.annual_xlsx(report).getvalue(), XLSX, f"gorjetas-{year}.xlsx")


# ---------- T-D: PIN gate, settings, audit ----------

class PinIn(BaseModel):
    pin: str

class SettingsIn(BaseModel):
    venue_name: str | None = None
    lang: str | None = None
    vale_max: float | None = None          # 0 = sem limite


def _settings() -> dict:
    return {"venue_name": db.get_setting("venue_name"),
            "lang": db.get_setting("lang", "pt"),
            "vale_max": float(db.get_setting("vale_max", "0") or 0)}


@app.middleware("http")
async def security_headers(request: Request, call_next):
    resp = await call_next(request)
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["Referrer-Policy"] = "same-origin"
    # never let a browser reuse an auth answer or a 401 — a cached "no PIN" or a
    # cached 401 makes the app look broken at exactly the wrong moment
    if request.url.path.startswith(("/api/", "/print/")):
        resp.headers["Cache-Control"] = "no-store"
    resp.headers["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
        "frame-ancestors 'none'")
    return resp


@app.middleware("http")
async def pin_gate(request: Request, call_next):
    """Once the owner PIN exists everything is gated except the page, /static and the
    auth routes. A staff session reaches exactly one thing: its own numbers."""
    path = request.url.path
    public = (path.startswith("/static") or path.startswith("/api/auth/")
              or path in ("/", "/favicon.ico"))
    if public or not auth.pin_is_set():
        return await call_next(request)
    session = auth.session_from_token(request.cookies.get(auth.COOKIE))
    if session is None:
        return JSONResponse({"detail": "PIN necessário"}, status_code=401)
    role, staff_id = session
    request.state.role, request.state.staff_id = role, staff_id
    if role == "staff":
        allowed = (path == "/api/me" or path.startswith("/print/me/")
                   or path == "/api/auth/logout")
        if not allowed:
            return JSONResponse({"detail": "Só os teus números"}, status_code=403)
    return await call_next(request)


@app.get("/api/auth/status")
def auth_status(request: Request):
    session = auth.session_from_token(request.cookies.get(auth.COOKIE))
    out = {"pin_set": auth.pin_is_set(), "role": None, "name": None,
           "staff_with_pins": len(db.staff_with_pins())}
    if session:
        role, sid = session
        out["role"] = role
        if role == "staff":
            person = next((s for s in db.get_staff() if s["id"] == sid), None)
            out["name"] = person["name"] if person else None
    return out


@app.post("/api/auth/setup")
def auth_setup(p: PinIn):
    if auth.pin_is_set():
        raise HTTPException(400, "PIN já definido")
    pin = p.pin.strip()
    if len(pin) < 4:
        raise HTTPException(400, "PIN demasiado curto (mínimo 4)")
    auth.set_pin(pin)
    db.audit("auth.setup", "PIN definido")
    return JSONResponse({"ok": True}, headers={"set-cookie": auth.make_cookie()})


@app.post("/api/auth/login")
def auth_login(p: PinIn, request: Request):
    """One field for everybody: the owner PIN opens the management side, a staff PIN
    opens that person's own page."""
    ip = request.client.host if request.client else "?"
    if auth.too_many_attempts(ip):
        raise HTTPException(429, "Demasiadas tentativas — espera 5 minutos")
    pin = p.pin.strip()
    if auth.check_pin(pin):
        auth.clear_failures(ip)
        return JSONResponse({"ok": True, "role": "owner"},
                            headers={"set-cookie": auth.make_cookie("owner")})
    for s in db.staff_with_pins():            # ~80 ms per person, fine on a LAN
        if auth.verify_pin(pin, s["pin_hash"]):
            auth.clear_failures(ip)
            db.audit("auth.staff_login", s["name"])
            return JSONResponse({"ok": True, "role": "staff", "name": s["name"]},
                                headers={"set-cookie": auth.make_cookie("staff", s["id"])})
    auth.note_failure(ip)
    raise HTTPException(401, "PIN errado")


@app.post("/api/auth/logout")
def auth_logout():
    return JSONResponse({"ok": True}, headers={"set-cookie": auth.clear_cookie()})


@app.post("/api/auth/pin")
def auth_change_pin(p: PinIn, current: str = ""):
    if not auth.check_pin(current):
        raise HTTPException(403, "PIN atual errado")
    pin = p.pin.strip()
    if len(pin) < 4:
        raise HTTPException(400, "PIN demasiado curto (mínimo 4)")
    auth.set_pin(pin)
    db.audit("auth.pin_alterado", "")
    return {"ok": True}


@app.get("/api/settings")
def get_settings():
    return _settings()


@app.put("/api/settings")
def put_settings(s: SettingsIn):
    if s.venue_name is not None:
        db.set_setting("venue_name", s.venue_name.strip())
        db.audit("settings.venue", s.venue_name.strip())
    if s.lang is not None:
        lang = "pt" if s.lang.lower().startswith("pt") else "en"
        db.set_setting("lang", lang)
        db.audit("settings.lang", lang)
    if s.vale_max is not None:
        if s.vale_max < 0:
            raise HTTPException(400, "O vale máximo não pode ser negativo")
        db.set_setting("vale_max", f"{round(s.vale_max, 2):g}")
        db.audit("settings.vale_max",
                 "sem limite" if s.vale_max == 0 else f"{s.vale_max:.2f} €")
    return _settings()


@app.get("/api/audit")
def list_audit(limit: int = 25):
    return db.get_audit(limit)


# ---------- The team's own page (/equipa) ----------

class StaffPinIn(BaseModel):
    pin: str = ""


def _require_staff(request: Request) -> int:
    sid = getattr(request.state, "staff_id", None)
    if getattr(request.state, "role", None) != "staff" or sid is None:
        raise HTTPException(403, "Só para sessões de equipa")
    return sid


@app.get("/api/me")
def me(request: Request):
    """A staff session's whole world: own line, the week's table, own advances and
    own locked history. The roster never reaches this endpoint."""
    view = db.staff_view(_require_staff(request))
    if view is None:
        raise HTTPException(404, "Pessoa não encontrada")
    return view


@app.get("/print/me/{week_id}", response_class=HTMLResponse)
def print_my_payslip(week_id: int, request: Request):
    sid = _require_staff(request)
    wk = db.get_week(week_id)
    if not wk:
        raise HTTPException(404, "Week not found")
    if wk["status"] != "locked":
        raise HTTPException(409, "Semana ainda não fechada")
    mine = [e for e in wk["entries"] if e["staff_id"] == sid]
    if not mine:
        raise HTTPException(404, "Sem horas nesta semana")
    return exporters.payslips_html(dict(wk, entries=mine),
                                   db.get_setting("venue_name"), _lang_setting())


@app.post("/api/staff/{staff_id}/pin")
def set_staff_pin(staff_id: int, p: StaffPinIn):
    """Owner issues or clears a person's PIN. Duplicates are refused: two people
    sharing a PIN means one of them reads the other's money."""
    pin = p.pin.strip()
    if pin and len(pin) < 4:
        raise HTTPException(400, "PIN demasiado curto (mínimo 4)")
    if pin:
        if auth.check_pin(pin):
            raise HTTPException(400, "Esse PIN é o do dono — escolhe outro")
        for s in db.staff_with_pins():
            if s["id"] != staff_id and auth.verify_pin(pin, s["pin_hash"]):
                raise HTTPException(400, f"PIN já usado por {s['name']}")
    out = db.set_staff_pin(staff_id, auth.hash_pin(pin) if pin else "")
    if out is None:
        raise HTTPException(404, "Pessoa não encontrada")
    db.audit("staff.pin_definido" if pin else "staff.pin_apagado", f"staff={staff_id}")
    return out
