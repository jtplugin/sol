# SOL Test Runners and the Execution Architecture

> Third companion to the testing docs. [`testing-sol.md`](testing-sol.md) is the **method**
> (what to measure: fidelity, quality, efficiency, variance). [`testing-strategy.md`](testing-strategy.md)
> is the **strategy and materials** (the three rings, the bespoke-fixture discipline, the W-class
> spine). This document is the **execution architecture**: what a *runner* is, the family of
> runners that realize each execution context, how interactivity and the model fit in, and how
> results are monitored, catalogued, and analyzed. It concretizes Ring **R3**.

---

## 1. The matrix is an orthogonal cross-product

Testing SOL means running every fixture in every execution context, on every model:

```
results = fixtures  ×  runners (execution contexts)  ×  models
```

The axes are **orthogonal**. We do not curate which fixture "belongs" to which runner — we take
the cross-product and let each cell resolve to one of three outcomes:

- **a result** — the cell ran and produced a run-record to score;
- **N/A** — the cell is *materially impossible* (e.g. an interactive fixture on a single-shot
  runner): nothing was attempted;
- **expected failure** — the cell *was attempted* and degraded (e.g. a `W3` spawn on a tool loop
  collapsing to role-play).

The last two are not noise — they are the most SOL-specific evidence we collect (see §8,
degradation modes). N/A and expected-failure cells are recorded, never skipped.

---

## 2. The runner contract (invariants every runner obeys)

A runner takes `(fixture, context, model, run-id)`, executes, and writes a **normalized
run-record**. However different two runners are inside, they all satisfy these invariants —
this is what makes the cross-product comparable:

1. **One normalized output schema.** Every runner emits the *same* run-record (§7), regardless of
   how it executed. This is the linchpin: lose it and nothing is comparable.
2. **One command, start to finish.** `runner run <fixture> --context <C> --model <M> --runs <N>`
   produces N records with no manual step in between — **even for interactive fixtures** (§5).
3. **Blindness to expectations.** The runner stages the input but never exposes the fixture's
   `expectations.json` to the agent. Otherwise the test measures nothing.
4. **Isolation between runs.** Each run executes in a clean sandbox (fresh working dir, freshly
   staged input). We measure *distributions over N runs*; runs must not contaminate each other.
5. **Honest realization of the context.** A runner must embody the *limits* of its context, not
   just its capabilities. It records **how** the context was realized — `env_realization:
   native | emulated` (§4) — so analysis never confuses an emulated E0 with a real one.
6. **Fixture portability.** The fixture does not know which runner runs it; the *same*
   `release-gate.json` runs unchanged on every runner. This invariant is what makes the matrix
   possible.
7. **Deterministic scaffolding.** Staging, capture, and record-writing are deterministic and
   reproducible (stamped run-id, timestamp, full config). Only the agent's execution is
   non-deterministic.

### 2.1 The unscored-input trap (probe-workflow discipline)

Invariant 3 (blindness) says the runner must never *show* the agent the expectations. Its
mirror image is a trap that bit us during boundary probing and is worth stating explicitly:

> **An input with no case in `expectations.json` is silently mis-scored, not unscored.**

The checker matches a run's `staged_input_id` to a case; if none matches, `expected_verdict`
falls back to `None`, and the quality test `got == expected_verdict` is then `False` for *any*
verdict the model returns — including the correct one. The cell reads `wrong-value` at 100%,
which looks like a hard model failure but is an artifact of the missing expectation.

We hit this exactly: a `--dry-run` of two fresh boundary inputs (`coverage=80`, `effort_days=5`)
showed `0/5 wrong-value` on both fixtures. The "off-by-one in the model" reading was wrong — the
inputs simply weren't in `expectations.json` yet. Once the cases were added with their spec-correct
verdicts (`READY`, `EXPEDITE`), the *same* runs scored `5/5 pass`: the model handles strict `<`/`>`
correctly at exact boundaries.

**Probe workflow, in order:**

1. Add the case to `expectations.json` with the expected verdict **first**.
2. `--dry-run` to execute and score **without writing** any result file.
3. `--runs N` for the real distributional matrix, only once the score is trustworthy.

The executor now hardens this: before running, it lists any input lacking an expectations case and
warns that quality will read as `wrong-value` regardless of the model's output. The run still
proceeds (the run-record is valid data), but the score is flagged as not yet meaningful.

---

## 3. The runner family = the E-axis made executable

The execution contexts are the `E0–E2+` environments of [`SOL-and-models.md`](SOL-and-models.md),
turned into runnable backends. The same fixture across these runners fills one row of the matrix.

| Runner | Context | What it really executes | Capturable trace | On `release-gate` (W2) |
|---|---|---|---|---|
| **R-E0** bare / "free" | one shot, no tools, no loop | W0 only | the single completion + return | **degrades**: no shell → the record must be inlined into the prompt (pushes it toward W0) |
| **R-E1** tool loop | model in a loop with shell/file tools | W1–W2 | tool-call log (command + args) + return | **runs genuinely**: `cat` the staged file, then branch |
| **R-E2** harness | a real agentic harness (sub-agents, hooks, permissions) | up to W3 | harness logs, per-call model metadata, sub-agent boundaries | runs; oversized for a single `WHEN` |
| **R-E2+** harness + predictability | E2 + L1 directives / L2 native sub-agents | W3 *deterministically* (isolation + tiers enforced) | as E2, plus verification of the layers | as E2 |

---

## 4. One executor, many contexts: emulation by restriction

We do **not** build a separate backend per context. We use a **single session-based executor**
(a Claude Code session, driven headlessly by one command) and realize the poorer contexts by
*removing capability* from it. The context is not a different machine — it is a restriction
level of the same session:

- **R-E2 (native).** The session with its full toolset — the harness as-is.
- **R-E1 (emulated).** The session restricted to shell/file tools, no sub-agents.
- **R-E0 (emulated).** The session restricted to a single turn, no tools; the input is inlined.

This collapses the executor backends to one and keeps the **one-command** invariant trivially.
Two honesty rules make it sound:

- **Hard restriction over soft.** Prefer denying tools via harness configuration (an L2 lever)
  over merely instructing "do not use tools" in the prompt (a soft L1 nudge the agent can
  violate). Record which was used.
- **Stamp the realization.** Every record carries `env_realization: native | emulated`. An
  *emulated* E0 on a frontier model and a *native* E0 (a bare API call to a small local model)
  answer different questions — the catalogue must keep them apart. The door stays open for a true
  bare-API executor later, when fidelity to a real thin runtime matters; for now, emulation is
  the pragmatic default.

---

## 5. Interactivity is an orthogonal modifier, not a new context

A fixture may require human input mid-run (`WAITUSERINPUT`). Interactivity is **not** a new
point on the E-axis (E0–E2+ measure execution *substrate*, not interaction). It is an orthogonal
**modifier** that applies to any runner with a turn loop:

- **R-E1 and R-E2 can each be interactive**; **R-E0** (single-shot) cannot — so an interactive
  fixture on R-E0 is an **N/A** cell. A Claude Code interactive session is the *interactive
  variant of R-E2*, not an "E3".
- **One command still holds.** The fixture ships a scripted **input feed**
  (`inputs/feed.json`: pre-canned answers + the condition each answers). When `WAITUSERINPUT`
  fires, the runner injects the matching answer. No human in the loop → still automatable and
  repeatable N times.
- **It unlocks a new fidelity oracle.** For an interactive fixture we check: did the agent
  **pause at the right point**, **consume the right input**, and **resume correctly**? That is
  exactly "the agent's behaviour in waiting for and taking input".

So the grid is `substrate (E) × interactivity (on/off)` — a sub-grid, not an extra row.

---

## 6. The third axis: model

The model is a free axis crossed with everything above: within a tier (small/medium/large of one
family) and across providers (a local model vs a hosted frontier one). In the session-based
executor it is just a parameter; in a future native bare-API executor it is the served model
itself. The model id is stamped in every record so a cell is fully `(fixture, context+modifier,
model, env_realization)`.

---

## 7. The run-record (the linchpin)

Every runner writes this, regardless of backend. Fields absent from a context are marked
*not observable*, so downstream checks degrade gracefully instead of lying.

```
run_id, timestamp
config:    { fixture_id, spec_version, sol_variant,
             context (E0|E1|E2|E2+), interactive (bool), env_realization (native|emulated),
             model_id, process_rendering (L0..L4 | prose-*) }
input:     { staged_input_id }                         # never the expected result
execution: { status (done|error|na), wall_clock_ms }
trace:     { steps[],            # parsed "[<case>][<agent>] <action>" spine
             tool_calls[],       # command + args  (E1+; else not-observable)
             boundaries[],       # SPAWN with/returns payloads  (E2+; else not-observable)
             per_call_model[] }  # model serving each call  (where the env exposes it)
output:    { raw, returned_payload }
usage:     { tokens_in, tokens_out, cost, sub_agent_count }   # where available
```

A cell that is materially impossible is still written, with `status: na` and a reason — so the
catalogue is complete.

---

## 8. Metrics: the three from the method, plus degradation mode

`testing-sol.md` defines three metric families — **fidelity**, **quality**, **efficiency** (with
**variance** reported over N runs). This architecture adds a fourth, because the most interesting
question here is *how the agent tries to reach the goal when the context is too poor for the
process*:

**Degradation mode (failure taxonomy).** A categorical label of *how* a run reached — or missed —
the goal under stress. It is qualitative, assigned by rules plus a judge. Worked example,
`release-gate` on R-E0 (no shell, cannot `cat` the file):

| Label | What the agent did |
|---|---|
| `inlined-and-reasoned` | virtuous degradation: reasoned over the provided record, gave the right verdict |
| `hallucinated-state` | invented the file contents |
| `asked-for-input` | requested the file (cannot, on E0 → stalls) |
| `simulated-run` | pretended to run `cat` and narrated its output |
| `refused` | gave up |

This taxonomy is a first-class field on the score-record. Across the matrix it becomes the
empirical story of *how SOL degrades* — which is the point of running the impossible cells, not
just the possible ones.

> Analysis discipline (from `testing-sol.md`): we *execute* the full N×N cross-product, but we
> *analyze* one axis at a time against a baseline, or effects are not attributable.

---

## 9. The results pipeline: monitor → catalogue → analyze

**Monitor (capture, live).** Each run emits, in real time, the run-record plus a parseable trace
spine (`[<case>][<agent>] <action>`). A run's status ∈ {pending, running, done, error, na} with
token/time counters. For the N×matrix this is a job queue; a simple progress ledger suffices
first.

**Catalogue (store, organized).** An **append-only** store keyed by the config tuple — never
overwrite, we are building distributions:

```
results/<fixture>/<context>/<model>/<spec-version>/run-<n>.json
results/index.jsonl          # one row per run: full config + computed scores
```

Versioned by `spec_version` for regression tracking. Each record self-stamps its config, so the
catalogue is reconstructable from the files alone.

**Analyze (score + compare).** Two stages:

- **Checker** (1 run → 1 score-record): reads the run-record + the fixture's `expectations.json`
  and computes fidelity (per oracle: "did *that* branch run?", "isolation held?" — `not_checkable`
  where the trace lacks the signal), quality (checkable property or judge), efficiency, and the
  degradation-mode label.
- **Aggregator** (N runs of a cell → scorecard): fidelity as a **rate** (49/50), quality mean,
  efficiency mean, and **variance/spread**. Cross-cell comparisons answer the real questions:
  *does an L1 directive raise fidelity on E1? does `model: smart` change anything below E2+ (it
  should not)? what is the cheapest cell that clears a fidelity threshold for W3?* On a spec
  change, rerun and flag any per-construct fidelity drop as a regression.

---

## 10. Build order

1. **Deterministic core** (pure Python, no model): the run-record schema, the **checker**
   (fidelity + degradation mode + efficiency), and an **executor-agnostic runner skeleton** with
   a `manual` executor. Covered by R1 unit tests.
2. **One real end-to-end run** of `release-gate` with a manual executor, to see the loop close
   and produce the first record + scorecard.
3. **Session executor with emulation** (§4): R-E2 native, R-E1/R-E0 emulated, driven by one
   headless command; then the first automated cells.
4. **Interactive modifier** (§5): the input feed and the `WAITUSERINPUT` oracle.

---

## See also

- [`testing-sol.md`](testing-sol.md) — the measurement **method** (fidelity/quality/efficiency/
  variance, the matrix, trace sources, scoring).
- [`testing-strategy.md`](testing-strategy.md) — the **rings**, the bespoke-fixture discipline,
  the W-class spine of the fixture catalogue.
- [`SOL-and-models.md`](SOL-and-models.md) — the `W0–W3` workloads and `E0–E2+` environments.
- [`predictability-strategies.md`](predictability-strategies.md) — the L0–L2 levers behind
  emulation hardness and the predictability layers of R-E2+.
