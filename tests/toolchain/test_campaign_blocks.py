"""
R1 tests for the campaign's two blocks — no server, no model, no GPU.

A block is one fixture, one plan file, one set of staged inputs and one
repetition count. The blocks share a results root and an index on purpose (every
index row carries fixture_id, and the dashboard already filters by it); what they
must never share is the plan file, because MAIN's is the record of a run that
happened.

The risk these tests exist for is narrow and expensive: _use_block rebinds module
globals, so a block left selected leaks into whatever runs next. In a test suite
that shows up as a puzzling failure; in the driver it would write rows for one
fixture into the other's plan.
"""
import importlib
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "tests"))

campaign_mod = importlib.import_module("runner.campaign")


@pytest.fixture(autouse=True)
def _restore_main_block():
    """Every test here leaves the module pointed back at MAIN. Without this the
    order tests run in would decide which fixture the others see."""
    yield
    campaign_mod._use_block("main")


# ---------------------------------------------------------------------------
# What a block selects
# ---------------------------------------------------------------------------

def test_selecting_the_routing_block_moves_fixture_reps_and_plan():
    campaign_mod._use_block("routing")
    assert campaign_mod.FIXTURE_ID == "w2-branching/support-routing"
    assert campaign_mod.REPS_PER_RENDERING == 2
    assert campaign_mod.PLAN_PATH.name == "campaign-plan-routing.json"


def test_selecting_main_puts_everything_back():
    campaign_mod._use_block("routing")
    campaign_mod._use_block("main")
    assert campaign_mod.FIXTURE_ID == "w2-branching/support-intake"
    assert campaign_mod.REPS_PER_RENDERING == 3
    assert campaign_mod.PLAN_PATH.name == "campaign-plan.json"


def test_the_blocks_share_a_results_root_and_not_a_plan():
    """Sharing the index is the point — one dashboard, two fixtures, filtered
    apart by a field that is already there. Sharing the plan would mean writing
    rows for one fixture into the other's record."""
    campaign_mod._use_block("main")
    main_root, main_plan = campaign_mod.RESULTS_DIR, campaign_mod.PLAN_PATH
    campaign_mod._use_block("routing")
    assert campaign_mod.RESULTS_DIR == main_root
    assert campaign_mod.INDEX_PATH == main_root / "index.jsonl"
    assert campaign_mod.PLAN_PATH != main_plan


def test_no_two_blocks_write_the_same_plan_file():
    names = [b["plan_name"] for b in campaign_mod.BLOCKS.values()]
    assert len(set(names)) == len(names), names


# ---------------------------------------------------------------------------
# The coordinate
# ---------------------------------------------------------------------------

def test_a_plan_row_written_before_the_rename_is_still_read():
    """MAIN's plan file was live, with hundreds of rows keyed `queue`, when the
    key became `input`. The resume matches on this value: read one way only and
    every executed row would have gone back to pending."""
    assert campaign_mod._input_of({"queue": "queue-03"}) == "queue-03"
    assert campaign_mod._input_of({"input": "r07"}) == "r07"


def test_a_new_plan_names_its_coordinate_input():
    rows = campaign_mod.build_plan(
        [{"cell": "c1", "modes": ["m1"]}], ["r01", "r02"], reps=2)
    assert all("input" in r and "queue" not in r for r in rows)


# ---------------------------------------------------------------------------
# The routing plan
# ---------------------------------------------------------------------------

def test_the_routing_plan_is_the_size_the_protocol_states():
    """SS7.6: 20 requests x 2 repetitions x 7 renderings x 6 modes = 1,680."""
    campaign_mod._use_block("routing")
    cells = campaign_mod._load_cells()
    inputs = campaign_mod._load_request_ids()
    rows = campaign_mod.build_plan(cells, inputs)

    n_modes = sum(len(c["modes"]) for c in cells)
    assert len(inputs) == 20
    assert len(rows) == 20 * 2 * len(campaign_mod.RENDERINGS) * n_modes == 1680


def test_the_routing_plan_covers_every_rendering_for_every_request():
    campaign_mod._use_block("routing")
    rows = campaign_mod.build_plan(campaign_mod._load_cells(),
                                   campaign_mod._load_request_ids())
    by_input = {}
    for r in rows:
        by_input.setdefault(campaign_mod._input_of(r), set()).add(r["rendering"])
    assert len(by_input) == 20
    for input_id, renderings in by_input.items():
        assert renderings == set(campaign_mod.RENDERINGS), (input_id, renderings)


def test_the_request_ids_are_the_ones_the_manifest_names():
    manifest = json.loads(
        (REPO_ROOT / "tests" / "fixtures" / "w2-branching" / "support-routing"
         / "items-manifest.json").read_text(encoding="utf-8"))
    assert campaign_mod._load_request_ids() == [r["request_id"] for r in manifest["requests"]]


# ---------------------------------------------------------------------------
# The pre-flight
# ---------------------------------------------------------------------------

def test_the_staged_requests_pass_their_alignment_check():
    from runner.runner import assert_request_alignment
    fixture_dir = REPO_ROOT / "tests" / "fixtures" / "w2-branching" / "support-routing"
    if not (fixture_dir / "inputs" / "r01.json").exists():
        pytest.skip("requests not hydrated in this checkout")
    assert_request_alignment(fixture_dir)


def test_the_alignment_check_notices_a_world_that_drifted(tmp_path):
    """The failure it exists for does not announce itself: a request staged
    against a world its expectation was not computed against still scores, and
    the wrong number looks exactly like a result."""
    from runner.runner import assert_request_alignment
    src = REPO_ROOT / "tests" / "fixtures" / "w2-branching" / "support-routing"
    if not (src / "inputs" / "r01.json").exists():
        pytest.skip("requests not hydrated in this checkout")

    (tmp_path / "inputs").mkdir()
    for name in ("items-manifest.json", "expectations.json"):
        (tmp_path / name).write_text((src / name).read_text(encoding="utf-8"),
                                     encoding="utf-8")
    manifest = json.loads((src / "items-manifest.json").read_text(encoding="utf-8"))
    for req in manifest["requests"]:
        staged = json.loads((src / "inputs" / f"{req['request_id']}.json")
                            .read_text(encoding="utf-8"))
        if req["request_id"] == "r01":
            staged["teams"]["T1"] = "CLOSED"      # the drift
        (tmp_path / "inputs" / f"{req['request_id']}.json").write_text(
            json.dumps(staged), encoding="utf-8")

    with pytest.raises(RuntimeError, match="team states"):
        assert_request_alignment(tmp_path)
