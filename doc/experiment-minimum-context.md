# Experiment Protocol — Minimum Context for SOL Interpretation

> **Status: pre-registration.** This document is written *before* any data is collected. It
> fixes the question, the materials, the design, the metrics, and the analysis plan. Anything
> decided after the first run is an amendment and must be recorded as such, with a date, in the
> Amendments section. The git history of this file is the evidence that the plan preceded the
> results.

> Companion documents: [`testing-strategy.md`](testing-strategy.md) (what we build and in what
> order), [`testing-sol.md`](testing-sol.md) (the general method), [`testing-runners.md`](testing-runners.md)
> (the execution architecture), [`SOL-and-models.md`](SOL-and-models.md) (workload classes and
> environments), [`predictability-strategies.md`](predictability-strategies.md) (the L1–L4 layers
> this campaign calibrates).

---

## 1. The question

> **Can an organisation obtain predictable results from SOL without a frontier model inside a
> rich agentic harness — and if so, under what conditions?**

The question is operational, not competitive. We are not asking whether a frontier model beats a
local one; we already know it does. We are asking what the *cheapest sufficient configuration*
looks like, along three cost dimensions an organisation actually controls:

1. **the model** — which locally-runnable model, on consumer hardware;
2. **the collateral context** — how much explanation SOL needs shipped alongside it;
3. **the input preparation** — how much cleaning of the raw material is worth doing first.

The deliverable is a threshold table: *for this model, at this level of collateral context, with
this preprocessing, fidelity reaches an acceptable rate — and it costs this much.*

### 1.1 Why this is the interesting question

A prior informal observation motivates the campaign: raw SOL (no explanation at all) works very
well inside Claude Code, and poorly on weak local models. Both halves of that observation are
confounded. The Claude Code result may come from the model, from the harness, or from both. The
local result was obtained with reasoning disabled and on unrepresentative hardware. Neither half
is usable as evidence.

More importantly, neither half answers the operational question. An organisation that will not
or cannot adopt a closed frontier model wrapped in a proprietary harness needs to know whether
there is *anything* it can do with SOL. That is what this experiment measures.

---

## 2. Hypotheses

Stated so they can fail.

- **H1 — A threshold exists.** For each tested local model there is a minimum level of collateral
  context L at which conditional fidelity crosses an acceptability threshold, and that level is
  below L4 (full spec plus repository examples). *Falsified if* one or more models never cross
  the threshold at any level.

- **H2 — Preprocessing lowers the threshold.** Deterministic input cleaning (P1) reduces the
  minimum L needed, relative to AI-based neutral condensation (P2a), or reaches the same fidelity
  at lower cost. *Falsified if* the two preprocessing regimes produce indistinguishable
  thresholds and costs.

- **H3 — Comprehension and execution fidelity are separable and separately limiting.** A model
  can score poorly on domain comprehension while executing the process structure faithfully, or
  the reverse. *Falsified if* the two scores move together across all cells, which would mean the
  decomposition carries no information.

- **H4 — SOL is at least as reliable as prose.** At the threshold level, the SOL variant achieves
  conditional fidelity no worse than a prose rendering of the same process. *Falsified if* prose
  is reliably better.

**On H4, a note about what a negative result would mean.** If prose matches SOL on fidelity, SOL
is not thereby refuted. The claim then shifts — legitimately, and this shift is declared here
rather than improvised afterwards — from *"SOL executes better"* to *"SOL is the consistency
point that encodes the business rules once, and prose is a compilation target derived from it."*
That claim is supported by the `prose-derived` variant being mechanically generated from the SOL
document. Declaring this in advance is what stops it from being a post-hoc rescue.

---

## 3. What this experiment deliberately does not test

Exclusions are decisions, not omissions. Each is listed with its reason.

| Excluded | Reason |
|---|---|
| **Variant B — state held outside the model** (one item per invocation, budget in an external counter) | It would work better by construction, and not every real process can externalise its state. The question is whether the harder architecture is feasible and at what price. |
| **P0 — raw, unprocessed input** | It would only demonstrate that noise degrades performance. Already known; not the question. |
| **P2b — AI preprocessing that knows the product catalogue** | If the preprocessor already resolves product and intent, the downstream SOL process has almost nothing left to decide, and the experiment stops measuring SOL. |
| **Frontier models inside the matrix** | A different weight class. One demonstrative pass is reported separately, explicitly labelled as a ceiling reference and not as a comparison term. |
| **Full factorial exploration of L** | We are looking for a threshold, not mapping a surface. See §7.3. |
| **Readability as a measured quantity** | Readability is an editorial claim. No automatic oracle for it is credible, and pretending otherwise would weaken the parts that *are* measurable. It is argued, not measured. |

---

## 4. Materials

### 4.1 The fixture — `w2-branching/support-intake`

A W2 branching fixture (per `SOL-and-models.md`) with **state accumulation across iterations**.
A queue of ~15 support items is triaged against a finite hour budget in a single invocation.

```
SUB classify-request → {product: P1..P5 | UNKNOWN, intent: BUG | FEATURE | QUESTION}
SUB estimate-effort  → deterministic lookup, intent × product → hours
SUB check-budget     → FITS | NOFIT

guard: malformed input → HALT / INVALID_INPUT

REPEAT foreach item in queue:
    CALL classify-request
    CALL estimate-effort
    CALL check-budget
    WHEN:
      product == UNKNOWN  → NEEDS_INFO
      intent == BUG and NOFIT → ESCALATE, record halted_at, exit loop
      FITS                → ASSIGN, budget -= hours
      else                → DEFER

RETURN { items: [{id, product, intent, effort, action}], remaining_hours, halted_at }
```

**Why this shape.** Every fixture currently in the corpus has the same degenerate form: read one
record, take one decision, return one verdict. That yields a binary fidelity oracle, which cannot
resolve a graded scale, and it saturates at 100% on strong models — no discriminating power in the
upper half of the matrix. It also leaves `REPEAT`, cross-iteration state, repeated `SUB`
invocation, and `HALT` entirely untested.

This fixture fixes all of that at once. The decisive property is that **the same item, in a
different position in the queue, takes a different branch**, because the accumulator has changed.
A model cannot pass by classifying items independently; it must actually execute the process. That
is the definition of the "self-regulation" this campaign is about.

The budget is calibrated so that it is exhausted somewhere between item 5 and item 11 — giving a
substantial "before" and "after" region within every queue.

The effort figure is a **deterministic lookup supplied in the context**, not an estimate. This is
essential: it makes everything downstream of classification exactly checkable, which is what makes
conditional fidelity scoring (§6.2) possible.

Arithmetic is restricted to subtraction over small integers. Prior runs show local models failing
`cart-total`-style fixtures on arithmetic rather than on control flow; here arithmetic is noise to
be suppressed, not a variable of interest.

### 4.2 The data — NLBSE'24 Issue Report Classification

3,000 labelled issue reports from **five real open-source projects** (`facebook/react`,
`tensorflow/tensorflow`, `microsoft/vscode`, `bitcoin/bitcoin`, `opencv/opencv`), fields
`repo, created_at, label, title, body`, labels `bug | feature | question`.

Mapping onto the fixture:

- the five repositories are the **five products**;
- the `repo` field is **withheld from the model** and used as ground truth. Note that the original
  competition task *gives* the repository to the classifier; withholding it makes our task strictly
  harder and is precisely the comprehension we want to measure;
- the three native labels are the **intents**. No fourth intent is invented: fabricating labels is
  exactly the problem this dataset was chosen to avoid.

**Reference ceiling.** The competition publishes a baseline: macro F1 **0.827** cross-repository,
using a fine-tuned SetFit classifier. This is worth more than a comparison against a frontier
model, because it frames the result as *"a general-purpose local model, with no fine-tuning,
reaches X against 0.827 from a purpose-trained classifier."*

**Licensing.** The repository's `LICENSE` file exists but is empty (0 bytes); no licence is
declared. Using the data locally for evaluation is the dataset's stated purpose and poses no
issue. **Redistribution has no basis to rest on**, so the fixture is *dehydrated*: the public
repository contains only references, labels, content hashes and a hydration script — no
third-party text. Explicit permission from the authors will be requested; if granted, the item
list can also be published for full transparency.

### 4.3 The pool

- **Random draw with a fixed seed** from the full test set, **stratified by repo × label** so that
  all five products and all three intents are represented.
- **300 items** drawn, then **manually verified**. The NLBSE labels are maintainer-assigned, not
  gold; part of the published 0.827 ceiling *is* this label noise. Manual verification converts an
  unknown noise floor into a known ground truth. **This substitutes the experimenter's judgement
  for the maintainers' and must be declared as such in any publication.**
- The 300 are split **50/50 by seed** into **MAIN** and **REPLICATION** (§8.3).

Manual selection of items is not permitted at any point. The draw is random; only the *queue
composition* is filtered, by the declared structural criterion below.

### 4.4 The queues

**K = 10 queues** of ~15 items each, drawn from the MAIN pool. Overlap of items between queues is
permitted and in fact desirable: it means differences between queues arise from composition and
ordering rather than from some queues having drawn intrinsically harder items.

**Rejection sampling against a criterion frozen in advance.** A randomly drawn queue may exhaust
the budget at item 2, or never exhaust it, or never produce an ESCALATE condition — such queues
measure nothing, because the process degenerates. Queues are therefore drawn with the seed and
rejected unless they satisfy a **structural** criterion, for example:

- the budget is exhausted between item 5 and item 11;
- at least one ESCALATE-eligible condition arises.

The criterion concerns the *informativeness* of the queue, never its difficulty for any particular
model — that distinction is what separates this from cherry-picking. **The criterion must be
written and frozen before generation.** Its final form is recorded in the fixture's `README.md`.

The malformed-input case sits outside the K queues, as a separate structural case.

**Binding constraint: the K queues are identical across every cell of the matrix** — same input for
every model, every level L, every preprocessing regime. The only thing that transforms the text is
the preprocessing, and it does so deterministically over the same underlying items.

---

## 5. Factors

### 5.1 L — collateral context

Applied to the SOL variant only. This is an empirical calibration of the **L1 "Linguistic" layer**
of `predictability-strategies.md`: the cheapest form of predictability, obtained inside the prompt,
before escalating to harness-level measures.

| Level | Content |
|---|---|
| **L0** | bare JSON, no explanation |
| **L1** | + a minimal instruction: "follow the algorithm described in the JSON literally" |
| **L2** | + an essential glossary of only the tags used in this fixture |
| **L3** | + the complete SOL specification (`spec/sol-0.6.md`) |
| **L4** | + specification and repository example pages |

**Two distinct questions live on this scale and must not be conflated in the analysis.** L0/L1 ask
*"is SOL self-explanatory?"*; L3/L4 ask *"does SOL plus its specification beat prose?"* They
coexist on one axis but a result from one is not an answer to the other.

### 5.2 P — input preparation

Both regimes are **frozen and pre-computed offline**, producing two fixed corpora. Preprocessing is
therefore not a per-run cost and is bit-for-bit reproducible — the same discipline applied to
`prose-derived`.

- **P1 — deterministic Python cleaning, no LLM.** Regex and parsers: GitHub issue-template headers,
  code blocks → `[code]`, stack traces, images and URLs → `[image]`, quoted replies, signatures,
  whitespace collapsing, truncation to budget.

  *No LLM is used here on purpose.* A model instructed to "just clean" still makes semantic
  choices; deciding what counts as noise is already half of comprehension. Only a deterministic
  cleaner can be audited line by line and honestly called frozen.

- **P2a — neutral AI condensation.** A model cleans and condenses, **without access to the product
  catalogue**. It supplies clean text, never pre-comprehension.

P1 also interacts with L: it frees input-side context, which is exactly the room the collateral
needs on the instruction side. On 8 GB of VRAM the SOL specification (~6–7k tokens) plus fifteen
raw issue bodies does not fit alongside a working KV cache. **P and L trade context budget against
each other**, so the optimum is unlikely to sit at either extreme.

### 5.3 Model

All locally runnable on the target hardware (RTX 5070 Laptop, 8 GB VRAM, 32 GB RAM).

| Role | Model | Rationale |
|---|---|---|
| balanced, primary | Qwen3.5-9B Q4_K_M | prior runs exist → direct comparability |
| balanced, second family | Mistral Small 3 7B or Ministral 8B | with one family only, the experiment measures that family, not SOL |
| fast | Phi-4-mini (~3.8B) | reported as the most reliable at this size for structured output |

**Excluded:** models below ~3B (prior runs show 2/50 pass — noise, not a tier) and 12B-class models
(~8.1 GB of weights alone; at L3/L4 they spill to CPU and timings explode).

### 5.4 Language variant

- **`sol`** — the JSON document, across the L scale;
- **`prose-derived`** — generated *from* the SOL document by `sol-translate` in a single mechanical
  pass, **frozen before any results are seen**, never hand-tuned;
- **`prose-native`** — written by hand as an analyst unfamiliar with SOL would write it.

The L scale does not apply to prose: prose needs no glossary or specification. This asymmetry is
intentional and is the actual question — *at what level L does SOL beat prose by enough to justify
the collateral it drags along?*

### 5.5 Temperature

**0.2, declared and identical everywhere.** Not a detail. At temperature 0 local models are
near-deterministic and repetitions would buy nothing, forcing the entire budget onto queue
diversity; at default temperature variance would swamp the signal. 0.2 is realistic for a
production classification task and leaves repetitions something to measure.

---

## 6. Metrics

### 6.1 The decomposition problem

Adding genuine semantic comprehension to the fixture violates the single-concern rule of
`testing-strategy.md`: if a model misidentifies the product at item 3, the whole downstream
sequence diverges, and a single aggregate score cannot say where it failed.

This is not a reason to avoid comprehension — for the operational question, the aggregate outcome
*is* what matters — but it must be decomposed. Three scores are recorded per run.

### 6.2 The three scores

| Score | Computation | What it isolates |
|---|---|---|
| **Comprehension** | extracted (product, intent) vs. verified ground truth, per item | domain understanding. Independent of SOL |
| **Conditional fidelity** | re-run the reference implementation using **the classifications the model itself produced**, then compare its actions and remaining budget against that | pure control-flow signal: *given what it understood, did it execute the process correctly?* |
| **End-to-end outcome** | everything vs. verified ground truth | the result the organisation actually gets |

The informative case is comprehension 60% with conditional fidelity 100%: *"it does not understand
the domain but executes the process perfectly."* That tells an organisation to invest in the
product catalogue, not in the notation. The converse tells the opposite. **This decomposition is
what turns a scorecard into operational advice**, and it is the reason the fixture is allowed to
break single-concern.

### 6.3 Cost

Tokens in/out, wall-clock seconds per item, collateral token count per level, peak VRAM. The
deliverable table is *configuration → fidelity → cost*, not fidelity alone.

### 6.4 Checker extensions required

`checker.py` currently scores a scalar verdict. It must be extended to:

- fidelity as a **rate over the branch sequence**, not pass/fail;
- new degradation modes: `partial-sequence` (executed but drifted), `no-halt` (ignored the early
  exit), `budget-drift` (right decisions, wrong accumulator — i.e. not maintaining state);
- variance decomposition, within-queue vs. between-queue (§7.2).

All covered by R1 unit tests in `tests/toolchain/test_checker.py`.

---

## 7. Experimental design

### 7.1 Crossed design K × R

Two sources of noise must be separated, and a naive design confounds them:

- **stochastic** — same input, different sampling from the model;
- **combinatorial** — different queue, different difficulty.

Running N repetitions of a single queue measures only the first, and cannot tell whether that
queue happened to be favourable. Running N different queues once each measures an uninterpretable
mixture — and variance is one of the four metric groups this framework claims to report.

**K = 10 queues × R = 3 repetitions = 30 runs per cell.**

- dispersion **within** a queue = stochastic noise;
- dispersion **between** queues = sensitivity to composition.

This is cheaper than the naive alternative (6 inputs × 10 repetitions = 60 runs per cell) and buys
two variance components instead of one.

### 7.2 Reported statistics

Per cell: mean and spread of each of the three scores, decomposed into within-queue and
between-queue components; degradation-mode histogram; cost figures. A configuration with equal
mean but lower between-queue spread is the better configuration, and the design makes that
visible.

### 7.3 Adaptive laddering on L

The L scale is **not** explored exhaustively. We are looking for a threshold: climb L0 → L1 → L2 …
and stop as soon as the model crosses the acceptability threshold. Prose variants run only at the
threshold level found. Full factorial exploration would add hours, not information.

### 7.4 Where the P axis is varied

The L threshold is established first at **P1**, the cheap default. **P2a** is then run only at the
threshold level and one level below, to see whether it moves the threshold. Varying P on cells
that are already saturated produces no information.

### 7.5 Sizing

Approximately **660 runs** for MAIN plus **180** for REPLICATION.

**Critical unknown.** June's local timings (Qwen3.5-9B at 114–199 s on three-item fixtures) come
from a different endpoint, which is **not** the target machine — almost certainly the Raspberry
Pi, consistent with the 1–5 tokens/s measured there. They do **not** estimate the target hardware.
At 1.5–3 min/run the campaign is 21–42 hours, unattended and feasible; at 15 min/run it is not.

> **Step zero of the campaign is to measure real throughput on the target machine with a
> realistically sized prompt.** All sizing decisions follow that number and not before.

---

## 8. Procedure

### 8.1 Frozen artefacts

The following are produced once, before any measurement, and never touched afterwards. Any change
is an amendment (§11).

1. the item pool and its manual verification;
2. the MAIN/REPLICATION split;
3. the structural acceptance criterion for queues;
4. the K queues;
5. the P1 and P2a corpora;
6. the `prose-derived` and `prose-native` documents;
7. the acceptability threshold for fidelity (90%, frozen 2026-08-17), and the fixture's `expectations.json`.

### 8.2 Probe discipline

Inherited from `testing-runners.md` §2.1 and not optional. An input with no matching case in
`expectations.json` is *silently mis-scored*: the checker compares against `None` and reports
`wrong-value` for any output, including the correct one. Order: (1) add the case with its expected
result, (2) `--dry-run` to check the score, (3) only then the real runs.

A fixture must **lint clean (gate R2) before it is ever run (gate R3)**.

### 8.3 Sealed replication

Binding order. Reversing it voids the pre-registration.

1. draw and manually verify the 300 items;
2. split into MAIN and REPLICATION;
3. run the campaign **on MAIN only**; find the thresholds;
4. **write the conclusion**;
5. *then* open REPLICATION and run the decisive cells only — the threshold level and the one below.

Sealed means *not looked at*, not *not possessed*. If the threshold holds, the claim moves from
"we measured this" to "it held on data we had not seen". If it moves by a level, that is reported.

### 8.4 Data hygiene before reusing existing results

The existing corpus in `tests/results/` is not usable as a baseline as-is:

- **Asymmetric reasoning budget.** June's `claude-haiku` runs used `reasoning_budget: 4000`; local
  models used 0. Not a fair comparison; local runs must be redone with reasoning enabled.
- **Mislabelled environments.** Part of the E1 corpus carries `runner_type: claude-code` with
  `env_realization: emulated` — these came from the manual runner, not the headless executor. They
  are E1 in name only; no tools were present.
- **Unexplained error rate.** The high `execution-error` rate on local models must be attributed to
  model or runner before it is read as model failure.

---

## 9. Analysis plan

Declared before data collection.

1. **Primary outcome** — for each model: the minimum L at which mean conditional fidelity on MAIN
   crosses the frozen acceptability threshold, at P1.
2. **Secondary** — whether P2a lowers that L; the size of the shift.
3. **Secondary** — at the threshold level, conditional fidelity of `sol` versus `prose-derived` and
   `prose-native` (tests H4).
4. **Secondary** — the joint distribution of comprehension and conditional fidelity across cells
   (tests H3).
5. **Variance** — within- versus between-queue components per cell.
6. **Cost** — the configuration → fidelity → cost table.
7. **Confirmation** — the same primary outcome recomputed on REPLICATION, for decisive cells only,
   after step 1–6 have been written up.

Expected-failure cells are recorded as such, not skipped.

---

## 10. Threats to validity

Stated because they will exist regardless of whether they are stated.

- **Label noise.** Mitigated by manual verification of the pool, at the cost of substituting the
  experimenter's judgement for the maintainers'. Declared.
- **Domain specificity.** The dataset is software issues. Whether the threshold transfers to other
  domains is untested; the claim must be scoped accordingly.
- **Ambiguous items.** Some issues legitimately admit two answers (a VS Code issue discussing
  TypeScript; a TensorFlow issue discussing Keras). These are marked `tolerant` in
  `expectations.json` and accept either — otherwise the model is punished for ambiguity the
  experimenter created.
- **Truncation.** Body truncation is part of P1 and therefore identical across cells, but it does
  discard information. The truncation budget is recorded.
- **Single fixture.** One fixture, one process shape. A second W2 fixture with a different shape
  would strengthen any generalisation; it is out of scope for this campaign and noted as future
  work.
- **Hardware specificity.** Cost figures are specific to one 8 GB consumer GPU. Fidelity figures
  should not be, but throughput figures are not transferable.
- **Experimenter degrees of freedom.** Minimised by §8.1 and §8.3; residual freedom exists in the
  acceptability threshold and the structural criterion, both of which are frozen in advance and
  recorded here.

---

## 11. Deliverables

1. **Threshold table** — model → minimum level of collateral context for acceptable fidelity.
2. **Cost table** — configuration → fidelity → collateral tokens → seconds per item → VRAM.
3. **A limits / opportunities / best-practice section**, reusable both as an article and as
   operational guidance for anyone authoring SOL processes. Candidate home:
   `doc/minimum-context-by-model.md`.
4. The frozen artefacts of §8.1, published alongside the results.

Intended outputs: a methodological paper, with the popular article serving as its abstract.

---

## 12. Amendments

Any deviation from this protocol after the first run is recorded here, dated, with its reason.

| Date | Amendment | Reason |
|---|---|---|
| 2026-08-19 | Two-metric sequence oracle: `sequence_rate` (denominator `max(len(expected), len(observed))`) plus `redundancy_ratio`, replacing the single-metric oracle. | The one-metric oracle rewarded runs that ran away or never halted with an inflated `sequence_rate`, because the comparison window was capped at `len(expected)`. Corrected before MAIN, so independent of MAIN's data. |

---

## 13. Open items

- Exact model builds and quantisations available at setup time.
- The final structural acceptance criterion for queues (to be frozen before generation).
- Whether to request explicit permission from the dataset authors before or after the first runs.
- Whether a second W2 fixture of a different shape is added before publication.
