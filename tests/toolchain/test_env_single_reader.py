"""
R1 tests for the single reader of the mode files.

T01 — run.py forwards the four cell-configuration fields introduced by the 2026-08-19 revision
      (thinking, ctx_size, kv_cache_type, n_parallel) to run_headless_api, and
      the three former env.json readers (api_executor._load_mode,
      run._load_env_entry, preprocess_p2a._load_mode) all go through the single
      reader api_executor._load_mode_entry.

The source was split in two: tests/modes.json (configuration, tracked) and
tests/env.json (the Anthropic keys, gitignored). The single-reader property is
still asserted behaviourally, now over both: patching *only*
api_executor.MODES_PATH and api_executor.ENV_PATH must be enough for run.py and
preprocess_p2a to see the temporary files. Before that fix each module
parsed the file on its own, so run.py kept reading the real one and the modes
were not found. The expected values below are unchanged on purpose:
the key now comes from the other file and no caller notices.
"""
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "tests"))

import runner.run as run_mod
import runner.api_executor as api_mod
import scripts.preprocess_p2a as p2a_mod

REAL_MODES_PATH = REPO_ROOT / "tests" / "modes.json"

CELL = {"ctx_size": 32768, "kv_cache_type": "q8_0", "n_parallel": 1}

MODES = [
    dict(mode="cell-think", runner_type="api", backend="openai",
         url="http://localhost:8090", model="m", reasoning=12000,
         temperature=0.2, thinking=True, **CELL),
    dict(mode="cell-nothink", runner_type="api", backend="openai",
         url="http://localhost:8090", model="m", reasoning=12000,
         temperature=0.2, thinking=False, **CELL),
    # No cell fields at all: they must stay None (today's untouched behaviour).
    dict(mode="cell-bare", runner_type="api", backend="anthropic",
         url="https://api.anthropic.com", model="m", reasoning=0),
]

# Credentials live apart: only cell-bare is backend=anthropic, so it is
# the only mode of the three that needs a key at all.
ENV = [{"mode": "cell-bare", "key": "k"}]


@pytest.fixture
def env_json(monkeypatch, tmp_path):
    """Temporary modes.json + env.json, installed on the single reader only."""
    modes_path = tmp_path / "modes.json"
    modes_path.write_text(json.dumps({"modes": MODES}), encoding="utf-8")
    monkeypatch.setattr(api_mod, "MODES_PATH", modes_path)
    env_path = tmp_path / "env.json"
    env_path.write_text(json.dumps({"modes": ENV}), encoding="utf-8")
    monkeypatch.setattr(api_mod, "ENV_PATH", env_path)
    return modes_path


@pytest.fixture
def captured_api(monkeypatch, tmp_path):
    """Capture run_headless_api kwargs; give run.py a fixture dir that exists."""
    captured = {}
    monkeypatch.setattr(run_mod, "run_headless_api", lambda **kw: captured.update(kw))
    monkeypatch.setattr(run_mod, "FIXTURES_DIR", tmp_path)
    (tmp_path / "fx").mkdir(exist_ok=True)
    return captured


def _run(mode: str) -> None:
    run_mod.main(["--fixture", "fx", "--input", "i1", "--mode", mode])


# ---------------------------------------------------------------------------
# T01 — the four cell fields cross run.py
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("mode,expected_thinking", [
    ("cell-think", True),
    ("cell-nothink", False),
])
def test_run_py_forwards_thinking(env_json, captured_api, mode, expected_thinking):
    _run(mode)
    assert captured_api["thinking"] is expected_thinking


def test_run_py_forwards_ctx_size_kv_cache_type_n_parallel(env_json, captured_api):
    _run("cell-think")
    assert captured_api["ctx_size"] == 32768
    assert captured_api["kv_cache_type"] == "q8_0"
    assert captured_api["n_parallel"] == 1


def test_run_py_cell_fields_absent_stay_none(env_json, captured_api):
    _run("cell-bare")
    for field in ("thinking", "ctx_size", "kv_cache_type", "n_parallel"):
        assert captured_api[field] is None


def test_think_and_nothink_are_distinguishable(env_json, monkeypatch, tmp_path):
    """The regression proper: the two arms of the A/B must not collapse."""
    seen = []
    monkeypatch.setattr(run_mod, "run_headless_api", lambda **kw: seen.append(kw))
    monkeypatch.setattr(run_mod, "FIXTURES_DIR", tmp_path)
    (tmp_path / "fx").mkdir(exist_ok=True)
    _run("cell-think")
    _run("cell-nothink")
    assert seen[0]["thinking"] != seen[1]["thinking"]


# ---------------------------------------------------------------------------
# T01 — one reader: patching the two api_executor paths is enough for everyone
# ---------------------------------------------------------------------------

def test_run_py_reads_through_single_reader(env_json):
    entry = run_mod._load_env_entry("cell-think")
    assert entry["thinking"] is True
    assert entry["runner_type"] == "api"


def test_preprocess_p2a_reads_through_single_reader(env_json):
    key, url, model, backend = p2a_mod._load_mode("cell-bare")
    assert (key, url, model, backend) == ("k", "https://api.anthropic.com", "m", "anthropic")


def test_load_env_entry_delegates_to_load_mode_entry(monkeypatch):
    calls = []
    monkeypatch.setattr(api_mod, "_load_mode_entry",
                        lambda mode: calls.append(mode) or {"mode": mode})
    run_mod._load_env_entry("whatever")
    assert calls == ["whatever"]


def test_preprocess_p2a_delegates_to_api_executor(monkeypatch):
    calls = []
    monkeypatch.setattr(
        api_mod, "_load_mode",
        lambda mode: calls.append(mode) or ("k", "u", "m", "b", 0, None, None, None, None, None),
    )
    assert p2a_mod._load_mode("whatever") == ("k", "u", "m", "b")
    assert calls == ["whatever"]


def test_load_mode_is_a_projection_of_load_mode_entry(env_json):
    assert api_mod._load_mode("cell-think") == (
        "", "http://localhost:8090", "m", "openai", 12000, 0.2, True, 32768, "q8_0", 1,
    )
    assert api_mod._load_mode("cell-bare") == (
        "k", "https://api.anthropic.com", "m", "anthropic", 0, None, None, None, None, None,
    )


# ---------------------------------------------------------------------------
# T01 — the real qwen cell, read from tests/modes.json (tracked)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("mode,expected_thinking", [
    ("llama-qwen3.5-9b-think", True),
    ("llama-qwen3.5-9b-nothink", False),
])
def test_real_qwen_modes_forward_thinking(captured_api, mode, expected_thinking):
    """No skipif: modes.json is in git, so this runs on a fresh clone too. Both
    qwen modes are backend=openai and never touch the credentials file."""
    known = {e.get("mode") for e in
             json.loads(REAL_MODES_PATH.read_text(encoding="utf-8")).get("modes", [])}
    if mode not in known:
        pytest.skip(f"mode {mode} not declared in tests/modes.json")
    _run(mode)
    assert captured_api["thinking"] is expected_thinking
    assert captured_api["ctx_size"] is not None
    assert captured_api["kv_cache_type"] is not None
    assert captured_api["n_parallel"] is not None
