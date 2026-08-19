"""
R1 toolchain tests for sol-lint.py — the deterministic half of the testing rings.

These are ordinary, fast, fully deterministic unit tests: a tiny SOL document goes in,
a known set of finding codes comes out. No model, no harness, no network. This is the
cheapest ring (R1) and the foundation every other ring depends on — see
doc/testing-strategy.md.

Run from the repo root:

    python3 -m pytest tests/toolchain -q
"""

import importlib.util
import json
import re as _re
import subprocess
import sys
from pathlib import Path

# --------------------------------------------------------------------------- #
# Load the linter. Its filename is hyphenated and lives under .claude/, so we
# import it by path rather than with a normal `import`.
# --------------------------------------------------------------------------- #
REPO_ROOT = Path(__file__).resolve().parents[2]
LINT_PATH = REPO_ROOT / ".claude" / "skills" / "sol" / "scripts" / "sol-lint.py"

_spec = importlib.util.spec_from_file_location("sol_lint", LINT_PATH)
sol_lint = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sol_lint)


# --------------------------------------------------------------------------- #
# Helpers — keep each test a one-line assertion about which codes are raised.
# --------------------------------------------------------------------------- #
def lint(doc):
    return sol_lint.SolLinter().lint(doc)


def codes(doc, severity=None):
    """Set of finding codes for `doc`, optionally filtered by severity."""
    return {f.code for f in lint(doc) if severity is None or f.severity == severity}


def errors(doc):
    return codes(doc, "ERROR")


def warnings(doc):
    return codes(doc, "WARN")


# A minimal, well-formed process used as the baseline several tests tweak.
def minimal_process(**overrides):
    doc = {
        "name": "t",
        "version": "1.0",
        "description": "d",
        "ROUTINE": [{"TODO": "do a single thing"}],
    }
    doc.update(overrides)
    return doc


# --------------------------------------------------------------------------- #
# Clean baseline
# --------------------------------------------------------------------------- #
def test_minimal_process_is_clean():
    assert lint(minimal_process()) == []


# --------------------------------------------------------------------------- #
# ERROR-level deterministic defects
# --------------------------------------------------------------------------- #
def test_single_brace_placeholder_is_error():
    doc = minimal_process(ROUTINE=[{"RUN": "cat {path}"}])
    assert "single-brace" in errors(doc)


def test_double_brace_placeholder_is_accepted():
    doc = minimal_process(
        accepts={"path": {"required": True, "desc": "input path"}},
        ROUTINE=[{"RUN": "cat {{path}}"}],
    )
    assert "single-brace" not in codes(doc)


def test_missing_routine_is_error():
    assert "root-routine" in errors({"name": "t", "version": "1.0", "description": "d"})


def test_unresolved_call_is_error():
    doc = minimal_process(ROUTINE=[{"CALL": "nope"}])
    assert "call-unresolved" in errors(doc)


def test_resolved_call_is_clean():
    doc = minimal_process(
        ROUTINE=[
            {"SUB": {"name": "greet", "ROUTINE": [{"TODO": "say hi"}]}},
            {"CALL": "greet"},
        ]
    )
    assert "call-unresolved" not in codes(doc)


def test_multi_construct_instruction_is_error():
    doc = minimal_process(ROUTINE=[{"TODO": "a", "RUN": "b"}])
    assert "multi-construct" in errors(doc)


def test_return_object_keys_must_match_structured_returns():
    doc = minimal_process(
        returns={"verdict": {"required": True}},
        ROUTINE=[{"RETURN": {"wrong_key": "x"}}],
    )
    assert "return-shape-mismatch" in errors(doc)


def test_return_object_with_matching_keys_is_clean():
    doc = minimal_process(
        returns={"verdict": {"required": True}},
        ROUTINE=[{"RETURN": {"verdict": "READY"}}],
    )
    assert "return-shape-mismatch" not in codes(doc)


# --------------------------------------------------------------------------- #
# WARN-level heuristic smells
# --------------------------------------------------------------------------- #
def test_buried_control_flow_in_todo_warns():
    doc = minimal_process(ROUTINE=[{"TODO": "if the file exists, delete it"}])
    assert "buried-flow" in warnings(doc)


def test_sub_with_contract_warns():
    doc = minimal_process(
        ROUTINE=[{"SUB": {"name": "s", "accepts": "x", "ROUTINE": [{"TODO": "t"}]}}]
    )
    assert "sub-contract" in warnings(doc)


# --------------------------------------------------------------------------- #
# Tie R1 to R2: the real fixture must lint clean through the same engine.
# --------------------------------------------------------------------------- #
def _load_sol_from_md(path):
    import yaml
    text = path.read_text(encoding="utf-8")
    m = _re.match(r'^---\n(.*?)\n---\n(.*)', text, _re.DOTALL)
    meta = yaml.safe_load(m.group(1)) if m else {}
    body = m.group(2) if m else text
    blocks = _re.findall(r'```json\n(.*?)```', body, _re.DOTALL)
    doc = json.loads(blocks[-1])
    for k in ('name', 'version', 'description', 'accepts', 'returns'):
        if k in meta:
            doc[k] = meta[k]
    return doc


def test_release_gate_fixture_lints_clean():
    fixture = (
        REPO_ROOT / "tests" / "fixtures" / "w2-branching" / "release-gate" / "release-gate.md"
    )
    doc = _load_sol_from_md(fixture)
    assert lint(doc) == []


def test_cart_total_fixture_lints_clean():
    fixture = (
        REPO_ROOT / "tests" / "fixtures" / "w1-linear" / "cart-total" / "cart-total.md"
    )
    doc = _load_sol_from_md(fixture)
    assert lint(doc) == []


def test_task_router_fixture_lints_clean():
    fixture = (
        REPO_ROOT / "tests" / "fixtures" / "w3-multi-call" / "task-router" / "task-router.md"
    )
    doc = _load_sol_from_md(fixture)
    assert lint(doc) == []


# --------------------------------------------------------------------------- #
# CLI contract: exit code is the CI gate (0 clean, 1 on ERROR).
# --------------------------------------------------------------------------- #
def _run_cli(tmp_path, doc):
    p = tmp_path / "doc.json"
    p.write_text(json.dumps(doc), encoding="utf-8")
    return subprocess.run(
        [sys.executable, str(LINT_PATH), str(p)],
        capture_output=True, text=True,
    )


def test_cli_exits_zero_on_clean(tmp_path):
    assert _run_cli(tmp_path, minimal_process()).returncode == 0


def test_cli_exits_one_on_error(tmp_path):
    assert _run_cli(tmp_path, minimal_process(ROUTINE=[{"RUN": "cat {x}"}])).returncode == 1
