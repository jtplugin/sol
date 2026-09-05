# w2-branching/support-routing-notrace

The **untracked arm** of the A/B registered in §10 of `doc/experiment-minimum-context.md`
("Whether the tracking requirement itself competes with the primary task"). This fixture is
`../support-routing` with the trace removed and nothing else changed. It exists to answer one
question: does carrying the `EVAL:`/`BRANCH:` lines cost the returned answer?

**Prediction, registered in advance (2026-08-24, before any run of this arm):** if the
tracking competes, this arm scores HIGHER quality than `support-routing`.

## The treatment, exactly

`support-routing-notrace.md` differs from `../support-routing/support-routing.md` in four
places and no others (verify with `git diff --no-index` on the pair):

1. frontmatter `name`: `fixture-w2-support-routing-notrace`;
2. frontmatter `description`: the closing sentence about EVAL/BRANCH scoreability is gone —
   nothing is added in its place, so neither arm's prompt names the experiment;
3. the eight `Emit verbatim` TODO steps (one guard BRANCH, one EVAL in `classify-request`,
   six branch BRANCHes) are removed;
4. the build-result TODO no longer says "The EVAL and BRANCH lines are not part of it" —
   there are no such lines to disclaim.

The renderings follow from the document, exactly as they do for every fixture: L0–L4 at run
time from the SOL script, `support-routing-notrace-prose-mechanical.md` from
`tests/scripts/build_prose_mechanical.py`, `support-routing-notrace-prose-generated.md` from
one pass of Claude Opus 5 under the frozen prompt `tests/fixtures/PROSE-VARIANT-PROMPT.md`
(§8.1 item 6 procedure). The manipulation therefore reaches all seven renderings, which is
what makes the A/B a comparison between treatments rather than between documents.

## What is copied, not written

`catalog.json`, `items-manifest.json`, `reference.py`, `inputs/` are byte-for-byte copies of
`../support-routing`'s. `expectations.json` is the same file with its `fixture` field
renamed; `expected_sequence` and `comprehension_ground_truth` are retained even though no run
of this arm can be scored against them — deleting them would make the two expectation files
differ by more than the treatment. If the source fixture's inputs or expectations are ever
regenerated, regenerate this copy in the same commit or the A/B is off.

## Scoring — what this arm can and cannot show

The runs carry no trace by construction. `traced` is False everywhere, and comprehension,
conditional fidelity and sequence are structurally unobservable — this is the sense of "the
untracked arm cannot be observed, only run" (§12, 2026-08-24). Fidelity, which reads the
trace, is not meaningful on this arm. **The endpoint of the A/B is `quality` alone**: the
returned object against `expected_output`, same oracle, same checker, no modification to
either.

## Running it

```
python tests/runner/campaign.py smoke --block routing-notrace   # 210 stratified rows
python tests/runner/campaign.py plan  --block routing-notrace   # 1680 rows
python tests/runner/campaign.py run   --block routing-notrace
```

Same grid as `routing` (20 requests × 2 reps × 7 renderings × 6 modes), same results root,
same index; `fixture_id` separates the arms, as it separates every block.

Since 2026-08-31 this fixture also carries the campaign's **frontier reference cell** — the same
documents through `claude -p --model claude-haiku-4-5` instead of a local llama-server, as a term
of comparison. It is a block of its own, on a cell table of its own, and it changes nothing above:

```
python tests/runner/campaign.py smoke --block routing-notrace-haiku   # 35 stratified rows
python tests/runner/campaign.py plan  --block routing-notrace-haiku   # 280 rows
python tests/runner/campaign.py run   --block routing-notrace-haiku
```

20 requests × 2 reps × 7 renderings × 1 mode. Same results root and index as every other
block; `mode` (`claude-code-haiku`) and `runner_type` (`claude-code`) separate it from the six
local cells, which are untouched. Registered in §5.3 and §12 of the protocol, and deliberately
outside §9's outcomes: it is a scale for the numbers, not a sixth family.

## Everything else

Process, data layout, request composition, regeneration, lint: see
`../support-routing/README.md`. This directory adds no design of its own — that is the point.
