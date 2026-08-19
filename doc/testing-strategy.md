# SOL Testing Strategy

> Companion to [`testing-sol.md`](testing-sol.md). That document describes the **method** for
> evaluating SOL execution (fidelity vs quality, the configuration matrix, trace capture,
> scoring). This document is the **strategy and the materials**: how the testing effort is
> structured, what we test where, and how the bespoke test processes are designed and
> catalogued. Method answers *how do we measure*; strategy answers *what do we build, in what
> order, and why*.

---

## 1. Three concentric rings

We do not have one testing plane, we have three — ordered by **determinism and cost**. The
inner rings are cheap, repeatable, and run on every commit; the outer ring is distributional,
expensive, and runs periodically. Crucially, the existing material (`testing-sol.md`) jumps
straight to the outermost ring; the two inner rings are currently empty and are the cheapest
insurance we can buy.

| Ring | What it gates | Nature | Cadence |
|---|---|---|---|
| **R1 — Toolchain** | the Python tools *around* SOL (`sol-lint.py`, `sol2mermaid.py`, `sol2drawio.py`) | deterministic unit tests | every commit (CI) |
| **R2 — Fixture conformance** | every bespoke fixture is well-formed: validates against the schema and lints clean | deterministic | every commit (CI) |
| **R3 — Execution** | a well-formed process is *faithfully executed* in a given configuration | non-deterministic, distributional | periodic (release / spec change) |

This refines the principle already stated in `testing-sol.md` — *"lint gates authoring, tests
gate execution"* — by inserting the two missing upstream gates: a gate on the **toolchain**
(R1) and a gate on the **fixture corpus** (R2). R3 is the method documented in `testing-sol.md`;
its **execution architecture** — the runner family, executor, interactivity, and results
pipeline — is designed in [`testing-runners.md`](testing-runners.md).

**Note on the existing `examples/`.** The files under `examples/` were authored at a
preliminary stage of the project and are *demonstrative*, not test material. They are **not**
fixtures and the testing library does not draw from them. Fixtures are authored from scratch
under `tests/` (see §3).

---

## 2. A fixture is not an example

A demo example and a test fixture have opposite goals:

- an **example** is realistic and readable — optimized to *convince a human* that SOL makes
  sense;
- a **fixture** is instrumented and almost adversarial — optimized so that *a machine can
  decide, without ambiguity*, whether a run went the way it had to.

Every fixture must therefore satisfy three properties an example need not have:

1. **Determined path.** Given the input, exactly one execution path is correct (one branch, one
   iterated collection), and taking the wrong path produces a *detectably* different output.
2. **Single concern.** A fixture isolates *one* variable. A branching fixture must not also
   require tools or emit quality-variable artifacts, or the fidelity signal is drowned in noise.
3. **Self-describing.** The fixture ships its own expectation — the correct path, the contract
   expectations, and the output oracle — alongside the SOL document.

---

## 3. The W-class spine

The *type* of process is not a difficulty dial — it is the organizing axis of the whole suite.
The workload class (`W0–W3` from [`SOL-and-models.md`](SOL-and-models.md)) decides **four things
at once** for any fixture: which constructs it must exercise, the minimum environment it can run
on, the kind of oracle that is even possible, and how the correct path is made knowable.

| W | Constructs the fixture *must* exercise | Min. env | Oracle type | How the path is made knowable |
|---|---|---|---|---|
| **W0** transform | `TODO`, `IF`/`WHEN`, `returns` | E0 (model only) | a checkable property of the output (valid JSON, every row classified, schema satisfied) | inline input built so that only one outcome is correct |
| **W1** linear+tool | + `RUN`, `REPEAT` | E1 (tool loop) | effect on a sandbox filesystem/state; expected commands | known-state sandbox → the right effect is singular |
| **W2** branching | + nested `IF`/`WHEN`/`REPEAT`, `SUB`/`CALL`, over **real state** | E1 | "did *that* branch run?", "did it iterate *exactly* those items?" | one input per branch + `else`; a known collection |
| **W3** multi-agent | + `AGENT`/`SPAWN`/`DELEGATE`, `model`, `accepts`/`returns` | E2 / E2+ | isolation held; `accepts` satisfied; `returns` conformant; declared tier used | sub-agent sees **only** the `with`; per-call trace |

Two consequences drive the catalogue:

- **Fidelity gets richer and cheaper as you climb, but the required environment narrows.** W0
  runs everywhere yet offers little process-structure to get wrong; **W2 is the sweet spot** —
  control-flow fidelity is fully testable at low cost (just observe which branch fired); W3 is
  the most informative but demands E2/E2+ and per-call traces. Matrix cells like *"W3 fixture on
  E0/E1"* are **expected failures** — recorded as such, not skipped (see `testing-sol.md` §
  configuration matrix).
- **We need families, not one process.** At least one fixture per class, plus a cross-cutting
  **error-path** family (inject a failing `RUN` or a malformed return; assert `ONERROR`/`HALT`).
  The W class is also what makes explicit, per fixture, which matrix cells it is meaningful to
  run on.

---

## 4. The fixture library

The testing library lives in a dedicated tree, organized by the W-class spine:

```
tests/
  README.md                       conventions; how to add a fixture
  fixtures/
    w0-transform/                 self-contained transform fixtures
    w1-linear/                    linear tool-process fixtures
    w2-branching/                 control-flow fidelity fixtures   ← first one built here
      release-gate/
        release-gate.json         the SOL document (lints clean)
        inputs/                   one staged input per branch + else
        expectations.json         machine-readable: input → expected verdict/branch + oracle
        README.md                 human description of the fixture
    w3-multiagent/                isolation / contract / tier fixtures
    error-path/                   injected-failure fixtures
```

Each fixture is a self-contained bundle (§2.3): the SOL document, the input set, the per-input
expectations, and a README. A fixture **must lint clean (R2) before it is ever run (R3)**.

The first fixture — `w2-branching/release-gate` — is built as proof of the model: a pure
branch-selection fixture where each staged input triggers exactly one branch, so the returned
verdict *is* the fidelity oracle. Sibling W2 concerns (a `REPEAT` loop-coverage fixture, a
`SUB`/`CALL` fixture) are separate entries, to keep each fixture single-concern.

---

## 5. Build order

1. **R1 first** — it is realizable immediately and protects the tools every other ring depends
   on.
2. **R2 alongside the first fixtures** — the schema+lint gate is a few lines and keeps the
   growing fixture corpus honest.
3. **R3 via the pragmatic first step** in `testing-sol.md` — a tiny runner + checker over the
   first per-class fixtures, on 2–3 configurations.

---

## See also

- [`testing-sol.md`](testing-sol.md) — the execution-testing **method** (R3): fidelity/quality,
  matrix, traces, scoring.
- [`SOL-and-models.md`](SOL-and-models.md) — the `W0–W3` workload classes and `E0–E2+`
  environments that define the spine and the matrix.
- [`predictability-strategies.md`](predictability-strategies.md) — the L0 observability layer
  that fidelity checking rests on.
