"""
R1 tests for the split of configuration and credentials into two files.

tests/modes.json holds the mode configuration and is tracked in git;
tests/env.json holds only the Anthropic keys and stays gitignored. The copy
that used to make the configuration reconstructible (tests/campaign-modes.json)
is gone, and with it the divergence class that kept the gemma-4-12b typo alive
for two months.

What is asserted here:
  - the shape of modes.json: twelve modes, no 'key' anywhere, frozen model ids,
    'thinking' absent (not false) where it was absent before;
  - the shape of env.example.json: two credential entries and nothing else;
  - the fresh-clone property: with no tests/env.json at all, a local mode loads
    and an anthropic mode still dies on the same guard as before;
  - build_plan does not need the credentials file;
  - a static check on run_w1_ollama.py, whose regression would be silent.
"""
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "tests"))

import runner.api_executor as api_mod
import runner.campaign as campaign_mod

MODES_PATH = REPO_ROOT / "tests" / "modes.json"
EXAMPLE_PATH = REPO_ROOT / "tests" / "env.example.json"

EXPECTED_ORDER = [
    "claude-api",
    "claude-api-thinking",
    "claude-code-local",
    "claude-code-haiku",
    "claude-code-sonnet",
    "claude-code-opus",
    "llama-qwen3.5-9b-think",
    "llama-qwen3.5-9b-nothink",
    "llama-ministral-8b",
    "llama-phi4-mini",
    "llama-gemma-4-12b",
    "llama-granite-4.1-8b",
]

# Frozen literally here on purpose, not derived from another file: 'model' is
# the provenance label written as Config.model_id into every record and into
# index.jsonl, and campaign._reconcile_with_index joins the resume on it. A
# cosmetic change does not fail — it silently re-runs work already done.
EXPECTED_MODELS = {
    "claude-api":               "claude-sonnet-4-6",
    "claude-api-thinking":      "claude-sonnet-4-6",
    "claude-code-local":        "claude-opus-4-8",
    "claude-code-haiku":        "claude-haiku-4-5",
    "claude-code-sonnet":       "claude-sonnet-5",
    "claude-code-opus":         "claude-opus-5",
    "llama-qwen3.5-9b-think":   "ai-models/Qwen3.5-9B-Q4_K_M.gguf",
    "llama-qwen3.5-9b-nothink": "ai-models/Qwen3.5-9B-Q4_K_M.gguf",
    "llama-ministral-8b":       "ai-models/Ministral-3-8B-Instruct-2512-Q4_K_M.gguf",
    "llama-phi4-mini":          "ai-models/Phi-4-mini-instruct-Q4_K_M.gguf",
    "llama-gemma-4-12b":        "ai-models/gemma-4-12b-it-qat-UD-Q4_K_L.gguf",
    "llama-granite-4.1-8b":     "ai-models/granite-4.1-8b-Q4_K_M.gguf",
}

# Non-reasoning models: the key must be absent, not false. _load_mode returns
# entry.get("thinking"), and api_executor tells None from False to decide
# whether to send chat_template_kwargs.enable_thinking at all.
NO_THINKING_KEY = ["llama-ministral-8b", "llama-phi4-mini", "llama-granite-4.1-8b"]


def _modes():
    return json.loads(MODES_PATH.read_text(encoding="utf-8"))["modes"]


def _by_mode():
    return {e["mode"]: e for e in _modes()}


# ---------------------------------------------------------------------------
# Shape of tests/modes.json
# ---------------------------------------------------------------------------

def test_modes_json_declares_the_twelve_modes_in_order():
    assert MODES_PATH.exists(), f"{MODES_PATH} missing — it is tracked, not gitignored"
    assert [e["mode"] for e in _modes()] == EXPECTED_ORDER


def test_modes_json_carries_no_credentials():
    """The one place in that split where a mistake becomes a secret in git."""
    offenders = [e["mode"] for e in _modes() if "key" in e]
    assert offenders == [], f"'key' present in tracked modes.json for: {offenders}"


def test_model_ids_are_the_frozen_ones():
    assert {m: e["model"] for m, e in _by_mode().items()} == EXPECTED_MODELS


def test_thinking_key_absent_where_it_was_absent():
    by_mode = _by_mode()
    for mode in NO_THINKING_KEY:
        assert "thinking" not in by_mode[mode], (
            f"{mode}: 'thinking' must be absent, not {by_mode[mode].get('thinking')!r}"
        )


def test_campaign_modes_copy_is_gone():
    assert (REPO_ROOT / "tests" / "campaign-modes.json").exists() is False


# ---------------------------------------------------------------------------
# Shape of tests/env.example.json
# ---------------------------------------------------------------------------

def test_env_example_is_a_credentials_only_template():
    modes = json.loads(EXAMPLE_PATH.read_text(encoding="utf-8"))["modes"]
    assert {e["mode"] for e in modes} == {"claude-api", "claude-api-thinking"}
    for entry in modes:
        assert set(entry) == {"mode", "key"}, f"{entry['mode']}: extra fields {set(entry) - {'mode', 'key'}}"


# ---------------------------------------------------------------------------
# Fresh clone: no tests/env.json on disk at all
# ---------------------------------------------------------------------------

LOCAL_MODE = {
    "mode": "local-cell", "runner_type": "api", "backend": "openai",
    "url": "http://localhost:8090", "model": "m", "reasoning": 12000,
    "temperature": 0.2, "thinking": True,
    "ctx_size": 32768, "kv_cache_type": "q8_0", "n_parallel": 1,
}
ANTHROPIC_MODE = {
    "mode": "remote-cell", "runner_type": "api", "backend": "anthropic",
    "url": "https://api.anthropic.com", "model": "m", "reasoning": 0,
}


@pytest.fixture
def no_env_json(monkeypatch, tmp_path):
    """modes.json present, env.json pointed at a file that does not exist."""
    path = tmp_path / "modes.json"
    path.write_text(json.dumps({"modes": [LOCAL_MODE, ANTHROPIC_MODE]}), encoding="utf-8")
    monkeypatch.setattr(api_mod, "MODES_PATH", path)
    missing = tmp_path / "assente.json"
    assert not missing.exists()
    monkeypatch.setattr(api_mod, "ENV_PATH", missing)
    return path


def test_local_mode_loads_without_any_credentials_file(no_env_json):
    assert api_mod._load_mode("local-cell") == (
        "", "http://localhost:8090", "m", "openai", 12000, 0.2, True, 32768, "q8_0", 1,
    )


def test_anthropic_mode_without_key_dies_on_the_usual_guard(no_env_json):
    """FR-04 unchanged: the missing key is the error, not the missing file."""
    with pytest.raises(SystemExit) as excinfo:
        api_mod._load_mode("remote-cell")
    assert "has no 'key' field" in str(excinfo.value)


def test_build_plan_does_not_need_the_credentials_file(no_env_json):
    cells = campaign_mod._load_cells()
    queue_ids = campaign_mod._load_queue_ids()
    plan = campaign_mod.build_plan(cells, queue_ids)
    expected = (sum(len(c["modes"]) for c in cells)
                * len(campaign_mod.RENDERINGS)
                * len(queue_ids)
                * campaign_mod.REPS_PER_RENDERING)
    assert len(plan) == expected


# ---------------------------------------------------------------------------
# FR-06 — static check: the residual reader would fail silently
# ---------------------------------------------------------------------------

def test_run_w1_ollama_reads_modes_json():
    """run_w1_ollama.py builds its own _mode_map. Left on env.json it would find
    no url/model after the split and fall back to http://localhost:11434 and the
    mode name — no exception, wrong target. Not observable by behaviour without a
    live ollama server, hence the static assertion."""
    src = (REPO_ROOT / "tests" / "run_w1_ollama.py").read_text(encoding="utf-8")
    assert "env.json" not in src
    assert "modes.json" in src
