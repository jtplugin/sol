"""
R1 tests for campaign.py: T06, T08, T09, T10, T11.

All server/network interaction is monkeypatched -- these are pure control-flow
tests over campaign.py's plan/reconcile/ladder/cell-lifecycle logic, no GPU,
no llama-server, no live model calls.

T06 (FR-10,FR-11) — plan reads campaign-cells.json: 5 cells, values match the
    frozen table in tests/env.json.
T08 (FR-14) — rows already 'done' in index.jsonl are marked done in a
    regenerated plan without rerunning.
T09 (FR-15,FR-17) — cell lifecycle: acceptance failure skips all pending rows
    of the cell (no run spent) and moves on; acceptance pass iterates every
    (mode, queue); server always stopped, even on exception.
T10 (FR-16) — adaptive ladder: mean conditional_rate >= 0.90 over 3 reps at a
    level skips the higher levels; a terna that never crosses 0.90 runs all
    five levels.
T11 (FR-18) — resume: rows already 'done' (simulating a kill mid-cell) are
    never re-executed when the ladder is walked again.
"""
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "tests"))

import runner.campaign as campaign_mod


class _FakeFidelity:
    def __init__(self, rate):
        self.conditional_rate = rate


class _FakeScore:
    def __init__(self, rate):
        self.fidelity = _FakeFidelity(rate)


# ---------------------------------------------------------------------------
# T06 — campaign-cells.json matches the frozen table
# ---------------------------------------------------------------------------

def test_plan_reads_five_cells_matching_env_json():
    cells = campaign_mod._load_cells()
    assert len(cells) == 5
    names = {c["cell"] for c in cells}
    assert names == {"qwen3.5-9b", "ministral-3-8b", "granite-4.1-8b", "gemma-4-12b", "phi4-mini"}

    for cell in cells:
        assert cell["kv_cache_type"] == "q8_0"
        assert cell["n_parallel"] == 1

    by_name = {c["cell"]: c for c in cells}
    assert by_name["qwen3.5-9b"]["ctx_size"] == 32768
    assert by_name["qwen3.5-9b"]["modes"] == ["llama-qwen3.5-9b-think", "llama-qwen3.5-9b-nothink"]
    assert by_name["ministral-3-8b"]["ctx_size"] == 31744
    assert by_name["ministral-3-8b"]["modes"] == ["llama-ministral-8b"]
    assert by_name["granite-4.1-8b"]["ctx_size"] == 28672
    assert by_name["gemma-4-12b"]["ctx_size"] == 31744
    assert by_name["phi4-mini"]["ctx_size"] == 32768


def test_build_plan_enumerates_full_coordinate_space():
    cells = campaign_mod._load_cells()
    queue_ids = campaign_mod._load_queue_ids()
    assert len(queue_ids) == 10

    rows = campaign_mod.build_plan(cells, queue_ids)

    n_modes = sum(len(c["modes"]) for c in cells)
    expected = n_modes * len(campaign_mod.LEVELS) * len(queue_ids) * campaign_mod.REPS_PER_LEVEL
    assert len(rows) == expected
    assert all(r["status"] == "pending" for r in rows)


# ---------------------------------------------------------------------------
# T08 — resume reconciliation against index.jsonl
# ---------------------------------------------------------------------------

def test_reconcile_marks_pending_rows_done_from_index(tmp_path, monkeypatch):
    monkeypatch.setattr(campaign_mod, "INDEX_PATH", tmp_path / "index.jsonl")
    monkeypatch.setattr(campaign_mod, "_mode_config", lambda mode: {
        "model": "model-x", "backend": "openai", "reasoning_budget": 0,
        "key": "", "url": "http://x", "temperature": 0.2, "thinking": None,
        "ctx_size": 1000, "kv_cache_type": "q8_0", "n_parallel": 1,
    })
    index_row = {
        "fixture_id": campaign_mod.SUPPORT_INTAKE_FIXTURE_ID,
        "staged_input_id": "queue-01", "context": "E0", "model_id": "model-x",
        "spec_version": campaign_mod.SPEC_VERSION, "backend": "openai",
        "reasoning_budget": 0, "predictability_layers": ["L1"],
        "status": "done",
    }
    (tmp_path / "index.jsonl").write_text(json.dumps(index_row) + "\n", encoding="utf-8")

    plan = [
        {"cell": "c1", "mode": "m1", "level": "L1", "queue": "queue-01", "rep": 1, "status": "pending"},
        {"cell": "c1", "mode": "m1", "level": "L1", "queue": "queue-01", "rep": 2, "status": "pending"},
        {"cell": "c1", "mode": "m1", "level": "L1", "queue": "queue-01", "rep": 3, "status": "pending"},
    ]
    campaign_mod._reconcile_with_index(plan)

    assert plan[0]["status"] == "done"
    assert plan[1]["status"] == "pending"
    assert plan[2]["status"] == "pending"


def test_reconcile_leaves_non_matching_rows_pending(tmp_path, monkeypatch):
    monkeypatch.setattr(campaign_mod, "INDEX_PATH", tmp_path / "index.jsonl")
    monkeypatch.setattr(campaign_mod, "_mode_config", lambda mode: {
        "model": "model-x", "backend": "openai", "reasoning_budget": 0,
        "key": "", "url": "http://x", "temperature": 0.2, "thinking": None,
        "ctx_size": 1000, "kv_cache_type": "q8_0", "n_parallel": 1,
    })
    (tmp_path / "index.jsonl").write_text("", encoding="utf-8")

    plan = [{"cell": "c1", "mode": "m1", "level": "L1", "queue": "queue-01", "rep": 1, "status": "pending"}]
    campaign_mod._reconcile_with_index(plan)
    assert plan[0]["status"] == "pending"


# ---------------------------------------------------------------------------
# T09 — cell lifecycle
# ---------------------------------------------------------------------------

def test_cell_acceptance_failure_skips_all_pending_no_run(monkeypatch, tmp_path):
    monkeypatch.setattr(campaign_mod, "_start_server", lambda cell: None)
    monkeypatch.setattr(campaign_mod, "_wait_for_server", lambda *a, **k: True)
    monkeypatch.setattr(campaign_mod, "_acceptance_check", lambda fixture_meta: False)
    stopped = []
    monkeypatch.setattr(campaign_mod, "_stop_server", lambda: stopped.append(True))
    ladder_calls = []
    monkeypatch.setattr(campaign_mod, "_run_ladder", lambda *a, **k: ladder_calls.append(a))
    monkeypatch.setattr(campaign_mod, "_save_plan", lambda plan: None)

    cell = {"cell": "c1", "gguf": "x.gguf", "ctx_size": 1000, "modes": ["m1"]}
    plan = [{"cell": "c1", "mode": "m1", "level": "L0", "queue": "queue-01", "rep": 1, "status": "pending"}]
    campaign_mod._run_cell(cell, plan, tmp_path, {}, {}, {})

    assert plan[0]["status"] == "skipped-acceptance"
    assert ladder_calls == []
    assert stopped == [True]


def test_cell_acceptance_pass_iterates_every_mode_and_queue(monkeypatch, tmp_path):
    monkeypatch.setattr(campaign_mod, "_start_server", lambda cell: None)
    monkeypatch.setattr(campaign_mod, "_wait_for_server", lambda *a, **k: True)
    monkeypatch.setattr(campaign_mod, "_acceptance_check", lambda fixture_meta: True)
    stopped = []
    monkeypatch.setattr(campaign_mod, "_stop_server", lambda: stopped.append(True))
    ladder_calls = []
    monkeypatch.setattr(
        campaign_mod, "_run_ladder",
        lambda cell, mode, queue_id, plan, *a, **k: ladder_calls.append((mode, queue_id)),
    )
    monkeypatch.setattr(campaign_mod, "_save_plan", lambda plan: None)

    cell = {"cell": "c1", "gguf": "x.gguf", "ctx_size": 1000, "modes": ["m1", "m2"]}
    plan = [
        {"cell": "c1", "mode": "m1", "level": "L0", "queue": "queue-01", "rep": 1, "status": "pending"},
        {"cell": "c1", "mode": "m2", "level": "L0", "queue": "queue-02", "rep": 1, "status": "pending"},
    ]
    campaign_mod._run_cell(cell, plan, tmp_path, {}, {}, {})

    assert set(ladder_calls) == {("m1", "queue-01"), ("m2", "queue-02")}
    assert stopped == [True]


def test_cell_no_pending_rows_skips_without_starting_server(monkeypatch, tmp_path):
    started = []
    monkeypatch.setattr(campaign_mod, "_start_server", lambda cell: started.append(True))
    stopped = []
    monkeypatch.setattr(campaign_mod, "_stop_server", lambda: stopped.append(True))

    cell = {"cell": "c1", "gguf": "x.gguf", "ctx_size": 1000, "modes": ["m1"]}
    plan = [{"cell": "c1", "mode": "m1", "level": "L0", "queue": "queue-01", "rep": 1, "status": "done"}]
    campaign_mod._run_cell(cell, plan, tmp_path, {}, {}, {})

    assert started == []
    assert stopped == []


def test_cell_server_stopped_even_on_exception(monkeypatch, tmp_path):
    monkeypatch.setattr(campaign_mod, "_start_server", lambda cell: None)
    monkeypatch.setattr(campaign_mod, "_wait_for_server", lambda *a, **k: True)

    def boom(fixture_meta):
        raise RuntimeError("boom")
    monkeypatch.setattr(campaign_mod, "_acceptance_check", boom)
    stopped = []
    monkeypatch.setattr(campaign_mod, "_stop_server", lambda: stopped.append(True))

    cell = {"cell": "c1", "gguf": "x.gguf", "ctx_size": 1000, "modes": ["m1"]}
    plan = [{"cell": "c1", "mode": "m1", "level": "L0", "queue": "queue-01", "rep": 1, "status": "pending"}]
    with pytest.raises(RuntimeError):
        campaign_mod._run_cell(cell, plan, tmp_path, {}, {}, {})

    assert stopped == [True]


# ---------------------------------------------------------------------------
# T10 — adaptive ladder
# ---------------------------------------------------------------------------

def _full_ladder_plan(cell="c1", mode="m1", queue="q1"):
    return [
        {"cell": cell, "mode": mode, "level": lvl, "queue": queue, "rep": rep, "status": "pending"}
        for lvl in campaign_mod.LEVELS for rep in (1, 2, 3)
    ]


def test_ladder_skips_higher_levels_when_threshold_met(monkeypatch):
    calls = []

    def fake_execute_row(row, cell, mode, level, queue_id, *a, **k):
        calls.append(level)
        row["status"] = "done"
        return _FakeScore(0.95 if level == "L0" else 0.0)

    monkeypatch.setattr(campaign_mod, "_execute_row", fake_execute_row)
    monkeypatch.setattr(campaign_mod, "_save_plan", lambda plan: None)

    plan = _full_ladder_plan()
    campaign_mod._run_ladder({"cell": "c1"}, "m1", "q1", plan, None, {}, {}, {})

    assert set(calls) == {"L0"}
    higher = [r for r in plan if r["level"] != "L0"]
    assert all(r["status"] == "skipped-adaptive" for r in higher)
    l0_rows = [r for r in plan if r["level"] == "L0"]
    assert all(r["status"] == "done" for r in l0_rows)


def test_ladder_runs_all_five_levels_when_threshold_never_met(monkeypatch):
    def fake_execute_row(row, cell, mode, level, queue_id, *a, **k):
        row["status"] = "done"
        return _FakeScore(0.10)

    monkeypatch.setattr(campaign_mod, "_execute_row", fake_execute_row)
    monkeypatch.setattr(campaign_mod, "_save_plan", lambda plan: None)

    plan = _full_ladder_plan()
    campaign_mod._run_ladder({"cell": "c1"}, "m1", "q1", plan, None, {}, {}, {})

    assert all(r["status"] == "done" for r in plan)


# ---------------------------------------------------------------------------
# T11 — resume: already-done rows never re-executed
# ---------------------------------------------------------------------------

def test_ladder_resume_skips_already_done_rows(monkeypatch):
    calls = []

    def fake_execute_row(row, cell, mode, level, queue_id, *a, **k):
        calls.append((level, row["rep"]))
        row["status"] = "done"
        return _FakeScore(0.10)

    monkeypatch.setattr(campaign_mod, "_execute_row", fake_execute_row)
    monkeypatch.setattr(campaign_mod, "_save_plan", lambda plan: None)

    plan = _full_ladder_plan()
    plan[0]["status"] = "done"  # (L0, rep=1) simulates a row completed before the kill

    campaign_mod._run_ladder({"cell": "c1"}, "m1", "q1", plan, None, {}, {}, {})

    assert ("L0", 1) not in calls
    assert ("L0", 2) in calls
    assert ("L0", 3) in calls
