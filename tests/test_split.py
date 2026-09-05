"""Regression tests for TipSplit's split math.

The core invariant: shares must always balance to the cent, match the
source spreadsheet, and never go negative — bar cash can't drift.

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


EXPECTED = {  # K column of the real Tips_2024.xlsx sheet
    "pedro": 61.14, "vitor": 47.03, "xana": 47.03, "bruna": 47.03,
    "rita": 47.03, "didi": 47.03, "diogo": 47.03, "felix": 47.03,
    "marin": 47.03, "vitanga": 70.55, "martin": 23.52, "hugo": 23.52,
}


def _share_for(week, name):
    return week["shares"][[e for e in week["entries"] if e["name"] == name][0]["staff_id"]]


def test_seed_week_matches_source_spreadsheet(fresh_db):
    weeks = fresh_db.get_weeks()
    assert len(weeks) == 1
    assert weeks[0]["pool_eur"] == 555.0
    week = fresh_db.get_week(weeks[0]["id"])
    assert len(week["entries"]) == 12
    assert week["total_points"] == 472.0
    for e in week["entries"]:
        assert math.isclose(week["shares"][e["staff_id"]], EXPECTED[e["name"]], abs_tol=0.011), (
            f"{e['name']}: got {week['shares'][e['staff_id']]}, want {EXPECTED[e['name']]}")


def test_shares_sum_exactly_to_pool(fresh_db):
    """Largest-remainder rounding: no drift, cash balances to the cent."""
    week = fresh_db.get_week(fresh_db.get_weeks()[0]["id"])
    total = sum(week["shares"].values())
    assert abs(total - 555.0) < 0.005, f"sum {total:.2f} != 555.00"


def test_zero_pool_and_zero_points_do_not_crash(fresh_db):
    week_id = fresh_db.get_weeks()[0]["id"]
    week = fresh_db.get_week(week_id)
    fresh_db.save_week(week_id, 0.0,
                       [{"staff_id": e["staff_id"], "points": 0, "vales": 0}
                        for e in week["entries"]])
    zero = fresh_db.get_week(week_id)
    assert all(v == 0.0 for v in zero["shares"].values())


def test_vales_deducted_and_never_negative(fresh_db):
    week_id = fresh_db.get_weeks()[0]["id"]
    week = fresh_db.get_week(week_id)
    fresh_db.save_week(week_id, 555.0, [
        {"staff_id": e["staff_id"], "points": e["points"],
         "vales": 20.0 if e["name"] == "pedro" else (100.0 if e["name"] == "hugo" else e["vales"])}
        for e in week["entries"]
    ])
    v = fresh_db.get_week(week_id)
    assert math.isclose(_share_for(v, "pedro"), 41.14, abs_tol=0.01)   # 61.14 − 20
    assert _share_for(v, "hugo") == 0.0                                 # gross < vale → 0


def test_staff_with_history_cannot_be_deleted(fresh_db):
    week = fresh_db.get_week(fresh_db.get_weeks()[0]["id"])
    staff_id = week["entries"][0]["staff_id"]
    assert fresh_db.delete_staff(staff_id) is False


def test_duplicate_week_date_rejected(fresh_db):
    assert fresh_db.create_week("2024-07-29") is None


def test_round_trip_new_week_balances(fresh_db):
    fresh = fresh_db.create_week("2024-09-02")
    assert fresh is not None
    staff = fresh_db.get_staff()
    assert len(staff) >= 2
    saved = fresh_db.save_week(fresh["id"], 100.0, [
        {"staff_id": staff[0]["id"], "points": 40, "vales": 5},
        {"staff_id": staff[1]["id"], "points": 20, "vales": 0},
    ])
    net = sum(saved["shares"].values())
    assert abs(net + 5.0 - 100.0) < 0.005   # gross balances to pool
    assert abs(net - 95.0) < 0.005          # net = pool − vales


def test_foreign_key_cascade_on_week_delete(fresh_db):
    week_id = fresh_db.get_weeks()[0]["id"]
    fresh_db.delete_week(week_id)
    conn = db._conn()
    n = conn.execute("SELECT COUNT(*) FROM entries WHERE week_id=?", (week_id,)).fetchone()[0]
    conn.close()
    assert n == 0
