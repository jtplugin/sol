# w2-branching/support-intake

W2 branching fixture with **state accumulation across iterations**, built for the
minimum-context campaign (`doc/experiment-minimum-context.md`). Triages a queue of
~15 support items against a finite hour budget in a single invocation.

## Why this fixture exists

Every other fixture in the corpus (`release-gate`, `task-router`, `cart-total`, ...) has the
same degenerate shape: read one record, take one decision, return one verdict. That yields a
binary fidelity oracle — it saturates at 100% on strong models and leaves `REPEAT`,
cross-iteration state, repeated `SUB` invocation, and `HALT`/early-exit entirely untested.

`support-intake` fixes this: the **same item, in a different position in the queue, takes a
different branch**, because the hour accumulator has changed. A model cannot pass by
classifying items independently — it must actually execute the process. That is the definition
of "self-regulation" this campaign is about.

## The process

```
SUB classify-request → {product: P1..P5 | UNKNOWN, intent: BUG | FEATURE | QUESTION}
SUB estimate-effort  → deterministic lookup, intent × product → hours
SUB check-budget     → FITS | NOFIT

guard: malformed input → INVALID_INPUT

REPEAT foreach item in queue:
    CALL classify-request
    IF product == UNKNOWN → NEEDS_INFO
    ELSE:
        CALL estimate-effort
        CALL check-budget
        WHEN:
          intent == BUG and NOFIT → ESCALATE, record halted_at, RETURN (exit loop)
          FITS                    → ASSIGN, budget -= hours
          else                    → DEFER

RETURN { status, items: [{id, product, intent, hours, action}], remaining_hours, halted_at }
```

`RETURN` is used both for the malformed-input guard and for the ESCALATE-and-stop path (not a
literal SOL `HALT`) — `HALT` carries no structured payload, and the checker needs the
accumulated `items`/`remaining_hours`/`halted_at` to score conditional fidelity. See the design
note at the top of `support-intake.md`'s SOL script and `doc/experiment-minimum-context.md`.

## The three-score oracle

Per `doc/experiment-minimum-context.md` SS6.2, single-concern is deliberately broken here because
the fixture introduces genuine semantic comprehension (product/intent classification). The
checker decomposes this into three separately-scoreable dimensions, all computed by
`tests/runner/checker.py`'s sequence-oracle path (triggered when a case carries
`expected_sequence`):

- **Comprehension** — `(product, intent)` extracted from `EVAL:` trace lines vs. the verified
  ground truth, per item. `score.comprehension.rate`.
- **Conditional fidelity** — `reference.py`'s `run_queue()` re-run using the MODEL's OWN
  classifications (not ground truth), compared against what it actually did. Isolates pure
  control-flow correctness from comprehension errors. `score.fidelity.conditional_rate`.
- **End-to-end outcome** — the full returned payload vs. ground truth (the existing
  `quality` check, unmodified).

Plus **sequence fidelity** (`score.fidelity.sequence_rate`) — the ground-truth version of
conditional fidelity, useful as a sanity check but not the primary campaign metric (conditional
fidelity is, since it isolates what the campaign is actually about).

## Trace format (per item, not per run)

Unlike `release-gate`/`task-router`, which emit ONE `BRANCH:` line per run, this fixture emits a
pair of trace lines **per queue item** (so a run can have up to ~15 EVAL/BRANCH pairs):

```
[fixture-w2-support-intake][main] EVAL: item=<id> product=<P1..P5|UNKNOWN> intent=<BUG|FEATURE|QUESTION>
[fixture-w2-support-intake][main] BRANCH: item=<id> action=<ASSIGN|DEFER|NEEDS_INFO|ESCALATE> remaining=<n>
```

## Bundle contents

| File | Committed? | Contents |
|---|---|---|
| `support-intake.md` | yes | SOL document (frontmatter + ROUTINE) |
| `catalog.json` | yes | 5 product personas (repo identity hidden) + intent×product→hours table |
| `reference.py` | yes | the oracle: `run_queue(items, budget_hours, hours_table)` |
| `pool-manifest.json` | yes | 300 pool items: id/repo/label/hashes — **zero third-party text** |
| `queue-criterion.json` | yes | frozen structural acceptance criterion (SS4.4) |
| `queues-manifest.json` | yes | K=10 queues by item id — **zero third-party text** |
| `expectations.json` | yes | malformed case + one case per queue (`expected_sequence`, `expected_output`, `comprehension_ground_truth`, embedded `catalog`) |
| `inputs/i0-malformed.json` | yes | the one structural case outside the K queues |
| `inputs/queue-01..10.json` | **no, gitignored** | hydrated queue text — regenerate with `tests/scripts/hydrate.py --mode queues` |

## Status (as of this build)

`pool-manifest.json`/`queues-manifest.json` are **provisional**: they use the raw NLBSE labels
as ground truth. The manual verification of the 300-item pool has not
run yet. Once it does, re-run `tests/scripts/build_queues.py` — same frozen seeds, so the K
queues stay the same 15-item draws, only the ground-truth labels used to compute
`expected_sequence`/`comprehension_ground_truth` may change.

## Lint

```bash
python3 .claude/skills/sol/scripts/sol-lint.py tests/fixtures/w2-branching/support-intake/support-intake.md
```

0 errors, 4 warnings (3 root-meta — expected, same as every fixture in this corpus, the
frontmatter fields aren't in the JSON fence; 1 buried-flow heuristic false positive on the
`classify-request` SUB's UNKNOWN fallback wording — reviewed, not lifted into a construct on
purpose, see the design note in `support-intake.md`).
