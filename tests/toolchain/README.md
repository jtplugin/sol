# Toolchain tests (R1)

Deterministic unit tests for the Python tools *around* SOL — the innermost, cheapest ring of
the [testing strategy](../../doc/testing-strategy.md). Input goes in, a known result comes out:
no model, no harness, no network. This ring runs on every commit and is the foundation the
other rings rest on.

## What is covered

- [`test_sol_lint.py`](test_sol_lint.py) — `sol-lint.py`: each ERROR code (single-brace
  placeholder, missing `ROUTINE`, unresolved `CALL`, multi-construct, `RETURN`/`returns` shape
  mismatch), representative WARN smells (buried control flow, `SUB` with a contract), the CLI
  exit-code contract (0 clean / 1 on ERROR), and a tie to R2 (the real `release-gate` fixture
  lints clean through the same engine).
- [`test_checker.py`](test_checker.py) — `checker.py`: all quality outcomes (pass / fail /
  not_checkable), each degradation mode (none, wrong-branch, no-output, refused,
  garbled-output, execution-error, na), fidelity propagation, score metadata, `_find_case`
  normalization, and a tie to the real `expectations.json`.

_To come: `sol2mermaid.py` and `sol2drawio.py` (the converters produce well-formed output and
do not crash on every construct)._

## Running

```bash
python3 -m pytest tests/toolchain -q
```

Requires `pytest` (`pip install pytest`). The linter itself is imported by path, since its
filename is hyphenated and lives under `.claude/skills/sol/scripts/`.
