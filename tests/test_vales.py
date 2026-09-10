"""Vales ledger + team/dashboard (T-B): dated advances, archive-not-delete,
and balances that can be checked by hand.

Run:  pytest tests/ -q
"""
import pytest

import db


@pytest.fixture()
def fresh(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "t.db")
    db.init_db()
    return db


def _clean_week(d):
    """Wipe the seeded week's staff so tests own the roster."""
    conn = d._conn()
    conn.execute("DELETE FROM vales")
    conn.execute("DELETE FROM entries")
    conn.execute("DELETE FROM staff")
    conn.execute("DELETE FROM weeks")
    conn.execute("DELETE FROM week_pools")
    conn.commit()
    conn.close()
    return d.create_week("2026-10-05")


def test_record_vale_links_to_the_open_week(fresh):
    _clean_week(fresh)
    week = fresh.create_week("2026-10-12")
    ana = fresh.create_staff("Ana Test", "Bartender")
    row = fresh.record_vale(ana["id"], 25.0, "adiantamento")
    assert row["week_id"] == week["id"], row
    assert row["amount"] == 25.0 and row["note"] == "adiantamento"
    assert row["date"]                       # dated, always


def test_a_vale_always_belongs_to_a_week(fresh):
    """V, 2026-09-10: no standalone advances — with no week there is nothing to
    deduct from, so it's refused instead of creating an orphan."""
    conn = fresh._conn()
    for t in ("vales", "entries", "staff", "weeks", "week_pools"):
        conn.execute(f"DELETE FROM {t}")
    conn.commit()
    conn.close()
    ana = fresh.create_staff("Ana Test")
    with pytest.raises(ValueError):
        fresh.record_vale(ana["id"], 10.0)                 # no week exists at all
    with pytest.raises(ValueError):
        fresh.record_vale(ana["id"], 10.0, week_id=424242)  # week that doesn't exist
    assert fresh.get_vales() == []
    wk = fresh.create_week("2026-10-19")                   # now it attaches to the open one
    assert fresh.record_vale(ana["id"], 10.0)["week_id"] == wk["id"]


def test_vales_group_by_week_with_subtotals(fresh):
    wk = _clean_week(fresh)
    older = fresh.create_week("2026-09-28")
    a = fresh.create_staff("Ana Test")
    fresh.record_vale(a["id"], 10.0, "atual", week_id=wk["id"])
    fresh.record_vale(a["id"], 2.5, "atual", week_id=wk["id"])
    fresh.record_vale(a["id"], 7.0, "antigo", week_id=older["id"])
    buckets = fresh.vales_by_week()
    assert [b["week_id"] for b in buckets] == [wk["id"], older["id"]]   # newest first
    assert buckets[0]["total"] == 12.5 and len(buckets[0]["rows"]) == 2
    assert buckets[1]["total"] == 7.0
    assert buckets[0]["start_date"] == wk["start_date"]
    assert fresh.vales_by_week(staff_id=424242) == []


def test_a_vale_alone_puts_the_person_in_the_week_table(fresh):
    """V, 2026-09-10: someone who took an advance shows up in that week's table even
    with no hours — 0 h, their advance, nothing hidden."""
    wk = _clean_week(fresh)
    ana = fresh.create_staff("Ana Test")
    ze = fresh.create_staff("Zé Sem Horas", "Barback")
    fresh.save_week(wk["id"], 600.0, [{"staff_id": ana["id"], "mon": 8, "tue": 8}])
    fresh.record_vale(ze["id"], 15.0, "tabaco", week_id=wk["id"])

    w = fresh.get_week(wk["id"])
    row = next(e for e in w["entries"] if e["staff_id"] == ze["id"])
    assert row["derived"] is True and row["hours"] == 0.0
    assert row["vales"] == 15.0 and row["name"] == "Zé Sem Horas"
    assert w["shares"][ze["id"]] == 0.0                  # no hours, no tips to receive
    assert w["total_hours"] == 16.0                      # his 0 h change nothing
    ana_row = next(e for e in w["entries"] if e["staff_id"] == ana["id"])
    assert "derived" not in ana_row and ana_row["vales"] == 0.0

    # once his hours are in, the row stops being derived — it's a real entry
    fresh.save_week(wk["id"], 600.0, [
        {"staff_id": ana["id"], "mon": 8, "tue": 8},
        {"staff_id": ze["id"], "mon": 4},
    ])
    w2 = fresh.get_week(wk["id"])
    row2 = next(e for e in w2["entries"] if e["staff_id"] == ze["id"])
    assert "derived" not in row2 and row2["hours"] == 4.0
    assert row2["vales"] == 15.0 and w2["total_hours"] == 20.0


def test_a_vale_never_needs_a_motivo(fresh):
    wk = _clean_week(fresh)
    a = fresh.create_staff("Ana Test")
    row = fresh.record_vale(a["id"], 10.0, week_id=wk["id"])     # no note at all
    assert row["note"] in (None, "", "adiantamento")
    assert fresh.get_week(wk["id"])["entries"][0]["vales"] == 10.0


def test_vale_max_cap(fresh):
    """Definições → Vale máximo: a ceiling per advance, 0 = sem limite."""
    wk = _clean_week(fresh)
    a = fresh.create_staff("Ana Test")
    assert fresh.record_vale(a["id"], 100.0, week_id=wk["id"]) is not None   # no cap yet

    fresh.set_setting("vale_max", "50")
    with pytest.raises(ValueError):
        fresh.record_vale(a["id"], 50.01, week_id=wk["id"])                  # above the cap
    assert fresh.record_vale(a["id"], 50.0, week_id=wk["id"])["amount"] == 50.0   # exactly the cap

    fresh.set_setting("vale_max", "0")                                       # back to no limit
    assert fresh.record_vale(a["id"], 999.0, week_id=wk["id"])["amount"] == 999.0

    fresh.set_setting("vale_max", "abc")                                     # junk in settings
    assert fresh.record_vale(a["id"], 999.0, week_id=wk["id"])["amount"] == 999.0


def test_vale_max_does_not_touch_existing_advances(fresh):
    """Lowering the ceiling never rewrites history — it only stops new ones."""
    wk = _clean_week(fresh)
    a = fresh.create_staff("Ana Test")
    old = fresh.record_vale(a["id"], 80.0, note="antes", week_id=wk["id"])
    fresh.set_setting("vale_max", "20")
    assert fresh.get_vale(old["id"])["amount"] == 80.0
    assert [v["amount"] for v in fresh.get_vales(staff_id=a["id"])] == [80.0]


def test_bad_vales_rejected(fresh):
    _clean_week(fresh)
    ana = fresh.create_staff("Ana Test")
    assert fresh.record_vale(ana["id"], 0.0) is None
    assert fresh.record_vale(ana["id"], -5.0) is None
    assert fresh.record_vale(99999, 10.0) is None          # unknown staff


def test_vales_sum_into_the_week_and_reduce_the_net(fresh):
    week = _clean_week(fresh)
    a = fresh.create_staff("Ana Test")
    b = fresh.create_staff("Bruno Test")
    fresh.save_week(week["id"], 600.0, [
        {"staff_id": a["id"], "mon": 8, "tue": 8, "wed": 8, "thu": 8, "fri": 8},
        {"staff_id": b["id"], "mon": 4, "tue": 4, "wed": 4, "thu": 4, "fri": 4},
    ])
    fresh.record_vale(a["id"], 20.0, week_id=week["id"])
    fresh.record_vale(a["id"], 5.5, week_id=week["id"])
    w = fresh.get_week(week["id"])
    row_a = [e for e in w["entries"] if e["name"] == "Ana Test"][0]
    assert row_a["vales"] == 25.5                      # 20 + 5.50
    assert row_a["hours"] == 40.0
    assert w["gross_shares"][a["id"]] == pytest.approx(400.0, abs=0.01)
    assert w["shares"][a["id"]] == pytest.approx(374.5, abs=0.01)   # 400 − 25.50


def test_vale_above_gross_is_surfaced_not_paid_out(fresh):
    """Soft rule: net floors at 0, the excess is debt to the pot."""
    week = _clean_week(fresh)
    a = fresh.create_staff("Ana Test")
    b = fresh.create_staff("Bruno Test")
    fresh.save_week(week["id"], 600.0, [
        {"staff_id": a["id"], "mon": 8, "tue": 8, "wed": 8, "thu": 8, "fri": 8},
        {"staff_id": b["id"], "mon": 4, "tue": 4, "wed": 4, "thu": 4, "fri": 4},
    ])
    fresh.record_vale(a["id"], 500.0, week_id=week["id"])          # gross 400
    w = fresh.get_week(week["id"])
    assert w["shares"][a["id"]] == 0.0
    assert w["shares"][b["id"]] == pytest.approx(200.0, abs=0.01)
    from splitting import vale_debt
    assert vale_debt(w["gross_shares"][a["id"]], 500.0) == 100.0
    assert db.dashboard()["vale_warnings"], "a vale over gross must be flagged"


def test_archive_keeps_history(fresh):
    week = _clean_week(fresh)
    a = fresh.create_staff("Ana Test", "Bartender")
    fresh.save_week(week["id"], 300.0, [{"staff_id": a["id"], "mon": 8, "tue": 8}])
    assert fresh.archive_staff(a["id"])["archived"] is True
    assert fresh.delete_staff(a["id"]) is False          # history → archive only
    assert [s["id"] for s in fresh.get_staff(include_archived=False)] == []
    w = fresh.get_week(week["id"])
    assert [e["name"] for e in w["entries"]] == ["Ana Test"]     # old week intact
    assert fresh.archive_staff(a["id"], archived=False)["archived"] is False


def test_team_balances_and_dashboard(fresh):
    week = _clean_week(fresh)
    a = fresh.create_staff("Ana Test", "Bartender")
    fresh.save_week(week["id"], 400.0, [{"staff_id": a["id"], "mon": 8, "tue": 8}])
    fresh.record_vale(a["id"], 30.0, week_id=week["id"])
    older = fresh.create_week("2026-09-28")
    fresh.save_week(older["id"], 200.0, [{"staff_id": a["id"], "mon": 8}])
    fresh.record_vale(a["id"], 12.0, week_id=older["id"])   # an older week's advance
    team = fresh.get_team()
    row = [s for s in team["staff"] if s["id"] == a["id"]][0]
    assert row["vales_week"] == 30.0 and row["vales_total"] == 42.0
    assert row["position"] == "Bartender"
    d = fresh.dashboard()
    assert d["week"]["pool_eur"] == 400.0
    assert d["week"]["vales_total"] == 30.0              # only the linked one
    assert d["staff_active"] == 1


def test_vale_can_be_deleted(fresh):
    _clean_week(fresh)
    a = fresh.create_staff("Ana Test")
    row = fresh.record_vale(a["id"], 15.0)
    assert fresh.delete_vale(row["id"]) is True
    assert fresh.get_vales(staff_id=a["id"]) == []
    assert fresh.delete_vale(row["id"]) is False
