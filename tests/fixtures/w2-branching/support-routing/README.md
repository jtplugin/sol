# w2-branching/support-routing

W2 branching fixture in **per-item delivery**: one support request per invocation, decided
against a world state the oracle supplies. Added 2026-08-23 for the minimum-context campaign
(`doc/experiment-minimum-context.md` §4.5, §7.6), as a second block of the same experiment
rather than a separate one.

## Why this fixture exists

`support-intake` hands the model a queue of fifteen items and asks for the whole triage in one
invocation. That is a real shape, and it is not the deployed one. A process of this kind is
invoked once per message: an intake worker is handed one request, applies the standing
instructions, returns a decision, and is invoked again for the next — with no history, no
retrieval, and nothing but the process document to work from.

Per-item delivery also buys something the queue could not. Fifteen items scored together produce
one number; twenty items scored apart produce twenty independent trials, and tell you **which**
request a model gets wrong instead of only that a queue came out at 0.6.

## What it inherits and what it adds

Inherited unchanged from `support-intake`, so the two stay comparable: the item pool, the five
product personas, the `hours_table`, the `classify-request` step, the hour budget, and the
`ESCALATE` rule for a `BUG` that does not fit.

Added: a routing decision over three teams, expressed as **set membership rather than
arithmetic**. Local models fail arithmetic fixtures on the arithmetic instead of on the control
flow, so the second decision axis deliberately involves no counting.

| team | accepts | backs up |
|---|---|---|
| T1 | P1, P2 | P3 |
| T2 | P3 | P2, P5 |
| T3 | P5 | — |

P4 appears in no team's `accepts` and no team's `backs_up`. It is the structural gap, and it
produces an action `support-intake` has no equivalent of: **`UNASSIGNED`** — nobody can ever take
this — as against `DEFER` — someone could, but not in this state. A model that collapses the two
has made a specific, observable mistake rather than a generic wrong answer.

Team load is a **state, not a counter**:

| state | takes |
|---|---|
| `OPEN` | anything it accepts, and anything it backs up |
| `LIMITED` | a request for a product it accepts, **only when the intent is `BUG`** |
| `CLOSED` | nothing |

`LIMITED` is what makes the same product route to two different teams depending on the request's
intent. It buys back, with no accumulator and no arithmetic, the property that made
`support-intake` non-degenerate: **the decision cannot be reached from the request alone.**

## The process

```
guard: malformed input → INVALID_INPUT

classify-request → {product: P1..P5 | UNKNOWN, intent: BUG | FEATURE | QUESTION}

  product == UNKNOWN                        → NEEDS_INFO
  product accepted by no team               → UNASSIGNED
  else:
    estimate-effort  (deterministic lookup, product × intent → hours)
    check-budget     (hours vs remaining_hours)
      intent == BUG and NOFIT                → ESCALATE
      NOFIT                                  → DEFER
      else pick-team:
        owner OPEN                           → ASSIGN to owner
        owner LIMITED and intent == BUG      → ASSIGN to owner
        the product's backup team, if OPEN   → ASSIGN to backup
        otherwise                            → DEFER

RETURN { status, item: {id, product, intent, hours, team, action}, remaining_hours }
```

**The trap is precedence, not calculation.** A `BUG` whose owning team is `LIMITED` while a
backup team is `OPEN` belongs to the owner. A model that reasons *there is a team with room, use
that one* answers a plausible question that was not asked, and gets the same request right when
its intent is `FEATURE`. That is what tells precedence apart from luck.

No product is backed up by more than one team, so the fixture states no rule for choosing among
backups: a rule that cannot fire is prompt weight with no behaviour behind it. Two tests hold
that invariant, because adding a second backup would make the fixture ambiguous without anything
failing.

## Where each piece of data lives

**Fixed → the document**, following `support-intake`, whose product catalogue is a section of its
SOL script and is therefore carried by all seven renderings: the capability matrix and the
`hours_table`.

**Mutable → the payload**: the request, `remaining_hours`, and the three team states.

**The payload's world state is computed by the oracle, never chained from the model's own
previous answer.** Chaining would restore the dependence per-item delivery exists to remove: a
wrong decision on request 3 hands request 4 a false world, and twenty independent trials collapse
into one observation. What chaining would have measured is recoverable without paying for it —
the first request whose action diverges from the oracle is the point at which a chained
deployment would have left the rails.

## Scoring

Same three scores as `support-intake` (protocol §6.2), same code. What changed in the checker is
that the compared label carries the team:

```
[fixture-w2-support-routing][main] EVAL: item=<id> product=<P1..P5|UNKNOWN> intent=<BUG|FEATURE|QUESTION>
[fixture-w2-support-routing][main] BRANCH: item=<id> action=<ASSIGN|DEFER|NEEDS_INFO|ESCALATE|UNASSIGNED> team=<T1|T2|T3|-> remaining=<n>
```

`team=` is optional in the parser, so `support-intake`'s lines produce exactly the labels they
always did — verified by re-scoring every record on disk, not assumed. Which control flow the
conditional-fidelity pass re-runs is named by the top-level `oracle` key of `expectations.json`
(`route_item` here, `run_queue` by default): an unknown name raises rather than scoring quietly
against the wrong algorithm.

## The twenty requests

Stratified, not sampled — a single draw over the pool lands three quarters of its mass on the easy
branch. Every stratum has at least two members and the precedence trap has three. Excluded:
unverified pool items (their ground truth would be the raw NLBSE label, and the whole case turns
on it) and `tolerant` items (they admit two intents, and intent decides both the hours and
whether a `LIMITED` owner takes the request).

Two cases are written rather than drawn and both are declared synthetic in the manifest. No item
from five real repositories is unrecognisable against five personas built from those same
repositories, so without an off-catalog request `NEEDS_INFO` would be reachable only through a
model's mistake — a stratum nothing can sample. The malformed payload is structural and sits
outside the twenty.

Composition: 10 `ASSIGN`, 5 `DEFER`, 2 `ESCALATE`, 2 `UNASSIGNED`, 1 `NEEDS_INFO`. `ASSIGN`
dominates because routing only happens on `ASSIGN`, and routing is what this fixture measures.

## Bundle contents

| File | Contents |
|---|---|
| `support-routing.md` | SOL document (frontmatter + catalog + team table + ROUTINE) |
| `support-routing-prose-mechanical.md` | rendered by `tests/scripts/build_prose_mechanical.py` |
| `support-routing-prose-generated.md` | rendered by a model in one pass from `../PROSE-VARIANT-PROMPT.md` |
| `catalog.json` | personas, repo mapping, `hours_table`, team matrix. No `budget_hours`: the budget arrives per request |
| `reference.py` | the oracle: `route_item(item, remaining_hours, team_states, catalog)` |
| `items-manifest.json` | the 20 requests: stratum, pool item id, world state, expected action and team |
| `expectations.json` | one case per request plus the malformed one; `oracle: route_item` |
| `inputs/r01..r20.json` | staged requests — regenerate with `tests/scripts/hydrate.py --mode requests` |
| `inputs/r00-malformed.json` | the structural case, written by hand |

## Regenerating

```bash
python tests/scripts/build_requests.py            # manifest + expectations (frozen seed)
python tests/scripts/hydrate.py --mode requests   # staged inputs
python tests/scripts/build_prose_mechanical.py    # the deterministic prose rendering
```

`build_requests.py --check` recomputes and reports drift without writing. The prose documents are
never hand-patched: a defect in one is fixed in its generator and the documents are regenerated
(protocol §8.1 item 6).

## Running it

```bash
python tests/runner/campaign.py plan --block routing
python tests/runner/campaign.py run  --block routing
```

Results land in MAIN's root and index; the plan is `campaign-plan-routing.json` beside MAIN's.
The block runs **after** MAIN and not beside it: one `llama-server` at `n_parallel: 1` holds the
GPU, so what forbids the overlap is the slot, not the files.

## Status

**Smoke-tested 2026-08-24; the full block has not run.** The pre-flight was action-stratified
across all seven renderings and all six cells — 210 runs, 57 minutes of GPU, zero errors, zero
`skipped-window`, every one of the five actions exercised exactly 42 times. It answered the
question the dry checks could not: models reading these renderings do emit the trace lines. The
failure that cost MAIN 69 rows on 2026-08-23 was of exactly that kind, invisible to every check
that does not involve a model.

What the smoke also showed, and the reason this fixture exists: `quality` 30.5% here against MAIN's
1.54%. Five of the six cells that sat on the floor on `support-intake` score above it here —
`ministral-8b` 57.1%, `gemma-4-12b` 37.1%, `granite-4.1-8b` 34.3%. MAIN's near-zero is dominated by
a barrier this fixture does not have: the halt at the end of the budget, which §9.1 of the protocol
measures separately. Read that section before reading these two numbers as one comparison — routing
is a shorter task, not `support-intake` with the halt removed.

Everything else remains verified dry: the SOL document lints clean, the oracle agrees with the
checker's copy over the whole state space, the twenty requests regenerate from their seed, and the
staged inputs pass their alignment check.

The probe is deliberately deferred rather than run on the Anthropic API: a frontier model
emitting the trace says little about a quantised 9B, which is the population this campaign is
about, and the local slot is held by MAIN. First real run: the routing block, after MAIN ends.

## Lint

```bash
python .claude/skills/sol/scripts/sol-lint.py tests/fixtures/w2-branching/support-routing/support-routing.md
```

0 errors, 3 warnings — the three root-meta warnings every fixture in this corpus carries (the
frontmatter fields are not inside the JSON fence).
