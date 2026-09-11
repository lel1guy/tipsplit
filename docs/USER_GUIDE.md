# TipSplit — User Guide

**English** · [Português (PT-PT)](USER_GUIDE.pt-PT.md) · [README](../README.md)

For the person who runs the week: the manager, the head bartender, whoever closes the
till. Everything below happens in a browser on the venue's network — no app to install,
no internet needed.

**The rule behind everything:**

    parte = pool × (horas da pessoa ÷ horas totais) − vales

Your hours decide your share. Advances you already took come off. Nothing else changes
the number.

---

## 1. First time only — set the owner PIN

Open the app and define a PIN (4+ digits). That PIN is yours: it opens the management
side. **The week's numbers are behind it** — nobody can read the split from the bar's
wifi without it.

If you forget it, the recovery is on the machine itself (see DEV_GUIDE) — there is no
"forgot my PIN" email because there is no cloud.

## 2. Add your team

**Equipa → Nova pessoa** → name + função (Bartender, Barback…). Função is a **label**,
not a multiplier: it shows next to the name in the roster, it does not affect the split.

People leave? **⊘** archives them: they disappear from the week's roster but every past
week keeps their name and their money. Never delete someone who has history — the app
refuses, because it would rewrite old weeks.

## 3. The weekly ritual

1. **+ Nova semana** — a new week opens dated to Monday, already carrying your roster
   with zeroed hours.
2. Type the **pool** for the week (total tips, one field).
3. Type each person's **hours per day** (Mon–Sun, 0.5 h steps). Hours total themselves,
   and each person's parte — their share — appears live while you type.
4. **Check the strip at the top:** it reads *fully split* when the pool and the shares
   agree to the cent.
5. **Guardar** (save). The week is now the record.

The amber strip **"Faltam horas de N pessoas"** names whoever hasn't got hours in yet.
Use it before you close — closing a week with missing hours is the classic quiet error.

## 4. Vales (advances)

Someone takes €20 out of the till on a Saturday. **Equipa → Adiantamento**:

| Field | What it means |
|-------|---------------|
| Semana | the week the advance belongs to (defaults to the open week) |
| Pessoa | who took it |
| Valor € | how much |
| Motivo *(opcional)* | "tabaco", "gasolina" — for your memory, not required |

A vale **always belongs to a week** — never global — so the week it was taken in pays
for it. The *Equipa* list shows every advance grouped per week with a subtotal per week.

**Two places it shows up:** the week's grid has a **Vales €** column (read-only, because
the ledger is the source of truth), and the week view lists its own advances under the
statement. Anyone who took an advance shows up in the week's table even if their hours
aren't in yet — tagged **sem horas**, so nothing hides.

**Vale máximo** (*Definições*) caps a single advance: with `50`, a €50,01 advance is
refused and €50 is accepted. `0` = no limit. Lowering it never touches advances already
recorded — it only stops new ones.

**If a vale is bigger than the person's share of the week**, the app says so in red and
the shortfall is a *dívida ao pote*: they were paid early, the week doesn't cover it,
settle it next week. Nothing is blocked — you decide, the app only refuses to lie about
it.

## 5. Day of payment

Open the locked week and use the buttons on the week:

- **Comprovativos** — one page per person with their hours, the formula, their advances
  and the net, with a signature line. Print it, hand it over, get it signed.
- **Folha de caixa** — the till sheet: who gets how much, total out.
- **Anual (Excel)** — the year to date, for your accountant.
- **Semana** export — the week as xlsx/csv.

The printed formula is unrounded on purpose (`470,40 € × 32 h ÷ 448 h = 33,60 €`), so it
survives a pocket calculator. If someone checks your maths, they will find the same
number you did.

## 6. Closing and reopening a week

**Fechar semana** locks it. A locked week can't be edited and can be printed.

Locked by mistake, or a late correction? **Reabrir** asks for a **motivo** and it is
recorded in *Alterações recentes* with the time. That's the point: a change to a settled
week always leaves a trace. Printing an open week is refused — lock first, then pay.

## 7. Let the team see their own numbers

**Equipa → dar PIN** on a person (4+ digits, unique). Tell them the PIN. They open the
same address on their phone, type their PIN, and land on **As minhas gorjetas**:

- their hours, parte (their share), advances and what's owed — and the week's full table, so nobody
  has to argue about the split
- their own payslip (once the week is closed)
- their advance history, per week

They see **exactly their own data plus the week's table** — nothing else. They can't
reach the pool, the settings, the other weeks or anyone else's advances: the server
refuses, it isn't just hidden on screen. Sharing a PIN is refused — if two people have
the same one, it isn't theirs anymore.

## 8. Definições

| Field | What it does |
|-------|--------------|
| Nome da casa | appears on printed payslips and the cash sheet |
| Vale máximo (€) | ceiling per advance; `0` = no limit |
| PIN do dono | change your own PIN |
| Alterações recentes | the last changes with time: saves, locks, reopenings, advances, PINs |

## Common questions

**"Why is X's number smaller than mine with the same hours?"** They took an advance. Open
the week — the Vales column and the advances list under the statement show it.

**"Can I split by role instead of hours?"** Not this version. Hours only, by decision:
hours are the thing nobody disputes on a Saturday night.

**"Does it pay people?"** No. It never touches money: it tells you who gets what and
prints the proof. The cash still leaves your hand.

**"What if the internet dies?"** It runs on the venue's own machine. Internet was never
required — it works behind the bar on a LAN.

**"Can I change a closed week?"** Yes, with a motivo, which is recorded. That's the
trade: corrections stay possible, silence doesn't.

## Backup

The whole app is one SQLite file (`tipsplit.db`). A nightly copy is worth having before
you trust it with a month of paydays — ask whoever set it up, or see DEV_GUIDE.
