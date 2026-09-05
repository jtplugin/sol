# Build log — minimum-context campaign infrastructure (2026-08-03)

> Companion to [`experiment-minimum-context.md`](experiment-minimum-context.md) (the
> pre-registered protocol). That document says *what* the campaign measures and *why*. This
> document is a factual, dated account of *how the infrastructure got built* — every commit,
> every number, every deviation from plan, every open question. Written the same day the work
> happened, from verified command output, not from memory. If this campaign becomes a
> methodology paper, this is the raw material for the "materials and methods" section and for
> honestly dating every claim.

> **Sequel**: [`experiment-minimum-context-pilot.md`](experiment-minimum-context-pilot.md) covers the
> technical pilot (2026-08-17 → 2026-08-19) — what it took to make this infrastructure run on real
> hardware, and the two defects that surfaced in the instrument once it was exercised end to end.

**Scope of this log**: the infrastructure-build session of 2026-08-03, covering steps 2–8 of the
planned build plus an ad-hoc extension (a blind-AI-assisted manual verification tool) requested
mid-session. **No campaign run happened.** No K×R matrix execution, no real
model scoring. Everything below is either (a) code/data that now exists in the repository, or
(b) a documented decision, or (c) a documented block waiting on a human.

---

## 1. Starting state

At the start of the session:

- `doc/experiment-minimum-context.md` (507 lines, the full pre-registered protocol) **existed on
  disk but was not committed to git** — `git status` showed it as untracked (`??`), alongside an
  uncommitted edit to `doc/README.md` that already linked to it. This was **not** a missing
  document to reconstruct; it was a real, already-written 507-line file, simply not yet in git
  history.
- The build plan already carried a fully closed design section (items 1.1–1.7, all settled) — fixture shape, L0–L4 scale, prose
  variants, three-score oracle, P-axis, K×R design, Claude-out-of-matrix — decided in prior
  sessions, dated 2026-08-01 through 2026-08-03 in the card's notes field.
- `tests/fixtures/w2-branching/release-gate/` was the only existing W2 fixture — single-branch,
  no state accumulation, no `REPEAT`. `w2-branching/support-intake` did not exist.
- `tests/runner/checker.py` scored a scalar verdict only (`_check_fidelity`, last-`BRANCH`-line
  match). No sequence oracle, no comprehension score, no conditional fidelity.
- `tests/results/index.jsonl` held 575 rows from a prior campaign (June 2026), with an
  unattributed high `execution-error` rate on local models and 13 rows carrying
  `runner_type: claude-code` + `env_realization: emulated` (a labeling inconsistency).
- `tests/runner/api_executor.py` supported two backends only: `anthropic`, `ollama`. No
  temperature control anywhere in the runner stack.
- `tests/env.json` did not exist (only `tests/env.example.json`, a template).
- No dataset-handling scripts existed under `tests/scripts/` except a one-off
  `backfill_request_messages.py`.

## 2. Two decisions frozen before any code was written

Per the protocol's explicit rule (§13, open items), two numbers required Gianni's sign-off
before generation could start. Asked via a two-question multiple-choice prompt at the start of
the build session; both confirmed as the recommended option:

- **Conditional-fidelity acceptability threshold: 90%.** Rationale offered: isolates pure
  control-flow (not comprehension), and on a ~15-item sequence at temperature 0.2, 90% tolerates
  roughly one stochastic slip.
- **Queue structural acceptance criterion: budget exhausted between item 5 and item 11
  inclusive, plus at least one ESCALATE-eligible condition before the halt.** Confirmed as
  literally stated in the protocol's §4.4 example. In this fixture's actual design, the two
  clauses turn out to be the same event (only `ESCALATE` sets `halted_at`), which is recorded
  as a design note in `tests/fixtures/w2-branching/support-intake/queue-criterion.json`.

Both are recorded, frozen, in `queue-criterion.json` and referenced by `build_queues.py`.

## 3. The Ultraplan detour (does not affect the delivered code)

Before local implementation began, the initial plan was sent to Ultraplan (Claude Code on the
web) for independent refinement, per Gianni's request. Ultraplan produced a revised plan and
was then **blocked by Gianni before execution** — it never touched the repository. `git log`
and `git branch -a` were checked immediately after and confirmed: no new commits, no new remote
branches, working tree unchanged from before the Ultraplan session.

Ultraplan's plan text was reviewed for its differences against the original local plan. Two
technical corrections in it were judged valid and were incorporated into the actual
implementation:

1. `checker.py`'s existing `_check_fidelity` only ever compares the **last** `BRANCH` line as a
   scalar (`_BRANCH_RE`, whole-line match) — a genuinely new function was needed for a per-item
   sequence, not an extension of the existing one. This shaped the `_check_sequence_fidelity` /
   `_check_conditional_fidelity` design in §5.5 below.
2. `tests/runner/run.py` has its **own** `_load_env_entry`, independent of
   `api_executor._load_mode` — a `temperature` field added only to `api_executor.py` would not
   reach `run.py`'s call path (the one actually used by the final `--dry-run` validation). Both
   were updated; see §5.7.

One part of Ultraplan's plan was **not** applied: it proposed, as "Step 0", *rewriting*
`doc/experiment-minimum-context.md` from a short summary, having concluded (from a fresh git
clone with no access to the local uncommitted file) that the protocol document didn't exist at
all. It exists, in full, and was committed as-is — see §4.

## 4. Commits, in order, with exact hashes

Six commits landed on `main` this session, all authored `Gianni Tommasi <gianni.tommasi@gmail.com>`
with `Co-Authored-By: Claude Sonnet 5`, all confirmed via `git log --stat`:

| Hash | Subject | Files changed | Lines |
|---|---|---|---|
| `4e9a2f4` | Add pre-registered protocol for minimum-context campaign | 2 | +515 |
| `f519d1f` | Build minimum-context campaign infrastructure (steps 2-8) | 22 | +7546 / −22 |
| `7e51b0a` | Add missing README.md for support-intake fixture | 1 | +108 |
| `4439b7c` | Add HTML generator for the manual pool verification (item 2.6) | 1 | +377 |
| `c0d14b9` | Add blind-AI triage column to the verification tool | 1 | +125 / −64 |

(A sixth item — the not-yet-committed `ai-blind-labels.json` generation step, §7 — lives only
in `tests/data-local/`, gitignored by design; there is nothing to commit there.)

`f519d1f` is the bulk commit; the full list of the 22 files it touched is preserved in the git
history itself (`git show --stat f519d1f`) and is not re-transcribed here to avoid drift between
this log and the actual diff.

## 5. What was built, with verified facts

### 5.1 Dataset pool (`tests/scripts/sample_pool.py`)

- Source: `data/issues_test.csv` from `github.com/nlbse2024/issue-report-classification`,
  downloaded via `raw.githubusercontent.com`. Verified schema:
  `repo, created_at, label, title, body`. Verified row count: **1500**, perfectly balanced —
  `Counter` over `repo` gave exactly 300 per repo (`facebook/react`, `tensorflow/tensorflow`,
  `microsoft/vscode`, `bitcoin/bitcoin`, `opencv/opencv`); `Counter` over `label` gave exactly
  500 per label (`bug`, `feature`, `question`).
- Sampling: stratified by `(repo, label)`, 15 strata, **20 items per stratum, seed `42`**
  (`SEED_POOL`), giving exactly 300 items. Verified output: `Counter` over `repo` in the drawn
  pool = 60 per repo (`{20 × 3 labels}`).
- MAIN/REPLICATION split: stratified again per `(repo, label)`, **10/10 per stratum, seed
  `1337`** (`SEED_SPLIT`). Verified: 150 MAIN, 150 REPLICATION.
- IDs are assigned by sorting the drawn pool by `(repo, label, title)` before numbering
  (`item-001`…`item-300`) — this makes the id assignment reproducible from the same CSV and
  seeds, independent of dict/set iteration order.
- Outputs: `pool-manifest.json` (committed, 141,854 bytes as of this log, zero body/title text —
  fields are `id, repo, nlbse_label, created_at, title_hash, body_hash, split, verified_label,
  tolerant, tolerant_alt_label, verified`, the last four `null`/`false` placeholders pending
  manual review); `pool-main.json` / `pool-replication.json` (local, gitignored, WITH full
  `title`/`body` text); `verification-sheet.csv` (local, gitignored — superseded by the HTML
  tool, §6–§7, but the script still produces it).

### 5.2 Fixture dehydration (`tests/scripts/hydrate.py`)

Two independent modes, both hash-verified against `pool-manifest.json`'s SHA-256 `title_hash`/
`body_hash` fields:

- `--mode pool`: rebuilds `pool-main.json`/`pool-replication.json` from the local CSV + the
  committed manifest, refusing (hard `sys.exit`) on any hash mismatch.
- `--mode queues`: materializes `inputs/queue-01.json`…`queue-10.json` (the `{queue:
  [{id,title,body}]}` shape the fixture's `accepts` contract expects) from
  `queues-manifest.json` + `pool-main.json`.

`git add -n` was run after both stages and confirmed: only `pool-manifest.json` and
`queues-manifest.json` (id/hash/verdict only) would be staged from
`tests/fixtures/w2-branching/support-intake/`; nothing under `tests/data-local/` and no
`inputs/queue-*.json` file appeared in the dry-run add list. `.gitignore` carries both patterns
explicitly (added this session).

### 5.3 Fixture `w2-branching/support-intake`

- `catalog.json`: 5 product personas (`P1`…`P5`, fictional names `Solidus/Lucent/Meridian/
  Aperture/Tensora`), each mapped 1:1 to a real repo via `product_to_repo` (never shown to the
  model), plus a fixed `hours_table` (intent × product → integer hours) and `budget_hours: 20`.
- `support-intake.md`: SOL document. `ROUTINE` has 9 top-level instructions: a `RUN`, an `IF`
  guard, an accumulator-init `TODO`, three `SUB` definitions (`classify-request`,
  `estimate-effort`, `check-budget`), one `REPEAT foreach`, a final `TODO`+`RETURN`. Verified via
  `_load_fixture()` (the actual loader `run.py`/`api_executor.py` use) — `len(sol_doc['ROUTINE'])
  == 9`.
  - Design choice, explicit in the file: neither the malformed-input guard nor the
    mid-loop ESCALATE-and-stop path use SOL's literal `HALT` construct. Both use `RETURN` with a
    structured payload. Rationale recorded inline: `HALT` per the spec (`spec/sol-0.6.md`)
    carries no structured payload and stops the entire run with no value returned; the checker
    needs the accumulated `items`/`remaining_hours`/`halted_at` to score conditional fidelity,
    which only `RETURN` can carry. This mirrors how the pre-existing `release-gate` fixture
    already handles its own `INVALID_INPUT` guard (via `RETURN`, not `HALT`).
  - Trace protocol, novel to this fixture: two structured lines per queue item, not one bare
    label per run as in `release-gate`/`task-router`:
    ```
    [fixture-w2-support-intake][main] EVAL: item=<id> product=<P1..P5|UNKNOWN> intent=<BUG|FEATURE|QUESTION>
    [fixture-w2-support-intake][main] BRANCH: item=<id> action=<ASSIGN|DEFER|NEEDS_INFO|ESCALATE> remaining=<n>
    ```
    Both prefixes (`EVAL`, `BRANCH`) were already recognized by `runner.py`'s generic
    `_TRACE_LINE_RE` (`EVAL|BRANCH|RETURN|START|HALT`) — no change needed to raw trace capture,
    only to how `checker.py` interprets the captured lines (§5.5).
- `reference.py`: pure function `run_queue(items, budget_hours, hours_table) -> {status, items,
  remaining_hours, halted_at}`. Hand-validated this session with four constructed cases, all
  asserted and all passing in a single interactive run (transcript preserved in this session's
  tool history, not re-run for this log to avoid re-doing work already verified):
  1. Exact budget exhaustion, no escalate (5× `P2/FEATURE`, 4h each = 20h budget exactly;
     `remaining_hours == 0`, `halted_at is None`).
  2. ESCALATE at the first item (budget 2h, item 1 is `P1/BUG` at 3h; `halted_at == "i1"`,
     exactly 1 item processed).
  3. ESCALATE at the last item of a 2-item queue (budget 5h; item 1 `P2/FEATURE` 4h → `ASSIGN`,
     remaining 1h; item 2 `P2/BUG` 2h → NOFIT+BUG → `ESCALATE`; `remaining_hours == 1` at halt).
  4. `UNKNOWN` product → `NEEDS_INFO`, budget unchanged (verified `hours is None`,
     `remaining_hours` unchanged from input).
- `inputs/i0-malformed.json`: the one structural case outside the K queues — a queue item
  missing the `body` field, tripping the `IF` guard before any `REPEAT` iteration. This is the
  **only** real (non-gitignored) file under this fixture's `inputs/`.
- `expectations.json` (37,503 bytes, committed): 1 malformed case + 10 queue cases. Each queue
  case carries `expected_sequence` (list of `"item=<id> action=<action>"` strings, ground truth),
  `expected_output` (full end-to-end payload), and `comprehension_ground_truth` — a list scoped
  to **only the items actually processed** (up to and including any halt), not the full 15-item
  draw, because a faithfully-executing model never reaches items past a halt and cannot have
  classified them. This restriction was a real bug caught and fixed mid-session (first draft of
  `build_queues.py` used the full 15-item list; a synthetic-record test immediately showed
  `comprehension.rate == 0.6` on a run built to be perfect, tracing to this exact cause). A
  top-level `catalog` field (`budget_hours` + `hours_table`) is embedded so `checker.py` can
  re-run the oracle without importing this fixture's `reference.py` — see §5.5.
- Lint (`sol-lint.py`, the R2 gate): **0 errors, 4 warnings** — 3 are the same `root-meta`
  warning every fixture in this corpus gets (frontmatter fields aren't in the JSON fence itself;
  `release-gate.md` gets the identical 3), the 4th is a heuristic `buried-flow` false positive on
  one `SUB`'s natural-language fallback wording ("if no product plausibly matches..."), reviewed
  and left as-is (not lifted into a construct, since the real branching already happens one level
  up in the main `IF`).
- `README.md`: written in a follow-up commit (`7e51b0a`) after being missed in the first pass —
  a real gap, caught only by cross-checking the file list against the plan before closing the
  card, not caught earlier.

### 5.4 Queue generation (`tests/scripts/build_queues.py`)

- Rejection sampling: draws 15-item queues (`random.Random(2024)`, `SEED_QUEUES`) from the 150
  MAIN pool ids, computing each candidate's ground-truth classification via
  `catalog.json['product_to_repo']` (inverted) + the raw NLBSE label (uppercased) as intent —
  **explicitly provisional**, since this predates manual verification (§2.6, still open).
- Acceptance criterion (§2 above) applied via `reference.run_queue()` on each candidate: reject
  unless `halted_at is not None` and its 1-indexed position in the processed-items list falls in
  `[5, 11]`.
- Verified run: **10 accepted queues in 25 total draw attempts** (2.5 average per accepted
  queue) — printed and captured, not re-estimated. Per-queue `n_processed` values recorded at
  generation time: 9, 6, 10, 11, 9, 11, 8, 6, 6, 8 — all within `[5,11]` as required by
  construction; every accepted queue's action sequence necessarily contains exactly one
  `ESCALATE` (the criterion's second clause) since `ESCALATE` is what produces `halted_at`.
- `queues-manifest.json` (committed): for each of the 10 queues, the ordered list of 15 item ids
  drawn, plus `halted_at`/`remaining_hours`/`n_processed` at generation time. Zero title/body
  text.

### 5.5 Checker extension (`tests/runner/checker.py`, `tests/runner/schema.py`)

All additions are **additive** — new optional dataclass fields (default `None`), new module-level
functions, no modification to any existing function's control flow or default behavior. Proven,
not asserted: **all 22 pre-existing R1 tests in `test_checker.py` pass unchanged**, including
`test_fidelity_uses_last_branch_entry`, which directly exercises the exact code path
(`_check_fidelity`'s `observed_labels[-1]` scalar match) that the new sequence logic deliberately
does not touch.

New schema fields (`schema.py`):
- `FidelityCheck`: `sequence_rate`, `expected_sequence`, `observed_sequence`,
  `conditional_rate`, `conditional_expected_sequence`, `conditional_observed_sequence` (all
  `Optional`, default `None`).
- `QualityCheck`: `rate: Optional[float] = None` (generic — used for `comprehension`, not
  specific to this fixture).
- `ScoreRecord`: `comprehension: Optional[QualityCheck] = None`.
- `Config`: `temperature: Optional[float] = None`.

New functions (`checker.py`):
- `_check_sequence_fidelity(trace, case)` — returns `None` (opt-out) if the case has no
  `expected_sequence` key; otherwise parses `BRANCH: item=<id> action=<action> ...` lines via a
  new regex (`_BRANCH_ITEM_RE`, distinct from the pre-existing `_BRANCH_RE` used by
  `_check_fidelity`), builds the observed action sequence, compares positionally against
  `expected_sequence`, returns a `FidelityCheck` with `sequence_rate` set.
- `_extract_eval_sequence(trace)` — parses `EVAL: item=<id> product=<p> intent=<i>` lines
  (`_EVAL_ITEM_RE`).
- `_run_queue_oracle(items, budget_hours, hours_table)` — a **deliberate duplicate** of
  `reference.py`'s `run_queue()` algorithm, kept inside the generic checker so it never imports a
  specific fixture's Python module. The duplication is documented in both files with a note that
  they must be kept in sync; `test_checker.py`'s
  `test_checker_against_real_support_intake_expectations` cross-checks the checker's copy against
  the real generated `expectations.json` (which was itself produced by `reference.py`), giving an
  indirect but real consistency check between the two copies.
- `_check_conditional_fidelity(trace, catalog)` — re-runs `_run_queue_oracle` using the EVAL
  lines (the model's own classifications, not ground truth), compares against the observed
  BRANCH sequence.
- `_check_comprehension(trace, case)` — compares EVAL classifications against
  `comprehension_ground_truth`, honoring `tolerant`/`tolerant_alt_label`.
- `_sequence_degradation_mode(fidelity, payload, expected_output)` — three new labels:
  - `no-halt`: the expected sequence ends in `ESCALATE` but the observed sequence either
    overran (more entries than expected) or has something other than `ESCALATE` at that exact
    position.
  - `partial-sequence`: `0 < sequence_rate < 1` and it's not a `no-halt` case (checked first —
    a missed halt is reported as `no-halt` even if it also technically constitutes a partial
    sequence; verified this priority order by constructing a test case that would trigger both
    conditions and confirming `no-halt` wins).
  - `budget-drift`: `sequence_rate == 1.0` (every action right) but the final payload's
    `remaining_hours` doesn't match — right decisions, wrong bookkeeping.
- `decompose_variance(scores, metric="conditional_rate")` — groups `ScoreRecord`s by
  `staged_input_id` (the queue id), computes per-queue mean, within-queue variance
  (`statistics.pvariance` per group), between-queue variance (`pvariance` of the per-queue
  means), and their means/grand mean. This is the K×R within/between decomposition the protocol
  calls for (§6.3/§7.2); it operates on a **list of already-scored runs**, not inside `check()`
  itself, since variance is inherently a multi-run statistic.

Test suite: **34 tests collected and passing** in `test_checker.py` (34 distinct `pytest`
node ids; the file has 35 `def test_...` lines because of one pre-existing duplicate function
name inherited from before this session, which pytest collapses to one collected test — not
introduced this session, not fixed, out of scope). 12 of the 34 are new this session, covering:
perfect-run sequence/conditional fidelity, the informative "60% comprehension / 100% conditional
fidelity" case the protocol explicitly names (§6.2) — constructed as
`test_comprehension_partial_misclassification` — a case where conditional fidelity diverges from
ground-truth sequence fidelity specifically because the model's own (wrong) classification would
imply a different correct action (`test_conditional_fidelity_isolates_control_flow_from_
comprehension`), all three new degradation modes with hand-built traces, `decompose_variance`
with a synthetic between-dominates-within scenario and a
none-values-are-ignored edge case, and a tie-in test against the real generated
`expectations.json`.

Full repo-wide run at time of this log: `python3 -m pytest tests/toolchain -q` → **48 passed, 2
failed**. The 2 failures (`test_sol_lint.py::test_cart_total_fixture_lints_clean`,
`::test_task_router_fixture_lints_clean`) are **pre-existing** — `git status`/`git log` confirmed
no modification to `cart-total.md`/`task-router.md` in this session or by this session's commits;
the failure traces to a `JSONDecodeError` in those fixtures' JSON fences, most likely introduced
by an earlier session's commit (`a515dc0 Fix typos in task-router.md` or `06dba1d Refine
task-router fixture and update prompts`, both from before this session, per `git log`). Flagged,
not fixed — out of this session's scope.

### 5.6 Preprocessing (`tests/scripts/preprocess_p1.py`, `preprocess_p2a.py`)

- P1 (deterministic, no LLM): regex-based cleaning — HTML-comment template boilerplate, code
  fences → `[code]`, a line-based stack-trace collapser → `[stacktrace]`, markdown images and
  bare URLs → `[image]` (per the protocol's explicit wording — both map to the same marker),
  quoted-reply lines stripped, signature blocks after `\n--\n` cut, whitespace collapsed,
  truncation to an 800-character budget (title excluded from the budget).
  - **Run once this session**, on `pool-main.json` (150 items, provisional pool): **76,377
    approximate tokens saved total, 509.2 average per item** (char/4 heuristic, explicitly
    documented as an approximation, not a real tokenizer), **46/150 items truncated**. Numbers
    from the script's own printed summary, not recomputed for this log.
- P2a (AI neutral condensation): **written, zero API calls made**. Verified by construction —
  the script was never invoked with real credentials in this session; only its `--help`/syntax
  was checked (`python3 -c "import ast; ast.parse(...)"`). System prompt explicitly forbids the
  model from naming or guessing the product/project.

### 5.7 Runner extensions (`tests/runner/api_executor.py`, `tests/runner/run.py`)

- New backend `"openai"`: talks to an OpenAI-compatible `/v1/chat/completions` endpoint (LM
  Studio's native local-server API), E0-only (same restriction the existing `"ollama"` backend
  already had — enforced by extending the same `if backend in (...) and context != "E0"` guard,
  not a new check). Implemented as `_post_messages_openai`, mirroring the existing `ollama`
  function's shape and error handling.
- `temperature` threaded end-to-end, confirmed present in **six** distinct places (this count
  itself was a direct consequence of the Ultraplan-flagged gap, §3): `tests/env.json` mode
  entries; `api_executor._load_mode` return tuple; `api_executor`'s own CLI `--temperature` flag;
  `run.py`'s independent `_load_env_entry` + its own `--temperature` flag; `_sdk_create` /
  `_post_messages_ollama` / `_post_messages_openai` (all three backends); `schema.Config
  .temperature` (so it's recorded in the run record, not silently dropped). A guard was added
  specifically for the Anthropic backend: `effective_temperature = temperature if
  reasoning_budget == 0 else None`, because the Anthropic API rejects a custom `temperature`
  alongside `thinking` (extended reasoning requires `temperature==1` or omitted) — this
  constraint was not previously encoded anywhere in the codebase and would otherwise have caused
  a live 400 error the first time someone combined `--reasoning` with a custom `--temperature`.
- A real bug was found and fixed mid-session: `run.py` had its own key-presence check
  (`if not api_key and backend != "ollama"`) separate from `api_executor.py`'s equivalent, and it
  had not been updated for the new `"openai"` backend — the very first smoke test
  (`run.py ... --mode lmstudio-qwen3.5-9b --dry-run`) failed immediately with `"Mode ... has no
  key"` before any network call was attempted. Fixed by extending the tuple check to `("ollama",
  "openai")` in both files.
- `tests/env.json` (local, gitignored) written with 3 LM Studio mode entries
  (`lmstudio-qwen3.5-9b`, `lmstudio-mistral`, `lmstudio-phi4-mini`), `backend: "openai"`,
  `temperature: 0.2` on all three, `url: "http://localhost:1234"` (LM Studio's default port,
  unverified against a live server — see §8). **Model identifiers in this file are placeholders**
  (`"qwen3.5-9b-instruct"`, `"mistral-small-3-7b-instruct"`, `"phi-4-mini-instruct"`) and must be
  corrected to whatever exact string LM Studio reports at `GET /v1/models` once the real models
  are downloaded — explicitly flagged in an inline `_comment` field and in this log.
- End-to-end plumbing validated via `run.py --dry-run` against `w2-branching/release-gate` and
  then against the new `w2-branching/support-intake`/`i0-malformed`: both printed `Temp : 0.2`,
  `Backend : openai` correctly in the summary table, and failed with a clean
  `connection-error` (LM Studio not running/found on this machine — §8), never a Python
  exception. Nothing was written to disk (`--dry-run` respected in both runs).

### 5.8 Results bonification (`tests/results/BONIFICA-2026-08-03.md`)

Read-only analysis of the pre-existing `tests/results/index.jsonl` (575 rows, from a prior
session). No data modified. Findings, all traced to the actual `output.raw` field of the
underlying `RunRecord` JSON files (not inferred from `index.jsonl`'s flattened summary alone):

- **13 rows** carry `context: E1`, `runner_type: claude-code`, `env_realization: emulated` —
  produced by the manual `runner.py`, not the headless `executor.py`, meaning no tools were
  actually available despite the E1 label. All 13 are `w2-branching/release-gate` runs dated
  2026-06-04, models `claude-sonnet-4-6` (8 rows) and `claude-opus-4-8` (5 rows); full run-id
  list preserved in the bonifica report.
- `execution-error` (97 rows total) root-caused by model, for the three highest-volume models
  (which together account for 91/97 of all such rows):
  - `qwen3.5:9b` (52 errors, 35.6% error rate over 146 total runs): **100% attributable to the
    endpoint**, all from one LAN endpoint that was not the target machine — 47 timeouts,
    5 out-of-memory (`"model
    requires more system memory (7.9 GiB) than is available (6.2 GiB)"`, read verbatim from a
    sampled run record).
  - `qwen2.5-coder:7b` (21 errors, 42.9% error rate over 49 runs): **100%** the single message
    `"qwen2.5-coder:7b" does not support thinking` — `reasoning_budget: 1` was set for a model
    whose backend doesn't support extended thinking. A runner/config mismatch, not a model
    failure on the task.
  - `claude-haiku-4-5` (18 of its 83 runs errored): **100%** `max_tokens must be greater than
    thinking.budget_tokens` at `reasoning_budget: 8000`, context E1. Cross-checked against the
    *current* `api_executor.py` source: the present formula
    (`effective_max_tokens = max(DEFAULT_MAX_TOKENS, reasoning_budget + 1024)`) would give 9024
    for this exact input, which is `> 8000` and would not trigger this error — i.e. this is a
    **historical, already-fixed** bug, not a live one.
- Confirms directly from the data (not just from the card's stated suspicion) that the June
  timings did not come from the target machine: every `qwen3.5:9b` row (error or not) carries the
  `api_base_url` of a different LAN endpoint, while this session's `hostname` command, run on the
  machine actually executing this session, returned the target machine's name.

## 6. The manual-verification tool — three iterations, in order

The original plan (before this section was requested) called for a plain CSV
(`verification-sheet.csv`, produced by `sample_pool.py`, 300 rows). Delivered first, via
`SendUserFile`. Rejected by Gianni as unreadable at 300 rows in a spreadsheet, with an explicit
instruction to build something better ("se vuoi che io lo legga devi creare un html o un md ed
anche fatto bene").

**v1 — `tests/scripts/build_verification_html.py` (commit `4439b7c`)**: a self-contained, offline
HTML page embedding all 300 items' full text as inline JSON (no network calls, no external
assets). Filters (search, repo, review status), radio buttons for `bug/feature/question`
pre-selected on the NLBSE label, a "tolerant + alternative label" control, autosave to browser
`localStorage`, a JSON export button. A real bug was found and fixed before shipping: several
NLBSE issue bodies contain the literal substring `</script`, which would have prematurely closed
the page's `<script>` block regardless of it being inside a JS string — fixed with a regex
substitution (`</script` → `<\/script`, case-insensitive) applied to the embedded JSON before
inlining it, and verified afterward with `node --check` on the extracted script plus a literal
count confirming exactly one real `</script` in the output file.

**v2 — same script, commit `c0d14b9`**, after Gianni's three explicit requirements (fatigue is a
real constraint — no one reviews 300 issues well in one sitting, so the review effort needed
triage) plus a fourth, procedural proposal (a blind AI cross-check to flag likely-mislabeled
items, with final judgment always human):
1. Full text, no scroll, no truncation.
2. Top filter bar: review status (now including a dedicated "⚠ disagreement" filter), label
   type, product/repo.
3. All three judgments — NLBSE original, blind-AI, reviewer's own — kept permanently separate
   fields, shown side by side, never merged into one value.

## 7. The blind AI classification pass

Executed as **10 parallel `general-purpose` subagents**, each given a 30-item batch
(`item-001`–`item-030` through `item-271`–`item-300`, contiguous, non-overlapping, covering
exactly the 300-item pool) containing **only** `{id, repo, title, body}` — the NLBSE label was
never included in any agent's input file, by construction (a separate script generated the
batch files by stripping it before the agents saw anything). Each agent was instructed to
classify BUG/FEATURE/QUESTION from content alone, ignoring GitHub template boilerplate, and to
write `{id, ai_label, rationale}` (rationale: one short phrase) per item to its own output file.

Merge and validation, run against the concatenated 10 output files:
- **300/300 ids present, zero duplicates, zero missing, matched exactly against the expected
  `item-001`…`item-300` set.**
- **Zero invalid labels** (all values were one of `BUG`/`FEATURE`/`QUESTION`).
- Label distribution: **143 BUG / 105 FEATURE / 52 QUESTION**.
- **NLBSE/blind-AI disagreement: 83/300 items (27.7%)** — this is the number the v2 tool surfaces
  as the default triage queue via its "⚠ disagreement" filter.

Output written to `tests/data-local/ai-blind-labels.json` (local, gitignored — the `rationale`
field is derived commentary on third-party issue content, kept under the same no-redistribution
discipline as the source text itself, even though it doesn't quote it verbatim).

**Explicit methodological caveat, to carry into any publication**: this blind pass is used
*only* to direct human review attention to likely-noisy NLBSE labels — the recorded ground truth
remains Gianni's judgment alone, never the AI's. This preserves the non-circularity the manual
verification step exists for (an LLM's opinion never becomes the oracle an LLM-classification
campaign is later scored against). One narrower caveat was raised and accepted, not yet acted
on: if the campaign's demonstrative Claude ceiling-reference pass (protocol §5.3, "one
demonstrative pass ... reported separately") is run with the same model family used for this
blind classification, that one data point should be flagged in the writeup as not fully
independent of the ground-truth construction — the local models under primary test
(Qwen/Mistral/Phi) are unaffected by this caveat.

## 8. What remains blocked, and on what

- ~~**Item 2.6** (manual verification of the 300 items) — tooling and the 83-item priority
  queue are ready; the human judgment itself has not started as of this log.~~
  **Corrected 2026-08-24, and the correction matters in the direction of understating the work.**
  The judgment was made and is recorded in `pool-manifest.json`, item by item, as `verified`,
  `verified_label`, `tolerant` and `tolerant_alt_label`: 91 of the 300 carry `verified: true`, and
  — the point — **every one of the 65 items the experiment actually consumes is among them**, with
  the queues' `comprehension_ground_truth` following `verified_label` on 65 of 65. 23 of the 91
  verified labels were changed from the NLBSE label (25%), 9 were marked tolerant. The bullet
  below inherited this bullet's error and is corrected with it. What remains untouched is the
  other 209 of the 300, which no queue draws from.
  - **How the review was actually conducted**, since the artefacts on disk mislead about it. The
    instrument was `verification-sheet.html`, one item per card, showing the FULL body in English
    and its Italian translation side by side (`build_verification_html.py` renders `item.body` and
    `item.body_it`; bodies come from `pool-replication.json`, translations from
    `it-translations.json`), with the blind AI pass's label and rationale shown alongside as an
    attention director. Verdicts were held in `localStorage` and exported into `pool-manifest.json`
    as `verified_label`. Worth stating plainly: the reviewer saw MORE evidence than the models do,
    not less — the models read the English body alone.
  - `verification-sheet.csv` is a blank form that was never the input path: `corrected_label` and
    `tolerant` are empty on all 300 rows, and its `body_excerpt` column is capped at 2,000
    characters. Reading it as the record of the review is what produced the error corrected here.
    Read the manifest, not the sheet.
- ~~**2.7, 3.2, 3.3, 4.3** — mechanically complete but explicitly provisional: they use the raw
  NLBSE label as interim ground truth and must be regenerated once 2.6 lands.~~ Corrected
  2026-08-24 with the bullet above: they rest on `verified_label`, not on the raw NLBSE label, and
  there is no regeneration pending on this account.
- **LM Studio (plan items 0.1, 0.2, 8.1, 8.3)** — searched exhaustively on the target machine:
  no listening process on ports 1234/1235/8080, no installation directory found in a full `C:\`
  filesystem scan, no registry uninstall entry, no `winget` record. Config is written and its
  plumbing validated end-to-end via clean `connection-error` failures, but no real LM Studio
  server has been reached from this session, so no throughput measurement and no model-identifier
  verification against a live `/v1/models` response has happened.
- **`test_sol_lint.py`'s 2 pre-existing failures** (cart-total, task-router) — confirmed
  unrelated to this session's changes, not investigated further, not fixed.

## 9. Numbers worth quoting verbatim in a future writeup

Collected here because they were each computed once, from a specific command, at a specific
point in this session — re-deriving them later risks drift if the underlying data changes
(e.g. after 2.6 lands, the "provisional" queue/pool numbers below will change and must be
re-quoted from a fresh run, not copied from here).

| Quantity | Value | Source |
|---|---|---|
| NLBSE test-set rows | 1500 | `csv.DictReader` count on the downloaded file |
| Pool size / MAIN / REPLICATION | 300 / 150 / 150 | `sample_pool.py` output |
| Queue generation attempts / accepted | 25 / 10 | `build_queues.py` stdout |
| Per-queue processed-item counts | 9,6,10,11,9,11,8,6,6,8 | `build_queues.py` stdout |
| R1 tests, checker-related | 34 collected, 34 passing (22 pre-existing + 12 new) | `pytest --collect-only` + `pytest -q` |
| R1 tests, repo-wide | 50 collected, 48 passing, 2 pre-existing failures | `pytest tests/toolchain -q` |
| `execution-error` rows explained | 91/97 (94%), 100% infra/config, 0% model capability | manual trace of `output.raw` per row, §5.8 |
| E1-mislabeled rows found | 13/575 | index.jsonl scan, §5.8 |
| P1 token savings (provisional pool) | ~509 tokens/item avg, 46/150 truncated | `preprocess_p1.py` stdout |
| Blind AI classification | 300/300 valid, 143/105/52 BUG/FEATURE/QUESTION, 83 disagreements with NLBSE (27.7%) | 10-agent merge + validation, §7 |

---

*This log was written from live command output and file inspection during the session it
describes, before any context compaction. Where a number could not be directly re-verified at
write time without re-running work already done, this is stated explicitly rather than
re-derived from memory.*
