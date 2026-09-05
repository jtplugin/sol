# The frontier reference cell: what the same documents are worth to a hosted model

**Run:** 2026-08-31, interactive session, at Gianni's request.
**Block:** `routing-notrace-haiku` — 280 rows, all `done`.
**Data:** `tests/results-main/`, `mode = claude-code-haiku`.
**Protocol:** registered in [`experiment-minimum-context.md`](experiment-minimum-context.md) §5.3
and §12 **before any row of it ran**.
**Depends on:** the untracked arm (§10, built 2026-08-25) whose documents it reuses unchanged.

---

## 1. The question, and why it needed answering

The campaign measures local models: five families between 3.8B and 12B, on one 8 GB card. Its
conclusions are ratios — quality 0.392 pooled on the untracked per-item arm, a fidelity curve flat
in `L`, a per-cell ranking — and ratios have no scale on them. A reader looking at 0.392 has no way
to tell whether the task is nearly saturated and the local models are close behind, or whether the
task is comfortably solvable and they are far from it. The two readings support opposite
conclusions about SOL, and nothing in the data separates them.

One hosted cell separates them, and it does not need to be a sixth family to do it. It needs to run
**the same documents, at the same coordinates, through the same oracle**, and to be read as a scale
rather than as a result.

## 2. The design: what was held fixed, and what was not

The arm is `w2-branching/support-routing-notrace` — the untracked per-item fixture, the one that
delivers one support request per invocation and is judged by what it returns — with nothing changed:

| | held fixed |
|---|---|
| items | the same twenty stratified requests, same `items-manifest.json` |
| renderings | the same seven, built by the same `api_executor._build_prompt_e0` |
| repetitions | 2, as in `routing-notrace` |
| context | E0, no tools, the input pre-injected |
| oracle | the same `expectations.json`, the same `checker.check` |
| results | the same root and the same `index.jsonl` |

What changed is the runner and the model: `claude -p --model claude-haiku-4-5` instead of an HTTP
call to a local `llama-server`. `tests/toolchain/test_campaign_frontier.py` asserts the equality
above where it can fail — same `fixture_id`, same inputs, same reps, same renderings — and asserts
that no pre-existing block can see the hosted cell.

### 2.1 Three invocation flags, and why each is load-bearing

Driving a coding agent as if it were a bare model is not automatic. Three flags do the work, and
each of them corresponds to a way the measurement would otherwise have been wrong:

- **`--safe-mode`.** Without it the CLI loads the host machine's `~/.claude/CLAUDE.md`, its
  `SessionStart` hooks and its plugins. On the machine that ran this arm, that means every one of
  the 280 rows would have opened with a plugin banner and a standing instruction to answer in
  Italian, reaching the model *before* the fixture did. The runs would have measured the operator's
  shell.
- **`--system-prompt`, not `--append-system-prompt`.** The fixture's frontmatter carries a system
  prompt, and the API arm sends it as `system`. Appending it would have layered the fixture's
  persona *on top of* Claude Code's coding-agent prompt, which is a different prompt from the one
  every other cell received.
- **`--tools ""`.** E0. The fixture's `## File content` section is the input; a model that could
  read the staged file would be running a different context than the cells it is compared against.

### 2.2 What the cell does *not* control

`reasoning` is 0 on the mode because the CLI exposes no thinking-budget flag — **not** because the
model does not think. A trivial probe the same day came back with 100 thinking tokens, and the arm's
mean output is 2,215 tokens against a payload that fits in 80. Whatever Claude Code decides to do
about thinking is inside what this cell measures.

That is the honest reading of the whole arm: it is a measurement of **that invocation** — Haiku 4.5
as this project actually invokes a model, every day — and not of Haiku 4.5 in the abstract. It is
also the reason the arm is worth having: the deployed situation is what the per-item fixture was
built to approximate.

## 3. The result

280 rows, all `done`. No error, no timeout, no row refused, no row skipped.

| | binary quality | graded `quality_rate` |
|---|---|---|
| **claude-code-haiku** | **221/280 = 0.789** | **0.908** (n=280) |
| six local cells, pooled | 657/1676 = 0.392 | 0.757 (n=1602) |

Per local cell, for the ranking the campaign already reports:

| cell | quality | `quality_rate` |
|---|---|---|
| llama-qwen3.5-9b-think | 0.639 | 0.890 |
| llama-ministral-8b | 0.557 | 0.842 |
| llama-gemma-4-12b | 0.446 | 0.794 |
| llama-granite-4.1-8b | 0.380 | 0.817 |
| llama-qwen3.5-9b-nothink | 0.264 | 0.728 |
| llama-phi4-mini | 0.064 | 0.473 |

The hosted cell is 15 points above the best local cell and 40 above the pool. **The task is not
saturated at 0.392**: a small hosted model solves four requests in five on documents that the local
grid solves two in five. That is the scale the campaign was missing, and it is the whole deliverable
of this arm.

The graded column says something the binary one hides. The `n` differs: 280 against 1602 of 1676,
because a row with no payload has no rate to compute. The hosted cell delivered a parseable object
**every single time**; the local cells failed to deliver on 74 rows.

### 3.1 The curve on `L` is flat, at a different level

| rendering | L0 | L1 | L2 | L3 | L4 | prose-mech | prose-gen |
|---|---|---|---|---|---|---|---|
| quality | 0.800 | 0.775 | 0.800 | 0.775 | 0.800 | 0.750 | 0.825 |

Five levels of collateral context — the minimal instruction, then a glossary, then the whole of
`spec/sol-0.6.md`, then every file in `examples/` — move this model by two and a half points, in no
particular direction. The spread across all seven renderings is 0.075, and prose-generated is the
top of it.

This is the campaign's own finding (§8.3 (c): "quality as a function of L stays flat — no monotone
rise to a threshold") reproduced on a model four to thirty times larger than the cells it was
established on. Explaining SOL to the reader does not help the reader execute SOL. Neither does
replacing the JSON with prose.

### 3.2 The failures are of one kind, and the local ones are not

| degradation mode | haiku | six local cells |
|---|---|---|
| `none` | 221 | 657 |
| `wrong-value` | 59 | 945 |
| `no-output` | 0 | 68 |
| `refused` | 0 | 6 |
| `timeout` | 0 | 3 |

Nothing but wrong answers. No missing payload, no payload the parser could not read, no refusal, no
run that never came back. Part of the local grid's distance from the ceiling is not *judgement* at
all — it is **delivery**: 77 rows in which no answer arrived to be judged. The hosted cell executes
the process every time and sometimes routes it wrong.

## 4. Where the 59 failures actually sit

They are not spread over the twenty requests. Eight requests account for all of them, and three
account for 42:

| request | failures / 14 | expected action |
|---|---|---|
| r02 | 14/14 | ASSIGN |
| r10 | 14/14 | ASSIGN |
| r19 | 14/14 | DEFER |
| r15 | 9/14 | UNASSIGNED |
| r11 | 5/14 | DEFER |
| r09, r14, r16 | 1/14 each | — |

Three requests are read the same wrong way **every time**: across all seven renderings, both
repetitions, fourteen independent invocations each. That is not stochastic noise, and no amount of
collateral context touches it.

Reading the payloads says what the disagreement is:

- **r02** — expected `P3 / QUESTION / 1h / T2 / ASSIGN`; returned `P3 / BUG / 2h / T2 / ASSIGN`,
  fourteen times out of fourteen. Product right, team right, action right. **Intent** classified
  differently, and `hours` and `remaining_hours` follow from it.
- **r10** — expected `P3 / QUESTION / 1h / T1 / ASSIGN`; returned `P3 / FEATURE / 4h / T1 / ASSIGN`,
  fourteen out of fourteen. Same shape.
- **r19** — the budget-exhausted world (`remaining_hours: 0`), expected `DEFER`. The intent error
  cascades: `NEEDS_INFO` nine times, `ESCALATE` five, never reaching the branch the world state
  selects.
- **r15** — `P4`, the product no team accepts, whose only correct answer is `UNASSIGNED`. Returned
  `P5 / T3 / ASSIGN` nine times, correct five.

The graded measure confirms the shape. Among the 59 failing rows the mean `quality_rate` is 0.561,
and the distribution has three values and no others: **39 rows at 0.625** — five of eight leaf
fields correct, i.e. one classification error propagating into `intent`, `hours` and
`remaining_hours` — 10 at 0.5, 10 at 0.375. There is no row in which the model produced a
structurally different answer; the disagreement is always about *what the request is*, and the
routing follows correctly from whatever it decided.

**This is a statement about the residual, not a challenge to the oracle.** The ground truth was
verified by hand (§4.3, §8.3) and is the same ground truth every local cell was scored against; the
comparison in §3 is unaffected either way. What the concentration says is that the last fifth of
this task, for this model, is semantic classification of a support request — not control flow, not
notation, not context.

## 5. What this arm does not say

- **It is not a sixth family.** One cell measures one cell. The campaign runs five local families
  precisely because one family measures the family and not SOL, and that argument does not stop
  applying because the cell is hosted.
- **It is outside §9.** No outcome of the analysis plan is computed over it, and no claim about
  local models depends on it. Kept out deliberately, so it cannot quietly become evidence for
  something the design does not support.
- **It is not a model benchmark.** See §2.2: the invocation is part of the measurement.
- **It is one fixture.** The untracked per-item arm only. Nothing here speaks about the batched
  `support-intake` shape, or about the tracked arm and its `EVAL:`/`BRANCH:` lines — an untracked
  arm has no trace by construction, so `fidelity`, `comprehension` and `sequence` are structurally
  unobservable here, exactly as they are for the local cells on this fixture.

## 6. Cost

| | |
|---|---|
| prompt tokens | 1,963,496 |
| output tokens | 612,591 |
| wall clock | 119 min (mean 25.5 s/row, max 78 s) |
| list-price equivalent | $7.21, as reported by the CLI over the 280 invocations |

The bill went to a Claude Code subscription, not to API credit: the two are separate billing
systems, and a `runner_type: claude-code` mode needs no key in `tests/env.json` for exactly that
reason. The figure is recorded in the run records and **not** in `index.jsonl` — it is an estimate
of a spend, not a measurement, and the index is the analysis surface.

For scale: the six local cells spend roughly twenty GPU-hours on the same 1,676-row arm.

## 7. Two defects the arm surfaced, both fixed

Neither is about SOL. Both were in the bench, and both are the kind that reports the wrong cause.

**The prompt could not travel in `argv`.** Windows caps a command line at 32,767 characters; this
fixture's prompt is 38,475 at L3 and 45,469 at L4. Past the cap `CreateProcess` raises
`ERROR_FILENAME_EXCED_RANGE`, which Python surfaces as `FileNotFoundError` — the same exception a
missing executable raises. The first smoke ran L1 and then died claiming the `claude` CLI was not
installed. Two of the seven renderings were unrunnable, and the bench said the wrong thing about
why. The prompt now goes on stdin, in `campaign.py` and in `executor.py` alike — the latter had the
same trap and stayed under the cap only because it never builds anything but L1.

**`quality_rate` never reached the index from the writer.** The graded measure was introduced on
2026-08-25 and back-filled onto every existing record by `backfill_index_scores.py`; but
`runner._append_index` was never taught to emit it, so every run since has written rows with the
column blank until somebody remembered to backfill. Noticed here, on 280 fresh rows that had it in
their score files and not in the index. The writer now emits it, a regression test holds it, and
this arm's rows were back-filled — which is why §3 can quote 0.908.

A third, smaller one: `tokens_in` was read from `usage.input_tokens` alone, and the CLI caches the
prompt. Measured on a 5,355-token prompt: `input_tokens` 9, `cache_creation_input_tokens` 5,346.
Reading the first field alone would have entered a five-thousand-token prompt in the dataset as a
nine-token one. It now sums the three prompt counters.

## 8. Reproducing it

```
python tests/runner/campaign.py smoke --block routing-notrace-haiku --plan   # 35 stratified rows
python tests/runner/campaign.py smoke --block routing-notrace-haiku --run
python tests/runner/campaign.py plan  --block routing-notrace-haiku          # 280 rows
python tests/runner/campaign.py run   --block routing-notrace-haiku
```

Relaunching `run` *is* the resume: the plan is checkpointed after every single row and rows already
in `index.jsonl` are credited without re-running. The hosted cell starts no `llama-server` and runs
no acceptance probe — the probe measures prefill throughput off `/v1/chat/completions` and has
nothing to say about a model on somebody else's hardware.


---

## 9. The other two rungs — registered 2026-09-01, run 2026-09-02

The arm above is one cell, and §5 says so twice: it measures that invocation, on that model. It
establishes that the task is not saturated at 0.392, and it cannot say whether the distance it
measures is a property of the **tier** or a step the smallest hosted model already reaches. Two more
arms separate those, and they are registered here before either has run:

| | |
|---|---|
| blocks | `routing-notrace-sonnet`, `routing-notrace-opus` |
| cells | `claude-code-sonnet`, `claude-code-opus` (`tests/campaign-cells-frontier.json`) |
| models | `claude-sonnet-5`, `claude-opus-5` |
| rows | 280 each — the same 20 × 7 × 2 grid |
| held fixed | fixture, items, renderings, repetitions, oracle, results root, index, and the three flags of §2.1 |

The model id is the only coordinate that moves. The ladder is **haiku-4.5 / sonnet-5 / opus-5** and
not one generation's three tiers: there is no Haiku 5, so what these arms compare is the three tiers
as this project can invoke them today — which is the same reading §2.2 gives the first rung, the
deployed situation rather than the model in the abstract.

**The prediction, registered in advance.** §3.1 found the curve on `L` flat and §4 found the
residual concentrated on three requests read the same wrong way fourteen times out of fourteen —
a semantic classification disagreement, not control flow, not notation, not context. If that
residual is a property of the task, quality is roughly flat from Haiku to Opus and r02, r10 and r19
fail on the larger models too. If it is a property of model size, they resolve and the ladder rises.
The two readings say different things about what the campaign's ratios are measured against, and
nothing in the data so far separates them.

Same standing as the first rung, for the same reasons: outside §9 of
[`experiment-minimum-context.md`](experiment-minimum-context.md), no outcome computed over them, no
claim about local models depending on them, not a model benchmark.

### 9.1 Running them

```
python tests/runner/campaign.py plan --block routing-notrace-sonnet   # 280 rows
python tests/runner/campaign.py run  --block routing-notrace-sonnet
python tests/runner/campaign.py plan --block routing-notrace-opus
python tests/runner/campaign.py run  --block routing-notrace-opus
```

Both plans were built on 2026-09-01 and one row of each executed the same evening as an environment
preflight — the CLI on PATH, the model id, the record and index writers, the oracle — both `done`,
both `quality=pass`. The remaining 279 of each run unattended from 02:00 on 2026-09-02, sequentially,
one arm after the other in a single process.

### 9.2 One thing the bench gained for the unattended run

An `error` row is never retried by the resume: `_reconcile_with_index` turns `pending` into `done`
and nothing else, so a failure stands until the plan is rebuilt. On a local cell that is academic —
llama-server either serves or fails its acceptance probe. On a hosted cell it is not: a rate limit,
an expired session or an outage fails every row it touches, in seconds each, and 280 rows can be
spent in minutes on a pause that would have cleared by itself.

`campaign._note_row_outcome` now stops the whole run after **eight consecutive rows that did not
complete**, saving the plan and exiting non-zero with the recovery in the message. `skipped-window`
is not counted either way: it is the bench declining to spend a run it measured as unrunnable, a
property of the prompt rather than of the backend. Recovery loses nothing:

```
python tests/runner/campaign.py plan --block <block> --force   # re-credits every row the index proves
python tests/runner/campaign.py run  --block <block>           # only the failed ones were pending
```

It did not fire. Both arms closed 280/280 `done`, exit 0.

### 9.3 The result: the ladder flattens one rung above Haiku

| | binary quality | graded `quality_rate` | n |
|---|---|---|---|
| **claude-code-opus** (Opus 5) | **0.836** | 0.931 | 280 |
| **claude-code-sonnet** (Sonnet 5) | **0.846** | 0.942 | 280 |
| **claude-code-haiku** (Haiku 4.5) | 0.789 | 0.908 | 280 |
| six local cells, pooled | 0.391 | 0.757 | 1679 / 1602 |

Haiku to Sonnet is +5.7 points. Sonnet to Opus is **−1.0**, which is three rows out of 280 and is
noise: the top of this task is reached at the middle rung, and the tier above it buys nothing. The
scale §3 was missing therefore has a ceiling as well as a floor — the local grid sits 45 points below
a hosted ceiling that **more model does not move**.

All three arms delivered a parseable object on every single row: 840 hosted rows, zero `no-output`,
zero `refused`, zero `timeout`, zero row lost. The 74 undelivered payloads of the local grid remain
the local grid's own.

### 9.4 The prediction of §9 holds, and it is the sharpest thing here

Registered before either arm ran: *if the residual is a property of the task, quality is roughly flat
from Haiku to Opus and r02, r10 and r19 fail on the larger models too.* They do — every one of them,
fourteen times out of fourteen, on all three tiers:

| request | haiku | sonnet | opus | expected action |
|---|---|---|---|---|
| r02 | 14/14 | 14/14 | 14/14 | ASSIGN |
| r10 | 14/14 | 14/14 | 14/14 | ASSIGN |
| r19 | 14/14 | 14/14 | 14/14 | DEFER |
| r15 | 9/14 | 1/14 | 1/14 | UNASSIGNED |
| r11 | 5/14 | 0/14 | 1/14 | DEFER |
| other | 3 rows | 0 | 2 rows | — |

Three requests account for 42 of Sonnet's 43 failures and 42 of Opus's 46. Everything the ladder
*does* buy is the rest of the tail: r15 — the P4 product no team accepts — collapses from 9 failures
to 1, and r11 disappears. The graded measure says the same thing twice: among failing rows, 42 of 43
(Sonnet) and 42 of 46 (Opus) sit at `quality_rate` 0.625, the signature §4 identified — five of eight
leaf fields correct, one classification error propagating into `intent`, `hours` and
`remaining_hours`.

So the last fifth of this task is not a capability the campaign's local models lack. It is a
disagreement about **what the request is**, and it survives a thirty-fold change of model. Two
readings were open in §4; this closes them in favour of the residual being a property of the task —
which also means the 0.789 / 0.846 / 0.836 band is the practical ceiling of this fixture, not a
staging post on the way to 1.0.

### 9.5 The curve on `L` is flat again, on both rungs

| rendering | L0 | L1 | L2 | L3 | L4 | prose-mech | prose-gen |
|---|---|---|---|---|---|---|---|
| sonnet | 0.850 | 0.825 | 0.850 | 0.850 | 0.850 | 0.850 | 0.850 |
| opus | 0.850 | 0.850 | 0.850 | 0.850 | 0.850 | **0.750** | 0.850 |

Sonnet's spread across all seven renderings is 0.025 — one row. The campaign's §8.3 (c) finding now
holds on three hosted tiers as well as on the local grid: explaining SOL to the reader does not help
the reader execute SOL, and replacing the JSON with prose does not either.

**The one exception is worth its own line, and it is not a quality loss.** Opus's prose-mechanical
cell is 0.75 because of four rows — the only four rows in 840 that did not answer `OK` — in which it
returned `INVALID_INPUT` and said why: the procedure's first step is `cat {{request_path}}`, no
`request_path` was supplied, the guard clause fires, and *"the JSON shown in the task body is not a
substitute — the procedure requires the content to come from reading the file"*. At E0 the input is
pre-injected precisely because there are no tools; Opus is the only model that read that literally
and stopped. The oracle scores it wrong, and by the oracle's standard it is wrong. It is also the
most faithful execution of the written procedure in the whole arm, and the disagreement is about the
bench's E0 convention, not about the model's comprehension.

### 9.6 Cost, and what it says about the tiers

| | prompt tokens | output tokens | wall (mean / max) | list-price equivalent |
|---|---|---|---|---|
| haiku | 1,963,496 | 612,591 | 25.5 s / 78 s | $7.21 |
| sonnet | 2,591,086 | 117,740 | 7.1 s / 12 s | $8.80 |
| opus | 2,586,606 | 187,011 | 11.7 s / 21 s | $20.46 |

Both arms ran unattended between 02:00 and 03:28 on 2026-09-02: Sonnet 279 rows in 33 minutes, Opus
279 in 55. The bill again went to a Claude Code subscription and is recorded as an estimate of a
spend, not as a measurement.

The output column is the surprise, and it survives into the wall clock: Haiku spends **five times**
the output tokens of Sonnet to answer the same 280 prompts worse. Whatever the CLI decides to do
about deliberation at each tier (§2.2) is inside these numbers, and at this task it buys Haiku
nothing.

The prompt column is not read here and should not be: the three arms sent the same seven documents,
and Haiku's total is 627,590 tokens lower than Sonnet's on the same 280 prompts. Something about the
invocation differs — the CLI's own context around the turn is the obvious candidate, and §7 records
that the prompt counters were being read wrong at the time the first arm ran — but this has not been
established, and no claim rests on it.

### 9.7 What these two arms do not say

Everything §5 already said about the first rung, unchanged: they are not families, they are outside
§9 of the protocol, no outcome is computed over them, no claim about local models depends on them,
and the invocation is part of the measurement. One thing is new and belongs here: **the ceiling is
now measured, and it is not 1.0.** A reader who takes 0.836 for "what a frontier model can do with
SOL" should read §9.4 first — 42 of those 46 failures are three requests whose ground truth every
tier disputes the same way.
