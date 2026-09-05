# tests/results-main/

MAIN's results: the campaign of `doc/experiment-minimum-context.md`, driven by
`tests/runner/campaign.py run`. Records, scores, `index.jsonl`, `campaign-plan.json`
and the dashboard built from them all live here, and all of it is tracked in git in the
working repository — without it a fresh clone can neither rerun nor verify MAIN.

Separate from `tests/results/` on purpose. That directory holds the pilot and the
earlier fixture work — measured on other fixtures, other models, and code that has
since changed; §8.4 of the protocol already ruled it unusable as a baseline as-is.
Keeping the two apart means nothing has to be filtered out at analysis time, and the
campaign's dashboard shows the campaign and nothing else.

## What is published, and what is not

**Only `index.csv` is published.** Every other file here records the prompt as it was
administered to the model, and for the `support-intake` and `support-routing` fixtures that
prompt embeds the queue of issue reports — third-party text, not ours to redistribute. The
same goes for the score files: on 59 of 5431 the model echoed a report back into its answer,
and the oracle stored the answer.

`index.csv` carries no free text: identifiers, the cell's configuration, the verdicts and the
rates. It is published because the analysis checks itself against it (chapter 1.8 of
`report/analysis/01_fatti.ipynb` asks whether the index agrees with the raw scores, and finds
17 runs where it does not).

The published analysis reads [`report/analysis/tidy.csv`](../../report/analysis/tidy.csv) —
the same 5431 runs as identifiers and measures, with the continuous rates the index drops.
Every number in the fact sheet and in the articles recomputes from it.

To reconstruct the raw layer you need the issue dataset itself: the fixture ships
dehydrated, with references, labels and hashes, and `tests/scripts/hydrate.py` rebuilds the
inputs from the source.

Read it with:

    python scripts/dashboard.py            # needs index.jsonl, i.e. the working repository
