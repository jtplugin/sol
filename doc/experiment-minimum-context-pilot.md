# Technical pilot — making the minimum-context campaign executable on local hardware (2026-08-17 → 2026-08-19)

> Companion to [`experiment-minimum-context.md`](experiment-minimum-context.md) (the pre-registered
> protocol) and to [`experiment-minimum-context-build-log.md`](experiment-minimum-context-build-log.md)
> (how the infrastructure was built, 2026-08-03). That first document says *what* the campaign
> measures and *why*; the second says *how the instrument was built*. This one says **what it took to
> make the instrument run on real hardware, and what the instrument turned out to get wrong**.
>
> Written from verified command output, not from memory. Every number below has a file behind it.
> Where a claim was later falsified — and several were, some within the same day — the falsification
> is kept in place rather than edited away, because the sequence of wrong turns is part of the
> methods record.
>
> **Raw source**: the contemporaneous working notes were kept verbatim, session by session, in the
> task tracker. This document is organised by question and states the considered position; the
> notes were organised by time and preserved the record as it was made.

**Scope**: the technical pilot, in two sessions — the pilot proper and the resumption of the
perimeter it left uncovered. Target hardware: a single NVIDIA GPU with **8151 MiB** of VRAM on the
target workstation, running `llama-server.exe` (llama.cpp, CUDA build) from `C:\srv\llama`,
exposing an OpenAI-compatible `/v1/chat/completions` that the runner's `openai` backend speaks
without an adapter.

**No campaign run happened.** No K×R matrix execution, no scoring that belongs to the dataset. What
happened is: the executable envelope of the hardware was measured, the model set was fixed, the cost
model was rebuilt from scratch twice, the runner chain was exercised end to end for the first time,
and two defects were found in the measuring instrument itself.

---

## 1. Starting state

At the start of the pilot:

- `doc/experiment-minimum-context.md` held the pre-registered protocol: the L0–L4 context scale, the
  P axis (prompt variants), the K×R design (10 queues × 3 repetitions), the three-score oracle
  (fidelity, quality, efficiency) plus comprehension and a degradation mode.
- The engine question was settled on 2026-08-14: the local engine already existed as
  `C:\srv\llama` and LM Studio was never needed. Throughput on the target workstation had been benchmarked
  (Qwen3.5-9B Q4_K_M: 2329 t/s pp512, 55.8 t/s tg128).
- **Every measurement up to this point had bypassed the runner**, going straight to
  `/v1/chat/completions` with hand-built payloads. The chain `runner → trace → checker → record` —
  the reason the pilot existed — had never been exercised.
- The model set was, on paper: `Qwen3.5-9B` primary, `Ministral-3-8B` as the second family,
  `Phi-4-mini` as the fast tier.
- `tests/results/index.jsonl` held 575 rows from the June 2026 campaign.
- The sizing estimate in circulation was **69 s/item**, taken from a single successful pilot run.

---

## 2. The hardware envelope

### 2.1 The cliff is a threshold, not a slope

The first genuine finding, and the one that invalidated the most prior conclusions: **below roughly
100 MiB of free VRAM, prefill throughput collapses by a factor of ~45**. It is a threshold, not a
gradual degradation.

| model | VRAM used | free | prefill |
|---|---|---|---|
| Phi-4-mini, ctx 32768 | 6706 | 1097 | 3160 t/s |
| Qwen3.5-9B, ctx 32768 | 6162 | 1641 | 2133 t/s |
| Ministral-3-8B, ctx 20480 | 7664 | 139 | 2210 t/s |
| gemma-4-12b, ctx 32768 | 7694 | 109 | 1653 t/s |
| Ministral-3-8B, ctx 32768 | 7740 | 63 | **44 t/s** |
| Granite-4.1-8b, ctx 32768 | 7754 | 49 | **40 t/s** |

Above the threshold everything runs at 1600–3200 t/s; below it, everything falls under 50. Within a
single collapsed prefill the rate also degrades as context grows (293 → 81 t/s), which is consistent
with an allocation spilling into host memory and getting worse as occupancy rises.

The practical consequence for the campaign is not "some cells are slow". **A cell running below the
threshold does not produce a slow datum, it produces an unusable one**: 40× out-of-scale timings
that would poison any cost table built from them.

### 2.2 What was falsified along the way

The same day produced three explanations of Ministral's collapse that were all wrong, and keeping
them on the record matters more than the tidy ending:

1. **The `common_fit_params` warning.** The pilot summary blamed
   `failed to fit params to free device memory ... abort`. False: the identical warning appears in
   Qwen's log, and Qwen runs normally.
2. **VRAM contention, flash-attention, KV cache size.** All tested and eliminated: the GPU was at
   0 MiB before start; `-fa on` changed nothing; dropping `--ctx-size` to 20480 moved only 76 MiB.
3. **"Ministral is not usable on this hardware."** Recorded as a decision on 2026-08-18 and
   **reversed the same day**: Ministral was not slow, it was misconfigured. At ctx 20480 it prefills
   at 2210 t/s.

A fourth reversal followed. `gemma-4-12b` was used to falsify the VRAM-pressure hypothesis, on the
grounds that it runs fine with 109 MiB free — but 109 MiB is *just above* the threshold, not below
it, so it falsified nothing.

### 2.3 The real constraint is the KV cache, not the weights

The final answer, found on 2026-08-19, is that neither the model file nor `--ctx-size` alone
governs the envelope. **The KV cache does.**

Measured KV cost on the clean 8k→16k segment, with 16-bit cache:

| model | base at ctx 8192 | KV per 1k tokens | usable ctx at ≥150 MiB free |
|---|---|---|---|
| Ministral-3-8B Q4_K_S | 5786 MiB | 137 MiB | ~24,700 |
| Granite-4.1-8b Q4_K_S | 6172 MiB | 161 MiB | ~19,800 |

Two consequences followed, and the first one is counter-intuitive:

**Quantising the weights buys nothing.** Ministral Q4_K_S occupies 7762 MiB at ctx 32768 against
7740 MiB for Q4_K_M — 250 MB less on disk, **zero** MiB more free on the card, because the KV cache
immediately takes back whatever the weights release. The two Q4_K_S files downloaded for this test
were wasted bandwidth; the weights stayed at Q4_K_M.

**Quantising the KV cache changes everything.** With `--cache-type-k q8_0 --cache-type-v q8_0`, same
weights and same context size:

| cell | KV f16 | KV q8_0 | speedup |
|---|---|---|---|
| Ministral-3-8B, ctx 31744 | 43 MiB free, 53.7 t/s, 329 s | 795 MiB free, 1710 t/s, 10.7 s | **32×** |
| Granite-4.1-8b, ctx 28672 | 43 MiB free, 41.2 t/s, 374.6 s | 465 MiB free, 1768 t/s, 9.1 s | **43×** |

Both models re-entered the set. The 2026-08-18 decision that excluded them "for a declared hardware
limit, not on merit" was itself based on an incomplete diagnosis.

### 2.4 Slot count

`llama-server` opens **4 slots by default**, which costs ~80 MiB of buffers the campaign never uses:
its runs are serial. **`-np 1` is a rule for every cell.**

This also resolved an inconsistency that briefly looked like measurement contamination: gemma-4-12b
measured 109 MiB free in one session and 33 MiB in another, same model and same context size. The
difference was the slot count, not the measurement.

### 2.5 Measurement hygiene

Two rules were learned by getting them wrong first:

- **Verify the GPU is actually clean before every load.** `taskkill` returns immediately but the
  driver releases memory afterwards, so a model loaded straight after a kill is measured on a dirty
  card. The probe harness (`proto/vramprobe.py`) now polls until used ≤ 200 MiB before starting the
  next server, and records the pre-load free figure in every result row.
- **The acceptance criterion is measured prefill, not free MiB.** The ~150 MiB rule was a proxy for
  "prefill does not collapse". With the full curve measured — 43 MiB → 41–54 t/s; 125 MiB →
  1616 t/s; 465 MiB → 1768 t/s; 795 MiB → 1710 t/s — the cliff sits between 43 and 125, and at
  125 MiB prefill is already at full speed. gemma at ctx 31744 runs with 125 MiB free: the 150 MiB
  rule rejects it, the prefill measurement accepts it. **The criterion is now prefill > 1000 t/s on
  L1**; the 150 MiB figure survives only as a first-approximation rule for choosing which context
  size to try.

---

## 3. The validated cell configurations

Context requirement per cell is `prompt at the highest L level, with that model's own tokenizer`
plus `~690 tokens of chat-template overhead` plus `3000 tokens of generation` (see §5). The overhead
figure is measured on Qwen: 14,240 raw text tokens against 14,931 reported by the server.

L4 prompt size by tokenizer: Phi-4-mini 22,713 · Granite 23,491 · Qwen 24,017 · gemma 26,934 ·
Ministral 27,179. The spread matters: Ministral needs **+19%** more context than Phi-4-mini for
identical text.

Final configurations, all measured on a verified-clean GPU with `-np 1` and `q8_0` KV:

| cell | weights | ctx | VRAM free | prefill | L1 prompt |
|---|---|---|---|---|---|
| Qwen3.5-9B | Q4_K_M | 32768 | 2025 MiB | 2125 t/s | 14,931 |
| Phi-4-mini | Q4_K_M | 32768 | 2913 MiB | 3248 t/s | 14,236 |
| gemma-4-12b | Q4_K_L | 31744 | 579 MiB | 1584 t/s | 17,049 |
| Ministral-3-8B | Q4_K_M | 31744 | 561 MiB | 1850 t/s | 17,468 |
| Granite-4.1-8b | Q4_K_M | 28672 | 219 MiB | 1727 t/s | 15,235 |

All five clear L4 with their own tokenizer plus the generation ceiling.

### 3.1 Cells are tuned per model, and this is deliberate

An earlier decision in this pilot imposed **one uniform configuration** across all cells — `q8_0` KV
everywhere, including on Qwen and gemma which do not need it — on the reasoning that differing cache
configurations would make any model-to-model difference inseparable from a configuration difference.

**That decision was reversed.** The campaign does not rank models against each other; it measures
*how much context SOL needs to be interpreted correctly*, with models as the population to
generalise over. If the unit of observation is a cell as an operator would actually deploy it on this
hardware, then **the per-model optimal configuration is the use case**, not a confound. And the
uniform rule was not even neutral: forcing 8-bit KV onto a model with 2 GB of headroom *introduces* a
degradation nobody would choose in practice.

The cost of this choice is paid in bookkeeping, not in validity: **every cell's configuration must be
recorded with its results** (weights file, `--ctx-size`, KV type, `-np`), and the write-up must state
plainly that cells are not configuration-matched, because it is a design decision and not an
oversight. Direct model-to-model comparisons carry that caveat.

---

## 4. How these models actually fail

### 4.1 Non-terminating reasoning

Both reasoning models in the set — Qwen3.5-9B and gemma-4-12b — fail the fixture the same way:
`reasoning_content` grows without terminating and `content` comes back empty. Qwen produced 86,770
characters of reasoning and no answer, closing on `length` after 647 s.

**Widening the window does not help.** Raised to `--ctx-size 49152`, giving a 34,221-token generation
budget, the model consumed 30,000 tokens of reasoning and still produced nothing. More room means a
more expensive failure, not a better outcome.

**Disabling thinking helps, but far less than it first appeared.** With
`chat_template_kwargs: {"enable_thinking": false}`, run time for a good run drops from 238–647 s to
27–40 s. The completion *rate*, however, does not improve the way a three-run sample suggested — see
§4.3.

This is why thinking is treated as a **declared factor** rather than a background setting: today,
"Qwen3.5-9B" in the matrix silently means "Qwen3.5-9B with non-terminating reasoning", and that
behaviour drowns out the signal the L scale is meant to measure. *A reasoning model failing the task
more often than itself with reasoning switched off* is a publishable result, not a configuration
accident.

### 4.2 Three distinct degradation modes, and they are not interchangeable

| mode | what it looks like | where observed |
|---|---|---|
| empty output | non-terminating `reasoning_content`, `content` empty | Qwen and gemma with thinking on |
| non-terminating content | well-formed trace that loops, no final JSON | Qwen with thinking off |
| wrong value | complete, well-formed, terminating output that is simply wrong | Phi-4-mini, 10/10 runs |

The middle one is the dangerous one, and it is worth describing precisely. The captured sample
(`fuga_sample.txt`, 9,185 characters) is **not** degenerate text. It is a correctly tagged, correctly
formatted trace:

- 15 `EVAL` lines, all correct, one per queue item — exactly as expected
- **95 `BRANCH` lines instead of 15**: seven passes over the same fifteen items, with contradictory
  actions on the same item (`item-241` as `ASSIGN`, then `ESCALATE`, then `ASSIGN` again)
- `remaining` descending correctly (17, 13, 13, 8, 6, 2, 1) down to **-3**, then pinned there for
  eighty lines
- no final JSON, truncated mid-line

Ground truth for `queue-01` is `halted_at: item-137`, `remaining_hours: 1`, `n_processed: 7`. The
model **did not stop at the budget**, and past the budget it has no halting condition left: it cycles
until it runs out of tokens.

**So the runaway *is* the `no-halt` degradation mode, taken to its limit** — the same fault that
`nothink_sample.txt` shows in mild form (15 items instead of 7, `remaining_hours: -10`,
`halted_at: null`), except diverging instead of closing.

**Therefore a `length` run is recorded as a result with its degradation mode; it is neither retried
nor discarded.** Treating it as a technical failure to retry would systematically censor the exact
failure the W2 fixture exists to measure, and would inflate fidelity in every cell where the model
diverges. In a pre-registered study with a sealed hold-out set, that would be a distortion of our own
making.

The checker must nevertheless separate two different `length` outcomes. What distinguishes them is
**not** the monotonicity of `remaining`, which is non-increasing in both cases, but **item repetition
plus a plateau**:

| | signal | reading |
|---|---|---|
| `length` from a loop | repeated items, `remaining` flat | valid datum: `no-halt` |
| `length` from truncation | monotone progress, no repetition | artefact: ceiling set too low |

### 4.3 The distribution is bimodal, and small samples lie

Ten identical runs of Qwen3.5-9B with thinking off, L1, temperature 0.2, `max_tokens` 13024:
**6 completed, 4 ran away**. Runs are either ~32 s or ~268 s, with nothing in between.

An earlier entry, honestly marked `(n=3)`, had recorded the completion rate as 100%. At n=10 it is
60%. With thinking *on* it was 40%. **Switching thinking off shortens the good run; it does not
lower the failure rate.**

This is the same sampling error made twice in one day: in the morning the pilot's 69 s/item estimate
was diagnosed as resting on a one-in-five lucky run, and by the afternoon a 6–7 hours/model estimate
had been built on a three-out-of-three sample.

**Rule adopted: on this fixture no rate is declared below n=10.** With a bimodal distribution, a
small sample samples one mode.

---

## 5. The `max_tokens` ceiling as a cost limit

Two separate questions were confused early and must stay separated.

**Question one: does `max_tokens` make a bad run good?** No. Ten runs with byte-identical payloads:
at 13024, 1 of 5 produced output; at 30000, 3 of 5. The difference is not significant at n=5, and the
two failures in the second arm stopped at 17,837 tokens — against the `--ctx-size` ceiling, not
against `max_tokens`. There is no evidence the budget is a lever in either direction.

**Question two: how much does failing cost?** This one has a useful answer. A good run closes at
1,355–1,614 tokens, so a ceiling of 3,000 leaves an 1.85× margin over any successful run while
cutting the runaway short.

Measured, n=10 per arm, same configuration otherwise:

| | ceiling 13024 | ceiling 3000 |
|---|---|---|
| runaway rate | 4/10 | 2/10 |
| good run | 27–40 s | 31.9–40.2 s |
| runaway | 266–270 s | **59.5–59.6 s** |
| runaway characters | 38,713–39,582 | 9,148 |
| runaway `finish_reason` | `length` | `length` |

**The 2/10 is not claimed as an improvement**: n=10 against n=10 is not a significant difference, and
an improvement would have been suspicious given that `max_tokens` is not a quality lever. Sizing uses
40%, not 20%.

**No good run is decapitated**, and the margin holds for the whole K set, not just the tested queue:
all ten queues in `queues-manifest.json` have `queue_size: 15`, so expected output length is uniform.
The L scale adds context on the **input** side, not the output side, so the ceiling does not need
re-tuning as the level rises — only if the fixture changes.

---

## 6. Determinism and the R axis

`llama-server` is **not** deterministic at fixed temperature. Ten runs, thinking off, temperature
0.2:

| block | distinct outputs | runaways |
|---|---|---|
| A, no seed declared | 4 of 5 | 1 of 5 |
| B, seeds 1–5 | 5 of 5 | 3 of 5 |

**The R axis stays in the design, without seeding.** The three repetitions per queue measure real
variance, so the GPU hours are not wasted. Seeding is a lever (5 distinct of 5) but is not needed to
*produce* variance, which is already present: it should be reserved for *reproducing* a specific run.

There is, however, a strong attractor, and it is worth recording because it changes how variance
should be read: **3 of 10 runs produced byte-identical output** (sha `2870d8b9f6fc`). An earlier
observation of "two identical gemma runs" had been read as determinism; it was n=2 on an attractor.
A model that frequently converges on the same answer is not a deterministic model.

---

## 7. Sizing, rebuilt twice

| basis | cost per item | hours per model |
|---|---|---|
| the pilot's single lucky run | 69 s | — |
| ceiling 13024, 40% runaway at 268 s | ~126 s | 25–29 |
| ceiling 3000, 40% runaway at 59.5 s | **~43 s** | **~8.5–10** |

The last figure is the prudent one: it applies the unchanged 40% runaway rate rather than the 2/10
measured in the ceiling-3000 block. It brings a per-model campaign back inside a single night,
narrowly.

---

## 8. Two defects found in the instrument

This is the part of the pilot that justifies its existence: both defects are in the measuring
apparatus, and both would have silently corrupted the campaign.

### 8.1 The sequence oracle rewards runaway runs

Feeding the captured runaway sample through the checker, against the first real runner-produced run
for comparison:

| | honest run (Ministral) | runaway sample |
|---|---|---|
| `degradation_mode` | no-halt | no-halt |
| `quality` | fail | fail |
| `fidelity.sequence_rate` | **0.286** | **0.714** |
| `comprehension` | **fail** | **pass** |

**The degenerate run scores better than the one that finished.** The rate compares the *first seven*
observed actions against the seven expected: the runaway gets five right on its first pass, then
loops another 88 times and nothing counts the excess. `comprehension` passes because the fifteen
`EVAL` lines are correct — the model classifies the items well, then loops, and the oracle only looks
at the beginning.

This compounds badly with the decision in §4.2 to keep `length` runs as data. If runaways stay in the
dataset **and** the checker rewards them, runaways *raise* mean fidelity, and a model that diverges
often looks better than one that fails honestly.

**Resolution: two metrics instead of one.**

- **`sequence_rate` = correct actions / `max(expected, observed)`.** Answers *how much of the correct
  sequence the model produced, without being forgiven for the excess*. It is monotone: it degrades
  both when actions are wrong and when surplus actions are emitted. On the runaway sample it falls
  from 0.714 to **0.053**.
- **`redundancy_ratio` = observed actions / expected actions.** Answers *how much was produced beyond
  what was asked*. 1.0 is exact length, above 1 the model kept going, below 1 it stopped early. On the
  runaway sample it is **13.6**.

Together they separate three faults the rate alone conflates: low rate with redundancy ≈ 1 means
**wrong actions**; low rate with high redundancy means **a loop**; low rate with redundancy below 1
means **early stopping**.

**On modifying a pre-registered oracle**: the correction is made *before* MAIN, not after. No MAIN
data exists yet and the defect is independent of the hypothesis under test, so this is not choosing a
denominator that flatters the results. It is nonetheless declared in the write-up, with its date and
its reason.

**Status: implemented 2026-08-19** — `sequence_rate`'s denominator and `redundancy_ratio`
land in `tests/runner/checker.py::_check_sequence_fidelity` and `tests/runner/schema.py::FidelityCheck`
exactly as specified above.

### 8.2 The record does not identify the cell

The record's `config` block carries fixture, context, `model_id`, spec version, backend,
`reasoning_budget` and temperature. It does **not** carry `--ctx-size`, the KV cache type, or `-np`.

While all cells shared one configuration this was harmless. Under the per-model tuning decision of
§3.1 those fields are part of the cell's identity: without them a result is neither interpretable nor
reproducible, and six months later nobody can tell whether a given row came from an 8-bit or a 16-bit
cache.

---

## 9. First end-to-end run through the runner

Every measurement described above bypassed the runner. On 2026-08-19 the chain was finally exercised
whole, with Ministral-3-8B (non-thinking, so no runner modification was required first):

```
  #     Input                       Q      F      Time     Tok      Degrade
  1     queue-01 #1                 XX     XX     59.9s    19607    no-halt
```

The run wrote its record, its score file, an `index.jsonl` row (576 total) and a regenerated
dashboard. The checker produced all three scores plus comprehension, correctly identified `no-halt`,
and returned `sequence_rate` 0.286 with the expected and observed action sequences side by side.

**`runner → trace → checker → record` is validated end to end.** Worth noting for planning: this step
was *not* blocked on the thinking modification. That modification exists to disable reasoning on the
primary model; the non-thinking cells run through the current runner unchanged.

---

## 10. An A/B that did not answer its question

Since cells are now tuned per model, a fair question follows: **do some configurations produce better
results with SOL than others?** The first attempt to answer it, on the KV cache, failed for a reason
worth recording.

Phi-4-mini, ten runs per arm through the runner, same queue:

| | f16 | q8_0 |
|---|---|---|
| quality pass | 0/10 | 0/10 |
| fidelity pass | 0/10 | 0/10 |
| mean time | 27.8 s | 28.9 s |
| degradation | 10 `wrong-value` | 7 `wrong-value`, 2 `no-output`, 1 `refused` |

**Phi-4-mini is on the floor**: it fails this fixture with both cache types, so there is no room
beneath it in which a degradation could show. The failure-mode distribution does shift (3/10 anomalies
against 0/10) but at n=10 that is p≈0.21 — suggestive, not established.

The subject was badly chosen: Phi-4-mini was picked because it is the only non-thinking model that
fits both cache types, without weighing that it is also the weakest cell in the set. A clean A/B needs
a model that *sometimes passes* — Qwen or gemma — and both are reasoning models, so both require the
runner's thinking control first. The question stays open with a clear method for closing it.

---

## 11. What remains open

- **The second family is now a choice, not a gap.** With five usable cells, the non-Qwen slot can be
  gemma (reasoning, Google lineage), Ministral (non-reasoning, Mistral lineage) or Granite
  (non-reasoning, IBM lineage). Widening the set costs GPU nights at ~8.5–10 hours per model.
- **The runner modifications**, as one change set: thinking as a declared factor on the `openai`
  backend, cell configuration recorded in the result, and the two-metric oracle.
- **The KV A/B**, redone on a model that is not on the floor, after the above.
- **The E2 cell** must not run until the `caveman` Claude Code plugin is either disabled or its
  contamination is declared: it registers a `UserPromptSubmit` hook that would rewrite prompts before
  they are sent, so the campaign would be measuring *SOL through caveman* without anyone declaring it.

---

## 12. Methodological rules this pilot produced

Stated separately because they outlive the specific hardware:

1. **No rate is declared below n=10 on this fixture.** The distribution is bimodal; small samples
   sample one mode. Violated twice in one day before being adopted.
2. **Measure the thing, not its proxy.** Free VRAM was a proxy for prefill health; once prefill was
   measured directly the proxy's threshold turned out to reject working configurations.
3. **Verify the instrument is clean before every measurement.** Memory released asynchronously
   produced a set of readings that looked like a real effect.
4. **A failure mode the fixture is designed to detect is data, not noise.** The rule for discarding
   runs must be written before the runs, and must not quietly delete the phenomenon under study.
5. **Configuration is part of the result.** If cells are tuned individually — and they should be, if
   the study is about realistic deployment — then the configuration travels with the record.
