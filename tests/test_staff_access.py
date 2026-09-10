"""Per-staff access: each person reaches their own numbers and nothing else.

Run:  pytest tests/ -q
"""
import time

import pytest

import auth
import db


@pytest.fixture()
def fresh(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "t.db")
    db.init_db()
    auth._fails.clear()
    conn = db._conn()                      # the demo seed would pollute the roster
    for t in ("vales", "entries", "staff", "weeks", "week_pools", "audit_log"):
        conn.execute(f"DELETE FROM {t}")
    conn.commit()
    conn.close()
    return db


@pytest.fixture()
def venue(fresh):
    """One locked week with two people: Ana 40 h, Bruno 20 h, Ana got a 10 € advance."""
    wk = fresh.create_week("2026-09-07")
    ana = fresh.create_staff("Ana Test", "Bartender")
    bruno = fresh.create_staff("Bruno Test", "Barback")
    fresh.save_week(wk["id"], 300.0, [
        {"staff_id": ana["id"], "mon": 8, "tue": 8, "wed": 8, "thu": 8, "fri": 8},
        {"staff_id": bruno["id"], "mon": 4, "tue": 4, "wed": 4, "thu": 4, "fri": 4},
    ])
    fresh.record_vale(ana["id"], 10.0, "adiantamento", week_id=wk["id"])
    fresh.lock_week(wk["id"])
    return fresh, ana, bruno, wk


# ---------- PIN storage ----------

def test_staff_pin_roundtrip(fresh):
    s = fresh.create_staff("Ana Test")
    assert fresh.staff_pin_hash(s["id"]) == ""            # no PIN issued yet
    fresh.set_staff_pin(s["id"], auth.hash_pin("4321"))
    stored = fresh.staff_pin_hash(s["id"])
    assert stored.startswith("pbkdf2$") and "4321" not in stored
    assert auth.verify_pin("4321", stored) is True
    assert auth.verify_pin("1234", stored) is False
    assert fresh.set_staff_pin(99999, "x") is None        # unknown person


def test_team_payload_never_leaks_the_hash(venue):
    d, ana, bruno, _ = venue
    d.set_staff_pin(ana["id"], auth.hash_pin("4321"))
    team = d.get_team()
    row = next(s for s in team["staff"] if s["id"] == ana["id"])
    assert row["has_pin"] is True
    assert "pin_hash" not in row
    assert next(s for s in team["staff"] if s["id"] == bruno["id"])["has_pin"] is False


def test_only_people_with_pins_can_log_in(venue):
    d, ana, bruno, _ = venue
    assert d.staff_with_pins() == []                      # nobody has one yet
    d.set_staff_pin(bruno["id"], auth.hash_pin("7777"))
    with_pins = d.staff_with_pins()
    assert [s["name"] for s in with_pins] == ["Bruno Test"]
    assert "pin_hash" in with_pins[0]                     # server-side use only


# ---------- tokens ----------

def test_owner_and_staff_tokens_are_distinguishable(fresh):
    auth.set_pin("2468")
    owner = auth.make_cookie("owner")
    staff = auth.make_cookie("staff", 7)
    assert auth.session_from_token(owner.split("; ")[0].split("=", 1)[1]) == ("owner", None)
    assert auth.session_from_token(staff.split("; ")[0].split("=", 1)[1]) == ("staff", 7)
    assert auth.session_from_token("") is None
    assert auth.session_from_token(None) is None


def test_a_staff_cookie_cannot_be_edited_into_an_owner_one(fresh):
    auth.set_pin("2468")
    value = auth.make_cookie("staff", 7).split("; ")[0].split("=", 1)[1]
    role, sid, exp, sig = value.split(".")
    forged = f"owner.{sid}.{exp}.{sig}"                   # swap the signed role
    assert auth.session_from_token(forged) is None
    other = f"staff.{int(sid) + 1}.{exp}.{sig}"           # swap the signed person
    assert auth.session_from_token(other) is None


def test_expired_staff_cookie_is_rejected(fresh):
    auth.set_pin("2468")
    exp = str(int(time.time()) - 10)
    payload = f"staff.3.{exp}"
    import hashlib, hmac
    sig = hmac.new(auth._secret().encode(), payload.encode(), hashlib.sha256).hexdigest()
    assert auth.session_from_token(f"{payload}.{sig}") is None


# ---------- what one person may see ----------

def test_staff_view_shows_their_own_line_and_the_week_table(venue):
    d, ana, bruno, wk = venue
    v = d.staff_view(ana["id"])
    assert v["staff"]["name"] == "Ana Test" and v["staff"]["position"] == "Bartender"
    assert v["week"]["id"] == wk["id"] and v["week"]["status"] == "locked"
    assert v["mine"]["hours"] == 40.0
    assert v["mine"]["gross"] == pytest.approx(200.0, abs=0.01)     # 300 × 40/60
    assert v["mine"]["vales"] == 10.0
    assert v["mine"]["net"] == pytest.approx(190.0, abs=0.01)
    assert v["week"]["statement"].startswith("300,00 € ÷ 60 h")
    names = [t["name"] for t in v["team"]]
    assert names == ["Ana Test", "Bruno Test"]                       # variant B: whole table
    assert [t["me"] for t in v["team"]] == [True, False]
    assert sum(t["net"] for t in v["team"]) == pytest.approx(290.0, abs=0.02)


def test_staff_view_carries_only_their_own_advances(venue):
    d, ana, bruno, wk = venue
    d.record_vale(bruno["id"], 5.0, "dele", week_id=wk["id"])
    mine = d.staff_view(ana["id"])["vales"]
    assert [b["week_id"] for b in mine] == [wk["id"]]          # grouped per week
    assert [v["amount"] for v in mine[0]["rows"]] == [10.0]
    assert mine[0]["total"] == 10.0
    assert all(v["staff_id"] == ana["id"] for v in mine[0]["rows"])


def test_history_lists_only_locked_weeks_with_their_own_hours(venue):
    d, ana, bruno, wk = venue
    open_wk = d.create_week("2026-09-14")
    d.save_week(open_wk["id"], 100.0, [{"staff_id": ana["id"], "mon": 5}])
    hist = d.staff_view(ana["id"])["history"]
    assert [h["week_id"] for h in hist] == [wk["id"]]                 # the open week is not history
    assert hist[0]["hours"] == 40.0 and hist[0]["net"] == pytest.approx(190.0, abs=0.01)


def test_someone_with_no_hours_gets_an_empty_view(fresh):
    ghost = fresh.create_staff("Zé Sem Horas")
    v = fresh.staff_view(ghost["id"])
    assert v["mine"] is None and v["history"] == [] and v["team"] == []
    assert fresh.staff_view(99999) is None
