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


# A RETURN whose whole value is one named placeholder points at an object built
# earlier in the script. Decision di Gianni (2026-08-20): costruire l'oggetto
# secondo il contratto e poi restituirne il riferimento non e' un difetto, e' la
# forma buona -- tiene la shape in un passo nominato invece di inlinearla
# all'uscita. La regola distingue il riferimento dalla stringa letterale, che
# resta il caso per cui il WARN e' nato.

def test_return_named_placeholder_reference_is_clean():
    doc = minimal_process(
        returns={"verdict": {"required": True}},
        ROUTINE=[
            {"TODO": "Build the result as JSON: {\"verdict\": <the verdict>}."},
            {"RETURN": "{{result}}"},
        ],
    )
    assert "return-shape-mismatch" not in codes(doc)


def test_return_dotted_placeholder_reference_is_clean():
    doc = minimal_process(
        returns={"verdict": {"required": True}},
        ROUTINE=[{"RETURN": "{{payload.body}}"}],
    )
    assert "return-shape-mismatch" not in codes(doc)


def test_return_literal_string_still_warns():
    doc = minimal_process(
        returns={"verdict": {"required": True}},
        ROUTINE=[{"RETURN": "the input was invalid"}],
    )
    assert "return-shape-mismatch" in codes(doc, "WARN")


def test_return_prose_placeholder_still_warns():
    """{{the array built earlier}} non e' un riferimento nominato: resta un rilievo."""
    doc = minimal_process(
        returns={"verdict": {"required": True}},
        ROUTINE=[{"RETURN": "{{the array built earlier}}"}],
    )
    assert "return-shape-mismatch" in codes(doc, "WARN")


# Un "if" in prosa si giudica da cosa fa il conseguente. Decisione di Gianni
# (2026-08-20): se si apre un ramo vero la IF va esplicitata, sempre; se e' solo
# l'assegnazione di un default il flusso prosegue identico e si tollera, salvo
# quando e' l'unica istruzione del suo flusso.

def test_buried_branch_when_the_consequent_transfers_control():
    """'skip it' salta i passi successivi: il diagramma mostrerebbe una linea
    dritta dove il processo si biforca."""
    doc = minimal_process(ROUTINE=[
        {"TODO": "a"},
        {"TODO": "If the line is marked as cancelled, skip it -- do not add its amount."},
        {"TODO": "b"},
    ])
    assert "buried-branch" in codes(doc, "WARN")


def test_buried_default_assignment_among_other_steps_is_tolerated():
    doc = minimal_process(ROUTINE=[
        {"TODO": "a"},
        {"TODO": "If no product plausibly matches, set product to UNKNOWN."},
        {"TODO": "c"},
    ])
    assert not [c for c in codes(doc) if c.startswith("buried")]


def test_buried_default_assignment_alone_in_its_routine_is_reported():
    """Unica istruzione del flusso: il diagramma si riduce a una scatola sola."""
    doc = minimal_process(ROUTINE=[
        {"TODO": "If no product plausibly matches, set product to UNKNOWN."},
    ])
    assert "buried-flow" in codes(doc, "WARN")


def test_buried_decision_with_unreadable_consequent_still_warns():
    """Se il conseguente non si legge, la chiamata prudente e' dire comunque qualcosa."""
    doc = minimal_process(ROUTINE=[
        {"TODO": "a"},
        {"TODO": "If the moon is full, something happens."},
    ])
    assert "buried-flow" in codes(doc, "WARN")


def test_step_without_a_decision_is_clean():
    doc = minimal_process(ROUTINE=[{"TODO": "Sum the amounts in the items array."}])
    assert not [c for c in codes(doc) if c.startswith("buried")]


def test_return_reference_must_be_bound_somewhere():
    """Esentare {{name}} dal warn di shape senza guardare cosa costruisce l'oggetto
    scambierebbe un falso positivo con un punto cieco. Se nulla nello script nomina
    quel riferimento, non c'e' passo che lo costruisca."""
    doc = minimal_process(
        returns={"verdict": {"required": True}},
        ROUTINE=[{"RETURN": "{{result}}"}],
    )
    assert "return-ref-unbound" in codes(doc, "WARN")


def test_return_reference_bound_by_a_previous_step_is_clean():
    doc = minimal_process(
        returns={"verdict": {"required": True}},
        ROUTINE=[
            {"TODO": "Build the result as JSON with key verdict."},
            {"RETURN": "{{result}}"},
        ],
    )
    assert "return-ref-unbound" not in codes(doc)


def test_return_reference_must_cover_every_contract_key():
    """Il contratto chiede verdict e total, il passo costruisce solo verdict."""
    doc = minimal_process(
        returns={"verdict": {"required": True}, "total": {"required": True}},
        ROUTINE=[
            {"TODO": "Build the result as JSON with key verdict."},
            {"RETURN": "{{result}}"},
        ],
    )
    assert "return-contract-keys-unmentioned" in codes(doc, "WARN")


def test_return_reference_covering_every_contract_key_is_clean():
    doc = minimal_process(
        returns={"verdict": {"required": True}, "total": {"required": True}},
        ROUTINE=[
            {"TODO": "Build the result as JSON with keys verdict and total."},
            {"RETURN": "{{result}}"},
        ],
    )
    assert not [c for c in codes(doc) if c.startswith("return")]


def test_contract_keys_are_searched_in_the_routine_not_the_contract():
    """Cercare le chiavi in tutto il documento renderebbe il controllo sempre verde:
    il blocco 'returns' nomina ogni chiave da se'. Vanno cercate nella ROUTINE."""
    doc = minimal_process(
        returns={"soltanto_qui": {"required": True}},
        ROUTINE=[{"TODO": "Build the result."}, {"RETURN": "{{result}}"}],
    )
    assert "return-contract-keys-unmentioned" in codes(doc, "WARN")


def test_return_placeholder_mixed_with_text_still_warns():
    doc = minimal_process(
        returns={"verdict": {"required": True}},
        ROUTINE=[{"RETURN": "{{result}} and then some"}],
    )
    assert "return-shape-mismatch" in codes(doc, "WARN")


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
    """Delegates to the runner's own loader instead of re-implementing it.

    The previous version picked the LAST ```json block; runner.py::_load_fixture
    picks the first block containing "ROUTINE". The two agree only when the SOL
    script happens to come last -- true for release-gate and task-router, false
    for cart-total, whose '## File content' section follows the script. The test
    therefore parsed the '{{file_content}}' placeholder and failed on a fixture
    the runner loads without trouble. Sharing the loader is what keeps a red test
    meaning "the fixture is broken" rather than "the test disagrees with the
    runner"."""
    sys.path.insert(0, str(REPO_ROOT / "tests"))
    from runner.runner import _load_fixture
    fixture_id = path.parent.relative_to(REPO_ROOT / "tests" / "fixtures").as_posix()
    return _load_fixture(fixture_id)[1]


def test_release_gate_fixture_lints_clean():
    fixture = (
        REPO_ROOT / "tests" / "fixtures" / "w2-branching" / "release-gate" / "release-gate.md"
    )
    doc = _load_sol_from_md(fixture)
    assert lint(doc) == []


# These two tests had been red since the day they were written (441c2c5,
# 2026-06-07), for three stacked reasons, all now resolved:
#   1. task-router.md carried invalid JSON (a515dc0, "Fix typos") -- unescaped
#      quotes and a missing comma. The runner's own loader choked on it too.
#   2. _load_sol_from_md picked the LAST ```json block while the runner picks the
#      first one containing "ROUTINE" -- they disagree on cart-total.
#   3. They asserted lint(doc) == [], which five of the six fixtures did not meet:
#      the house pattern builds the payload in a named step and RETURNs a
#      reference to it, which 'return-shape-mismatch' used to flag as an
#      off-contract string. Decisione di Gianni (2026-08-20): quella forma e' una
#      best practice, non un difetto -- la regola ora esenta il riferimento
#      nominato (RETURN_REF_RE in sol-lint.py).
#
# What is left is 'buried-flow' on two fixtures, and it stays: it is a judgment
# call the linter cannot make (declarative criterion vs. program flow), which is
# why it is WARN. Rewriting a fixture to silence it would change the prompt every
# model is given and invalidate the records already in index.jsonl -- a decision
# about the experiment, not a test fix.
#
# So these tests assert what they mean: no ERROR, and no WARN beyond the known
# ones. A new finding of any kind still turns them red.

WARN_ATTESI = {"buried-branch"}


def _assert_no_error_and_only_known_warns(doc, nome):
    findings = lint(doc)
    errori = [f for f in findings if f.severity == "ERROR"]
    assert not errori, f"{nome}: ERROR di lint: {[f.as_dict() for f in errori]}"
    ignoti = [f for f in findings if f.code not in WARN_ATTESI]
    assert not ignoti, f"{nome}: rilievo non previsto: {[f.as_dict() for f in ignoti]}"


def test_cart_total_fixture_has_no_lint_errors():
    fixture = (
        REPO_ROOT / "tests" / "fixtures" / "w1-linear" / "cart-total" / "cart-total.md"
    )
    _assert_no_error_and_only_known_warns(_load_sol_from_md(fixture), "cart-total")


def test_task_router_fixture_has_no_lint_errors():
    fixture = (
        REPO_ROOT / "tests" / "fixtures" / "w3-multi-call" / "task-router" / "task-router.md"
    )
    _assert_no_error_and_only_known_warns(_load_sol_from_md(fixture), "task-router")


def test_every_fixture_has_no_lint_errors():
    """Widened from the two fixtures above: an ERROR anywhere in the suite is a
    blocker for the campaign, and support-intake in particular gates MAIN."""
    fixtures_dir = REPO_ROOT / "tests" / "fixtures"
    visti = 0
    for md in sorted(fixtures_dir.glob("*/*/*.md")):
        if md.stem != md.parent.name:
            continue
        visti += 1
        _assert_no_error_and_only_known_warns(
            _load_sol_from_md(md), md.parent.relative_to(fixtures_dir).as_posix())
    # Legato al filesystem, non a un numero cablato: ogni fixture ha una
    # expectations.json accanto al suo .md, quindi i due conteggi devono
    # coincidere. Cosi' il test segue le fixture nuove da solo, e resta rosso
    # se il glob smette di agganciarle o se a una manca l'oracolo.
    attese = len(list(fixtures_dir.glob("*/*/expectations.json")))
    assert visti == attese, f"lintate {visti} fixture ma expectations.json sono {attese}"
    assert visti >= 6, f"solo {visti} fixture trovate: il glob non aggancia piu' la suite"


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
