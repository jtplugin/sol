"""R1 tests for the stratified smoke of campaign.py (2026-08-22).

The smoke exists because the pilot proved the chain on exactly ONE
(mode, rendering) combination -- one queue at L1. Since 2026-08-22 it is aimed at
the two prose renderings of SS5.4: they are the cells whose documents and whose
branch in _build_prompt_e0 have never been through a live model. 36 stratified
runs say whether that chain holds before MAIN spends 18-25 hours on it.

Two properties are worth a test, and they are the two this file covers:

  stratification -- a plain random sample of the same size would leave
      combinations uncovered by chance, which is precisely the gap the smoke
      exists to close;
  separation -- the smoke's runs are throwaway by construction (SV decision,
      2026-08-22). If they reached MAIN's index the resume would count them as
      already done, and a smoke that finds a defect would leave runs produced by
      pre-fix code inside the dataset. That is the contamination this campaign's
      design exists to prevent.

No GPU, no llama-server, no live model calls: the redirection is observed on the
module globals, and every test restores them in a finally block -- a test that
left RESULTS_DIR redirected would silently contaminate the tests after it in the
same pytest session, which is the very failure mode under test.
"""
import argparse
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "tests"))

import runner.api_executor as api_mod
import runner.campaign as campaign_mod
import runner.runner as runner_mod


@pytest.fixture
def restore_results_root():
    """Snapshot every global _use_results_root touches, and put it back."""
    saved = (
        campaign_mod.RESULTS_DIR, campaign_mod.INDEX_PATH, campaign_mod.PLAN_PATH,
        runner_mod.RESULTS_DIR, runner_mod.INDEX_PATH,
    )
    try:
        yield
    finally:
        (campaign_mod.RESULTS_DIR, campaign_mod.INDEX_PATH, campaign_mod.PLAN_PATH,
         runner_mod.RESULTS_DIR, runner_mod.INDEX_PATH) = saved


# ---------------------------------------------------------------------------
# stratification
# ---------------------------------------------------------------------------

def _smoke_plan():
    return campaign_mod.build_smoke_plan(campaign_mod._load_cells(),
                                         campaign_mod._load_queue_ids())


def test_smoke_plan_covers_every_mode_level_combination():
    rows = _smoke_plan()

    n_modes = sum(len(c["modes"]) for c in campaign_mod._load_cells())
    assert n_modes == 6
    expected_combos = n_modes * len(campaign_mod.SMOKE_RENDERINGS)
    assert expected_combos == 12

    combos = {}
    for row in rows:
        combos.setdefault((row["mode"], row["rendering"]), []).append(row)

    assert len(combos) == expected_combos
    assert all(len(v) == campaign_mod.SMOKE_RUNS_PER_COMBO for v in combos.values())
    assert len(rows) == expected_combos * campaign_mod.SMOKE_RUNS_PER_COMBO == 36
    assert all(r["status"] == "pending" for r in rows)


def test_smoke_plan_draws_distinct_queue_rep_pairs_inside_a_combination():
    """Three runs of the same (queue, rep) would measure the same coordinate
    three times and leave the combination's variance unexplored."""
    combos = {}
    for row in _smoke_plan():
        combos.setdefault((row["mode"], row["rendering"]), []).append((campaign_mod._input_of(row), row["rep"]))

    for key, pairs in combos.items():
        assert len(set(pairs)) == len(pairs), f"duplicate (queue, rep) in {key}"


def test_smoke_plan_uses_only_legal_queues_and_reps():
    queue_ids = set(campaign_mod._load_queue_ids())
    cells = {c["cell"]: c for c in campaign_mod._load_cells()}

    for row in _smoke_plan():
        assert campaign_mod._input_of(row) in queue_ids
        assert 1 <= row["rep"] <= campaign_mod.REPS_PER_RENDERING
        assert row["rendering"] in campaign_mod.SMOKE_RENDERINGS
        assert row["mode"] in cells[row["cell"]]["modes"]


def test_smoke_plan_is_grouped_by_cell():
    """Execution order is the plan's order, and a cell means one llama-server
    load: five server starts, not one hundred."""
    seen, order = set(), []
    for row in _smoke_plan():
        if not order or order[-1] != row["cell"]:
            assert row["cell"] not in seen, f"cell {row['cell']} interleaved with another"
            order.append(row["cell"])
            seen.add(row["cell"])

    assert order == [c["cell"] for c in campaign_mod._load_cells()]


def test_smoke_plan_is_deterministic_for_a_given_seed():
    cells, queues = campaign_mod._load_cells(), campaign_mod._load_queue_ids()
    assert campaign_mod.build_smoke_plan(cells, queues) == campaign_mod.build_smoke_plan(cells, queues)
    assert campaign_mod.build_smoke_plan(cells, queues, seed=1) != campaign_mod.build_smoke_plan(cells, queues, seed=2)


# ---------------------------------------------------------------------------
# separation of the results root
# ---------------------------------------------------------------------------

def test_use_results_root_redirects_both_modules(restore_results_root, tmp_path):
    main_index = runner_mod.INDEX_PATH

    campaign_mod._use_results_root(tmp_path, "campaign-smoke-plan.json")

    assert runner_mod.RESULTS_DIR == tmp_path
    assert runner_mod.INDEX_PATH == tmp_path / "index.jsonl"
    assert campaign_mod.INDEX_PATH == tmp_path / "index.jsonl"
    assert campaign_mod.RESULTS_DIR == tmp_path
    assert campaign_mod.PLAN_PATH == tmp_path / "campaign-smoke-plan.json"
    assert runner_mod.INDEX_PATH != main_index


def test_redirected_record_and_index_paths_land_under_the_new_root(restore_results_root, tmp_path):
    """The property the redirection exists for: _record_path and _append_index
    resolve their module globals at call time, so writes follow the root."""
    from runner.schema import Config

    campaign_mod._use_results_root(tmp_path, "campaign-smoke-plan.json")
    config = Config(fixture_id="w2-branching/support-intake", context="E0",
                    model_id="ai-models/x.gguf")
    path = runner_mod._record_path(config, "run-id-1")

    assert tmp_path in path.parents


def test_smoke_run_refuses_an_index_outside_the_smoke_root(restore_results_root, tmp_path,
                                                           monkeypatch):
    """Belt and braces: the redirection is global mutable state, and a smoke that
    writes into MAIN's index is the worst outcome this card can produce."""
    started = []
    monkeypatch.setattr(campaign_mod, "_start_server", lambda cell: started.append(True))
    monkeypatch.setattr(campaign_mod, "_use_results_root", lambda *a, **k: None)  # redirection defeated

    args = type("A", (), {"plan": False, "run": True, "clean": False})()
    with pytest.raises(SystemExit) as exc:
        campaign_mod.cmd_smoke(args)

    assert "throwaway" in str(exc.value)
    assert started == []


def test_smoke_results_dir_is_separate_from_main():
    assert campaign_mod.SMOKE_RESULTS_DIR != runner_mod.RESULTS_DIR
    assert campaign_mod.SMOKE_RESULTS_DIR.name == "results-smoke"
    assert campaign_mod.SMOKE_PLAN_PATH.parent == campaign_mod.SMOKE_RESULTS_DIR


def test_smoke_results_dir_is_gitignored():
    """tests/results/ is tracked on purpose -- it is the evidence of what was
    measured. The smoke's output is evidence of nothing, and gate.py commits with
    'git add -A'."""
    ignored = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "tests/results-smoke/" in ignored


def test_smoke_clean_removes_the_smoke_root_and_nothing_else(monkeypatch, tmp_path, capsys):
    root = tmp_path / "results-smoke"
    (root / "w2-branching").mkdir(parents=True)
    (root / "index.jsonl").write_text("{}\n", encoding="utf-8")
    main = tmp_path / "results"
    main.mkdir()
    (main / "index.jsonl").write_text("{}\n", encoding="utf-8")

    monkeypatch.setattr(campaign_mod, "SMOKE_RESULTS_DIR", root)

    args = type("A", (), {"plan": False, "run": False, "clean": True})()
    campaign_mod.cmd_smoke(args)

    assert not root.exists()
    assert (main / "index.jsonl").exists()
    assert "removed" in capsys.readouterr().out


def test_smoke_clean_is_quiet_when_there_is_nothing_to_remove(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(campaign_mod, "SMOKE_RESULTS_DIR", tmp_path / "absent")

    args = type("A", (), {"plan": False, "run": False, "clean": True})()
    campaign_mod.cmd_smoke(args)

    assert "nothing to remove" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# scope (2026-08-22)
# ---------------------------------------------------------------------------

def test_smoke_plan_leaves_the_l_cells_out():
    """SMOKE_RENDERINGS is the two prose cells and nothing else.

    Narrowing the smoke is a decision, and a decision belongs in a test: if the L
    cells ever come back into it, that should be a choice someone makes and this
    assertion records, not a drift nobody notices. What the choice rests on is in
    the constant's comment -- the prose branch is new code over new documents,
    L0..L4 travel a chain the rest of this suite already covers."""
    rows = _smoke_plan()
    renderings = {row["rendering"] for row in rows}
    assert renderings == set(campaign_mod.PROSE)
    assert not renderings & set(api_mod.LEVELS)


def test_smoke_renderings_are_a_subset_of_the_cells_main_runs():
    """A smoke cell MAIN would not run is a smoke of nothing."""
    assert set(campaign_mod.SMOKE_RENDERINGS) <= set(campaign_mod.RENDERINGS)


# ---------------------------------------------------------------------------
# separation, the other way: MAIN out of the pilot's root
# ---------------------------------------------------------------------------

def test_main_writes_to_its_own_root(restore_results_root, monkeypatch):
    """tests/results holds the pilot's 576 runs and the earlier fixture work,
    measured on other fixtures, other models and code that has since changed.
    Blended into the campaign's index they would move every KPI and every chart on
    the page without any of it being about the campaign."""
    monkeypatch.setattr(campaign_mod, "_run_plan", lambda plan_path: None)

    campaign_mod.cmd_run(argparse.Namespace())

    assert campaign_mod.RESULTS_DIR == campaign_mod.MAIN_RESULTS_DIR
    assert campaign_mod.INDEX_PATH == campaign_mod.MAIN_RESULTS_DIR / "index.jsonl"
    assert runner_mod.RESULTS_DIR == campaign_mod.MAIN_RESULTS_DIR
    assert campaign_mod.MAIN_RESULTS_DIR != campaign_mod.SMOKE_RESULTS_DIR


def test_the_plan_is_written_where_the_run_looks_for_it(restore_results_root,
                                                        monkeypatch):
    """PLAN_PATH derives from RESULTS_DIR. A plan built before the redirection
    would land in tests/results and 'run' would exit saying it does not exist."""
    written = []
    monkeypatch.setattr(campaign_mod, "_save_plan", lambda plan: written.append(campaign_mod.PLAN_PATH))

    # --force: this asks where the plan lands, and MAIN's real plan has rows that
    # have run, which the guard added on 2026-08-23 would refuse over
    campaign_mod.cmd_plan(argparse.Namespace(force=True))

    assert written == [campaign_mod.MAIN_RESULTS_DIR / "campaign-plan.json"]


# ---------------------------------------------------------------------------
# the routing block's smoke (2026-08-24)
# ---------------------------------------------------------------------------
#
# MAIN's smoke and routing's answer different questions, because what has never
# run is different in the two blocks. MAIN's L documents had been through a live
# model and only the prose branch had not, so prose was the whole of it.
# support-routing has never met a model in any rendering, and its decision space
# has an action -- UNASSIGNED -- with no counterpart in support-intake. Hence
# seven renderings, and a stratification by action rather than a uniform draw.


@pytest.fixture(autouse=True)
def _restore_main_block():
    """_use_block rebinds module globals. A block left selected would decide
    which fixture the tests after it see -- and, in the driver, which fixture's
    rows land in the other's plan."""
    yield
    campaign_mod._use_block("main")


def _actions_by_request():
    path = (REPO_ROOT / "tests" / "fixtures" / "w2-branching" / "support-routing"
            / "expectations.json")
    actions = {}
    for case in json.loads(path.read_text(encoding="utf-8"))["cases"]:
        item = (case.get("expected_output") or {}).get("item") or {}
        actions[Path(case["input"]).stem] = item.get("action")
    return actions


def _routing_block():
    block = campaign_mod._use_block("routing")
    return block, campaign_mod.build_smoke_plan(
        campaign_mod._load_cells(), block["inputs"](),
        renderings=block["smoke_renderings"],
        strata=block["smoke_strata"]())


def test_routing_smoke_covers_every_action_in_every_mode_and_rendering():
    """The property the stratification exists for. Uniform over twenty requests,
    three draws per combination, gives a combination a 28% chance of seeing an
    UNASSIGNED -- so most would not, and the smoke would report green without
    having tried the one action support-intake never had."""
    _block, rows = _routing_block()
    actions = _actions_by_request()

    seen = {}
    for row in rows:
        seen.setdefault((row["mode"], row["rendering"]), set()).add(
            actions[campaign_mod._input_of(row)])

    n_modes = sum(len(c["modes"]) for c in campaign_mod._load_cells())
    assert len(seen) == n_modes * len(campaign_mod.RENDERINGS) == 42
    every_action = {"ASSIGN", "DEFER", "ESCALATE", "UNASSIGNED", "NEEDS_INFO"}
    for combo, found in seen.items():
        assert found == every_action, combo


def test_routing_smoke_is_the_size_the_stratification_implies():
    _block, rows = _routing_block()
    assert len(rows) == 6 * 7 * 5 == 210
    assert all(r["status"] == "pending" for r in rows)


def test_routing_smoke_covers_all_seven_renderings():
    """The counterpart of test_smoke_plan_leaves_the_l_cells_out, recording the
    opposite decision for the opposite reason: MAIN could leave L0..L4 out
    because another run had already vouched for them; here nothing has."""
    _block, rows = _routing_block()
    renderings = {row["rendering"] for row in rows}
    assert renderings == set(campaign_mod.RENDERINGS)
    assert renderings > set(campaign_mod.PROSE)
    assert set(api_mod.LEVELS) <= renderings


def test_routing_smoke_draws_only_requests_the_plan_stages():
    """r00-malformed has an expectation but no action, and is not in the
    manifest. Drawn into a stratum it would be a row the block's plan never
    runs."""
    _block, rows = _routing_block()
    staged = set(campaign_mod._load_request_ids())

    assert "r00-malformed" not in staged
    drawn = {campaign_mod._input_of(row) for row in rows}
    assert drawn <= staged
    for row in rows:
        assert 1 <= row["rep"] <= campaign_mod.REPS_PER_RENDERING


def test_routing_strata_are_the_composition_the_fixture_declares():
    """SS7.6: ten ASSIGN, five DEFER, two ESCALATE, two UNASSIGNED, one
    NEEDS_INFO. Read off expectations.json, so a restratified fixture that
    forgets to say so fails here rather than quietly smoking another shape."""
    campaign_mod._use_block("routing")
    sizes = {k: len(v) for k, v in campaign_mod._routing_action_strata().items()}
    assert sizes == {"ASSIGN": 10, "DEFER": 5, "ESCALATE": 2,
                     "UNASSIGNED": 2, "NEEDS_INFO": 1}
    assert sum(sizes.values()) == len(campaign_mod._load_request_ids()) == 20


def test_routing_smoke_is_deterministic_for_a_given_seed():
    block, first = _routing_block()
    args = (campaign_mod._load_cells(), block["inputs"]())
    kwargs = dict(renderings=block["smoke_renderings"],
                  strata=block["smoke_strata"]())
    assert campaign_mod.build_smoke_plan(*args, **kwargs) == first
    assert (campaign_mod.build_smoke_plan(*args, seed=1, **kwargs)
            != campaign_mod.build_smoke_plan(*args, seed=2, **kwargs))


def test_routing_smoke_is_grouped_by_cell():
    """A cell means one llama-server load. 210 rows must still be six starts."""
    _block, rows = _routing_block()
    seen, order = set(), []
    for row in rows:
        if not order or order[-1] != row["cell"]:
            assert row["cell"] not in seen, f"cell {row['cell']} interleaved"
            order.append(row["cell"])
            seen.add(row["cell"])
    assert order == [c["cell"] for c in campaign_mod._load_cells()]


def test_main_smoke_is_untouched_by_the_second_block():
    """Adding a block must not restratify the one that already ran."""
    campaign_mod._use_block("main")
    block = campaign_mod.BLOCKS["main"]
    assert block["smoke_strata"] is None
    assert tuple(block["smoke_renderings"]) == tuple(campaign_mod.PROSE)
    assert len(campaign_mod.build_smoke_plan(campaign_mod._load_cells(),
                                             campaign_mod._load_queue_ids())) == 36


# ---------------------------------------------------------------------------
# separation, block by block
# ---------------------------------------------------------------------------

def test_each_block_smokes_into_its_own_plan_file(restore_results_root):
    """Same reason the blocks do not share campaign-plan.json: one plan file for
    two blocks means the second erases the first, and a resume reads rows for a
    fixture it is not running."""
    names = [b["smoke_plan_name"] for b in campaign_mod.BLOCKS.values()]
    assert len(set(names)) == len(names), names

    plans = {}
    for name in campaign_mod.BLOCKS:
        block = campaign_mod._use_block(name)
        campaign_mod._use_results_root(campaign_mod.SMOKE_RESULTS_DIR,
                                       block["smoke_plan_name"])
        plans[name] = campaign_mod.PLAN_PATH

    assert len(set(plans.values())) == len(plans)
    assert all(p.parent == campaign_mod.SMOKE_RESULTS_DIR for p in plans.values())


def test_a_block_smoke_never_writes_into_that_blocks_real_plan(restore_results_root):
    """_use_block points the root at MAIN's; cmd_smoke redirects afterwards. Get
    that order wrong and a smoke overwrites campaign-plan-routing.json -- 1,680
    rows of a real run's record, replaced by 210 throwaway ones."""
    for name, block in campaign_mod.BLOCKS.items():
        campaign_mod._use_block(name)
        campaign_mod._use_results_root(campaign_mod.SMOKE_RESULTS_DIR,
                                       block["smoke_plan_name"])
        assert campaign_mod.PLAN_PATH.name != block["plan_name"]
        assert campaign_mod.MAIN_RESULTS_DIR not in campaign_mod.PLAN_PATH.parents


def test_smoke_runs_the_block_it_was_asked_for(restore_results_root, monkeypatch):
    """Before blocks reached the smoke, FIXTURE_ID kept its module default here:
    'smoke --block routing' would have started a server and run support-intake,
    and the green would have been about the wrong fixture."""
    ran = {}
    monkeypatch.setattr(campaign_mod, "_run_plan",
                        lambda plan_path: ran.update(fixture=campaign_mod.FIXTURE_ID,
                                                     plan=plan_path))

    campaign_mod.cmd_smoke(argparse.Namespace(plan=False, run=True, clean=False,
                                              block="routing"))

    assert ran["fixture"] == campaign_mod.SUPPORT_ROUTING_FIXTURE_ID
    assert ran["plan"] == (campaign_mod.SMOKE_RESULTS_DIR
                           / "campaign-smoke-plan-routing.json")
    assert campaign_mod.REPS_PER_RENDERING == 2
    assert campaign_mod.INDEX_PATH == campaign_mod.SMOKE_RESULTS_DIR / "index.jsonl"


def test_smoke_without_a_block_is_still_main(restore_results_root, monkeypatch):
    """Every command that grew a --block kept its behaviour when nobody passes
    one."""
    ran = {}
    monkeypatch.setattr(campaign_mod, "_run_plan",
                        lambda plan_path: ran.update(fixture=campaign_mod.FIXTURE_ID,
                                                     plan=plan_path))

    campaign_mod.cmd_smoke(argparse.Namespace(plan=False, run=True, clean=False))

    assert ran["fixture"] == campaign_mod.SUPPORT_INTAKE_FIXTURE_ID
    assert ran["plan"] == campaign_mod.SMOKE_PLAN_PATH
