# tests/results/

The pilot and the earlier fixture work: 576 runs from June–August 2026, on fixtures and
models the main campaign no longer uses, and on code that has since changed. §8.4 of
`doc/experiment-minimum-context.md` rules this set unusable as a baseline for the campaign
as it stands, which is why the campaign records live apart, in `tests/results-main/`.

Kept because it is the record of how the instrument behaved before it was trusted, and
because `results-audit-2026-08-03.md` is read against it.

## What is published, and what is not

The records and the index are published. Two things are not:

- **The administered prompt on `support-intake` runs.** `trace.request_messages` held the
  queue as the model received it, hence the issue reports themselves. The field is emptied
  on publication and carries a note saying so; everything else in those records — the
  configuration, the trace, the answer, the usage — is ours and is intact.
- **`dashboard.html` and `assets/`.** The dashboard is a view, not data: it embeds each
  run's staged input so a detail panel can show what the model was asked, and for the queue
  fixtures that input is the issue reports. It reads them from the fixture tree rather than
  from the records, so emptying the records does not clean it.

Rebuild the dashboard yourself once the fixture is hydrated
(`tests/scripts/hydrate.py`, plus the source dataset):

    python scripts/dashboard.py --index tests/results/index.jsonl
