"""
R1 tests for the --level scale: T01, T02, T03, T05.

T01 (FR-01,FR-02,FR-04,FR-08) — --level (choices L0-L4, default L1) accepted
    by run.py and api_executor.py, forwarded through to run_headless_api;
    run.py's claude-code branch stays untouched.
T02 (FR-03) — _normalize_rendering: the cell applied, recorded as a cell.
T03 (FR-05,FR-09) — _build_prompt_e0 builds the scale of SS5.1: L0 is the task
    material (input data + SOL script) with no explanatory prose, L1 is L0 plus
    the minimal instruction verbatim, and the chain is a strict prefix chain
    from L0 up. Criterion revised by the L-scale realignment: what is asserted is conformity to
    the protocol, not identity with yesterday's output — a golden capture of the
    current prompt would have frozen the defect instead of catching it.
T05 (FR-07) — _append_index writes process_rendering; index rows written before
    the key existed stay readable (absence, not error).
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
# T02 — _normalize_rendering
# ---------------------------------------------------------------------------

def test_normalize_rendering_is_identity_on_every_cell():
    # SS5.4: seven cells on one selector -- five levels of the L scale plus the
    # two prose renderings, which replace the SOL document rather than extend it.
    for cell in ("L0", "L1", "L2", "L3", "L4",
                 "prose-mechanical", "prose-generated"):
        assert api_mod._normalize_rendering(cell) == cell


def test_normalize_rendering_unrecognized_falls_back_to_l1():
    assert api_mod._normalize_rendering("bogus") == "L1"


def test_level_is_recorded_as_a_level_not_as_layer_labels():
    # After the L-scale realignment: the record used to carry ["L1", "L2"] for level L2 — the labels of
    # the predictability LAYERS, a different taxonomy that happens to share the
    # letters. A level is one level.
    assert api_mod._normalize_rendering("L2") == "L2"
    assert not hasattr(api_mod, "_LEVEL_LAYERS")
    assert not hasattr(api_mod, "_layers_for_level")


# ---------------------------------------------------------------------------
# T03 — _build_prompt_e0 builds the scale the protocol prescribes
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not _has_hydrated_queues(),
                    reason="queue-*.json not hydrated locally -- run hydrate.py --mode queues")
class TestBuildPromptE0Levels:
    def test_a_prose_rendering_replaces_the_sol_document(self):
        # SS5.4: prose does not extend the SOL document, it stands in for it.
        # The task material is still there -- the input is substituted into the
        # prose document exactly as into the SOL one -- but the script is not.
        sol_doc, bundle, fixture_body = _real_bundle()
        _, _, _, meta = runner_mod._load_fixture(SUPPORT_INTAKE)
        prompt = api_mod._build_prompt_e0(
            sol_doc, bundle, fixture_body, level="prose-generated",
            prose_bodies=meta["prose"])
        assert '"ROUTINE"' not in prompt
        assert "{{file_content}}" not in prompt
        assert json.dumps(bundle.payload, indent=2, ensure_ascii=False) in prompt
        assert "[fixture-w2-support-intake][main] EVAL:" in prompt
        assert runner_mod.L1_INSTRUCTION not in prompt

    def test_a_missing_prose_rendering_is_refused_not_downgraded(self):
        # a silent fallback to the SOL prompt would file a measurement of SOL
        # under a prose cell, and the failure would be invisible in the data.
        sol_doc, bundle, fixture_body = _real_bundle()
        with pytest.raises(FileNotFoundError):
            api_mod._build_prompt_e0(sol_doc, bundle, fixture_body,
                                     level="prose-mechanical", prose_bodies={})

    def test_l0_carries_the_task_material_and_no_explanatory_prose(self):
        sol_doc, bundle, fixture_body = _real_bundle()
        prompt = api_mod._build_prompt_e0(sol_doc, bundle, fixture_body, level="L0")
        # the process, and the data the process needs, are present at L0:
        # subtracting them would not measure context, it would break the task
        assert "## SOL script" in prompt
        assert '"ROUTINE"' in prompt
        assert "## Product catalog" in prompt
        assert "hours_table" in prompt
        assert json.dumps(bundle.payload, indent=2, ensure_ascii=False) in prompt
        assert "{{file_content}}" not in prompt
        # and nothing that explains how SOL is to be read
        assert runner_mod.L1_INSTRUCTION not in prompt

    def test_l1_is_exactly_l0_plus_the_minimal_instruction(self):
        sol_doc, bundle, fixture_body = _real_bundle()
        l0 = api_mod._build_prompt_e0(sol_doc, bundle, fixture_body, level="L0")
        l1 = api_mod._build_prompt_e0(sol_doc, bundle, fixture_body, level="L1")
        assert l1 == l0 + "\n\n" + runner_mod.L1_INSTRUCTION

    def test_default_level_is_l1(self):
        sol_doc, bundle, fixture_body = _real_bundle()
        default_prompt = api_mod._build_prompt_e0(sol_doc, bundle, fixture_body)
        l1_prompt = api_mod._build_prompt_e0(sol_doc, bundle, fixture_body, level="L1")
        assert default_prompt == l1_prompt

    def test_minimal_instruction_is_the_protocol_wording(self):
        # SS5.1, verbatim: the level is defined by this sentence, not by a
        # paraphrase of it that happens to be in the fixture
        assert runner_mod.L1_INSTRUCTION == (
            "follow the algorithm described in the JSON literally")

    def test_levels_are_additive_prefix_chain(self):
        sol_doc, bundle, fixture_body = _real_bundle()
        l0 = api_mod._build_prompt_e0(sol_doc, bundle, fixture_body, level="L0")
        l1 = api_mod._build_prompt_e0(sol_doc, bundle, fixture_body, level="L1")
        l2 = api_mod._build_prompt_e0(sol_doc, bundle, fixture_body, level="L2")
        l3 = api_mod._build_prompt_e0(sol_doc, bundle, fixture_body, level="L3")
        l4 = api_mod._build_prompt_e0(sol_doc, bundle, fixture_body, level="L4")
        assert l1.startswith(l0) and l1 != l0
        assert l2.startswith(l1) and l2 != l1
        assert l3.startswith(l2) and l3 != l2
        assert l4.startswith(l3) and l4 != l3

    def test_unrecognized_level_falls_back_to_l1(self):
        sol_doc, bundle, fixture_body = _real_bundle()
        l1 = api_mod._build_prompt_e0(sol_doc, bundle, fixture_body, level="L1")
        weird = api_mod._build_prompt_e0(sol_doc, bundle, fixture_body, level="bogus")
        assert weird == l1


# ---------------------------------------------------------------------------
# T05 — _append_index writes process_rendering; old rows stay readable
# ---------------------------------------------------------------------------

def test_append_index_includes_process_rendering(tmp_path, monkeypatch):
    monkeypatch.setattr(runner_mod, "RESULTS_DIR", tmp_path)
    monkeypatch.setattr(runner_mod, "INDEX_PATH", tmp_path / "index.jsonl")

    config = Config(fixture_id="f", context="E0", model_id="m",
                    process_rendering="L2")
    record = RunRecord(
        run_id="r1", timestamp="2026-01-01T00:00:00+00:00", config=config,
        staged_input_id="i1", execution=Execution(status="done"),
        trace=Trace(), output=Output(), usage=Usage(),
    )
    score = check(record, {"cases": []})
    runner_mod._append_index(record, score)

    lines = (tmp_path / "index.jsonl").read_text(encoding="utf-8").splitlines()
    row = json.loads(lines[-1])
    assert row["process_rendering"] == "L2"


def test_pre_card_index_row_without_key_reads_without_error():
    # rows written before the key existed carry neither process_rendering nor its
    # predecessor -- reading it back is a plain .get(), never a KeyError (FR-07).
    old_row = json.loads(json.dumps({"run_id": "old", "fixture_id": "f", "status": "done"}))
    assert old_row.get("process_rendering") is None
