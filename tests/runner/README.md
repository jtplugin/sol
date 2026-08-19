# Runner — the R3 execution core

The concrete implementation of Ring R3 from
[`doc/testing-runners.md`](../../doc/testing-runners.md).
Three modules, all pure Python, no external model required:

| File | What it does |
|---|---|
| `schema.py` | `RunRecord` and `ScoreRecord` dataclasses — the normalized I/O of the whole pipeline |
| `checker.py` | `check(record, expectations) → ScoreRecord` — scores fidelity, quality, efficiency, and degradation mode |
| `runner.py` | Manual executor CLI — stages the input, prompts for the returned payload, writes the record, calls the checker |
| `executor.py` | Headless executor CLI — stages the input, drives `claude -p`, parses trace + payload, writes the record, calls the checker. The automated path for R3 matrices. |

## Running the headless executor (the R3 matrix path)

```bash
python3 tests/runner/executor.py \
  --fixture w2-branching/release-gate \
  --all-inputs \
  --context E1 \
  --model claude-opus-4-8 \
  --runs 5
```

`--input <id>` runs a single input; `--all-inputs` sweeps every file in the fixture's
`inputs/`. `--runs N` repeats each input N times — that is how a distribution is built.

**`--dry-run`** executes and scores but writes nothing to disk. Use it to probe a new
input before committing results, and **always** while iterating on a fresh boundary case.

> **Probe discipline (read this before adding a new input).** An input with no matching case
> in `expectations.json` is *silently mis-scored*: the checker compares the verdict against
> `None`, so quality reads `wrong-value` for any output, including the correct one. Order of
> operations: (1) add the case with its expected verdict, (2) `--dry-run` to check the score,
> (3) `--runs N` for the real matrix. The executor warns up front when an input has no case.
> Full account in [`doc/testing-runners.md` §2.1](../../doc/testing-runners.md).

## Running a test manually

```bash
python3 tests/runner/runner.py \
  --fixture w2-branching/release-gate \
  --input i1-blocked \
  --context E1 \
  --model <model-id>
```

The runner prints the SOL document and the path to the staged input, then waits
for you (or an agent session) to execute the process and paste back the returned
JSON payload. It writes the `RunRecord` and `ScoreRecord` to `tests/results/`
(gitignored) and appends one line to `tests/results/index.jsonl`.

To run all four inputs in one go:

```bash
for i in i1-blocked i2-insufficient-coverage i3-security-hold i4-ready; do
  python3 tests/runner/runner.py \
    --fixture w2-branching/release-gate \
    --input $i --context E1 --model <model-id>
done
```

## Degradation-mode taxonomy

When an execution falls short, the checker labels *how*:

| Mode | Meaning |
|---|---|
| `none` | correct — no degradation |
| `wrong-value` | a valid verdict, but the wrong one |
| `no-output` | no returned payload |
| `refused` | agent explicitly declined to execute |
| `garbled-output` | payload present but missing/malformed verdict key |
| `execution-error` | run failed (`status: error`) |
| `na` | was not attempted (`status: na`) |

## Results layout

```
tests/results/
  <fixture>/<context>/<model>/<spec-version>/
    <run-id>.json          ← RunRecord
    <run-id>.score.json    ← ScoreRecord
  index.jsonl              ← one row per run, all fields for aggregation
```

`tests/results/` is an append-only store, now versioned in git so the distributional
snapshots behind the analysis are reproducible. `--dry-run` writes nothing, for probing.
The checker is fully covered by R1 unit tests in `tests/toolchain/test_checker.py`.
