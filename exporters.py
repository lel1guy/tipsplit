"""Payday outputs: payslips + cash sheet (HTML print), and the Excel/CSV escapes.

Numbers come from db + splitting — this module only formats. Vales were already
handed out during the week, so the cash that leaves the till on payday is Σ net.

print pages: /print/payslips/{week} · /print/cashsheet/{week}
data:        /api/export/week/{week}?fmt=xlsx|csv · /api/export/annual/{year}?fmt=…
"""
import csv
import io
from html import escape

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter

HEAD_FILL = PatternFill("solid", fgColor="1F2430")
HEAD_FONT = Font(color="FFFFFF", bold=True)

HEAD = ["Pessoa", "Função", "Horas", "Bruto", "Adiantamentos", "A pagar"]


def payable(week: dict) -> list[dict]:
    """Staff who get a line: worked hours or took an advance."""
    return [e for e in week["entries"] if e["hours"] or e["vales"]]


def week_table(week: dict) -> list[list]:
    """Header + one row per payable staff + TOTAL. Gross/pool always balance."""
    rows = [list(HEAD)]
    for e in payable(week):
        sid = e["staff_id"]
        rows.append([e["name"], e.get("position") or "", e["hours"],
                     week["gross_shares"].get(sid, 0.0), e["vales"],
                     week["shares"].get(sid, 0.0)])
    rows.append(["TOTAL", "", week["total_hours"],
                 round(sum(week["gross_shares"].values()), 2),
                 round(sum(e["vales"] for e in week["entries"]), 2),
                 round(sum(week["shares"].values()), 2)])
    return rows


def week_rows_dicts(week: dict) -> list[dict]:
    return [dict(zip(HEAD, r)) for r in week_table(week)[1:-1]]      # no TOTAL


def week_cash_total(week: dict) -> float:
    return round(sum(week["shares"].values()), 2)


# ---------- data exports ----------

def week_csv(week: dict) -> str:
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")            # ; = what PT Excel expects
    w.writerows(week_table(week))
    return buf.getvalue()


def week_xlsx(week: dict) -> io.BytesIO:
    wb = Workbook()
    ws = wb.active
    ws.title = "Semana"
    _sheet(ws, week_table(week))
    out = io.BytesIO()
    wb.save(out)
    out.seek(0)
    return out


def annual_table(report: dict) -> list[list]:
    months = report["months"]
    head = ["Pessoa", "Função"] + [f"M{m:02d}" for m in months] + ["Bruto", "Adiant.", "Total"]
    rows = [head]
    for s in sorted(report["staff"], key=lambda x: x["name"]):
        rows.append([s["name"], s["position"]]
                    + [s["monthly"].get(m, 0.0) for m in months]
                    + [s["gross"], s["vales"], s["net"]])
    return rows


def annual_csv(report: dict) -> str:
    buf = io.StringIO()
    csv.writer(buf, delimiter=";").writerows(annual_table(report))
    return buf.getvalue()


def annual_xlsx(report: dict) -> io.BytesIO:
    wb = Workbook()
    ws = wb.active
    ws.title = f"Gorjetas {report['year']}"
    _sheet(ws, annual_table(report))
    out = io.BytesIO()
    wb.save(out)
    out.seek(0)
    return out


def _sheet(ws, rows: list[list]) -> None:
    for r in rows:
        ws.append(r)
    for col in range(1, len(rows[0]) + 1):
        c = ws.cell(row=1, column=col)
        c.fill, c.font = HEAD_FILL, HEAD_FONT
    ws.freeze_panes = "A2"
    for col in ws.columns:
        letter = get_column_letter(col[0].column)
        ws.column_dimensions[letter].width = min(
            max(len(str(c.value or "")) for c in col) + 2, 40)


# ---------- print pages ----------

_CSS = """
  :root { --ink:#12161a; --muted:#5b6672; --line:#c9d1d9; }
  * { box-sizing: border-box; }
  body { margin:0; padding:18px; color:var(--ink); background:#fff;
         font-family: system-ui, -apple-system, "Segoe UI", sans-serif; font-size:14px; }
  h1 { font-size:20px; margin:0 0 2px; }
  .sub { color:var(--muted); font-size:13px; margin-bottom:14px; }
  table { width:100%; border-collapse:collapse; margin-top:8px; }
  th { text-align:left; font-size:12px; color:var(--muted); border-bottom:1px solid var(--line); padding:4px 6px; }
  td { padding:4px 6px; border-bottom:1px solid #eef1f4; }
  td.num, th.num { text-align:right; font-variant-numeric:tabular-nums; }
  .total td { font-weight:700; border-top:2px solid var(--ink); }
  .statement { margin-top:10px; padding:6px 10px; border-left:3px solid #67707a;
               background:#f6f8fa; color:var(--muted); font-size:12px; }
  .sign { margin-top:26px; display:flex; justify-content:space-between; gap:40px; font-size:12px; color:var(--muted); }
  .sign span { border-top:1px solid var(--ink); padding-top:4px; min-width:190px; }
  .slip { page-break-after: always; }
  .slip:last-child { page-break-after: auto; }
  .bar { margin-bottom:14px; }
  .bar button { font-size:14px; padding:6px 12px; }
  @media print { .bar { display:none; } body { padding:0; } }
"""


def _page(title: str, body: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="pt"><head><meta charset="UTF-8">
<title>{escape(title)}</title><style>{_CSS}</style></head>
<body>
<div class="bar"><button onclick="window.print()">Imprimir</button></div>
{body}
</body></html>"""


def _euros(v) -> str:
    return f"{float(v):,.2f}".replace(",", "\u00a0").replace(".", ",").replace("\u00a0", ".") + " €"


def _slip(week: dict, e: dict, venue: str) -> str:
    sid = e["staff_id"]
    gross = week["gross_shares"].get(sid, 0.0)
    vale = e["vales"]
    net = week["shares"].get(sid, 0.0)
    rate = week["rate_per_hour"]
    return f"""<div class="slip">
  <h1>{escape(venue or "Gorjetas")} — comprovativo de gorjetas</h1>
  <div class="sub">Semana de {week["start_date"]} · {escape(e["name"])}
    {("· " + escape(e["position"])) if e.get("position") else ""}</div>
  <table>
    <tr><th>Horas trabalhadas</th><td class="num">{e["hours"]:g} h</td></tr>
    <tr><th>Rateio (horas ÷ total)</th><td class="num">{_euros(gross)}</td></tr>
    <tr><th>Adiantamentos (vales)</th><td class="num">− {_euros(vale)}</td></tr>
    <tr class="total"><td>A receber</td><td class="num">{_euros(net)}</td></tr>
  </table>
  <div class="statement">{_euros(week["pool_eur"])} ÷ {week["total_hours"]:g} h =
    {_euros(rate)}/h · {e["hours"]:g} h × {_euros(rate)} = {_euros(gross)}.
    Regra: horas ÷ total de horas. Nenhuma parte fica com a casa.</div>
  <div class="sign"><span>Assinatura</span><span>Data ___/___/______</span></div>
</div>"""


def payslips_html(week: dict, venue: str = "") -> str:
    slips = "".join(_slip(week, e, venue) for e in payable(week))
    if not slips:
        slips = "<p>Sem horas nem adiantamentos nesta semana.</p>"
    title = f"Gorjetas {week['start_date']}"
    return _page(title, slips)


def cashsheet_html(week: dict, venue: str = "") -> str:
    rows = "".join(
        f"<tr><td>{escape(e['name'])}</td>"
        f"<td class='num'>{_euros(week['gross_shares'].get(e['staff_id'], 0.0))}</td>"
        f"<td class='num'>{_euros(e['vales'])}</td>"
        f"<td class='num'>{_euros(week['shares'].get(e['staff_id'], 0.0))}</td>"
        f"<td class='num'>☐</td></tr>"
        for e in payable(week))
    total = week_cash_total(week)
    body = f"""<h1>{escape(venue or "Gorjetas")} — folha de caixa</h1>
<div class="sub">Semana de {week["start_date"]} · pool {_euros(week["pool_eur"])} ·
  {len(payable(week))} pessoas · vales já pagos {_euros(sum(e["vales"] for e in week["entries"]))}</div>
<table>
  <tr><th>Pessoa</th><th class="num">Bruto</th><th class="num">Adiant.</th>
      <th class="num">A pagar</th><th class="num">Pago</th></tr>
  {rows}
  <tr class="total"><td>Dinheiro a tirar da caixa</td><td class="num"></td><td class="num"></td>
      <td class="num">{_euros(total)}</td><td></td></tr>
</table>
<div class="statement">{_euros(week["pool_eur"])} ÷ {week["total_hours"]:g} h =
  {_euros(week["rate_per_hour"])}/h. Regra: horas ÷ total de horas.</div>
<div class="sign"><span>Assinatura (gerência)</span><span>Data ___/___/______</span></div>"""
    return _page(f"Caixa {week['start_date']}", body)
