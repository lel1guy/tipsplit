"""TipSplit money math — the single source of truth.

The frontend never computes a share; it renders what this module returns
(no Python/JS drift). Formula locked 2026-09-08, hours-pro-rata:

    gross_i = largest_remainder(pool × hours_i / Σ hours)   # Σ gross == pool exactly
    net_i   = max(0, gross_i − vales_i)

Rounding rule: largest remainder on the GROSS shares, so the cents that
independent rounding would drop land somewhere instead of vanishing
(Excel's per-row ROUND drifts €0.05 a week — that bug is why this exists).

Vale rule (V, 2026-09-09): soft. A vale above gross floors net at 0 and the
excess is surfaced as debt to the pot — no negative payout, no auto-carry.
The owner settles it next week.
"""
import math

DAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")


def _round2(v: float) -> float:
    return math.floor(v * 100 + 1e-9) / 100


def hours_of(entry: dict) -> float:
    """Week hours for one entry: precomputed 'hours' if present, else the day
    columns. The API passes raw grid rows, the DB passes computed ones — both
    route through here so no caller has to know the difference."""
    if entry.get("hours") is not None:
        return float(entry["hours"])
    return round(sum(float(entry.get(d) or 0) for d in DAYS), 1)


def total_hours(entries: list[dict]) -> float:
    return round(sum(hours_of(e) for e in entries), 1)


def compute_shares(pool_eur: float, entries: list[dict]) -> dict:
    """Net share per staff_id. Entries need 'staff_id', 'vales' and hours
    (either an 'hours' key or the mon..sun columns)."""
    total = sum(hours_of(e) for e in entries)
    if total <= 0 or pool_eur <= 0:
        return {e["staff_id"]: 0.0 for e in entries}

    exact = {e["staff_id"]: pool_eur * (hours_of(e) / total) for e in entries}
    floored = {sid: _round2(v) for sid, v in exact.items()}
    leftover_cents = round((pool_eur - sum(floored.values())) * 100)

    order = sorted(floored, key=lambda sid: exact[sid] - floored[sid], reverse=True)
    for i in range(max(0, leftover_cents)):
        floored[order[i % len(order)]] += 0.01

    shares = {}
    for e in entries:
        sid = e["staff_id"]
        gross = round(floored[sid], 2)
        shares[sid] = round(max(0.0, gross - float(e.get("vales") or 0)), 2)
    return shares


def gross_shares(pool_eur: float, entries: list[dict]) -> dict:
    """Gross (pre-vales) share per staff_id — balances to the pool exactly."""
    total = sum(hours_of(e) for e in entries)
    if total <= 0 or pool_eur <= 0:
        return {e["staff_id"]: 0.0 for e in entries}
    exact = {e["staff_id"]: pool_eur * (hours_of(e) / total) for e in entries}
    floored = {sid: _round2(v) for sid, v in exact.items()}
    leftover_cents = round((pool_eur - sum(floored.values())) * 100)
    order = sorted(floored, key=lambda sid: exact[sid] - floored[sid], reverse=True)
    for i in range(max(0, leftover_cents)):
        floored[order[i % len(order)]] += 0.01
    return {sid: round(v, 2) for sid, v in floored.items()}


def rate_per_hour(pool_eur: float, total_hours: float) -> float:
    """€ per hour this week — constant for everyone under hours-pro-rata."""
    if total_hours <= 0 or pool_eur <= 0:
        return 0.0
    return round(pool_eur / total_hours, 4)


def vale_debt(gross: float, vale: float) -> float:
    """Portion of a vale the week's gross did not cover — debt to the pot."""
    return round(max(0.0, float(vale) - float(gross)), 2)


def fmt_eur(value: float, lang: str = "pt") -> str:
    """Euros are always written the Portuguese way — '600,00 €' — in both languages.

    The toggle switches words, not the money: the printed payslip keeps the same format,
    and a manager comparing the screen with the paper must not have to translate a
    decimal point. `lang` is kept for callers that pass it.
    """
    s = f"{value:,.2f}"
    return s.replace(",", "\u00a0").replace(".", ",").replace("\u00a0", ".") + " €"


def statement(pool_eur: float, total_hours: float, lang: str = "pt") -> str:
    """One derived line proving how the week was split (fairness statement)."""
    if total_hours <= 0 or pool_eur <= 0:
        return ("Sem horas registadas — sem divisão esta semana."
                if lang.startswith("pt") else
                "No hours recorded — nothing to split this week.")
    rate = rate_per_hour(pool_eur, total_hours)
    hours = f"{total_hours:g}"
    if lang.startswith("pt"):
        return (f"{fmt_eur(pool_eur, lang)} ÷ {hours} h = {fmt_eur(rate, lang)}/h. "
                f"Regra: horas ÷ total de horas. Nenhuma parte fica com a casa.")
    return (f"{fmt_eur(pool_eur, lang)} ÷ {hours} h = {fmt_eur(rate, lang)}/h. "
            f"Rule: hours ÷ total hours. No part stays with the house.")


if __name__ == "__main__":  # tiny self-check
    staff = [{"staff_id": 1, "hours": 40, "vales": 0},
             {"staff_id": 2, "hours": 20, "vales": 0}]
    s = compute_shares(600.0, staff)
    assert s == {1: 400.0, 2: 200.0}, s
    # largest remainder: €100 over 3 equal → 33.34 / 33.33 / 33.33
    three = [{"staff_id": i, "hours": 10, "vales": 0} for i in (1, 2, 3)]
    t = compute_shares(100.0, three)
    assert abs(sum(t.values()) - 100.0) < 1e-9, t
    # vale above gross floors at 0, excess is debt
    v = compute_shares(600.0, [{"staff_id": 1, "hours": 40, "vales": 500},
                               {"staff_id": 2, "hours": 20, "vales": 0}])
    assert v[1] == 0.0 and v[2] == 200.0, v
    assert vale_debt(400.0, 500.0) == 100.0
    # zero hours / zero pool safe
    assert compute_shares(0.0, staff) == {1: 0.0, 2: 0.0}
    assert compute_shares(600.0, [{"staff_id": 1, "hours": 0, "vales": 0}]) == {1: 0.0}
    print("splitting self-check OK")
