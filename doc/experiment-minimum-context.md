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
That claim is supported by both prose variants being rendered *from* the SOL document rather than
written independently of it (§5.4), and by where the human sits in the chain that produces a prompt
in practice: the analyst confirms the algorithm, and the prompt is written downstream of that
confirmation. If prose executes better, the compilation target changes and the point of
confirmation does not, and the renderer that produces the prompt becomes a step of the
toolchain rather than a research artefact — it ships with the skill. Declaring this in advance
is what stops it from being a post-hoc rescue. What stops it from being unfalsifiable is
stated in the table above: this design cannot test it, and does not claim to.

Read H4 with the derivation asymmetry of §5.4 in view. The prose descends from a SOL document that
has been executed and corrected in this repository, so the comparison favours SOL by construction.
A prose result that merely matches is therefore stronger evidence than the raw numbers suggest, and
a SOL win at the margin is weaker.

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
| **Whether representing the algorithm was worth it** | Every cell of the matrix renders *the same* SOL document: the two prose variants of §5.4 descend from it, so SOL sits upstream of every arm and no result can count for or against its presence in the chain. The control that would test it is a prompt generated straight from the requirements, with no algorithm represented in between. The requirements did precede the fixtures — each one comes from a concrete problem, and the tiers w0…w3 exist to mobilise different parts of the notation — but they were never written down as artefacts, and materialising seven of them is a second experiment, not a cell of this one. What is measured here is which rendering of one algorithm a model executes better. Whether the algorithm needed to exist is a question this design cannot answer, and the claim in §3's note on H4 is therefore declared, not tested. |

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

### 4.5 The second fixture — `w2-branching/support-routing`

*Added 2026-08-23 — see §12. This resolves the last open item of §13.*

`support-intake` triages a queue of ~15 items in a **single invocation**. That is not how a process
of this shape is deployed. A real intake worker is handed one message, applies the standing
instructions, returns a decision, and is invoked again for the next one — with no history, no
retrieval, and nothing but the process document to work from. `support-routing` is that shape: **one
item per invocation**, across the same seven renderings (§5.1, §5.4) and the same six model cells
(§5.3).

**What it inherits, unchanged.** The item pool (§4.3), the five product personas, the `hours_table`,
the `classify-request` SUB, the hour budget, and the `ESCALATE` rule for a `BUG` that does not fit.
The three scores of §6.2 and the code that computes them are untouched: a shorter
`expected_sequence` is still a sequence.

**What it adds — routing over three teams, as set membership.** Local models fail arithmetic
fixtures on the arithmetic rather than on the control flow (§4.1), so the second decision axis is
deliberately not numeric. Each team accepts a fixed set of products and stands as backup on another:

| team | accepts | backs up |
|---|---|---|
| T1 | P1, P2 | P3 |
| T2 | P3 | P2, P5 |
| T3 | P5 | — |

P4 appears in no team's `accepts` and in no team's `backs up`. It is the structural gap, and it
produces an action `support-intake` has no equivalent of: **`UNASSIGNED`** — nobody can ever take
this — as distinct from `DEFER` — someone could, but not in this state. Collapsing the two is a
specific, observable comprehension failure rather than a generic wrong answer.

**Team load is categorical, not a counter.**

| state | takes |
|---|---|
| `OPEN` | anything it accepts |
| `LIMITED` | **`BUG` only** |
| `CLOSED` | nothing |

`LIMITED` is what makes the same product route to two different teams depending on the item's
`intent`. It buys back, with no accumulator and no arithmetic, the property that made
`support-intake` non-degenerate (§4.1): the decision cannot be reached from the item alone.

**The order of operations.**

```
classify                                          (SUB, inherited)
  product == UNKNOWN                              -> NEEDS_INFO
  product accepted by no team                     -> UNASSIGNED
look up hours ; compare with remaining_hours
  intent == BUG and NOFIT                         -> ESCALATE
  NOFIT                                           -> DEFER
route:
  primary team OPEN                               -> ASSIGN to primary
  primary team LIMITED and intent == BUG          -> ASSIGN to primary
  the backup team for the product, if it is OPEN   -> ASSIGN to that team
  otherwise                                       -> DEFER
```

A backup team takes another team's work only while `OPEN`: a team under strain does not absorb
overflow. No product is backed up by more than one team, so the choice among backups never
arises and the fixture states no rule for it — a rule that cannot fire is prompt weight with no
behaviour behind it.

**The trap is precedence, not calculation.** A `BUG` whose primary team is `LIMITED` while a backup
team is `OPEN` belongs to the primary. A model that reasons *there is a team with room, use that
one* answers a plausible question that was not asked. The error is in the order of the rules, which
is what conditional fidelity isolates (§6.2), and no amount of arithmetic competence prevents it.

**Where each piece of data lives.** Fixed data goes in the process document, following
`support-intake`, whose product catalogue is a section of its SOL script and is therefore carried by
all seven renderings: the capability matrix and the `hours_table` are document. Mutable data goes in
the payload: the item, `remaining_hours`, and the three team states.

**The state in the payload is computed by the oracle, never chained from the model's own previous
answer.** Chaining would restore the dependence the per-item shape exists to remove — a wrong
decision at item 3 hands item 4 a false world, and fifteen runs collapse into one observation. With
the state injected, every run is an independent trial of *given this world and this message, take
the right branch*. What chaining would have measured is recoverable without paying for it: the first
item whose action diverges from the oracle is the point at which a chained deployment would have
left the rails, and that is read off the per-item results.

**Arithmetic.** One table lookup and one comparison, inherited from `support-intake` so the
`ESCALATE` path stays comparable. Nothing is added.

**Trace format**, per invocation:

```
[fixture-w2-support-routing][main] EVAL: item=<id> product=<P1..P5|UNKNOWN> intent=<BUG|FEATURE|QUESTION>
[fixture-w2-support-routing][main] BRANCH: item=<id> action=<ASSIGN|DEFER|NEEDS_INFO|ESCALATE|UNASSIGNED> team=<T1|T2|T3|-> remaining=<n>
```

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

**Levels are not layers, despite the letters.** L0-L4 here are *levels of collateral context*; L1,
L2, ... in `predictability-strategies.md` are *layers of predictability*. The whole L0-L4 scale
sits inside one of those layers, the linguistic one. The two never index each other.

**What varies across the levels is the explanation, never the task.** The input data and the SOL
script are what make the task executable at all, so they are present at every level, L0 included;
L0 is SOL without prose, not SOL removed. Each level is a strict prefix of the next.

> **Conformity note, 2026-08-22.** Until this date the implementation did not match the
> table above: `L0` emitted only the input payload — no SOL script, no product catalog — and `L1`
> was therefore not additive over it. The cause was a vocabulary collision: "bare JSON" was read as
> the input JSON rather than the SOL document. The code was brought in line with the table; the
> table itself is unchanged, so this is a correction of conformity and **not** an amendment under
> §12. Consequence for existing results: every E0 run recorded before this date — the technical
> pilot and the Ministral run in the index — was produced at the pre-realignment prompts and is not
> comparable with runs produced after it.

### 5.2 P — input preparation

Both regimes are **frozen and pre-computed offline**, producing two fixed corpora. Preprocessing is
therefore not a per-run cost and is bit-for-bit reproducible — the same discipline applied to
`prose-mechanical` and `prose-generated`.

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

*Amended 2026-08-19 and 2026-08-22 — see §12. This section previously listed three cells and
excluded the 12B class outright.*

All locally runnable on the target hardware (RTX 5070 Laptop, 8 GB VRAM, 32 GB RAM). Five cells,
five families: with one family only, the experiment measures that family and not SOL.

| Role | Model | Context | Rationale |
|---|---|---|---|
| balanced, primary | Qwen3.5-9B Q4_K_M | 51,200 | prior runs exist → direct comparability. Two modes, thinking on and off |
| balanced, second family | Ministral-3-8B Q4_K_M | 38,912 | Mistral lineage, non-thinking |
| third family | granite-4.1-8b Q4_K_M | 28,672 | IBM lineage, hybrid Mamba/attention — the only non-transformer-only cell |
| thinking, fourth family | gemma-4-12b QAT UD-Q4_K_L | 43,008 | Google lineage. 12B admitted (see below) |
| fast | Phi-4-mini (~3.8B) Q4_K_M | 43,008 | reported as the most reliable at this size for structured output |

**Excluded:** models below ~3B (prior runs show 2/50 pass — noise, not a tier).

**On the 12B class.** This section previously excluded it on the grounds that ~8.1 GB of weights
spill to CPU at L3/L4. The QAT UD-Q4_K_L quantisation of gemma-4-12b fits, and — measured
2026-08-22 — its sliding-window attention makes the KV cache cheap: +11,264 tokens of window cost
it 116 MiB, against 512 MiB for Ministral. The exclusion stands for a dense 12B at a heavier
quantisation, not for this cell.

**On the contexts.** Each cell's context is the largest that stays resident in VRAM, measured cell
by cell on 2026-08-22 with prefill throughput as the witness. The failure mode being avoided is not
a crash: past the ceiling the Windows driver silently spills the KV cache to system memory and
prefill collapses — Ministral 2,344 → 82.8 t/s at 43,008, granite 2,176 → 53.9 t/s at 32,768. The
acceptance criterion (§8, prefill > 1000 t/s) catches exactly this, which is why it is measured on a
campaign-sized prefill.

granite has no headroom at all: 28,672 is its ceiling on this card.

**What does not fit is declared.** A row is refused before it is run when fewer than 2,048 tokens
remain for the answer after the prompt, and is reported as `skipped-window`: a limit of the bench,
not an execution error and not a verdict on the model. Counted exactly with each cell's own
tokenizer on 2026-08-22, that is **18 rows out of 900** — all of them queue-07, the outlier of the
ten (24,908 tokens at L0 against 6,177–15,792 for the other nine): granite 12, from L1 upwards;
Ministral 3 and gemma 3, at L4 only; Qwen and Phi-4-mini none.

The count is done per tokenizer and not from an average because the same prompt is 37,961 tokens for
Qwen and 42,960 for gemma. Silently letting such a row run is worse than refusing it: measured
before this rule was added, gemma had 48 tokens left to answer in and reported the run as done — a
measurement of the bench filed as a measurement of the model.

**The frontier reference cell (added 2026-08-31, §12).** The cells above are the object of the
experiment: what a model running on the operator's own machine does with SOL. They say nothing
about what the same documents are worth to a hosted model, and that is the first question any
reader of the campaign asks. One reference cell answers it without touching the grid:
`claude-code-haiku` — Claude Haiku 4.5, invoked exactly the way this project invokes a model every
day, `claude -p --model claude-haiku-4-5`, with the fixture's own system prompt and no tools. It
runs one block and one only, `routing-notrace-haiku`: the untracked per-item arm, same twenty
requests, same seven renderings, same two repetitions, same oracle, same index. It is a term of
comparison and not a sixth family — no outcome in §9 is computed over it, and no claim about local
models depends on it. Its cell table is separate (`tests/campaign-cells-frontier.json`) so that no
block written before it can pick it up, and it starts no llama-server, so §5.3's contexts,
acceptance criterion and `skipped-window` rule do not apply to it: none of them is a statement
about a model on someone else's hardware.

**The other two rungs (added 2026-09-01, §12).** The same reference, twice more, on the two tiers
above Haiku: `claude-code-sonnet` (Claude Sonnet 5) and `claude-code-opus` (Claude Opus 5), blocks
`routing-notrace-sonnet` and `routing-notrace-opus`, 280 rows each. Everything the haiku arm holds
fixed stays fixed — fixture, twenty requests, seven renderings, two repetitions, oracle, results
root, index, and the three flags of §2.1 in `experiment-frontier-reference.md` — and the model id is
the only coordinate that moves. This is deliberately **not** a same-generation family sweep: there
is no Haiku 5, so the ladder is haiku-4.5 / sonnet-5 / opus-5, the three tiers as this project can
invoke them today. What the three together answer that one could not: whether the gap between the
local grid and a hosted model is a property of the *tier* — a ladder the reader can place 0.392 on —
or a step that Haiku already saturates. Same standing as the first rung: outside §9, no outcome
computed over them, no claim about local models depending on them.

### 5.4 Language variant

The same process in two languages. Both prose renderings are produced *from* the SOL document,
frozen before any results are seen, never hand-tuned afterwards.

- **`sol`** — the JSON document, across the L scale;
- **`prose-mechanical`** — rendered from the SOL document by the deterministic renderer shipped
  with the SOL skill. No model in the loop, bit-for-bit reproducible;
- **`prose-generated`** — rendered from the SOL document by a model in a single pass, from a
  prompt frozen in advance (`tests/fixtures/PROSE-VARIANT-PROMPT.md`, which is itself a frozen
  artefact under §8.1).

The L scale does not apply to prose: prose needs no glossary or specification. This asymmetry is
intentional and is the actual question — *at what level L does SOL beat prose by enough to justify
the collateral it drags along?*

**Why there is no hand-written prose variant.** An earlier version of this section listed a
`prose-native` rendering, written by hand as an analyst unfamiliar with SOL would write it. It was
withdrawn on 2026-08-22 (§12), and the reason is not that it would be hard to score. It is that it
does not correspond to anything. The chain that actually produces a prompt in the field runs:
requirements gathered, written up, a model asked to derive an algorithm from them, the algorithm
represented so that the user can confirm it is what they wanted, a model asked to write the prompt
that implements it. The human step in that chain is the **confirmation of the algorithm**, not the
composition of the prompt. That step is where the criterion of validity actually sits: in the
field, what settles whether a process works is the user's consent to the contents and to the
results it produces, and that consent is given on the algorithm, upstream of either rendering.
The comprehension and fidelity oracles of §6 are measurable proxies for it, not the criterion
itself. A hand-written prompt is therefore not the rigorous baseline the comparison lacks; it is
the artificial object. It would also carry no definable quality criterion
— a prose loss would be answered with *"it was written badly"* and a prose win with *"it was
written too well"* — but that is the lesser objection, and it is downstream of the first.

**The direction of derivation, and what it costs.** Both prose renderings descend from the SOL
document, so the SOL document is the mature artefact of the pair: it has been executed, scored and
corrected in this repository, and wording that models tripped over has been fixed. The prose
descends from it in one pass, from a prompt validated for conformity — does it say everything, is
it prose rather than the notation with its punctuation removed — and never for performance. The
comparison is therefore not notation against notation in the abstract; it is a matured document
against a fresh one, and the advantage runs towards SOL. That direction is declared rather than
corrected: correcting it would mean tuning a frozen artefact against model behaviour, which is
what the freeze forbids. Its consequence is stated with H4 in §3.

**How the cells are recorded.** §5.1 applies to `sol` only and this section does not apply to
`sol`, so the two factors never cross: the design space is not a grid but a flat list of seven
cells — `L0` through `L4`, `prose-mechanical`, `prose-generated` — carried on a single selector in
the run record. **The seven do not sit on one axis.** Five of them form a curve, in which each
level is a strict prefix of the next; two are comparison points against it. A figure that plots
all seven in sequence, or an average taken across them, reads a change of language as a change of
quantity and is wrong by construction.

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

### 7.3 The full L grid

*Amended 2026-08-22 — see §12. This section previously prescribed adaptive laddering: climb
L0 → L1 → L2 … and stop as soon as the model crosses the acceptability threshold.*

The L scale is explored **exhaustively**: all five levels of every (cell, mode, queue, repetition)
combination, with no early stop.

Stopping at the first level above threshold assumes fidelity is monotone increasing in L — that
above the threshold it stays above. But the existence of a threshold is precisely the conclusion
this campaign is meant to establish, not its premise, and the mechanism that breaks monotonicity is
already documented: the L scale competes with reasoning for the window (decision of 2026-08-18), and
at L4 the prompt sits between 22,713 and 27,179 tokens depending on the tokenizer, leaving less room
to generate. A model that closes well at L1 may have no room left at L4. The curve can be a bell
rather than a step — and under the adaptive design that behaviour is invisible by construction,
because the levels above the threshold are never looked at.

What the grid yields is therefore not a table of thresholds but a **fidelity curve per level**, for
every cell: monotonicity becomes something demonstrated rather than assumed.

### 7.4 Where the P axis is varied

The L curve is established first at **P1**, the cheap default. **P2a** is then run at the level
chosen **post hoc** from that curve — the lowest level whose fidelity clears the acceptability
threshold, or the level of best fidelity if none does — and one level below, to see whether
preprocessing moves it. Varying P on cells that are already saturated produces no information.

The acceptability threshold itself is unchanged (90%, §8.1): what the 2026-08-22 amendment changes
is *when* it is read — after the data, not during the run.

### 7.5 Sizing

Approximately **900 runs** for MAIN's P1 block (6 modes × 5 levels × 10 queues × 3 repetitions),
plus P2a and the prose variants at the chosen level, plus **180** for REPLICATION. Estimated
**13–18 hours** for the P1 block. The band is wider than the pre-amendment estimate (~660 runs)
because L0 — bare JSON, no instructions — is expected to produce a high runaway rate, and a runaway
run costs about twice a good one.

**Critical unknown.** June's local timings (Qwen3.5-9B at 114–199 s on three-item fixtures) come
from a different endpoint on the same LAN, which is **not** the target machine — almost certainly a
Raspberry Pi, consistent with the 1–5 tokens/s measured there. They do **not** estimate the target
hardware.
At 1.5–3 min/run the campaign is 21–42 hours, unattended and feasible; at 15 min/run it is not.

> **Step zero of the campaign is to measure real throughput on the target machine with a
> realistically sized prompt.** All sizing decisions follow that number and not before.

---

### 7.6 Composition and sizing of the per-item block

`support-routing` (§4.5) runs **after** MAIN, not beside it. One `llama-server` instance holds the
GPU at `n_parallel: 1`, so what forbids the overlap is the slot, not the files.

**Items replace repetitions — but not entirely.** Each item is already an independent trial, so the
K × R design of §7.1 does not carry over unchanged; its reason does. One repetition of many items
measures combinatorial difficulty alone, and variance is one of the four metric groups this
framework reports (§7.2).

**20 items × 2 repetitions = 40 runs per cell**, against MAIN's 30. Twenty because the strata below
need at least two members each; two repetitions because one measures no stochastic noise at all.

- dispersion **within** an item = stochastic noise;
- dispersion **between** items = sensitivity to the case.

20 × 2 × 7 renderings × 6 modes = **1,680 runs**. More rows than MAIN's 1,260 and, in expectation,
less wall clock: the prompt is dominated by the rendering rather than by the payload — at L4 the
document alone is 22,713–27,179 tokens (§7.3) — while the output is one item's decision instead of
fifteen. That expectation is not a measurement, and §7.5's step zero applies here as it applied to
MAIN: measure the real per-run time on the first cell before committing to the block.

**The 20 items are stratified, not sampled.** A single draw over the pool would land three quarters
of its mass on the easy branch. Every stratum is represented at least twice and the precedence trap
three times, with one exception noted under the table:

| stratum | expected action |
|---|---|
| primary team `OPEN` | `ASSIGN` primary |
| primary `CLOSED`, backup `OPEN` | `ASSIGN` backup |
| **primary `LIMITED`, intent `BUG`** — the precedence trap | `ASSIGN` primary |
| primary `LIMITED`, intent `FEATURE`/`QUESTION`, backup `OPEN` | `ASSIGN` backup |
| no eligible team taking work — owner and backup `CLOSED`, or a backup `LIMITED` | `DEFER` |
| a `FEATURE` or `QUESTION` that does not fit the remaining budget | `DEFER` |
| product P4 — accepted by nobody | `UNASSIGNED` |
| product not recognisable from the personas | `NEEDS_INFO` |
| `BUG` that does not fit the remaining budget | `ESCALATE` |
| malformed input | `INVALID_INPUT` |

Two of those cannot be drawn from the pool and are written instead, and both are declared as
synthetic in the manifest. No item from five real repositories is unrecognisable against the five
personas built from those same repositories, so the off-catalog request — the only stratum with a
single member — is one the experimenter wrote; without it `NEEDS_INFO` is reachable only through a
model's mistake, which is a stratum nothing can sample. The malformed payload is structural and
sits outside the twenty, exactly as `support-intake`'s does.

**Where the results go.** The same results root as MAIN, `tests/results-main/`, and the same
`index.jsonl`. The index already records `fixture_id` and `staged_input_id` on every row
(`tests/runner/runner.py`), and the dashboard already filters, tabulates and charts by fixture
(`scripts/dashboard.py`): the two fixtures separate themselves, and their L curves are read side by
side without exporting anything. What cannot be shared is the plan file — MAIN's is a frozen
artefact of a finished run — so the block gets `campaign-plan-routing.json` beside it, which
`campaign._use_results_root(root, plan_name=...)` already supports. One plan per block because a
plan is frozen, not because this is a different experiment.

---

## 8. Procedure

### 8.1 Frozen artefacts

The following are produced once, before any measurement, and never touched afterwards. Any change
is an amendment (§12).

1. the item pool and its manual verification;
2. the MAIN/REPLICATION split;
3. the structural acceptance criterion for queues;
4. the K queues;
5. the P1 and P2a corpora;
6. the two prose generators of §5.4 and the documents rendered from the SOL fixtures with
   them: the frozen generation prompt (`tests/fixtures/PROSE-VARIANT-PROMPT.md`) for
   `prose-generated`, and `tests/scripts/build_prose_mechanical.py` for
   `prose-mechanical`. The second assembles the skill's deterministic renderer
   (`sol2prose.py`) into the fixture's own shell, replacing the process section and
   nothing else; the three normalisations it applies to the renderer's output are stated
   in its docstring. Both are generators in the same sense: a defect in a prose document
   is fixed in the generator and the documents are regenerated, never hand-patched;
7. the acceptability threshold for fidelity (90%, frozen 2026-08-17), and the fixture's `expectations.json`;
8. for `support-routing` (§4.5): the team capability matrix, the three team states, the 20
   stratified items of §7.6 together with the world state injected with each of them, and that
   fixture's own `expectations.json`.

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

Since 2026-08-22 the separation is physical rather than advisory: MAIN writes to `tests/results-main/`
and leaves `tests/results/` as it stands. Nothing has to be filtered out at analysis time, and the
campaign's dashboard is the campaign's — blending 576 runs measured on other fixtures, other models
and code that has since changed would move every figure on that page without any of it being about
the campaign.

---

## 9. Analysis plan

Declared before data collection.

1. **Primary outcome** — for each model: the minimum L at which mean conditional fidelity on MAIN
   crosses the frozen acceptability threshold, at P1.
2. **Secondary** — whether P2a lowers that L; the size of the shift.
3. **Secondary** — at the threshold level, conditional fidelity of `sol` versus
   `prose-mechanical` and `prose-generated` (tests H4).
4. **Secondary** — the joint distribution of comprehension and conditional fidelity across cells
   (tests H3).
5. **Variance** — within- versus between-queue components per cell.
6. **Cost** — the configuration → fidelity → cost table.
7. **Confirmation** — the same primary outcome recomputed on REPLICATION, for decisive cells only,
   after step 1–6 have been written up.

8. **Secondary** — the shape of the L curve on `support-routing` against its shape on
   `support-intake`, per cell. The same shape is evidence that a rendering result is a property
   of the rendering rather than of one process; a different shape is a finding about the
   interaction between rendering and delivery, and §10 states why it cannot be attributed to
   delivery alone.

Expected-failure cells are recorded as such, not skipped.

### 9.1 Unplanned: the halt is a second barrier, and it binds first

Post hoc, 2026-08-24, on MAIN's 1,236 rows. Not pre-registered — it was found by asking why
`llama-qwen3.5-9b-nothink` never passed once, and it is reported here because it changes what the
headline number means, not because the protocol anticipated it.

**The queue is not fifteen decisions.** `support-intake` stops when the hour budget cannot absorb a
`BUG`: the expected item list runs 6 to 11 long, mean 8.7, never 15. So end-to-end `quality`
factorises into two independent conditions, and they are not equally hard:

| cell | ① stops at the right length | ② passes, given ① | `quality` | comprehension |
|---|---|---|---|---|
| `qwen3.5-9b-think` | 21.9% | 19/46 = 41% | 9.05% | 0.817 |
| `gemma-4-12b` | 18.8% | 0/39 | 0 | 0.723 |
| `granite-4.1-8b` | 6.3% | 0/12 | 0 | 0.518 |
| `ministral-8b` | 2.4% | 0/5 | 0 | 0.711 |
| `phi4-mini` | 2.4% | 0/5 | 0 | 0.267 |
| `qwen3.5-9b-nothink` | **0.0% (0/213)** | — | 0 | 0.782 |

Four cells of six die at ①. Classification alone would predict far better: 0.745^8.7 ≈ 7.7%, against
1.54% observed. The gap is the halt — and it is wider than that line suggests, because 0.745 is the
campaign comprehension mean, depressed by the four items §10 describes; per item read cleanly the
figure is 0.863, which predicts 27.7%.

**The `nothink` zero is not improbable, it is impossible.** No payload it produced ever had the
expected number of items; 154 of its 181 readable payloads carried all fifteen. It cannot pass by
accident, because it is not answering the same question. And it is not ignorance of the rule: **46
times it wrote the correct `halted_at` while returning the whole queue underneath it**. It locates
the exit, reports it, and does not take it — the `RETURN` nested inside the `REPEAT` read as a fact
to state rather than an exit to execute. This is now a named degradation mode, `halt-not-taken`
(§12, 2026-08-24): 82 of MAIN's 1,236 rows.

**The controlled comparison is already in the grid.** Same weights, same quantisation, same context,
`thinking` the only difference: with it, barrier ① at 21.9%; without it, 0.0%. The halt is the sole
element of the process requiring state carried *between* items — the hour accumulator — and it is
the element that disappears when the scratchpad does.

**Reading the result generously does not rescue it.** Truncating each payload at the first
`ESCALATE` the model itself declared — crediting the holistic reading in full — takes the campaign
from 19 passes to 34 of 1,229, 1.5% to 2.8%. `nothink` goes from 0% to 6.6%. Barrier ② still binds.

**More SOL documentation does not help; prose does.** Barrier ① by rendering, on rows returning a
readable payload:

| rendering | stops at right length | | |
|---|---|---|---|
| L0 (script only) | 8/125 = 6.4% | | |
| L1 (+ minimal instruction) | 20/130 = 15.4% | vs L0 | p = 0.027 |
| L2 (+ glossary) | 11/150 = 7.3% | | |
| L3 (+ the whole of `spec/sol-0.6.md`) | 12/146 = 8.2% | vs L1 | p = 0.089 |
| L4 (+ examples) | 9/130 = 6.9% | | |
| prose-mechanical | 14/158 = 8.9% | | |
| prose-generated | 33/166 = 19.9% | vs L0–L4 pooled | **p = 0.0001** |

L3 carries the sentence that settles the question — *"`RETURN` does not end the executing agent — it
ends this process and yields upward"* — and does not beat L1, which carries no spec at all. The same
process written as prose doubles the rate against the whole L ladder. The reading this supports is
that the notation, not the task, hides the early exit: a `RETURN` three levels inside `REPEAT` →
`IF` → `WHEN` is visually indistinguishable from the terminal `RETURN` twelve lines below it.

Two caveats, both real. The rates are conditioned on rows that returned a readable payload, and the
denominators differ (125 to 166) — but the bias runs *against* the prose result, whose larger
denominator admits weaker runs that the L cells lost to `no-output`. And barrier ① is measured by
item count, which is necessary and not sufficient: a payload of the right length has taken the halt,
but may have taken it in the wrong place.

What follows for the campaign: the `support-routing` block has no halt and no accumulator — one
item, world state supplied — so it measures barrier ② alone, at n=1 instead of n≈8.7. Its 30.5%
against MAIN's 1.54% in the 2026-08-24 smoke is that difference, not a separate result. §10's
fixture/delivery confound applies: routing is a shorter task, not the same task with the halt
removed.

---

### 9.2 Unplanned: one model's branching is a property of the item, and the ladder never touches it

Post hoc, 2026-08-29, on the routing block. Not pre-registered — it was opened because
`gemma-4-12b` returned `conditional_rate` **0.400 exactly** on five of seven renderings
(n=40 each), which is too flat to be a sample. It is not: the flatness is the result.

**The same eight items, in six of seven renderings.** Conditional fidelity asks whether the model
branched correctly *given its own classification*, so it reads control flow with classification
noise removed. Taking the items gemma gets right in both repetitions:

| rendering | items always right | runs |
|---|---|---|
| L0 | 8 | 17/40 = 0.425 |
| L1 · L2 · L3 · L4 · prose-mechanical | 8 | 16/40 = 0.400 |
| prose-generated | 10 | 21/40 = 0.525 |

The eight are not merely the same *number*: across L0–L4 and `prose-mechanical` they are the
identical set — `r01 r02 r03 r06 r07 r08 r15 r20`. L0's extra run is `r05` passing once of two.
`prose-generated` adds two (`r11`, `r18`) and removes none. Sampling is at temperature 0.2, not 0
(§5.5), so this is behavioural determinism and not greedy decoding.

**The eight are one rule.** By stratum, over the six renderings that share the set:

| stratum | always right | expected action |
|---|---|---|
| `owner-open` | 3/3 | ASSIGN (primary) |
| `trap-limited-bug` | 3/3 | ASSIGN (primary) |
| `off-catalog` | 1/1 | NEEDS_INFO |
| `accepted-by-nobody` | 1/2 | UNASSIGNED |
| `owner-closed-backup` | 0/2 | ASSIGN (backup) |
| `limited-nonbug-backup` | 0/2 | ASSIGN (backup) |
| `no-team-available` | 0/3 | DEFER |
| `bug-over-budget` | 0/2 | ESCALATE |
| `nonbug-over-budget` | 0/2 | DEFER |

gemma has one branch: *route to the team that owns the product*. Every stratum whose answer is the
primary team passes, every stratum requiring a fallback — backup team, `DEFER`, `ESCALATE` — fails,
in every rendering, in every repetition.

**The fixture's designed trap is passed for the wrong reason.** `trap-limited-bug` (§4.5) exists to
catch the model that reasons *there is a team with room, use that one* when the owning team is
`LIMITED` and the item is a `BUG`. gemma clears it 3 of 3 — not by getting the precedence right,
but because it never considers a backup at all. A model that always answers "primary" cannot fall
into a trap made of preferring the backup. The trap discriminates only among models that have the
second rule to begin with, which is worth knowing before a per-stratum result is read as competence.

**Why this bears on H1.** The aggregate L curve is flat, which is the falsification as planned.
This is the same fact at the resolution of the individual decision: L0 through L4 add the products,
the hours table, the precedence rule and the spec sentence, and **not one item changes hands**. The
ladder does not fail to move the average; it fails to move any decision at all. What moves gemma is
a different rendering of the same content — `prose-generated`, +2 items — which is §4.5's other
finding arriving through the same door.

Not tested here: whether the one-rule shape is peculiar to gemma. `ministral-8b` varies across
renderings (0.727–0.889) and `qwen3.5-9b-nothink`'s two 0.400 cells are 8 always-right items each
but **different** eights, so its equality is arithmetic coincidence rather than invariance. Only
gemma shows the set identity.

### 9.3 Unplanned: the rendering effect differs by model, but the crossover does not replicate

Post hoc, 2026-08-29, on both per-item arms. `tests/scripts/analyse_rendering_interaction.py`,
seed 20260829. Opened because §4.5's reading rested on an ordering of six points, and because a
stronger claim was circulating alongside it — that `prose-generated` helps weak models *at the
strong ones' expense*. The first survives; the second does not.

**Method.** The unit is the item: all twenty requests run in every cell, so a comparison between
renderings is paired within item and runs inside an item are not independent. Every interval is a
percentile bootstrap over items resampled with replacement, 20,000 draws, twenty clusters — few,
and the widths say so. The delta is `P(pass | prose-generated) − P(pass | L0–L4)`.

The trap this had to avoid: a delta correlated against its own baseline is negatively biased
before any model behaviour enters, because the two share a term. Regression to the mean alone
produces the reversal. Three baselines are therefore reported — the coupled one (shown to be
discounted), a split-half one (rep01 for baseline, rep02 for the delta), and the opposite arm,
which shares items, modes and renderings but no run. The correlation is also given on the
log-odds scale, where a mode at 2% and one at 61% are not measured on different rulers.

**`prose-generated` beats the ladder, and by how much depends on the model.**

| mode | tracked arm | untracked arm |
|---|---|---|
| `gemma-4-12b` | +9.0 [−1.5, +22.5] | **+41.0 [+21.0, +61.5]** |
| `granite-4.1-8b` | +4.7 [−7.9, +17.9] | +6.3 [−8.0, +21.0] |
| `ministral-8b` | −8.0 [−21.0, +2.5] | +3.0 [−8.5, +15.5] |
| `phi4-mini` | **+21.0 [+8.0, +35.5]** | **+20.5 [+4.5, +38.5]** |
| `qwen3.5-9b-nothink` | **+17.0 [+3.0, +33.5]** | +8.5 [−5.0, +24.0] |
| `qwen3.5-9b-think` | +2.0 [−15.0, +18.5] | **+14.4 [+6.7, +23.2]** |

That the effect varies by model is established in both arms: the spread of the six deltas is
29.0 pp [14.0, 54.5] tracked and 38.0 pp [22.5, 66.1] untracked, and neither interval reaches
zero. §4.5's own sentence — best rendering for several modes, gemma untracked 0.75 against 0.38
on L0 — is confirmed with an interval that excludes zero.

**The crossover is not.** On the tracked arm the pre-specified contrast (weakest minus strongest
on the ladder) is +29.0 pp [+8.5, +52.0], which excludes zero — but it rests on ministral's −8.0,
whose own interval [−21.0, +2.5] does not. On the untracked arm the same contrast is +6.1 pp
[−11.0, +24.4], and **no mode has a negative delta at all**: the strongest model there gains
+14.4 with an interval clear of zero. A pattern that reverses between two arms of the same task
is not a finding about model strength.

The correlation between strength and gain tells the same story once decoupled:

| baseline | tracked | untracked |
|---|---|---|
| coupled (biased — for reference only) | ρ = −1.000, p = 0.0028 | ρ = −0.429, p = 0.419 |
| split-half | ρ = −1.000, p = 0.0028 | ρ = −0.429, p = 0.419 |
| the opposite arm (independent) | ρ = −0.943, p = 0.0167 | ρ = −0.600, p = 0.242 |
| the same, on log-odds | ρ = −0.943, p = 0.0167 | ρ = −0.714, p = 0.136 |

Decoupling costs the tracked arm its perfect reversal but leaves it significant; the untracked arm
never had one. **And six modes cap what any of this can show**: the tightest two-sided exact test
available at n=6 is p = 0.0028, which is what a *perfect* reversal buys. The ceiling on the
evidence is set by the grid, not by the effect. The defensible statement is that `prose-generated`
helps, most where the model is weakest, and that whether it ever *costs* a model is unresolved.

**A correction to §4.5, and a new fact.** The claim that SOL and `prose-mechanical` are
interchangeable holds only where the trace is demanded. On the tracked arm five of six modes
cannot be told apart (`phi4-mini` alone at +13.5 [+4.0, +25.0]). On the untracked arm three can:
`gemma` +33.5 [+15.5, +53.0], `phi4-mini` +10.5 [+2.0, +20.0], and `ministral` **−12.0**
[−24.5, −1.0]. So ministral is not "indifferent to rendering across all seven" as §4.5 says: it is
indifferent to `prose-generated` and measurably worse on `prose-mechanical` once the trace is
gone. The deterministic renderer is not a neutral carrier of the same content — the equivalence
was an artefact of measuring it only where every rendering also had to emit a trace.

## 10. Threats to validity

Stated because they will exist regardless of whether they are stated.

- **Label noise.** Mitigated by manual verification of the pool, at the cost of substituting the
  experimenter's judgement for the maintainers'. Declared.
- **Domain specificity.** The dataset is software issues. Whether the threshold transfers to other
  domains is untested; the claim must be scoped accordingly.
- **The reporter's own `Type:` field is in the body.** GitHub issue templates ask the reporter to
  pick a category, and the answer is stored in the body text the model reads — so the input carries
  a self-reported label alongside the text to be labelled. 14 of the 65 experiment items carry one;
  on 4 it contradicts the verified label, and on those 4 intent accuracy collapses to **4.2%**
  against **93.0%** on the 61 items that carry none (8,349 `EVAL` lines, MAIN). It is the field
  named by the header that fails, not the item: on those same 4, `product` is read at 95.4%,
  *above* the campaign average. Those 4 are also 4 of the 5 items on which every model contradicts
  the verified label — the whole of the ground-truth dispute reduces to this one cue.

  Not corrected, and deliberately so. Every cell reads the same bodies, so the contamination is a
  constant: it lowers the absolute level of comprehension without touching any comparison the
  campaign makes — between L levels, between renderings, between models. Recorded here so the
  absolute number is read for what it is. In a deployment the field would simply not be shown to
  the classifier, which is a statement about preparing input and not about SOL.

  It also fixes what `comprehension` measures. The campaign mean of 0.738 decomposes as
  **coverage 0.969 × per-line accuracy 0.815**: models emit an `EVAL` line for almost every item
  they are given, and are right about four in five of the ones they speak about. Per line, `product`
  reads 92.4% and `intent` 87.9% — 93.0% once the four tainted items are set aside.
- **Ambiguous items.** Some issues legitimately admit two answers (a VS Code issue discussing
  TypeScript; a TensorFlow issue discussing Keras). These are marked `tolerant` in
  `expectations.json` and accept either — otherwise the model is punished for ambiguity the
  experimenter created.
- **Truncation.** Body truncation is part of P1 and therefore identical across cells, but it does
  discard information. The truncation budget is recorded.
- **Fixture and delivery are confounded.** `support-intake` is delivered batched and
  `support-routing` per item (§4.5); neither is run the other way. A difference between the two
  therefore cannot be attributed to the delivery shape rather than to the process content, and
  no such attribution is claimed. Isolating it needs a third block — `support-intake` per item,
  its state injected the same way — recorded in §13 and not part of this campaign.
- **Two fixtures, two process shapes.** Better than the single fixture this protocol was
  written around, and still not a corpus. Generalisation beyond a W2 branching process remains
  unsupported.
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
| 2026-09-02 | **The two registered arms ran, and the prediction of 2026-09-01 holds: the hosted ladder flattens one rung above Haiku.** 280/280 `done` each, exit 0, in 88 minutes unattended. Quality 0.789 (Haiku 4.5) → 0.846 (Sonnet 5) → 0.836 (Opus 5); graded `quality_rate` 0.908 → 0.942 → 0.931. Sonnet to Opus is −1.0 points, three rows, noise. r02, r10 and r19 fail 14/14 on **all three** tiers and account for 42 of Sonnet's 43 and 42 of Opus's 46 failures, at the same `quality_rate` 0.625 signature §4 identified; what the ladder does buy is the tail (r15 9→1, r11 5→0/1). The curve on `L` is flat on both rungs (Sonnet's spread across the seven renderings is 0.025 — one row). 840 hosted rows delivered a parseable payload 840 times. Recorded in full in `doc/experiment-frontier-reference.md` §9.3–§9.7, cost included ($8.80 and $20.46, subscription). One observation kept out of the quality reading and written down instead: Opus's four `INVALID_INPUT` rows, all prose-mechanical, are the guard clause of the procedure firing on a missing `request_path` — the strictest reading of the written process against the bench's E0 convention of pre-injecting the input. | The first rung established that the task is not saturated at 0.392; these two establish the other end, which no single hosted cell could: the local grid's 45-point distance is measured against a ceiling that more model does not move. That makes the campaign's residual a property of the task — semantic classification of a support request — and not of model size, which is exactly the reading §4 left open and could not settle from one cell. It also puts a number on the practical ceiling of this fixture (~0.85) that any later claim about SOL and frontier models has to sit under. |
| 2026-09-01 | **The frontier reference becomes a ladder: two more hosted arms, planned and registered before they ran — blocks `routing-notrace-sonnet` (cell `claude-code-sonnet`, Claude Sonnet 5) and `routing-notrace-opus` (cell `claude-code-opus`, Claude Opus 5), 280 rows each, on `w2-branching/support-routing-notrace` unchanged.** Same twenty requests, same seven renderings, same two repetitions, same oracle, same results root and index as the haiku arm of 2026-08-31; same invocation and the same three flags (`--safe-mode`, `--system-prompt` with the fixture's own, `--tools ""`); the model id is the only coordinate that moves. One block and one plan file per rung, each naming its cell through `cells`, because the frontier table now holds three. Model ids are `claude-sonnet-5` and `claude-opus-5`: there is no Haiku 5, so the ladder is the three tiers as invocable today and NOT a same-generation sweep — recorded here because it is the one thing about the design a later reader could take for granted and be wrong about. One row of each arm was executed on 2026-09-01 as an environment preflight (both `done`, both `quality=pass`); the remaining 279 of each run unattended from 02:00 on 2026-09-02. Standing: outside §9, exactly as the first rung. | The first rung answered whether the task is saturated at 0.392 — it is not — but one hosted cell cannot tell a *tier* effect from a step that the smallest hosted model already reaches. Three rungs can: if quality is flat from Haiku to Opus, the residual §4 concentrates on (semantic classification of the request) is a property of the task and not of model size, and the campaign's ranking of local cells is measured against a ceiling that more money does not move. If it rises, the reader gets the scale the ratios lack. Registered before the run for the same reason §5.3 was: an arm designed after its own data has no prediction in it. |
| 2026-08-31 | **A frontier reference cell is added, and it runs the untracked per-item arm and nothing else: block `routing-notrace-haiku`, cell `claude-code-haiku`, 280 rows planned, not yet run.** Claude Haiku 4.5 through `claude -p --model claude-haiku-4-5` — the project's own everyday invocation — against `w2-branching/support-routing-notrace` unchanged: the same twenty requests, the same seven renderings built by the same `_build_prompt_e0`, the same two repetitions, the same oracle, the same results root and index. The prompt is byte-identical to the one the API arm would send; three CLI flags carry that equality and are recorded here because each of them is load-bearing. `--system-prompt` (not `--append-system-prompt`) puts the fixture's own persona where the API arm puts `system`, instead of layering it over Claude Code's coding-agent prompt. `--safe-mode` disables the host machine's CLAUDE.md, SessionStart hooks and plugins — without it every row of this arm would have opened with whatever that machine tells its sessions to do, and would have measured the operator's shell. `--tools ""` is E0. The prompt travels on **stdin**, not as an argv element: Windows caps a command line at 32,767 characters and this fixture's prompt is 38,475 at L3 and 45,469 at L4, so two of the seven renderings were unrunnable in the first smoke — and unrunnable in a way that lied, since `ERROR_FILENAME_EXCED_RANGE` reaches Python as `FileNotFoundError` and the runner reported a missing `claude` CLI. `reasoning` is 0 on the mode because the CLI exposes no thinking-budget flag, which is **not** a claim that the model does not think: a trivial probe the same day returned 100 thinking tokens, so whatever Claude Code decides to do is inside what this arm measures, and the cell is a measurement of *that invocation*, not of Haiku 4.5 in the abstract. Additive by construction: the six GPU cells, the five blocks and every plan already written are untouched, the hosted cell lives in a table of its own, and `tests/toolchain/test_campaign_frontier.py` asserts that no pre-existing block can see it. | The campaign's conclusions are about local models, and they are stated as ratios and curves with no scale on them: a reader has no way to tell whether 0.39 quality on the untracked arm is close to the ceiling of the task or far from it. A single hosted cell on the arm the report actually leads with supplies that scale at 280 rows and roughly two hours, and supplies it on the arm closest to a deployed situation — one item per invocation, judged by what it returns. Registered before any row of it has run, so the arm cannot be tuned to what it finds; and kept out of §9 so it cannot silently become evidence for a claim the design does not support — one cell is one cell, and the six local ones exist because one family measures the family and not SOL. |
| 2026-08-29 | **`no-halt` is restricted to fixtures that have a queue, and MAIN re-scored onto the restriction.** The mode fired whenever the expected sequence ended in an `ESCALATE` and the observed sequence disagreed at that position — a test that is vacuous when the expected sequence has length 1, which is every scoreable case of the per-item fixtures (§4.5). On `support-routing` it carried 57 labels: 55 were a model answering `ASSIGN` where the oracle said `ESCALATE`, and 2 emitted a second `BRANCH` line for an item that had only one — wrong answers and redundant trace, not queues that ran away. It also overwrote a verdict the payload comparison had already reached: 13 of the 57 returned no payload at all and were `no-output` until the sequence oracle relabelled them, so the mode was hiding a delivery failure behind a fidelity one. The guard is `len(expected_sequence) > 1`. Re-scored with `rescore.py` then `backfill_index_scores.py --refresh` over all 4,591 records: 57 rows change, every one of them on `support-routing`, becoming `wrong-value` 43, `no-output` 13, `partial-sequence` 1, and `no-halt` on that block goes 57 → 0. `support-intake` is untouched — all 458 of its `no-halt` labels sit on queues of six to eleven items — and no rate moves anywhere: intake's 19 passes and routing's 597 are exactly as they were. Four regression tests added, including the queue case as a guard against over-restricting. | The mode's definition is an arrest not taken, and no arrest can be missed inside a single item. Read as published, routing's 57 would have reported a halt problem on the fixture from which §4.5 deliberately removed the halt. Found while auditing degradation counts before rewriting the deliverables — which are frozen at `report/frozen/` until the data work closes, so that corrections like this one do not reach them one at a time. |
| 2026-08-27 | **REPLICATION opens (§8.3 step 5): the two per-item arms are rerun on the sealed half of the pool, decisive cells only.** Scope, declared before any run: blocks `routing-repl` and `routing-notrace-repl` — the same twenty frozen strata and world states as `routing`/`routing-notrace` (`build_requests.STRATA`, unchanged), the same seven renderings and two repetitions, the process documents byte-identical to the source arms (frontmatter names included: no prompt names the arm) — with the items drawn from the REPLICATION split, seed 20260827, and the grid restricted to the four decisive cells (`campaign.DECISIVE_CELLS`: ministral-8b, qwen3.5-9b-think, gemma-4-12b, qwen3.5-9b-nothink). granite and phi4-mini support no headline claim and are not rerun. One divergence from §4.3 as written is owned here: "300 items drawn, then manually verified" was implemented lazily — verification covered only the items a model actually consumed (91 of MAIN; the sheet's own header said REPLICATION "needs no verified ground truth yet"), so the REPLICATION half is unverified at opening. The gap is closed by a two-stage procedure that keeps selection prior to judgment: `select_repl_candidates.py` picks, with the declared seed, need+2 candidates per (product, intent) pair the strata consume (39 items); they are verified manually on the same sheet as MAIN's (`build_verification_html.py --repl`), blind to any model behaviour — no model has ever read a REPLICATION item; `apply_pool_corrections.py` lands the judgments; `build_requests.py --repl` then draws among verified, non-tolerant survivors only. What counts as "holds", stated in advance: (a) ministral-8b remains the best of the four on the tracked arm; (b) the untracked arm scores higher quality than the tracked one on the pooled four cells, with the gain concentrated in the three trace-emitting modes; (c) quality as a function of L stays flat — no monotone rise to a threshold. Movement in any of these is reported as such, per §8.3. | The campaign's conclusions are written (report/, 2026-08-26) and §8.3's binding order is therefore satisfied: draw, verify, run MAIN, write the conclusion, only then open the seal. Every choice that could tune the replication to the data is frozen the same way the originals were — strata, worlds, documents and oracle are the source arms' own artefacts, and the only new degrees of freedom (which items, which cells) are fixed by a declared seed and by which claims the report actually makes. Cost honesty: four cells, two arms, 2,240 rows, ≈20 h of GPU, dominated by qwen-think. |
| 2026-08-25 | **The graded quality of §10 exists: `quality_rate`, the fraction of `expected_output`'s leaf fields the payload reproduces exactly.** Dicts recurse by key, lists by position, every scalar (null included) is one leaf; equality is strict, the binary verdict's own standard, and `None` marks the absence of a measurement — a run with no payload — rather than a zero (the comprehension lesson, 2026-08-23). Computed in `checker._field_rate()`, stored as `quality.rate`, indexed as `quality_rate`; documented in `doc/measures.md`, both halves. Re-derived at zero GPU for every record: `rescore.py` then `backfill_index_scores.py --refresh` on `tests/results-main` and `tests/results-smoke`; `tests/results` untouched, closed records. Applied to the tracking A/B it sharpens the mechanism into two distinct components. **Delivery:** with the trace, qwen3.5-9b-nothink returned a payload in 72% of runs; without, in 100% — the whole of its +0.121 arrives there — and think moves 72% → 82% (the budget relief). **Correctness given delivery:** flat everywhere (mean `quality_rate` over returned payloads 0.761 vs 0.757) except gemma-4-12b, whose delivered payloads pass 35% → 45% on presence ~1.00 in both arms. The trace costs the answer's *arrival* on the qwen modes and the answer's *last field* on gemma; it does not degrade delivered payloads field-by-field anywhere. | §10 recorded the prerequisite as worth having before the A/B; the A/B ran first because the binary effect (+3.6 points, z≈2.1) did not need the extra power, and the graded measure was re-derivable from the raws after the fact — which this entry is. The refinement matters for the paper's claim: "the tracking competes with the primary task" could have meant worse answers, and it turns out to mean *fewer* answers — a budget-and-attention effect on delivery, not a corruption of the work. A measure that can distinguish those two readings retroactively, on data already collected, at zero GPU, is the §12 2026-08-23 principle again: the payload is the observation, everything derived from it can be re-derived. |
| 2026-08-25 | **The untracked arm ran, and the §10 prediction holds: the arm without the trace scores higher quality — +3.6 points overall (0.356 → 0.392 on 1,676 vs 1,676 done rows, z≈2.1), and the item closes.** The block completed as 1,673 done + 4 `skipped-window` (granite's window, the same four requests as the tracked arm) + 3 timeouts, retried the same day to 1,676 done — the two arms end at identical N. The effect is not uniform and its structure is the finding: the three modes that emitted the trace gain (qwen3.5-9b-nothink +0.121, gemma-4-12b +0.104, qwen3.5-9b-think +0.082) and the three that already ignored it do not (granite −0.014, phi4-mini −0.025, ministral-8b −0.054, none beyond noise); by rendering, the gain concentrates where the trace was actually being emitted — +0.09 on both prose renderings, which traced at 0.71–0.75 in the tracked arm, and ~0.00 on L0–L2, where tracing was rare. On qwen3.5-9b-think the removal also relieves the budget: runs burning the full reasoning budget fall 79 → 50 of 280, mean output 5,889 → 4,627 tokens, mean wall 117 → 93 s, while quality rises 0.557 → 0.639 — better, shorter, faster on the same rows. The §10 prerequisite (field-level quality) was not needed at this effect size and remains open as an analysis refinement, re-derivable from the raws. | The cost of the tracking is paid where the tracking is obeyed, and only there — the same conclusion arrives independently from the per-mode split and the per-rendering split, which is what elevates it from a difference to a mechanism. The self-selection objection that voided the observational comparison (§12 2026-08-24) does not reach this design: the instruction was removed, not waited for, so the treated arm differs in the prompt itself. Consequence for the campaign's headline question: the trace is the bench's instrument, not SOL's requirement — deployed SOL processes that read the outcome and skip the scaffolding can expect the notation to cost less than MAIN measured, and the per-item, outcome-scored shape of this arm is the closest the campaign has come to the deployed situation. |
| 2026-08-25 | **The untracked arm of §10 is built: `w2-branching/support-routing-notrace`, campaign block `routing-notrace`, 1680 rows planned, not yet run.** The fixture is `support-routing` with exactly four differences: the frontmatter `name`; the `description`'s closing sentence about EVAL/BRANCH scoreability, removed with nothing in its place; the eight `Emit verbatim` steps; and the build-result sentence disclaiming the trace lines. `catalog.json`, `items-manifest.json`, `reference.py` and `inputs/` are byte-for-byte copies; `expectations.json` differs only in its `fixture` field, retaining `expected_sequence` and `comprehension_ground_truth` that no run of this arm can meet. All seven renderings carry the treatment: L0–L4 derive from the document at run time, `prose-mechanical` was regenerated by `build_prose_mechanical.py`, `prose-generated` by one pass of Claude Opus 5 under the frozen prompt of §8.1 item 6 — verified to differ from its SOL source in the process section and nowhere else. Same grid as `routing` (20 × 2 × 7 × 6), same results root and index. Endpoint: `quality` alone, per the §10 design; the §10 prerequisite (field-level quality over the returned object) remains open and is re-derivable from the raws after the fact, so it does not gate the run. Prediction already registered in §10 stands: if the tracking competes, this arm scores HIGHER quality. | The routing block completed 2026-08-25 (1676 done) and its reading sharpened the question rather than answering it: trace emission collapsed by rendering and by model (qwen3.5-9b-nothink 0.96 → 0.50, all of the loss on L0–L4) while quality sat in a band the trace metrics do not predict, and the within-rendering traced/untraced comparison remains self-selected — a run that omits the trace is not a run relieved of it, because the instruction was in its prompt all the same. The instruction has to be removed, not waited for (§12 2026-08-24), and this build is that removal. It is also a deliberate step of the method's arc: MAIN instrumented the execution and read comprehension off the trace; this arm moves to the deployed situation, where a process is judged by what it returns — comprehension read through the outcome, which is how a real user of the process would read it. |
| 2026-08-24 | **New degradation mode `halt-not-taken`, and MAIN and the smoke re-scored onto it.** It fires when the returned payload names the *correct* `halted_at` and returns more items than expected: the model located the stopping point, reported it, and handed back the whole queue anyway. Read off the payload rather than the trace, and checked before `no-halt`, of which it is a strictly more informative sub-case. 82 of MAIN's 1,236 rows — 46 `qwen3.5-9b-nothink`, 14 `granite-4.1-8b`, 10 `gemma-4-12b`, 8 `ministral-8b`, 4 `qwen3.5-9b-think`; `no-halt` falls from 518 to 458, the remaining 22 arriving from labels the trace could not reach. Documented in `doc/measures.md`; the analysis it records is §9.1. No inference re-run: `rescore.py` then `backfill_index_scores.py --refresh` on `tests/results-main` and `tests/results-smoke`, zero GPU. `tests/results` is left alone — it holds the pilot and the KV-quantisation study, whose write-ups are closed records. | The label separates a misread task from an ordinary mistake, and the two were being counted together. `no-halt` says the model ran past the exit; it does not distinguish a model that never found it from one that found it, said so, and returned a payload contradicting its own `halted_at`. The second is the more interesting failure and the harder to see, and reading it off the trace made it nearly invisible on models that skip the scaffolding: `granite-4.1-8b` shows 5 `no-halt` labels in 189 runs and 14 `halt-not-taken`. Naming it is the whole point — the effect was measured on 2026-08-24 and would otherwise have lived only in that analysis, with every future run re-collapsing it into `no-halt`. |
| 2026-08-23 | **A second fixture, `w2-branching/support-routing`, added to the campaign (§4.5), composed and sized in §7.6.** One item per invocation instead of a queue of fifteen, with the world state — remaining hours and the state of three teams — injected by the oracle rather than chained from the model's own previous answer. It adds a routing decision expressed as set membership (each team accepts a fixed set of products and backs up another) with categorical team load (`OPEN` / `LIMITED` / `CLOSED`, where `LIMITED` takes `BUG` only), a fifth action `UNASSIGNED` for the product no team accepts, and no new arithmetic. §8.1 gains frozen artefact 8; §9 gains outcome 8; §10 replaces the single-fixture threat with the fixture/delivery confound. Results land in MAIN's `index.jsonl` — `fixture_id` already separates them and the dashboard already filters by it — under their own plan file, `campaign-plan-routing.json`. The block runs after MAIN, which is a GPU constraint and not a data one. | The batched shape is not the deployed one: a process of this kind is invoked once per message, with no history and no retrieval, and that is the case the campaign claims to speak about. Per-item delivery also buys independent trials where the queue bought one, which is what makes a per-item diagnosis possible at all — MAIN can report that a queue scored 0.6 and not which item cost it. On the algorithm: the second decision axis is set membership rather than a load counter because local models fail arithmetic fixtures on the arithmetic (§4.1), so routing through a numeric threshold would measure the wrong faculty; `LIMITED` restores, without an accumulator, the property that made `support-intake` non-degenerate — the decision cannot be reached from the item alone. Stateful delivery, one conversation of fifteen turns, was considered and rejected: it measures a model's endurance under a growing window, which is not a question about SOL, and a real deployment would answer it with retrieval rather than with a context left to fill. Nothing in MAIN is touched — separate fixture directory, separate plan file, MAIN's own frozen artefacts unmodified. |
| 2026-08-22 | §5.4: three language variants reduced to two — `prose-mechanical`, rendered from the SOL document by the deterministic renderer of the SOL skill, and `prose-generated`, rendered from it by a model in one pass from a frozen prompt. `prose-native`, the hand-written analyst rendering, is withdrawn. §8.1 item 6 accordingly freezes the generation prompt (`tests/fixtures/PROSE-VARIANT-PROMPT.md`) together with the documents rendered with it. The five L cells and the two prose cells are recorded on one selector with seven values, not as a grid. | A hand-written prompt does not correspond to how prompts are produced: the analyst confirms the algorithm and a model writes the prompt downstream of that confirmation, so the hand-written rendering is the artificial object rather than the missing baseline (§5.4). It also admits no quality criterion, which makes any result it produces uninterpretable in both directions. On the encoding: §5.1 already applies to `sol` only and §5.4 already does not apply to `sol`, so the two factors never crossed — a flat list of seven cells is the faithful reading of the protocol as written, not a simplification imposed on it. Amended before MAIN's first run, therefore independent of MAIN's data. |
| 2026-08-22 | Coherence audit of the seven fixtures, before MAIN's first run. Four corrections reach frozen artefacts (§8.1 items 6 and 7). (a) `task-router` read `cat {{file content}}` — a placeholder with a space, naming a parameter its own `accepts` does not declare; corrected to `{{record_path}}`, in the RUN and in the guard condition that repeated the name. (b) Ten contract constraints across four fixtures used `type:`, a key `sol-schema.json` rejects (`contractField` is `additionalProperties: false`); mapped to `number: true` or dropped, no contract redesigned. (c) `task-router` and `support-intake` required trace lines and then said 'no other output'; the constraint is now scoped to the returned object, in the SOL document, so both prose renderings inherit the same sentence and no arm is more explicit than another. (d) The sequence oracle read only the keyed label shape, so `polarity-flip`, whose labels are bare words, observed an empty sequence and scored `fail` on a perfect run; `checker._observed_sequence` now reads both shapes. Also: `min_environment` corrected from E1 to E0 on the two fixtures that carry a `## File content` section and run at E0, and the `prose-mechanical` generator now re-points the sentence that named a SOL script no longer present. | A defect in the prompt is not a result about the model, and a bench that cannot record a success is not measuring anything: (d) would have entered `polarity-flip`'s every run as a failure of the model. Each correction restores agreement between a document and something it cites — its own `accepts`, the schema in its frontmatter, the trace its oracle reads. None changes what any fixture asks a model to do. MAIN had not run, so no result is affected; the 53 historical `task-router` runs scored fidelity `pass` 53 times, which is why (c) had never surfaced. |
| 2026-08-23 | MAIN launched, aborted after 9 rows, apparatus corrected, relaunched from an empty index. Four of the first five rows returned `raw: ""` after exactly 13,024 output tokens — `max(DEFAULT_MAX_TOKENS, reasoning_budget + 1024)` for `llama-qwen3.5-9b-think`, i.e. truncation at the ceiling — and were scored `no-output`. `_post_messages_openai` read only `message.content`, while llama-server returns the thinking block in `reasoning_content` when the chat template separates it, so a model that had deliberated for 13,000 tokens and one that produced nothing were the same record on disk. Two fields added: `Output.reasoning` and `Execution.stop_reason`. Neither is scored — the answer is still `content`, because the SOL contract asks for the payload and deliberating is not delivering. The 9 rows were discarded rather than kept: they were produced by the pre-fix reader. | The distinction the reader could not make is the one the campaign exists to make. `no-output` names a model that produced nothing; on 210 `qwen-think` rows this would have spent roughly fourteen hours recording that verdict without the evidence to support it, and the resulting cell would have carried an ambiguity into the analysis with no way to resolve it after the fact. Caught at row 9, the cost of correcting it was nine rows; caught at row 900 it would have been the mode. Nothing about what any fixture asks a model to do changed, and nothing about how an answer is scored changed. |
| 2026-08-23 | **`prose-generated` withdrawn from MAIN and regenerated; the generation prompt of §8.1 item 6 revised.** The `support-intake` prose-generated document required per-item `EVAL:`/`BRANCH:` lines throughout and closed with *“Output that JSON object and nothing else: no commentary before it, none after it”*. Every model obeyed the closing sentence: 61 of the 69 MAIN rows on that rendering returned the JSON object alone, `stop_reason` `stop`, not one trace line. The contradiction is the one corrected on 2026-08-22 as (c), but the correction was made in the SOL documents, which `prose-mechanical` inherits through its renderer and `prose-generated` does not — and the instruction did not come from the source at all: `PROSE-VARIANT-PROMPT.md` itself required the generator to carry across *“the instruction to return it alone with nothing around it”*, one bullet below the bullet requiring every verbatim line to survive. Regenerating against the corrected SOL would have reproduced it. The prompt is therefore revised, and with it, in one pass so the documents are regenerated once: the return instruction is scoped to the object; a governing sentence states that the style prohibitions never reach a verbatim line or anything the source states, which closes the same collision in *“its way of labelling branches”* (the verbatim lines carry `action=ASSIGN`, `branch-else`, and variable names inside placeholders) and in *“no advice on how to recognise anything”* (`classify-request` states in the source how the product is to be judged). All seven prose-generated documents are invalidated by the prompt change and regenerated, per the rule the prompt states. MAIN's 69 prose-generated rows are discarded and the plan rows returned to `pending`. Also corrected here: `prose-derived` and `prose-native`, both retired on 2026-08-22, survived in §5.2 and in secondary outcome 3 of the analysis plan, where the comparison named neither arm that exists. | A defect in the prompt is not a result about the model — the same reason given for the 2026-08-22 audit, and this is the third place that one contradiction lived. The rendering was not measuring what the other six measure: it forbade the trace its own oracle reads, so its runs were unscoreable for conditional fidelity by construction, and a comparison of prose against SOL drawn from them would have compared a document that suppresses the trace with six that do not. Six of the prompt's seven recorded defects are collisions between two of its own rules rather than errors in either, which is why the seventh revision replaces an exception per rule with one sentence saying where the prohibitions stop. |
| 2026-08-23 | **Comprehension is `not_checkable`, not `0.0`, when a run emitted no `EVAL:` line at all.** `checker._check_comprehension` read the classifications off the trace and divided by the number of ground-truth items, so a run with no trace scored zero — the same number as a run that named every product and missed every one. 215 of MAIN's 493 rows carried that zero. The 493 existing runs were re-scored from their records with `tests/scripts/rescore.py`; no inference was re-run and no record was modified. A partial trace is unchanged: five `EVAL` lines out of fifteen is an observation, and the ten missing are the model's doing. | The distinction is the one the campaign is about. Read off the payload those runs did return, the same 215 sit at 0.59 (granite-4.1-8b), 0.70 (Ministral-3-8B) and 0.81 (Qwen3.5-9B nothink) — two of the three above their own traced average, so the zeros were not a low score but the absence of a measurement written where a result goes. granite in particular read as a model that understands nothing, when what it does is answer with a markdown table instead of the trace lines. The payload is deliberately NOT adopted as a second source: the fixture defines comprehension as what the trace says, and changing that is a decision to be specified, not improvised inside a correction. |
| 2026-08-22 | §5.3 brought up to date with the cell set actually in use: **five cells, five families** (Qwen3.5-9B two modes, Ministral-3-8B, granite-4.1-8b, gemma-4-12b, Phi-4-mini), and the blanket exclusion of the 12B class narrowed to dense 12B at heavier quantisations. Contexts raised to each cell's measured VRAM ceiling (Qwen 32,768→51,200; Ministral 31,744→38,912; gemma 31,744→43,008; Phi-4-mini 32,768→43,008; granite unchanged at 28,672, having none). What still does not fit is recorded as `skipped-window`, distinct from an execution error. | The cell set changed on 2026-08-19 when the exclusion of Ministral and granite was traced to the 16-bit KV cache rather than to the models, and gemma-4-12b was admitted because its QAT quantisation fits; §5.3 was never updated and still described three cells. On the contexts: the stratified smoke of 2026-08-22 exposed the window as a live constraint on MAIN. At the old contexts 36 of 900 rows would have been refused outright (prompt larger than the window) and a further 54 would have run with less generation room than the declared cap — 30 of those on Qwen-thinking, whose 12,000-token reasoning budget is reserved before the prompt is read. Raising each context to its VRAM ceiling leaves 18 rows out of 900 that cannot be run at all, counted exactly with each cell's tokenizer, at no cost in throughput; that residue is a property of an 8 GB card. Amended before MAIN's first run, therefore independent of MAIN's data. |
| 2026-08-22 | Adaptive laddering on L withdrawn in favour of the **full L0–L4 grid**, no early stop (§7.3). Consequently: P2a and the prose variants run at the level chosen post hoc from the P1 curve (§7.4), and MAIN's P1 block is sized at 900 runs, 13–18 h (§7.5). The acceptability threshold (90%) and the acceptance criterion (prefill > 1000 t/s) are unchanged. | The adaptive design assumes fidelity is monotone increasing in L, i.e. that a threshold exists — which is the conclusion the campaign must establish, not its premise. The 2026-08-18 decision (the L scale competes with reasoning for the window: at L4 the prompt is 22,713–27,179 tokens depending on the tokenizer) describes the mechanism that breaks monotonicity, so the curve may be a bell rather than a step; under the adaptive design that is invisible by construction, because levels above the threshold are never run. Amended before MAIN's first run, therefore independent of MAIN's data. |
| 2026-08-19 | Two-metric sequence oracle: `sequence_rate` (denominator `max(len(expected), len(observed))`) plus `redundancy_ratio`, replacing the single-metric oracle. | The one-metric oracle rewarded runs that ran away or never halted with an inflated `sequence_rate`, because the comparison window was capped at `len(expected)`. Corrected before MAIN, so independent of MAIN's data. |

---

## 13. Open items

- Exact model builds and quantisations available at setup time.
- The final structural acceptance criterion for queues (to be frozen before generation).
- Whether to request explicit permission from the dataset authors before or after the first runs.
- Whether a bridge block — `support-intake` delivered per item, its state injected the same way
  — is run to separate the delivery shape from the process content (§10).
- ~~Whether the tracking requirement itself competes with the primary task.~~ **Resolved
  2026-08-25: it does, where it is obeyed** — the untracked arm scores +3.6 points of quality
  overall, the gain concentrated in the modes and renderings that actually emitted the trace
  (§12, 2026-08-25). The `EVAL`/`BRANCH`
  lines are a secondary objective imposed on top of the work: the fixture asks for them so that
  comprehension and conditional fidelity can be scored separately, and nothing about the process
  needs them. The hypothesis was that carrying them costs the returned answer — that a model asked
  only to route the request would route it right more often. Recorded 2026-08-24 (Gianni); built
  and run 2026-08-25 as `w2-branching/support-routing-notrace`, block `routing-notrace`. The
  design record below stands as written before the run.
  - **Design.** A clone of `support-routing`, identical in every respect except that the
    intermediate `Emit verbatim` steps are gone. The manipulation must be applied to **all seven
    renderings, the two prose documents included** — otherwise the arms differ by rendering rather
    than by treatment, which is the confound the clone exists to avoid. The prose-generated
    document therefore needs its own model pass under the §8.1 item 6 procedure, from the frozen
    prompt, which is the one part of this that is not free.
  - **Why a clone rather than a new fixture.** A different process would confound content with the
    manipulation. What isolates the treatment is the same requests, the same world states, the same
    oracle, minus the emits. The residual confound to declare is that removing those steps shortens
    every document; that is part of the treatment — asking for the trace costs tokens and attention
    — not noise to be removed.
  - **Why on `support-routing` and not `support-intake`.** Quality cannot pass on the batched
    fixture by design (`doc/measures.md`, and MAIN passes 1.5%), so both arms would sit on the
    floor and the comparison would be between two distributions of failure — the flaw that made the
    first KV A/B uninformative (`doc/experiment-kv-quantization.md` §2). The 2026-08-24 pre-flight
    puts routing near 30%, which is the headroom this test needs.
  - **What it can measure.** Only `quality`. With no trace by construction, comprehension,
    `sequence_rate` and `conditional_rate` are unmeasurable in the treated arm — which is
    acceptable, since quality is the outcome the hypothesis is about, but it means the experiment
    reports one number and not four.
  - **Prerequisite: a continuous quality.** `quality` is binary, and this bench has already
    established what a binary oracle costs in power (`experiment-kv-quantization.md` §5). Against
    p≈0.30, separating 30% from 40% needs roughly 350 runs per arm. Field-level agreement over the
    returned object (`status`, `id`, `product`, `intent`, `hours`, `team`, `action`,
    `remaining_hours`) would grade what is now pass/fail, costs no GPU, and is re-derivable from
    the raws already on disk. Worth having before this A/B rather than because of it.
  - **Prediction, registered in advance.** If the tracking competes, the untracked arm scores
    HIGHER quality.
  - **Why the question cannot be answered by observation, which is the argument for running it.**
    The obvious cheap test — compare, inside the existing routing data, runs that traced against
    runs that did not — is not merely confounded but empty where it matters. In the 2026-08-24
    pre-flight the models with a large untraced cell are the two on the floor (phi4-mini 0 traced
    of 35, quality 6%; qwen3.5-9b-nothink 17 untraced, 9%): a weak model does neither thing, so its
    untraced runs measure incapacity, not relief from a burden. The models that can do the task
    barely vary — gemma-4-12b traced 35 of 35, ministral-8b 31 of 35 — and what does not vary
    cannot be compared. The single natural experiment in the set is granite-4.1-8b, decent at 34%
    and split 17/18, where the difference is nil (6 of 18 untraced against 6 of 17 traced) on a
    self-selected n=35. The instruction has to be removed rather than waited for, which is what the
    clone is.
  - Noted while looking: qwen3.5-9b-think traced 2 runs of 16 on this fixture while scoring 38%
    quality — the one mode that ever passed on MAIN does the per-item work and skips the
    scaffolding.
- ~~Whether a second W2 fixture of a different shape is added before publication.~~ Resolved
  2026-08-23: `w2-branching/support-routing`, §4.5.
