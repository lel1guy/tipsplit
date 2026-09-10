"""Schema migrations + week lifecycle: an old v0 database must upgrade in place
without losing a row or a cent, and a locked week must refuse writes.

Run:  pytest tests/ -q
"""
import sqlite3

import pytest

import db

LATEST = 5          # bump when a migration lands


def _legacy_v0_db(path, staff=("Ana", "Bruno"), pool=500.0, vale=10.0):
    """Build a pre-migration database: the old shape, user_version 0, real rows
    (including a vales column value that must survive as ledger rows)."""
    conn = sqlite3.connect(path)
    conn.executescript(db.SCHEMA)          # SCHEMA is deliberately the OLD shape
    cur = conn.execute("INSERT INTO weeks (start_date) VALUES ('2026-08-03')")
    week_id = cur.lastrowid
    conn.execute("INSERT INTO week_pools (week_id, pool_eur) VALUES (?,?)", (week_id, pool))
    for name in staff:
        c = conn.execute("INSERT INTO staff (name) VALUES (?)", (name,))
        conn.execute(
            "INSERT INTO entries (week_id, staff_id, mon, tue, wed, thu, fri, vales) "
            "VALUES (?,?,8,8,8,8,4,?)", (week_id, c.lastrowid, vale))
    conn.commit()
    assert conn.execute("PRAGMA user_version").fetchone()[0] == 0
    conn.close()
    return week_id


@pytest.fixture()
def legacy_db(tmp_path, monkeypatch):
    path = tmp_path / "legacy.db"
    week_id = _legacy_v0_db(path)
    monkeypatch.setattr(db, "DB_PATH", path)
    db.init_db()
    return db, path, week_id


def _cols(path, table):
    conn = sqlite3.connect(path)
    cols = [r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()]
    conn.close()
    return cols


class TestLegacyUpgrade:
    def test_version_bumped(self, legacy_db):
        _, path, _ = legacy_db
        conn = sqlite3.connect(path)
        assert conn.execute("PRAGMA user_version").fetchone()[0] == LATEST
        conn.close()

    def test_rows_preserved(self, legacy_db):
        d, path, week_id = legacy_db
        wk = d.get_week(week_id)
        assert len(wk["entries"]) == 2
        assert wk["pool_eur"] == 500.0
        assert sum(e["hours"] for e in wk["entries"]) == 72.0   # 2 staff × 36 h

    def test_shares_still_balance_after_upgrade(self, legacy_db):
        d, _, week_id = legacy_db
        wk = d.get_week(week_id)
        assert abs(sum(wk["shares"].values()) + sum(e["vales"] for e in wk["entries"])
                   - wk["pool_eur"]) < 0.005

    def test_new_columns_and_table_exist(self, legacy_db):
        _, path, _ = legacy_db
        assert {"status", "closed_at", "closed_by"} <= set(_cols(path, "weeks"))
        assert {"position", "archived"} <= set(_cols(path, "staff"))
        conn = sqlite3.connect(path)
        tables = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        conn.close()
        assert {"settings", "vales", "audit_log"} <= set(tables)

    def test_old_week_defaults_to_open(self, legacy_db):
        d, _, week_id = legacy_db
        assert d.get_week(week_id)["status"] == "open"

    def test_rerun_is_idempotent(self, legacy_db):
        d, path, week_id = legacy_db
        d.init_db()                       # second init must be a no-op
        conn = sqlite3.connect(path)
        assert conn.execute("PRAGMA user_version").fetchone()[0] == LATEST
        assert conn.execute("SELECT COUNT(*) FROM staff").fetchone()[0] == 2
        assert conn.execute("SELECT COUNT(*) FROM vales").fetchone()[0] == 2
        conn.close()
        assert d.get_week(week_id) is not None


class TestValesBackfill:
    def test_legacy_vales_became_ledger_rows(self, legacy_db):
        d, _, week_id = legacy_db
        rows = d.get_vales(week_id=week_id)
        assert len(rows) == 2                                   # one per staff
        assert all(r["amount"] == 10.0 and r["note"] == "importado" for r in rows)
        assert all(r["date"] == "2026-08-03" for r in rows)     # dated to the week

    def test_week_totals_unchanged_after_backfill(self, legacy_db):
        d, _, week_id = legacy_db
        wk = d.get_week(week_id)
        assert all(e["vales"] == 10.0 for e in wk["entries"])

    def test_entries_vales_column_is_gone(self, legacy_db):
        _, path, _ = legacy_db
        assert "vales" not in _cols(path, "entries")


class TestWeekLifecycle:
    def test_lock_then_save_is_refused(self, tmp_path, monkeypatch):
        monkeypatch.setattr(db, "DB_PATH", tmp_path / "t.db")
        db.init_db()
        wk = db.get_weeks()[0]
        locked = db.lock_week(wk["id"], "gerente")
        assert locked["status"] == "locked" and locked["closed_at"]
        with pytest.raises(PermissionError):
            db.save_week(wk["id"], 100.0, [])

    def test_lock_is_idempotent_and_keeps_first_timestamp(self, tmp_path, monkeypatch):
        monkeypatch.setattr(db, "DB_PATH", tmp_path / "t2.db")
        db.init_db()
        wk = db.get_weeks()[0]
        first = db.lock_week(wk["id"])["closed_at"]
        again = db.lock_week(wk["id"])["closed_at"]
        assert first == again

    def test_open_week_still_saves(self, tmp_path, monkeypatch):
        monkeypatch.setattr(db, "DB_PATH", tmp_path / "t3.db")
        db.init_db()
        wk = db.get_weeks()[0]
        saved = db.save_week(wk["id"], 123.0, [])
        assert saved["pool_eur"] == 123.0
