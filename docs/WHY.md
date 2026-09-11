# Why TipSplit works the way it does

**English** · [Português (PT-PT)](WHY.pt-PT.md) · [README](../README.md)

Design decisions with reasons, so nobody has to guess later — and so a future version
doesn't quietly undo them.

## 1. Hours only, no position weights

A bartender and a barback on the same hours get the same money. Position is a **label**
next to the name, not a multiplier.

Because the argument at 2am is never "I should get 1.2×". It's "why is my number that
number?" — and hours are the thing on that sheet nobody disputes. The moment a venue
wants weights, that's a different product with a different trust problem.

## 2. An advance always belongs to a week

Vales are cash someone took *during* a week, so that week pays for it. There is no
floating "debt" pot that drifts between weeks, and the ledger is read grouped per week
with subtotals.

A week-less advance would mean the money is deducted somewhere arbitrary — and the person
who took it can't check it against anything.

## 3. The pool check exists because spreadsheets drift

The app shows *pool todo dividido* or *split + €X em vales* before you save. That check
exists because a real Excel sheet with a €555 pool displayed €554.95: independent
per-person rounding loses cents, and nobody notices until a month of paydays is wrong.

TipSplit floors everyone (so nobody is overpaid) and hands out the leftover cents by
largest remainder, so the shares sum to the pool **to the cent** — an invariant with
tests behind it.

## 4. An advance above someone's share is allowed, and flagged

Blocking it would mean the manager can't help someone on a bad week. So the app allows it,
prints `€X vale acima do ganho (dívida ao pote)` in red, floors the net at zero, and lets
the venue settle it next week. The rule is: nothing is hidden, and the person sees the
same flag the owner sees.

## 5. A closed week can be reopened — with a motivo

Mistakes happen; locking people out of a correction would just mean corrections happen
off the books. So reopening is possible, requires a written reason, and that reason lands
in the audit trail with a timestamp.

Corrections stay possible. Silence doesn't.

## 6. The printed formula is unrounded

`470,40 € × 32 h ÷ 448 h = 33,60 €` — never the rounded rate multiplied back out, which
is off by a cent and makes the paper look wrong to anyone checking with a calculator.

A payslip that fails a calculator check destroys the exact trust it was printed for.

## 7. The staff table shows advances, not just the net

Without the advances column, a person with an advance sees a number lower than
`hours × rate` and concludes the house kept the difference. That misreading is one
screenshot away, and it's the most expensive misunderstanding this app can cause.

So the table shows hours, share, advances and net, plus the line
`pool − advances = to pay now`.

## 8. A staff session is filtered server-side

The staff page never receives the roster or anybody else's advances — the server returns
only that person's slice. Hiding it in the browser instead would be one "view source"
away from every wage on the team.

Same reasoning for the PIN signature: it carries the **role and the person's id**, so a
staff cookie can't be edited into an owner one.

## 9. The interface is Portuguese (PT-PT) only

The people typing hours at closing time are Portuguese-speaking, and a half-translated
interface is worse than one language done properly. Docs are bilingual; the UI is not,
until there's an English-toggle reason good enough to justify ~60 labels of maintenance.

## 10. No money movement, no POS, no payroll

TipSplit tells you what to pay and prints the proof; the cash still leaves your hand.
Integrating with tills or banks would mean PCI-style obligations and a support burden that
kills a one-person product — and none of it makes the split fairer.

## 11. One SQLite file, one process, system fonts

A bar's back office is a cheap PC that may or may not have internet. One file is backup,
restore and archive; system fonts mean the layout doesn't depend on a download. It runs on
a LAN with the router unplugged from the world.
