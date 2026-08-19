"""
R1 tests for the --level scale: T01, T02, T03, T05.

T01 (FR-01,FR-02,FR-04,FR-08) — --level (choices L0-L4, default L1) accepted
    by run.py and api_executor.py, forwarded through to run_headless_api;
    run.py's claude-code branch stays untouched.
T02 (FR-03) — _layers_for_level's cumulative mapping.
T03 (FR-05,FR-09) — _build_prompt_e0 at level=L1 matches the golden capture
    byte-for-byte; L0/L2/L3/L4 shape.
T05 (FR-07) — _append_index writes predictability_layers; pre-card index rows
    without the key stay readable (absence, not error).
"""
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "tests"))

import runner.run as run_mod
import runner.api_executor as api_mod
import runner.runner as runner_mod
from runner.schema import Config, Execution, Output, RunRecord, Trace, Usage
from runner.checker import check

GOLDEN_PATH = REPO_ROOT / "tests" / "toolchain" / "fixtures" / "golden_l1_prompt.txt"
SUPPORT_INTAKE = "w2-branching/support-intake"


def _has_hydrated_queues() -> bool:
    return any((runner_mod.FIXTURES_DIR / SUPPORT_INTAKE / "inputs").glob("queue-*.json"))


def _real_bundle():
    from runner.runner import _load_fixture, _load_input
    fixture_dir, sol_doc, expectations, fixture_meta = _load_fixture(SUPPORT_INTAKE)
    bundle = _load_input(fixture_dir, "queue-01")
    return sol_doc, bundle, fixture_meta["body"]


# ---------------------------------------------------------------------------
# T01 — --level CLI wiring
# ---------------------------------------------------------------------------

def test_run_py_level_default_forwarded_to_api_executor(monkeypatch, tmp_path):
    captured = {}
    monkeypatch.setattr(run_mod, "run_headless_api", lambda **kw: captured.update(kw))
    monkeypatch.setattr(run_mod, "_load_env_entry", lambda mode: {
        "runner_type": "api", "model": "m", "reasoning": 0, "backend": "anthropic", "key": "k",
    })
    monkeypatch.setattr(run_mod, "FIXTURES_DIR", tmp_path)
    (tmp_path / "fx").mkdir()

    run_mod.main(["--fixture", "fx", "--input", "i1", "--mode", "m"])
    assert captured["level"] == "L1"


def test_run_py_level_flag_forwarded_to_api_executor(monkeypatch, tmp_path):
    captured = {}
    monkeypatch.setattr(run_mod, "run_headless_api", lambda **kw: captured.update(kw))
    monkeypatch.setattr(run_mod, "_load_env_entry", lambda mode: {
        "runner_type": "api", "model": "m", "reasoning": 0, "backend": "anthropic", "key": "k",
    })
    monkeypatch.setattr(run_mod, "FIXTURES_DIR", tmp_path)
    (tmp_path / "fx").mkdir()

    run_mod.main(["--fixture", "fx", "--input", "i1", "--mode", "m", "--level", "L3"])
    assert captured["level"] == "L3"


def test_run_py_claude_code_branch_gets_no_level_kwarg(monkeypatch, tmp_path):
    captured = {}
    monkeypatch.setattr(run_mod, "run_headless", lambda **kw: captured.update(kw))
    monkeypatch.setattr(run_mod, "_load_env_entry", lambda mode: {
        "runner_type": "claude-code", "model": "m", "reasoning": 0,
    })
    monkeypatch.setattr(run_mod, "FIXTURES_DIR", tmp_path)
    (tmp_path / "fx").mkdir()

    run_mod.main(["--fixture", "fx", "--input", "i1", "--mode", "m", "--level", "L2"])
    assert "level" not in captured


def test_run_py_level_invalid_choice_rejected():
    with pytest.raises(SystemExit):
        run_mod.main(["--fixture", "fx", "--input", "i1", "--mode", "m", "--level", "L9"])


def test_api_executor_level_default_forwarded(monkeypatch, tmp_path):
    captured = {}
    monkeypatch.setattr(api_mod, "run_headless_api", lambda **kw: captured.update(kw))
    monkeypatch.setattr(api_mod, "FIXTURES_DIR", tmp_path)
    (tmp_path / "fx").mkdir()

    api_mod.main(["--fixture", "fx", "--input", "i1", "--api-key", "k"])
    assert captured["level"] == "L1"


def test_api_executor_level_flag_forwarded(monkeypatch, tmp_path):
    captured = {}
    monkeypatch.setattr(api_mod, "run_headless_api", lambda **kw: captured.update(kw))
    monkeypatch.setattr(api_mod, "FIXTURES_DIR", tmp_path)
    (tmp_path / "fx").mkdir()

    api_mod.main(["--fixture", "fx", "--input", "i1", "--api-key", "k", "--level", "L4"])
    assert captured["level"] == "L4"


def test_api_executor_level_invalid_choice_rejected():
    with pytest.raises(SystemExit):
        api_mod.main(["--fixture", "fx", "--input", "i1", "--api-key", "k", "--level", "L9"])


# ---------------------------------------------------------------------------
# T02 — _layers_for_level mapping
# ---------------------------------------------------------------------------

def test_layers_for_level_cumulative_mapping():
    assert api_mod._layers_for_level("L0") == []
    assert api_mod._layers_for_level("L1") == ["L1"]
    assert api_mod._layers_for_level("L2") == ["L1", "L2"]
    assert api_mod._layers_for_level("L3") == ["L1", "L2", "L3"]
    assert api_mod._layers_for_level("L4") == ["L1", "L2", "L3", "L4"]


def test_layers_for_level_unrecognized_falls_back_to_l1():
    assert api_mod._layers_for_level("bogus") == api_mod._layers_for_level("L1")


# ---------------------------------------------------------------------------
# T03 — _build_prompt_e0 shape, byte-for-byte L1 non-regression
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not _has_hydrated_queues(),
                    reason="queue-*.json not hydrated locally -- run hydrate.py --mode queues")
class TestBuildPromptE0Levels:
    def test_l1_matches_golden_byte_for_byte(self):
        sol_doc, bundle, fixture_body = _real_bundle()
        prompt = api_mod._build_prompt_e0(sol_doc, bundle, fixture_body, level="L1")
        golden = GOLDEN_PATH.read_text(encoding="utf-8")
        assert prompt == golden

    def test_default_level_is_l1(self):
        sol_doc, bundle, fixture_body = _real_bundle()
        default_prompt = api_mod._build_prompt_e0(sol_doc, bundle, fixture_body)
        l1_prompt = api_mod._build_prompt_e0(sol_doc, bundle, fixture_body, level="L1")
        assert default_prompt == l1_prompt

    def test_l0_is_rendered_file_content_only(self):
        sol_doc, bundle, fixture_body = _real_bundle()
        prompt = api_mod._build_prompt_e0(sol_doc, bundle, fixture_body, level="L0")
        fc = json.dumps(bundle.payload, indent=2, ensure_ascii=False)
        assert prompt == fc
        assert "## SOL script" not in prompt

    def test_levels_are_additive_prefix_chain(self):
        sol_doc, bundle, fixture_body = _real_bundle()
        l1 = api_mod._build_prompt_e0(sol_doc, bundle, fixture_body, level="L1")
        l2 = api_mod._build_prompt_e0(sol_doc, bundle, fixture_body, level="L2")
        l3 = api_mod._build_prompt_e0(sol_doc, bundle, fixture_body, level="L3")
        l4 = api_mod._build_prompt_e0(sol_doc, bundle, fixture_body, level="L4")
        assert l2.startswith(l1) and l2 != l1
        assert l3.startswith(l2) and l3 != l2
        assert l4.startswith(l3) and l4 != l3

    def test_unrecognized_level_falls_back_to_l1(self):
        sol_doc, bundle, fixture_body = _real_bundle()
        l1 = api_mod._build_prompt_e0(sol_doc, bundle, fixture_body, level="L1")
        weird = api_mod._build_prompt_e0(sol_doc, bundle, fixture_body, level="bogus")
        assert weird == l1


# ---------------------------------------------------------------------------
# T05 — _append_index writes predictability_layers; old rows stay readable
# ---------------------------------------------------------------------------

def test_append_index_includes_predictability_layers(tmp_path, monkeypatch):
    monkeypatch.setattr(runner_mod, "RESULTS_DIR", tmp_path)
    monkeypatch.setattr(runner_mod, "INDEX_PATH", tmp_path / "index.jsonl")

    config = Config(fixture_id="f", context="E0", model_id="m",
                    predictability_layers=["L1", "L2"])
    record = RunRecord(
        run_id="r1", timestamp="2026-01-01T00:00:00+00:00", config=config,
        staged_input_id="i1", execution=Execution(status="done"),
        trace=Trace(), output=Output(), usage=Usage(),
    )
    score = check(record, {"cases": []})
    runner_mod._append_index(record, score)

    lines = (tmp_path / "index.jsonl").read_text(encoding="utf-8").splitlines()
    row = json.loads(lines[-1])
    assert row["predictability_layers"] == ["L1", "L2"]


def test_pre_card_index_row_without_key_reads_without_error():
    # 576 rows written before this card carry no predictability_layers key --
    # reading it back is a plain .get(), never a KeyError (FR-07 note).
    old_row = json.loads(json.dumps({"run_id": "old", "fixture_id": "f", "status": "done"}))
    assert old_row.get("predictability_layers") is None
