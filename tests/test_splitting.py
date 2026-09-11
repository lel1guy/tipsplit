"""Splitting invariants — the money math is the product, so it gets its own tests.

Run:  pytest tests/ -q
"""
import random

import splitting


def _entries(*pairs, vales=None):
    """pairs: (staff_id, hours). vales: optional {staff_id: amount}."""
    vales = vales or {}
    return [{"staff_id": sid, "hours": h, "vales": vales.get(sid, 0.0)}
            for sid, h in pairs]


def test_hours_pro_rata_basic():
    s = splitting.compute_shares(600.0, _entries((1, 40), (2, 20)))
    assert s == {1: 400.0, 2: 200.0}


def test_largest_remainder_sums_to_the_cent():
    """€100 over three equal shares: 33.34 + 33.33 + 33.33, never 99.99."""
    s = splitting.compute_shares(100.0, _entries((1, 10), (2, 10), (3, 10)))
    assert abs(sum(s.values()) - 100.0) < 1e-9
    assert sorted(s.values()) == [33.33, 33.33, 33.34]


def test_gross_balances_on_messy_real_input():
    """The 2024-07-29 shape: €555 over uneven hours — gross == pool exactly."""
    hours = [52, 40, 40, 40, 40, 40, 40, 40, 40, 60, 20, 20]
    entries = _entries(*enumerate(hours, start=1))
    gross = splitting.gross_shares(555.0, entries)
    assert abs(sum(gross.values()) - 555.0) < 1e-9


def test_zero_pool_and_zero_hours_are_safe():
    assert splitting.compute_shares(0.0, _entries((1, 40))) == {1: 0.0}
    assert splitting.compute_shares(555.0, _entries((1, 0))) == {1: 0.0}


def test_vale_above_gross_floors_at_zero_and_reports_debt():
    s = splitting.compute_shares(600.0, _entries((1, 40), (2, 20), vales={1: 500.0}))
    assert s[1] == 0.0            # never negative
    assert s[2] == 200.0          # untouched colleague
    assert splitting.vale_debt(400.0, 500.0) == 100.0
    assert splitting.vale_debt(400.0, 300.0) == 0.0


def test_fractional_hours():
    s = splitting.compute_shares(100.0, _entries((1, 7.5), (2, 2.5)))
    assert s[1] == 75.0 and s[2] == 25.0


def test_rate_per_hour():
    assert splitting.rate_per_hour(555.0, 472.0) == round(555 / 472, 4)
    assert splitting.rate_per_hour(555.0, 0) == 0.0
    assert splitting.rate_per_hour(0.0, 472.0) == 0.0


def test_statement_both_languages():
    pt = splitting.statement(555.0, 472.0, "pt")
    en = splitting.statement(555.0, 472.0, "en")
    assert "472" in pt and "Regra" in pt and "555,00" in pt
    assert "472" in en and "Rule" in en and "555,00" in en   # euros stay PT-formatted
    assert "Sem horas" in splitting.statement(0.0, 0.0, "pt")
    assert "No hours" in splitting.statement(0.0, 0.0, "en")


def test_raw_day_columns_work_like_precomputed_hours():
    """Regression: the API preview passes grid rows (mon..sun, no 'hours' key).
    That path used to KeyError; both shapes must give the same split."""
    raw = [{"staff_id": 1, "mon": 8, "tue": 8, "wed": 8, "thu": 8, "fri": 8},
           {"staff_id": 2, "mon": 4, "tue": 4, "wed": 4, "thu": 4, "fri": 4}]
    pre = [{"staff_id": 1, "hours": 40}, {"staff_id": 2, "hours": 20}]
    assert splitting.compute_shares(600.0, raw) == {1: 400.0, 2: 200.0}
    assert splitting.compute_shares(600.0, raw) == splitting.compute_shares(600.0, pre)
    assert splitting.total_hours(raw) == 60.0
    assert splitting.hours_of({"staff_id": 1, "mon": 7.5, "tue": 0}) == 7.5


def test_invariants_hold_on_random_weeks():
    """Property check: sum(gross) == pool, net >= 0, net == pool − Σmin(vale,gross)."""
    rng = random.Random(7)
    for _ in range(200):
        n = rng.randint(1, 18)
        pool = round(rng.uniform(0, 3000), 2)
        entries = [{"staff_id": i,
                    "hours": rng.choice([0, 4, 7.5, 8, 12, 40]),
                    "vales": round(rng.uniform(0, 400), 2)}
                   for i in range(n)]
        gross = splitting.gross_shares(pool, entries)
        net = splitting.compute_shares(pool, entries)
        assert all(v >= 0 for v in net.values())
        if any(e["hours"] > 0 for e in entries):
            assert abs(sum(gross.values()) - pool) < 1e-6, (pool, gross)
            capped = sum(min(e["vales"], gross[e["staff_id"]]) for e in entries)
            assert abs(sum(net.values()) - round(pool - capped, 2)) < 0.02, (pool, entries, net)
        else:
            # nothing worked → nothing split, pool stays whole
            assert all(v == 0.0 for v in gross.values())
            assert all(v == 0.0 for v in net.values())
