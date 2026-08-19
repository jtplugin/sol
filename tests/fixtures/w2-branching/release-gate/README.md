# Fixture: `release-gate` (W2 — branching)

The reference fixture for **control-flow fidelity**: does the agent take the branch the process
says it should, given the input?

## Intent

A release-gate classifier. The process reads a release record (real state, from a file) and
returns exactly one verdict:

| Condition (evaluated in order) | Verdict |
|---|---|
| `blocking_bugs > 0` | `BLOCKED` |
| `coverage < 80` | `INSUFFICIENT_COVERAGE` |
| `security_review != "passed"` | `SECURITY_HOLD` |
| otherwise | `READY` |
| (input invalid / unreadable) | `INVALID_INPUT` — the `accepts` guard |

## Why this is a faithful fixture

- **Determined path.** Each staged input under `inputs/` is built so that **exactly one**
  `WHEN` condition is true (the others are made false), so the branch to take is unambiguous even
  though the conditions could overlap in general. See `expectations.json` for the input→branch map.
- **Single concern.** Pure branch selection. The only tool is reading a tiny fixed file; there
  is no quality-variable artifact to muddy the fidelity signal. Loop-coverage and `SUB`/`CALL`
  are *separate* W2 fixtures by design.
- **Self-describing.** `expectations.json` carries the expected verdict, the branch, and the
  oracle for every input.
- **Detectable wrong path.** The five verdicts are distinct strings, so the wrong branch is
  visible in `returns.verdict`.

## What it exercises

- `WHEN` with a shared `else`, over **real state** read with `RUN` — this is what lifts it from
  a W0 inline transform to a W2 process.
- An `accepts` guard at the top of the routine with a defined, emitted violation path
  (`RETURN { "verdict": "INVALID_INPUT" }` — never silent, never `HALT`).
- A structured `returns` contract that `RETURN` echoes on every branch.

## How it is run (R3)

The runner stages one `inputs/*.json` at the `record_path` the process is invoked with, executes
`release-gate.json`, and the checker compares the returned `verdict` to the case's
`expected_verdict` in `expectations.json`. Fidelity is scored as a rate over N runs per input
(see `doc/testing-sol.md`). This fixture is meaningful on E1 and above.

Before it is ever run, it must lint clean (R2):

```bash
python3 ../../../../.claude/skills/sol/scripts/sol-lint.py release-gate.json
```
