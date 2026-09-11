# TipSplit — Demo Script (5 minutes, in front of a venue)

Four moments, in this order. Rehearse once, then do it live. Everything runs on the demo
dataset — a fictional venue, never a real one.

```bash
TIPSPLIT_DB=/tmp/tipsplit-demo.db .venv/bin/python ops/seed_demo.py --weeks 8
TIPSPLIT_DB=/tmp/tipsplit-demo.db .venv/bin/python -m uvicorn main:app --port 8791
# open http://localhost:8791 · owner PIN 1234 · staff PIN 2468
```

Before they arrive: open the **open week** so the screen is already alive, and have the
phone-sized staff page open on a second screen or your phone.

---

## 1. "This is your Monday" (90 s)

**On screen:** the week view, open week.

Type a pool number in front of them, then type hours into a couple of cells. Say:

> "You write the pool. You write the hours. The split appears as you type — and this
> strip tells you when the pool and the shares agree to the cent."

Point at the statement line: `886,20 € ÷ 371 h = 2,39 €/h. Regra: horas ÷ total de horas.
Nenhuma parte fica com a casa.`

> "That's the invoice to your team. Same number on every phone."

## 2. "The thing your spreadsheet gets wrong" (60 s)

> "Show me your Excel. If it rounds each person separately, the shares don't add up to the
> pool — a €555 pool that pays out €554.95. It's five cents, until it's a month of five
> cents, and then it's an argument."

Point at **Conferência ✓ OK**.

> "Here nobody is overpaid, and the leftover cents are handed out in order. Every week,
> every person, adds up."

## 3. "Advances stop being a mystery" (90 s)

**Go to:** Equipa → the advances list grouped per week.

> "Somebody takes €30 on a Saturday. You record it here — one person, one amount, and it
> belongs to *this* week. It shows up in the week's table automatically, so nobody has to
> remember it later."

Then open the staff page (**their PIN**) on the phone:

> "This is what your team sees. Their hours, their share, their advances, and the whole
> week's table. Not their colleague's wage — the table: the same numbers everyone else
> has. You want to see the end of 'why is mine less?'"

## 4. "Payday, and the proof" (90 s)

**Go to:** a closed week → **Comprovativos**.

> "Day of payment: print. One page per person, with the formula on it —
> `470,40 € × 32 h ÷ 448 h = 33,60 €` — advances, net, and a line to sign. If anyone
> checks it with a calculator, they get the same number. That's the whole point."

Close with the audit trail (*Definições → Alterações recentes*):

> "And if a closed week ever has to be corrected, it needs a written reason and it stays
> in this list. Nothing changes silently."

---

## Questions they will ask

| They ask | You answer |
|---|---|
| "Does it pay people?" | No. It tells you what to pay and prints the proof. The cash leaves your hand. |
| "Does it work with my POS?" | No, on purpose. No POS, no bank, no payroll integration. |
| "Is my data in the cloud?" | No. One file on your machine, on your network. Works with the internet down. |
| "Can staff see each other's wages?" | They see their own numbers plus the week's table their colleagues see. Never the pool settings, never another week, never someone else's advances. |
| "What if the internet dies?" | It never needed it. |
| "How much?" | (Your price — the pilot is free for 30 days, then a setup fee and/or a monthly.) |

## Reset between demos

```bash
rm -f /tmp/tipsplit-demo.db
TIPSPLIT_DB=/tmp/tipsplit-demo.db .venv/bin/python ops/seed_demo.py --weeks 8
```

Deterministic: you get the same venue back, so your rehearsal still matches.
