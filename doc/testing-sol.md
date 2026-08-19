# Toward a Testing Framework for SOL

> SOL's promise is "the shortest path from human intent to agent execution." Whether that
> promise holds depends on the *configuration* it runs in — the language variant, the harness,
> and the model. This document outlines how, in the near future, we can stand up structured
> tests to evaluate SOL's behavior across those configurations. It describes a method, not an
> implemented suite.

---

## Why SOL needs its own kind of testing

SOL is not deterministic at the leaf level — that is a deliberate design choice (`why-sol-works.md`).
So classic "assert output == expected" testing does not fit: two correct runs can differ in
wording. Testing SOL therefore means measuring **distributions over runs**, and separating two
questions that are usually conflated:

1. **Did the agent execute the process we wrote?** — *fidelity*. Were the right branches taken,
   the right collection iterated, the `SPAWN` actually isolated, the contract respected, the
   `ONERROR` fired when it should?
2. **Did the task come out well?** — *quality*. Independent of fidelity: a run can follow the
   structure perfectly and still produce a mediocre artifact, or vice versa.

Keeping these apart is the central idea. Fidelity tells us whether SOL-the-language is being
honored; quality tells us whether the process *as designed* is any good. They have different
oracles and different fixes.

---

## What to measure

### 1. Structural fidelity (the SOL-specific metric)

This is the trace-level check introduced as "observability" in `predictability-strategies.md`
(L0). Given a run's trace, verify against the process definition:

- **Control flow:** the branch whose condition held is the one that executed; no dead branch
  ran; loops covered exactly the intended collection.
- **Boundaries:** each `SPAWN` produced a genuinely isolated execution (not in-context
  role-play); the sub-agent saw only the `with` payload.
- **Model tiers:** each boundary ran on a model of the declared tier (only checkable where the
  environment records per-call model metadata).
- **Contracts:** `accepts` were present/validated; `returns` matched the declared shape.
- **Error semantics:** `ONERROR` fired on injected failures; `HALT` stopped cleanly where
  expected.

Fidelity is scored as a rate (e.g., "branch taken correctly in 49/50 runs"), not a boolean.

### 2. Outcome quality

Task-specific, and it needs an **oracle**:

- **Deterministic-ish transforms (W0 in `SOL-and-models.md`):** a reference answer or a
  checkable property (valid JSON, every input row classified, schema satisfied).
- **Open-ended artifacts:** a rubric scored by a strong "judge" model and/or a human spot-check.

### 3. Efficiency

- token usage (in/out), wall-clock time, number of sessions / sub-agent spawns, monetary cost.
- Efficiency is where the cheaper configurations earn their keep — a config that matches a more
  expensive one on fidelity and quality but at a fraction of the tokens is a win.

### 4. Robustness / variance

- Run each (fixture × configuration) N times; report mean and spread for every metric above.
  Low variance is itself a quality of a configuration.

---

## The configuration matrix

The experiment varies three axes. Change **one axis at a time** against a fixed baseline so
effects are attributable.

| Axis | Example values |
|---|---|
| **SOL / language variant** | prose vs SOL; open vs structured contracts; `model` hints present vs absent; with vs without an L1 execution-directive block |
| **Environment / harness** | bare API (E0), tool loop (E1), agentic harness (E2), harness + predictability layers (E2+) — see `SOL-and-models.md` |
| **Model** | within a tier (e.g. small/medium/large of one family) and across providers (e.g. a local Qwen vs a hosted frontier model) |

The cells of this matrix are the experiments. Not every cell is meaningful (a W3 fixture on E0
is expected to fail) — those expected-failure cells are themselves informative and should be
recorded, not skipped.

---

## Test fixtures

A curated suite of SOL **cases**, each paired with an expectation and an oracle. Organize by the
workload classes of `SOL-and-models.md` so a fixture's environment requirements are explicit:

- **W0 — transform fixtures:** self-contained input + a checkable output property. Best for
  isolating *model* quality with minimal environment noise; runnable even on E0.
- **W2 — branching fixtures:** designed so exactly one branch is correct given the input;
  fidelity oracle = "did that branch run?" Include inputs that exercise each branch and the
  `else`.
- **W2 — loop fixtures:** a known collection; oracle = "iterated over exactly these items."
- **W3 — multi-agent fixtures:** a `SPAWN` with a contract; oracles = "isolation held",
  "`accepts` satisfied", "`returns` shape correct", "declared tier used". These only pass on
  E2/E2+ — which is the point of running them across the matrix.
- **Error-path fixtures:** inject a failure (a failing `RUN`, a malformed sub-agent return) and
  assert the `ONERROR` / `HALT` behavior.

Each fixture is a small, self-describing bundle: the SOL document, the input, the expected
control-flow path, the contract expectations, and the quality oracle.

---

## Capturing traces

Fidelity checking needs a machine-readable record of what happened. Sources, roughly in order
of richness:

- **Structured run logs.** A convention like `[<case>][<agent>] <action>` emitted at each
  significant transition gives a cheap, parseable spine of the execution (this mirrors how an
  orchestrator can already narrate its steps).
- **Return signals.** Compact JSON returned at each boundary (the `returns` payloads) records
  what crossed each contract.
- **Session metadata.** Where the environment exposes it: which model served each call/sub-agent
  (the only reliable way to check tier fidelity), token counts, timings.
- **Tool-call records.** Which tools/commands ran, with arguments — to confirm `RUN` steps and
  detect improvisation.

An automated **checker** then compares the captured trace to the fixture's expectations and
emits the fidelity scores.

---

## Scoring and reporting

- **Per-configuration scorecard:** for each matrix cell, the four metric groups (fidelity,
  quality, efficiency, variance) over N runs.
- **Comparisons that answer real questions:** *Does adding an L1 directive raise fidelity on
  E1? By how much? Does `model: "smart"` change anything below E2+ (it should not — a good
  sanity check)? What is the cheapest configuration that hits a fidelity threshold for W3?*
- **Regression tracking across spec versions:** rerun the suite when the SOL spec changes;
  a drop in fidelity for a construct flags a regression in the language or its guidance.

---

## Relationship to the linter

The existing linter (`sol-lint.py`, referenced from the SOL skill) is **static**: it checks a
document is well-formed — valid constructs, resolvable `CALL`/`SPAWN`, double-brace
placeholders, contracts present where required. This testing framework is **dynamic**: it
checks that a *well-formed* document is *faithfully executed* in a given configuration. They are
complementary — lint gates authoring, tests gate execution — and a fixture should lint clean
before it is run.

---

## A pragmatic first step

The full matrix is a long-term goal. A useful minimum, buildable soon:

1. **3–5 fixtures**, one per workload class (a W0 transform, a W2 branch, a W2 loop, a W3
   spawn, an error-path).
2. **A tiny runner** that takes `(fixture, environment, model)`, executes it, and writes the
   trace + raw outputs to disk.
3. **A checker** that scores structural fidelity from the trace and runs each fixture's quality
   oracle.
4. **2–3 configurations** to start: e.g. a local model on a bare API (E0) for the W0 fixture,
   and a harness (E2) with and without an L1 directive for the W2/W3 fixtures.

That is enough to produce the first real evidence: not opinions about which configuration
executes SOL faithfully, but numbers.

---

## See also

- `predictability-strategies.md` — the L0 observability layer is the basis of fidelity checking.
- `SOL-and-models.md` — the workload classes and environments that define the test matrix.
- `why-sol-works.md` — why we measure distributions, not exact outputs.
