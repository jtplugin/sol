"""
R1 tests for the routing oracle — deterministic, no model, no I/O.

checker.py carries its own copy of each fixture's control flow, because a
generic checker must not import a specific fixture's Python module. That is the
right call and it has a cost: two implementations of one algorithm, which agree
until one of them is edited. These tests are what makes the duplication safe,
and they are exhaustive rather than sampled — the state space is small enough
that there is no reason to guess.

The docstring in checker._run_queue_oracle claimed test_checker.py cross-checked
it against support-intake's reference.py. It did not; nothing imported that
module anywhere in the suite. It does now, here, alongside the new one.
"""
import importlib.util
import itertools
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "tests"))

from runner.schema import Config, Execution, Output, RunRecord, Trace, Usage  # noqa: E402
from runner import checker as ck                                             # noqa: E402

FIXTURES = REPO_ROOT / "tests" / "fixtures" / "w2-branching"
ROUTING = FIXTURES / "support-routing"
INTAKE = FIXTURES / "support-intake"


def _load(name: str, path: Path):
    """Both fixtures name their oracle `reference.py`; loading them under
    distinct module names keeps the second from shadowing the first."""
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


routing_ref = _load("_routing_reference", ROUTING / "reference.py")
intake_ref = _load("_intake_reference", INTAKE / "reference.py")

import json  # noqa: E402

ROUTING_CATALOG = json.loads((ROUTING / "catalog.json").read_text(encoding="utf-8"))
INTAKE_CATALOG = json.loads((INTAKE / "catalog.json").read_text(encoding="utf-8"))

PRODUCTS = ["P1", "P2", "P3", "P4", "P5", "UNKNOWN"]
INTENTS = ["BUG", "FEATURE", "QUESTION"]
STATES = ["OPEN", "LIMITED", "CLOSED"]
# 0 forces NOFIT on everything, 2 splits the hours table, 20 fits everything.
BUDGETS = [0, 2, 20]


def _worlds():
    for t1, t2, t3 in itertools.product(STATES, repeat=3):
        for remaining in BUDGETS:
            yield {"remaining_hours": remaining, "teams": {"T1": t1, "T2": t2, "T3": t3}}


# ---------------------------------------------------------------------------
# The two copies of the algorithm agree
# ---------------------------------------------------------------------------

def test_the_checkers_copy_matches_the_routing_fixtures_oracle():
    """Exhaustive: every product x intent x team-state triple x budget. 1,458
    combinations, which is cheaper to run than to argue about."""
    checked = 0
    for product, intent in itertools.product(PRODUCTS, INTENTS):
        item = {"id": "x1", "product": product, "intent": intent}
        for world in _worlds():
            mine = ck._route_item_oracle([item], world, ROUTING_CATALOG)
            theirs = routing_ref.route_item(
                item, world["remaining_hours"], world["teams"], ROUTING_CATALOG)

            assert mine[0]["action"] == theirs["item"]["action"], (product, intent, world)
            assert mine[0]["team"] == (theirs["item"]["team"] or "-"), (product, intent, world)
            assert ck._action_labels(mine)[0] == routing_ref.action_label(theirs)
            checked += 1
    assert checked == len(PRODUCTS) * len(INTENTS) * 27 * len(BUDGETS)


def test_the_checkers_copy_matches_the_intake_fixtures_oracle():
    """The claim checker._run_queue_oracle's docstring already made."""
    queue = [{"id": f"q{i}", "product": p, "intent": t}
             for i, (p, t) in enumerate(itertools.product(PRODUCTS, INTENTS))]
    budget = INTAKE_CATALOG["budget_hours"]
    table = INTAKE_CATALOG["hours_table"]

    mine, remaining, halted = ck._run_queue_oracle(queue, budget, table)
    theirs = intake_ref.run_queue(queue, budget, table)

    assert [m["action"] for m in mine] == [t["action"] for t in theirs["items"]]
    assert remaining == theirs["remaining_hours"]
    assert halted == theirs["halted_at"]
    assert ck._action_labels(mine) == intake_ref.action_sequence(theirs)


# ---------------------------------------------------------------------------
# The matrix the algorithm assumes
# ---------------------------------------------------------------------------

def test_no_product_is_accepted_by_two_teams():
    """`owner_of` returns the first match and treats it as the only one. If a
    second team ever accepted the same product, routing would silently depend
    on the order of a JSON array."""
    teams = ROUTING_CATALOG["teams"]
    for product in ["P1", "P2", "P3", "P4", "P5"]:
        owners = [t["id"] for t in teams if product in t["accepts"]]
        assert len(owners) <= 1, (product, owners)


def test_no_product_is_backed_up_by_two_teams():
    """The document states no rule for choosing among backups, because there is
    never a choice. Add a second backup and the fixture becomes ambiguous
    without anything failing."""
    teams = ROUTING_CATALOG["teams"]
    for product in ["P1", "P2", "P3", "P4", "P5"]:
        backups = [t["id"] for t in teams if product in t["backs_up"]]
        assert len(backups) <= 1, (product, backups)


def test_exactly_one_product_is_accepted_by_nobody():
    """UNASSIGNED has to be reachable, and it has to be reachable for exactly
    one product — otherwise the stratum in SS7.6 is either empty or two."""
    teams = ROUTING_CATALOG["teams"]
    orphans = [p for p in ["P1", "P2", "P3", "P4", "P5"]
               if not any(p in t["accepts"] for t in teams)]
    assert orphans == ["P4"], orphans


def test_every_action_is_reachable():
    """A stratum of SS7.6 that no world can produce is a stratum that will not be
    sampled, and nobody would notice."""
    seen = set()
    for product, intent in itertools.product(PRODUCTS, INTENTS):
        for world in _worlds():
            out = ck._route_item_oracle(
                [{"id": "x", "product": product, "intent": intent}], world, ROUTING_CATALOG)
            seen.add(out[0]["action"])
    assert seen == {"ASSIGN", "DEFER", "NEEDS_INFO", "ESCALATE", "UNASSIGNED"}


# ---------------------------------------------------------------------------
# The trap
# ---------------------------------------------------------------------------

def test_the_owner_outranks_an_idle_backup_for_a_bug():
    """The decision the fixture exists to observe. Same product, same world,
    two intents: the BUG stays with the limited owner and the feature request
    goes to the idle backup. A model that reasons 'there is a team with room,
    use that one' gets the second right and the first wrong, which is what
    tells precedence apart from luck."""
    world = {"remaining_hours": 12, "teams": {"T1": "LIMITED", "T2": "OPEN", "T3": "OPEN"}}

    bug = ck._route_item_oracle(
        [{"id": "x", "product": "P2", "intent": "BUG"}], world, ROUTING_CATALOG)[0]
    feature = ck._route_item_oracle(
        [{"id": "x", "product": "P2", "intent": "FEATURE"}], world, ROUTING_CATALOG)[0]

    assert (bug["action"], bug["team"]) == ("ASSIGN", "T1")
    assert (feature["action"], feature["team"]) == ("ASSIGN", "T2")


def test_a_limited_team_does_not_absorb_another_teams_overflow():
    """LIMITED buys the owner a BUG, not somebody else's."""
    world = {"remaining_hours": 12, "teams": {"T1": "CLOSED", "T2": "LIMITED", "T3": "OPEN"}}
    out = ck._route_item_oracle(
        [{"id": "x", "product": "P2", "intent": "BUG"}], world, ROUTING_CATALOG)[0]
    assert out["action"] == "DEFER" and out["team"] == "-"


# ---------------------------------------------------------------------------
# The trace line
# ---------------------------------------------------------------------------

def _trace(*lines):
    return Trace(steps=list(lines))


def test_the_team_survives_the_round_trip_from_trace_to_label():
    obs = ck._observed_sequence(_trace(
        "[fixture-w2-support-routing][main] BRANCH: item=r7 action=ASSIGN team=T2 remaining=8"))
    assert obs == ["item=r7 action=ASSIGN team=T2"]


def test_an_intake_line_still_produces_a_label_with_no_team():
    """The 645 rows already scored must re-score to the same labels; the team
    group is optional precisely so that they do."""
    obs = ck._observed_sequence(_trace(
        "[fixture-w2-support-intake][main] BRANCH: item=q3 action=ASSIGN remaining=14"))
    assert obs == ["item=q3 action=ASSIGN"]


def test_a_bare_branch_label_is_still_read_whole():
    """polarity-flip's shape, unchanged."""
    assert ck._observed_sequence(_trace("[fixture-w0][main] BRANCH: flip")) == ["flip"]


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

def _record(trace, payload=None, input_id="r01"):
    return RunRecord(
        run_id="test-run",
        timestamp="2026-01-01T00:00:00+00:00",
        config=Config(fixture_id="w2-branching/support-routing",
                      context="E0", model_id="test-model"),
        staged_input_id=input_id,
        execution=Execution(status="done"),
        trace=trace,
        output=Output(raw="", returned_payload=payload),
        usage=Usage(),
    )


WORLD = {"remaining_hours": 12, "teams": {"T1": "LIMITED", "T2": "OPEN", "T3": "OPEN"}}
GOOD_TRACE = _trace(
    "[fixture-w2-support-routing][main] EVAL: item=r01 product=P2 intent=BUG",
    "[fixture-w2-support-routing][main] BRANCH: item=r01 action=ASSIGN team=T1 remaining=10")

ROUTING_EXPECTATIONS = {
    "oracle": "route_item",
    "catalog": ROUTING_CATALOG,
    "cases": [{
        "input": "inputs/r01.json",
        "world": WORLD,
        "expected_sequence": ["item=r01 action=ASSIGN team=T1"],
        "comprehension_ground_truth": [{"id": "r01", "product": "P2", "intent": "BUG"}],
        "expected_output": {"status": "OK", "remaining_hours": 10,
                            "item": {"id": "r01", "product": "P2", "intent": "BUG",
                                     "hours": 2, "team": "T1", "action": "ASSIGN"}},
    }],
}


def test_a_faithful_run_scores_one_on_both_rates():
    score = ck.check(_record(GOOD_TRACE,
                             payload=ROUTING_EXPECTATIONS["cases"][0]["expected_output"]),
                     ROUTING_EXPECTATIONS)
    assert score.fidelity.sequence_rate == 1.0
    assert score.fidelity.conditional_rate == 1.0
    assert score.comprehension.rate == 1.0
    assert score.quality.result == "pass"


def test_routing_to_the_idle_backup_costs_conditional_fidelity():
    """The trap, scored. The classification is right, the action is right, and
    the run is still wrong — which is the distinction conditional fidelity was
    introduced to make."""
    trace = _trace(
        "[fixture-w2-support-routing][main] EVAL: item=r01 product=P2 intent=BUG",
        "[fixture-w2-support-routing][main] BRANCH: item=r01 action=ASSIGN team=T2 remaining=10")
    score = ck.check(_record(trace), ROUTING_EXPECTATIONS)
    assert score.comprehension.rate == 1.0        # it understood the request
    assert score.fidelity.conditional_rate == 0.0  # and routed it wrong anyway


def test_conditional_fidelity_is_computed_from_the_models_own_classification():
    """Misread the product, route it correctly for what you read: comprehension
    falls, control flow does not."""
    trace = _trace(
        "[fixture-w2-support-routing][main] EVAL: item=r01 product=P5 intent=BUG",
        "[fixture-w2-support-routing][main] BRANCH: item=r01 action=ASSIGN team=T3 remaining=9")
    score = ck.check(_record(trace), ROUTING_EXPECTATIONS)
    assert score.comprehension.rate == 0.0
    assert score.fidelity.conditional_rate == 1.0


def test_a_case_with_no_world_is_unmeasurable_not_zero():
    """Same rule as the 2026-08-23 comprehension correction: the absence of a
    measurement does not get written where a result goes."""
    exp = json.loads(json.dumps(ROUTING_EXPECTATIONS))
    del exp["cases"][0]["world"]
    score = ck.check(_record(GOOD_TRACE), exp)
    assert score.fidelity.conditional_rate is None


def test_an_unknown_oracle_name_raises():
    """Scoring quietly against the wrong algorithm is the failure mode worth
    paying an exception to avoid."""
    exp = json.loads(json.dumps(ROUTING_EXPECTATIONS))
    exp["oracle"] = "run_quueue"
    with pytest.raises(ValueError, match="does not implement"):
        ck.check(_record(GOOD_TRACE), exp)


def test_expectations_with_no_oracle_key_still_mean_the_queue():
    """support-intake's expectations.json names no oracle and must keep working
    without being edited."""
    intake_exp = json.loads((INTAKE / "expectations.json").read_text(encoding="utf-8"))
    assert "oracle" not in intake_exp
    assert ck._check_conditional_fidelity(
        Trace(), intake_exp.get("catalog"))["conditional_rate"] is None


# ---------------------------------------------------------------------------
# The frozen set
# ---------------------------------------------------------------------------

def test_the_request_set_on_disk_is_what_the_generator_produces():
    """SS8.1 item 8: the twenty requests are a frozen artefact, and a frozen
    artefact edited by hand is one nobody can regenerate. Same check the
    prose documents get, for the same reason."""
    build = _load("_build_requests", REPO_ROOT / "tests" / "scripts" / "build_requests.py")
    manifest, expectations = build._build()
    on_disk_manifest = json.loads((ROUTING / "items-manifest.json").read_text(encoding="utf-8"))
    on_disk_expectations = json.loads((ROUTING / "expectations.json").read_text(encoding="utf-8"))
    assert on_disk_manifest == manifest
    assert on_disk_expectations == expectations


def test_every_stratum_is_represented_at_least_twice():
    """A stratum with one member is a stratum whose result is one run."""
    manifest = json.loads((ROUTING / "items-manifest.json").read_text(encoding="utf-8"))
    counts = {}
    for r in manifest["requests"]:
        counts[r["stratum"]] = counts.get(r["stratum"], 0) + 1
    thin = {k: v for k, v in counts.items() if v < 2 and k != "off-catalog"}
    assert not thin, thin
    assert counts["trap-limited-bug"] == 3, counts


def test_no_pool_item_is_used_twice():
    """Twenty requests, twenty distinct items: a repeated item would make two
    strata share a comprehension result."""
    manifest = json.loads((ROUTING / "items-manifest.json").read_text(encoding="utf-8"))
    ids = [r["item_id"] for r in manifest["requests"]]
    assert len(set(ids)) == len(ids) == 20


def test_every_staged_request_carries_its_world():
    """The model cannot decide without the state, and the state must be the one
    the expectation was computed against."""
    manifest = json.loads((ROUTING / "items-manifest.json").read_text(encoding="utf-8"))
    for r in manifest["requests"]:
        staged = ROUTING / "inputs" / f"{r['request_id']}.json"
        if not staged.exists():
            pytest.skip("inputs not hydrated in this checkout")
        payload = json.loads(staged.read_text(encoding="utf-8"))
        assert payload["remaining_hours"] == r["world"]["remaining_hours"]
        assert payload["teams"] == r["world"]["teams"]
        assert payload["item"]["id"] == r["item_id"]
        assert "product" not in payload["item"] and "intent" not in payload["item"]
