"""T-D: PIN gate, audit log, unlock-with-reason.

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
    return db


def test_pin_hash_roundtrip(fresh):
    stored = auth.hash_pin("1234")
    assert stored.startswith("pbkdf2$") and "1234" not in stored
    assert auth.verify_pin("1234", stored) is True
    assert auth.verify_pin("1235", stored) is False
    assert auth.verify_pin("1234", "garbage") is False


def test_set_and_check_pin(fresh):
    assert auth.pin_is_set() is False
    auth.set_pin("4321")
    assert auth.pin_is_set() is True
    assert auth.check_pin("4321") is True
    assert auth.check_pin("0000") is False


def test_cookie_signature_and_expiry(fresh):
    auth.set_pin("1234")                       # creates the signing secret
    cookie = auth.make_cookie()
    value = cookie.split(";")[0].split("=", 1)[1]
    assert auth.cookie_valid(value) is True
    assert auth.cookie_valid(value[:-1] + ("0" if value[-1] != "0" else "1")) is False
    assert auth.cookie_valid("") is False and auth.cookie_valid(None) is False
    expired = f"{int(time.time()) - 10}." + value.split(".", 1)[1]
    assert auth.cookie_valid(expired) is False


def test_brute_force_brake(fresh):
    ip = "192.168.1.9"
    assert auth.too_many_attempts(ip) is False
    for _ in range(auth.MAX_FAILS):
        auth.note_failure(ip)
    assert auth.too_many_attempts(ip) is True
    auth.clear_failures(ip)
    assert auth.too_many_attempts(ip) is False


def test_audit_log_ordering_and_limit(fresh):
    db.audit("week.fechar", "semana=1")
    db.audit("week.unlock", "semana=1 motivo=erro de horas", actor="gerente")
    rows = db.get_audit()
    assert [r["action"] for r in rows] == ["week.unlock", "week.fechar"]
    assert "erro de horas" in rows[0]["detail"]
    assert len(db.get_audit(limit=1)) == 1
    assert len(db.get_audit(limit=999)) == 2


def test_unlock_requires_a_reason_and_logs_it(fresh):
    auth._fails.clear()
    wk = fresh.get_weeks()[0]
    fresh.lock_week(wk["id"])
    assert fresh.get_week(wk["id"])["status"] == "locked"
    with pytest.raises(ValueError):
        fresh.unlock_week(wk["id"], "   ")
    out = fresh.unlock_week(wk["id"], "horas da Ana estavam mal")
    assert out["status"] == "open" and out["closed_at"] is None
    top = fresh.get_audit()[0]
    assert top["action"] == "week.unlock" and "horas da Ana" in top["detail"]
    assert fresh.unlock_week(99999, "x") is None


def test_locked_week_cannot_be_unlocked_twice_over(fresh):
    auth._fails.clear()
    wk = fresh.get_weeks()[0]
    fresh.lock_week(wk["id"])
    fresh.unlock_week(wk["id"], "primeira correção")
    fresh.lock_week(wk["id"])
    fresh.unlock_week(wk["id"], "segunda correção")
    unlocks = [r for r in fresh.get_audit() if r["action"] == "week.unlock"]
    assert len(unlocks) == 2                  # every reopen leaves a trace
