# W2 — Branching workflow fixtures

Conditionals and loops over **real state**. Adds nested `IF`/`WHEN`/`REPEAT` and `SUB`/`CALL` to
W1. Requires **E1** (a tool loop). This is the **sweet spot** for fidelity testing: control-flow
adherence is fully checkable at low cost — just observe which branch fired or which items were
iterated.

**Oracle:** "did *that* branch run?" / "did it iterate *exactly* those items?"
**Path made knowable:** one input per branch (plus `else`), or a known collection.

Each W2 concern is its own fixture, to stay single-concern:

- [`release-gate`](release-gate/) — **branch selection** (built). The returned verdict reveals
  which branch executed.
-  _loop coverage_ — `REPEAT foreach` over a known collection (not yet authored).
- _`SUB`/`CALL`_ — shared-context subroutine invocation (not yet authored).
