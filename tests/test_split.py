"""Regression tests for TipSplit's split math (hours-based model).

Invariants under test: shares always balance to the cent, hours drive the
split proportionally, vales deduct, nets never go negative, and the DB
guards (delete with history, duplicate weeks) hold. The seeded data is
random demo data, so tests build their own known weeks instead of
asserting against fixed values.

Run:  pytest tests/ -q
"""
import math
import sqlite3

import pytest

import db


@pytest.fixture()
def fresh_db(tmp_path, monkeypatch):
    """Point db at a throwaway SQLite file before any init."""
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test_tipsplit.db")
    db.init_db()
    return db


def _entry(staff_id, name, hours_by_day, vales=0.0):
    """hours_by_day: {"mon": 8, "tue": 0, ...} — missing days default 0."""
    e = {"staff_id": staff_id, "name": name, "vales": vales}
    for d in db.DAYS:
        e[d] = hours_by_day.get(d, 0.0)
    e["hours"] = sum(hours_by_day.values())
    return e


def _known_week(fresh_db):
    """Build a week with a clean, hand-checkable split:
    TestPersonA 40h, TestPersonB 20h, pool €600.
    A = 600 × 40/60 = 400.00 · B = 600 × 20/60 = 200.00.

    Names deliberately can't collide with the random demo roster
    (demo names never contain "Test").
    """
    staff_a = fresh_db.create_staff("TestPersonA")
    staff_b = fresh_db.create_staff("TestPersonB")
    assert staff_a and staff_b, "staff create failed (name collision with seed?)"
    week = fresh_db.create_week("2026-10-05")
    mon_a = {"mon": 8, "tue": 8, "wed": 8, "thu": 8, "fri": 8}
    mon_b = {"mon": 4, "tue": 4, "wed": 4, "thu": 4, "fri": 4}
    fresh_db.save_week(week["id"], 600.0, [
        _entry(staff_a["id"], "TestPersonA", mon_a),
        _entry(staff_b["id"], "TestPersonB", mon_b),
    ])
    return fresh_db.get_week(week["id"]), staff_a, staff_b


def test_seed_is_random_demo_data(fresh_db):
    """Seed week must NOT contain the real spreadsheet names."""
    weeks = fresh_db.get_weeks()
    assert len(weeks) == 1
    week = fresh_db.get_week(weeks[0]["id"])
    real_names = {"pedro", "vitor", "xana", "bruna", "rita", "didi",
                  "diogo", "felix", "marin", "vitanga", "martin", "hugo"}
    seeded = {e["name"].lower() for e in week["entries"]}
    assert seeded.isdisjoint(real_names), f"real spreadsheet names leaked: {seeded & real_names}"
    assert week["entries"], "seed week has no staff"
    assert week["pool_eur"] > 0
    # every seeded person has a plausible 4-60h week
    for e in week["entries"]:
        assert 4.0 <= e["hours"] <= 60.0, f"{e['name']} has {e['hours']}h"


def test_seed_shares_balance_exactly(fresh_db):
    """Even with random data the demo week must balance to the cent.

    Vales were already paid out during the week, so the invariant is
    net shares + total vales == pool (i.e. gross always balances).
    """
    week = fresh_db.get_week(fresh_db.get_weeks()[0]["id"])
    total_net = sum(week["shares"].values())
    total_vales = sum(e["vales"] for e in week["entries"])
    assert abs(total_net + total_vales - week["pool_eur"]) < 0.005, (
        f"net {total_net:.2f} + vales {total_vales:.2f} != pool {week['pool_eur']}")


def test_hours_drive_split_proportionally(fresh_db):
    """40h vs 20h with €600 pool: A €400.00, B €200.00."""
    week, staff_a, staff_b = _known_week(fresh_db)
    shares = {e["name"]: week["shares"][e["staff_id"]] for e in week["entries"]}
    assert shares["TestPersonA"] == pytest.approx(400.00, abs=0.01)
    assert shares["TestPersonB"] == pytest.approx(200.00, abs=0.01)


def test_total_hours_reported(fresh_db):
    week, _, _ = _known_week(fresh_db)
    assert week["total_hours"] == 60.0


def test_fractional_hours_balance(fresh_db):
    """7.5h + 2.5h days → total 40h + 20h split still balances."""
    staff_a = fresh_db.create_staff("TestPersonA")
    staff_b = fresh_db.create_staff("TestPersonB")
    week = fresh_db.create_week("2026-10-12")
    fresh_db.save_week(week["id"], 100.0, [
        _entry(staff_a["id"], "TestPersonA", {"mon": 7.5, "tue": 8.5, "wed": 8, "thu": 8, "fri": 8}),
        _entry(staff_b["id"], "TestPersonB", {"mon": 4, "tue": 4, "wed": 4, "thu": 4, "fri": 4}),
    ])
    full = fresh_db.get_week(week["id"])
    assert full["total_hours"] == 60.0  # 40 + 20
    total = sum(full["shares"].values())
    assert abs(total - 100.0) < 0.005


def test_zero_hours_do_not_crash(fresh_db):
    staff_a = fresh_db.create_staff("TestPersonA")
    week = fresh_db.create_week("2026-10-19")
    fresh_db.save_week(week["id"], 555.0, [
        _entry(staff_a["id"], "TestPersonA", {"mon": 0}),
    ])
    zero = fresh_db.get_week(week["id"])
    assert zero["total_hours"] == 0.0
    assert all(v == 0.0 for v in zero["shares"].values())


def test_vales_deducted_and_never_negative(fresh_db):
    """A €500 vale against a €400 gross → net 0, not −100. Colleague untouched.
    Vales are ledger rows now (T-B), so they're recorded, not saved with hours."""
    week, staff_a, staff_b = _known_week(fresh_db)
    fresh_db.record_vale(staff_a["id"], 500.0, week_id=week["id"])
    v = fresh_db.get_week(week["id"])
    a_row = [e for e in v["entries"] if e["name"] == "TestPersonA"][0]
    b_row = [e for e in v["entries"] if e["name"] == "TestPersonB"][0]
    assert a_row["vales"] == 500.0                      # read back from the ledger
    assert v["shares"][a_row["staff_id"]] == 0.0        # never negative
    assert v["shares"][b_row["staff_id"]] == pytest.approx(200.00, abs=0.01)  # untouched


def test_staff_with_history_cannot_be_deleted(fresh_db):
    week = fresh_db.get_week(fresh_db.get_weeks()[0]["id"])
    staff_id = week["entries"][0]["staff_id"]
    assert fresh_db.delete_staff(staff_id) is False


def test_duplicate_week_date_rejected(fresh_db):
    first = fresh_db.get_weeks()[0]["start_date"]
    assert fresh_db.create_week(first) is None


def test_foreign_key_cascade_on_week_delete(fresh_db):
    week_id = fresh_db.get_weeks()[0]["id"]
    fresh_db.delete_week(week_id)
    conn = db._conn()
    n = conn.execute("SELECT COUNT(*) FROM entries WHERE week_id=?", (week_id,)).fetchone()[0]
    conn.close()
    assert n == 0
