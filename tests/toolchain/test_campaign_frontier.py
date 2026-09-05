"""
R1 tests for the frontier arm (2026-08-31) — no CLI, no model, no network.

The arm is the untracked routing fixture run through `claude -p --model
claude-haiku-4-5` instead of a local llama-server, as a term of comparison for
the six GPU cells. It is additive by construction and these tests are mostly
about that word: the GPU grid, the blocks that read it and the plans they have
already written must be exactly what they were, and the hosted cell must not be
able to leak into any of them.

What is asserted here:
  - every cell in both tables declares a runner_type, and it agrees with the
    runner_type of every mode the cell names in tests/modes.json;
  - the GPU grid is entirely 'api', so no pre-existing block can pick up a
    hosted cell, and the frontier table carries no llama-server field;
  - _block_cells reads the block's own table: the haiku block sees the hosted
    cell and nothing else, routing-notrace sees the six GPU cells and nothing
    else;
  - the two arms are the same document at the same coordinates -- same fixture,
    same inputs, same renderings, same reps -- and a different plan file;
  - a claude-code cell starts no server and runs no acceptance probe;
  - _execute_row skips the window check for it (there is no /tokenize and no
    ctx_size to measure into) and records runner_type='claude-code' with
    api_base_url None, which is what separates the arms in index.jsonl;
  - _invoke_claude_code builds the command that makes the comparison honest --
    --safe-mode, --system-prompt with the fixture's own, --tools "" -- and
    refuses a fixture that declares no system_prompt.
"""
import importlib
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "tests"))

campaign_mod = importlib.import_module("runner.campaign")
import runner.api_executor as api_mod

MODES_PATH = REPO_ROOT / "tests" / "modes.json"
HAIKU_BLOCK = "routing-notrace-haiku"
HAIKU_CELL = "claude-code-haiku"
HAIKU_MODE = "claude-code-haiku"

# The hosted ladder (2026-09-01): one block, one cell, one mode and one model id
# per rung, everything else held fixed. Each entry is asserted end to end below,
# so a fourth rung added to the tables without a block -- or with the wrong cell
# filter -- fails here and not overnight.
LADDER = [
    (HAIKU_BLOCK, HAIKU_CELL, HAIKU_MODE, "claude-haiku-4-5"),
    ("routing-notrace-sonnet", "claude-code-sonnet", "claude-code-sonnet", "claude-sonnet-5"),
    ("routing-notrace-opus", "claude-code-opus", "claude-code-opus", "claude-opus-5"),
]
HOSTED_CELLS = [cell for _b, cell, _m, _id in LADDER]


@pytest.fixture(autouse=True)
def _restore_main_block():
    """_use_block rebinds module globals; a block left selected leaks into
    whatever runs next. Same guard as test_campaign_blocks.py."""
    yield
    campaign_mod._use_block("main")


def _modes_by_name():
    return {e["mode"]: e
            for e in json.loads(MODES_PATH.read_text(encoding="utf-8"))["modes"]}


def _all_cells():
    return (campaign_mod._load_cells()
            + campaign_mod._load_cells(campaign_mod.FRONTIER_CELLS_PATH))


# ---------------------------------------------------------------------------
# The cell declares its runner, and modes.json agrees
# ---------------------------------------------------------------------------

def test_every_cell_declares_a_known_runner_type():
    """_run_cell and _execute_row both branch on cell['runner_type'] and read it
    without a default: a cell that omits it must fail loudly at the first row,
    not start a llama-server for a hosted model."""
    for cell in _all_cells():
        assert cell["runner_type"] in ("api", "claude-code"), cell


def test_cell_runner_type_agrees_with_its_modes():
    """The same invariant T12 keeps for gguf and the context knobs: two places
    to write 'claude-code' is one place to forget it. The cell decides whether a
    server is started, the mode decides how the row is invoked; if they disagree
    the campaign starts a server nobody talks to, or talks to nobody."""
    by_mode = _modes_by_name()
    for cell in _all_cells():
        for name in cell["modes"]:
            assert name in by_mode, f"mode {name} (cell {cell['cell']}) missing from modes.json"
            assert by_mode[name]["runner_type"] == cell["runner_type"], (
                f"cell {cell['cell']} is runner_type={cell['runner_type']!r} but its mode "
                f"{name} declares {by_mode[name]['runner_type']!r}")


def test_the_gpu_grid_is_untouched_and_entirely_api():
    """The additive property, stated where it can fail. Six cells, all local: a
    hosted cell filed here would be picked up by main / routing /
    routing-notrace / both repl arms, none of which asked for one."""
    cells = campaign_mod._load_cells()
    assert len(cells) == 6
    assert {c["runner_type"] for c in cells} == {"api"}


def test_the_frontier_table_holds_the_hosted_ladder_and_nothing_else():
    """One cell per rung, each naming exactly its own mode. A cell that named two
    modes would run the same 280 coordinates twice under one set of plan rows."""
    cells = campaign_mod._load_cells(campaign_mod.FRONTIER_CELLS_PATH)
    assert [c["cell"] for c in cells] == HOSTED_CELLS
    by_name = {c["cell"]: c for c in cells}
    for _block, cell, mode, _model in LADDER:
        assert by_name[cell]["runner_type"] == "claude-code"
        assert by_name[cell]["modes"] == [mode]


def test_each_rung_names_the_model_it_is_the_rung_of():
    """The model id is the only coordinate that moves across the ladder, so it is
    the one thing a typo here would silently swap -- two blocks on one model read
    as a replication, not as a comparison."""
    by_mode = _modes_by_name()
    for _block, _cell, mode, model in LADDER:
        assert by_mode[mode]["model"] == model
    assert len({m for _b, _c, _mo, m in LADDER}) == len(LADDER)


def test_the_hosted_cell_carries_no_llama_server_field():
    """gguf / ctx_size / kv_cache_type / n_parallel are llama-server launch
    parameters. Present but unused they would read as a measured context ceiling
    for a model whose window nobody here measured."""
    cell = campaign_mod._load_cells(campaign_mod.FRONTIER_CELLS_PATH)[0]
    for key in ("gguf", "ctx_size", "kv_cache_type", "n_parallel"):
        assert key not in cell, f"{key} is meaningless on a hosted cell"


@pytest.mark.parametrize("block,cell,mode,model", LADDER)
def test_a_hosted_mode_loads_with_no_credentials(monkeypatch, tmp_path, block, cell, mode, model):
    """A claude-code mode names an Anthropic model and needs no key: the CLI
    authenticates on the Claude Code session. Before 2026-08-31 _load_mode's
    guard fired on it and campaign._mode_config could not read the mode at all."""
    missing = tmp_path / "env.json"
    monkeypatch.setattr(api_mod, "ENV_PATH", missing)
    key, url, got_model, backend, reasoning, *_ = api_mod._load_mode(mode)
    assert key == ""
    assert got_model == model
    assert backend == "anthropic"
    assert reasoning == 0


def test_an_anthropic_api_mode_still_dies_without_a_key(monkeypatch, tmp_path):
    """The exemption is for the claude-code runner, not for the backend. An api
    mode on the anthropic backend must still refuse to run credential-less."""
    monkeypatch.setattr(api_mod, "ENV_PATH", tmp_path / "env.json")
    with pytest.raises(SystemExit) as exc:
        api_mod._load_mode("claude-api")
    assert "has no 'key' field" in str(exc.value)


# ---------------------------------------------------------------------------
# The block reads its own table
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("block,cell,mode,model", LADDER)
def test_each_hosted_block_sees_exactly_its_own_cell(block, cell, mode, model):
    """Since the table holds three cells, `cells` is what keeps each block to its
    own rung. Without it every hosted block would run all three -- and the haiku
    block would re-run an arm that is already recorded."""
    campaign_mod._use_block(block)
    assert [c["cell"] for c in campaign_mod._block_cells()] == [cell]


def test_no_pre_existing_block_can_see_a_hosted_cell():
    """The blast radius of the whole change, in one assertion."""
    hosted_blocks = {b for b, _c, _m, _id in LADDER}
    for name in campaign_mod.BLOCKS:
        if name in hosted_blocks:
            continue
        campaign_mod._use_block(name)
        names = [c["cell"] for c in campaign_mod._block_cells()]
        assert not set(names) & set(HOSTED_CELLS), f"block {name} picked up a hosted cell"


@pytest.mark.parametrize("block,cell,mode,model", LADDER)
def test_the_arm_is_the_same_document_at_the_same_coordinates(block, cell, mode, model):
    """A term of comparison is only one if nothing else moved. Same fixture, same
    staged inputs, same repetition count as the untracked arm it is read
    against; the plan file is the only thing that differs, and it must."""
    arm, notrace = campaign_mod.BLOCKS[block], campaign_mod.BLOCKS["routing-notrace"]
    assert arm["fixture_id"] == notrace["fixture_id"]
    assert arm["reps"] == notrace["reps"]
    assert arm["inputs"]() == notrace["inputs"]()
    assert arm["smoke_renderings"] == notrace["smoke_renderings"]
    assert arm["plan_name"] != notrace["plan_name"]
    assert arm["smoke_plan_name"] != notrace["smoke_plan_name"]


def test_the_three_rungs_do_not_share_a_plan_file():
    """Shared results root, shared index, separate plans -- as with every other
    block. One plan file for two blocks would have the second `plan` overwrite
    the first arm's record of what it ran."""
    names = [campaign_mod.BLOCKS[b]["plan_name"] for b, _c, _m, _id in LADDER]
    smokes = [campaign_mod.BLOCKS[b]["smoke_plan_name"] for b, _c, _m, _id in LADDER]
    assert len(set(names)) == len(names)
    assert len(set(smokes)) == len(smokes)


@pytest.mark.parametrize("block,cell,mode,model", LADDER)
def test_each_hosted_plan_is_the_full_grid_on_one_cell(block, cell, mode, model):
    campaign_mod._use_block(block)
    inputs = campaign_mod.BLOCKS[block]["inputs"]()
    rows = campaign_mod.build_plan(campaign_mod._block_cells(), inputs)
    assert len(inputs) == 20
    assert len(rows) == 20 * 2 * len(campaign_mod.RENDERINGS) == 280
    assert {r["cell"] for r in rows} == {cell}
    assert {r["rendering"] for r in rows} == set(campaign_mod.RENDERINGS)


# ---------------------------------------------------------------------------
# A hosted cell starts no server
# ---------------------------------------------------------------------------

def test_a_hosted_cell_starts_no_server_and_runs_no_probe(monkeypatch, tmp_path):
    started, probed, stopped = [], [], []
    monkeypatch.setattr(campaign_mod, "_start_server", lambda cell: started.append(True))
    monkeypatch.setattr(campaign_mod, "_acceptance_check", lambda meta: probed.append(True) or True)
    monkeypatch.setattr(campaign_mod, "_stop_server", lambda: stopped.append(True))
    calls = []
    monkeypatch.setattr(campaign_mod, "_run_rows",
                        lambda cell, mode, input_id, *a, **k: calls.append((mode, input_id)))

    cell = {"cell": HAIKU_CELL, "runner_type": "claude-code", "modes": [HAIKU_MODE]}
    plan = [{"cell": HAIKU_CELL, "mode": HAIKU_MODE, "rendering": "L0",
             "input": "r01", "rep": 1, "status": "pending"}]
    campaign_mod._run_cell(cell, plan, tmp_path, {}, {}, {})

    assert started == [] and probed == [] and stopped == []
    assert calls == [(HAIKU_MODE, "r01")]


def test_a_hosted_cell_with_no_pending_rows_is_still_skipped(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(campaign_mod, "_run_rows", lambda *a, **k: calls.append(a))
    cell = {"cell": HAIKU_CELL, "runner_type": "claude-code", "modes": [HAIKU_MODE]}
    plan = [{"cell": HAIKU_CELL, "mode": HAIKU_MODE, "rendering": "L0",
             "input": "r01", "rep": 1, "status": "done"}]
    campaign_mod._run_cell(cell, plan, tmp_path, {}, {}, {})
    assert calls == []


# ---------------------------------------------------------------------------
# _execute_row: no window check, and the record says which arm it is
# ---------------------------------------------------------------------------

_HOSTED_MODE_CFG = {
    "key": "", "url": "", "model": "claude-haiku-4-5", "backend": "anthropic",
    "reasoning_budget": 0, "temperature": None, "thinking": None,
    "ctx_size": None, "kv_cache_type": None, "n_parallel": None,
}


class _FakeFidelity:
    result = "n/a"
    conditional_rate = None


class _FakeScore:
    quality = type("q", (), {"result": "correct"})()
    fidelity = _FakeFidelity()

    def save(self, path):
        pass


def _hosted_row_env(monkeypatch, tmp_path, invoke):
    monkeypatch.setattr(campaign_mod, "_mode_config", lambda mode: dict(_HOSTED_MODE_CFG))
    monkeypatch.setattr(campaign_mod, "_load_input", lambda *a, **k: object())
    monkeypatch.setattr(campaign_mod, "_window_room",
                        lambda *a, **k: pytest.fail("window check ran on a hosted cell"))
    monkeypatch.setattr(campaign_mod, "_stage", lambda b: (tmp_path / "sandbox", tmp_path / "in.json"))
    monkeypatch.setattr(campaign_mod, "_invoke_claude_code", invoke)
    monkeypatch.setattr(campaign_mod, "_invoke_api",
                        lambda *a, **k: pytest.fail("the api runner ran on a hosted cell"))
    monkeypatch.setattr(campaign_mod, "check", lambda record, expectations: _FakeScore())
    monkeypatch.setattr(campaign_mod, "_record_path", lambda config, run_id: tmp_path / f"{run_id}.json")
    monkeypatch.setattr(campaign_mod, "_score_path", lambda p: tmp_path / "score.json")
    saved = []
    monkeypatch.setattr(campaign_mod, "_append_index", lambda record, score: saved.append(record))
    return saved


def test_hosted_row_skips_the_window_check_and_uses_the_cli_runner(monkeypatch, tmp_path):
    """There is no /tokenize endpoint to measure against and no --ctx-size to
    measure into: running the check would compare a prompt against None."""
    invoked = []

    def invoke(sol_doc, bundle, fixture_meta, model, rendering, timeout_s):
        invoked.append((model, rendering))
        return "done", '{"status": "OK"}', [], {"status": "OK"}, {
            "tokens_in": 1200, "tokens_out": 90, "cost": 0.0017,
            "request_messages": [], "reasoning": "", "stop_reason": "end_turn"}

    saved = _hosted_row_env(monkeypatch, tmp_path, invoke)
    row = {"cell": HAIKU_CELL, "mode": HAIKU_MODE, "rendering": "L2",
           "input": "r01", "rep": 1, "status": "pending"}
    cell = {"cell": HAIKU_CELL, "runner_type": "claude-code", "modes": [HAIKU_MODE]}

    campaign_mod._execute_row(row, cell, HAIKU_MODE, "L2", "r01", None, {}, {}, {})

    assert invoked == [("claude-haiku-4-5", "L2")]
    assert row["status"] == "done"


def test_hosted_row_records_the_arm_it_belongs_to(monkeypatch, tmp_path):
    """fixture_id and mode already separate the arms in index.jsonl; runner_type
    is what says the row is a `claude -p` invocation and not an HTTP call, and
    api_base_url must be None because there is no endpoint (runner.schema)."""
    def invoke(*a, **k):
        return "done", '{"status": "OK"}', [], {"status": "OK"}, {
            "tokens_in": 1200, "tokens_out": 90, "cost": 0.0017,
            "request_messages": [], "reasoning": "", "stop_reason": "end_turn"}

    saved = _hosted_row_env(monkeypatch, tmp_path, invoke)
    campaign_mod._use_block(HAIKU_BLOCK)
    row = {"cell": HAIKU_CELL, "mode": HAIKU_MODE, "rendering": "L1",
           "input": "r01", "rep": 1, "status": "pending"}
    cell = {"cell": HAIKU_CELL, "runner_type": "claude-code", "modes": [HAIKU_MODE]}

    campaign_mod._execute_row(row, cell, HAIKU_MODE, "L1", "r01", None, {}, {}, {})

    assert len(saved) == 1
    config = saved[0].config
    assert config.runner_type == "claude-code"
    assert config.api_base_url is None
    assert config.model_id == "claude-haiku-4-5"
    assert config.fixture_id == campaign_mod.BLOCKS["routing-notrace"]["fixture_id"]
    assert saved[0].usage.cost == 0.0017


# ---------------------------------------------------------------------------
# The command that makes the comparison honest
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = "You are a senior support triage lead."
FIXTURE_META = {"meta": {"system_prompt": SYSTEM_PROMPT}, "body": "BODY", "prose": {}}


class _FakeCompleted:
    returncode = 0

    def __init__(self, payload):
        self.stdout = json.dumps(payload)
        self.stderr = ""


def _capture_cmd(monkeypatch, payload=None):
    seen = {}

    def fake_run(cmd, **kwargs):
        seen["cmd"] = cmd
        seen["kwargs"] = kwargs
        return _FakeCompleted(payload if payload is not None else {
            "result": '{"status": "OK"}', "is_error": False,
            "usage": {"input_tokens": 1200, "output_tokens": 90},
            "total_cost_usd": 0.0017, "stop_reason": "end_turn"})

    monkeypatch.setattr(campaign_mod.subprocess, "run", fake_run)
    monkeypatch.setattr(campaign_mod, "_build_prompt_e0",
                        lambda sol_doc, bundle, body, level, prose_bodies: f"PROMPT@{level}")
    return seen


def test_the_cli_is_driven_with_safe_mode_and_the_fixture_system_prompt(monkeypatch):
    """--safe-mode is not cosmetic: without it the CLI loads the host machine's
    CLAUDE.md, SessionStart hooks and plugins, and every row would open with
    whatever that machine tells its sessions to do. --system-prompt (not
    --append-system-prompt) is what makes the persona the fixture's own, as the
    API arm's `system` is. --tools "" is E0."""
    seen = _capture_cmd(monkeypatch)
    campaign_mod._invoke_claude_code({}, object(), FIXTURE_META, "claude-haiku-4-5", "L3", 300)

    cmd = seen["cmd"]
    assert cmd[0] == "claude" and cmd[1] == "-p"
    assert seen["kwargs"]["input"] == "PROMPT@L3"
    assert "--safe-mode" in cmd
    assert cmd[cmd.index("--model") + 1] == "claude-haiku-4-5"
    assert cmd[cmd.index("--system-prompt") + 1] == SYSTEM_PROMPT
    assert cmd[cmd.index("--tools") + 1] == ""
    assert cmd[cmd.index("--output-format") + 1] == "json"
    assert "--append-system-prompt" not in cmd
    assert "--add-dir" not in cmd, "E0 gives the CLI no tools; a directory would be noise"


def test_the_rendering_reaches_the_prompt_builder(monkeypatch):
    """executor.py is deliberately not reused: it has no --level and always
    builds L1. Reusing it would file six renderings under a label they never had."""
    for level in campaign_mod.RENDERINGS:
        seen = _capture_cmd(monkeypatch)
        campaign_mod._invoke_claude_code({}, object(), FIXTURE_META, "m", level, 300)
        assert seen["kwargs"]["input"] == f"PROMPT@{level}"


def test_usage_is_read_off_the_scored_turn_not_the_whole_invocation(monkeypatch):
    """modelUsage aggregates the CLI's own side calls too -- a trivial probe on
    2026-08-31 showed 899 extra input tokens against the turn's 251. The top-level
    usage block is the scored turn; total_cost_usd is the bill for everything and
    is recorded as a cost, not as a measurement."""
    seen = _capture_cmd(monkeypatch, payload={
        "result": "{}", "is_error": False,
        "usage": {"input_tokens": 251, "output_tokens": 109},
        "modelUsage": {"a": {"inputTokens": 899, "outputTokens": 10},
                       "b": {"inputTokens": 251, "outputTokens": 109}},
        "total_cost_usd": 0.001745, "stop_reason": "end_turn"})
    status, _raw, _steps, _payload, extras = campaign_mod._invoke_claude_code(
        {}, object(), FIXTURE_META, "m", "L1", 300)

    assert status == "done"
    assert extras["tokens_in"] == 251
    assert extras["tokens_out"] == 109
    assert extras["cost"] == 0.001745


def test_the_cached_prefix_counts_as_prompt_tokens(monkeypatch):
    """The CLI caches the prompt, so most of it is billed once as
    cache_creation_input_tokens and read back afterwards; input_tokens then holds
    only what fell outside the cached prefix. Measured 2026-08-31: a 5,355-token
    prompt reported input_tokens 9 and cache_creation 5,346. Reading the first
    field alone puts a 5,000-token prompt in the dataset as a 9-token one."""
    _capture_cmd(monkeypatch, payload={
        "result": "{}", "is_error": False,
        "usage": {"input_tokens": 9, "cache_creation_input_tokens": 5346,
                  "cache_read_input_tokens": 0, "output_tokens": 40},
        "total_cost_usd": 0.03, "stop_reason": "end_turn"})
    _s, _r, _st, _p, extras = campaign_mod._invoke_claude_code(
        {}, object(), FIXTURE_META, "m", "L1", 300)
    assert extras["tokens_in"] == 5355


def test_the_prompt_never_travels_in_argv(monkeypatch):
    """Windows caps a command line at 32,767 characters and raises
    ERROR_FILENAME_EXCED_RANGE past it -- which Python surfaces as
    FileNotFoundError, the same exception a missing executable raises. With the
    prompt in argv the smoke ran L1 and then died claiming the claude CLI was not
    installed: this fixture's L3 and L4 prompts are 38,475 and 45,469 characters.
    Two of the seven renderings were unrunnable and the bench said the wrong thing
    about why."""
    seen = {}

    def fake_run(cmd, **kwargs):
        seen["cmd"] = cmd
        seen["kwargs"] = kwargs
        return _FakeCompleted({"result": "{}", "is_error": False, "usage": {},
                               "total_cost_usd": 0.0})

    monkeypatch.setattr(campaign_mod.subprocess, "run", fake_run)
    huge = "x" * 50_000
    monkeypatch.setattr(campaign_mod, "_build_prompt_e0",
                        lambda sol_doc, bundle, body, level, prose_bodies: huge)
    campaign_mod._invoke_claude_code({}, object(), FIXTURE_META, "m", "L4", 300)

    assert seen["kwargs"]["input"] == huge
    assert huge not in seen["cmd"]
    assert sum(len(a) for a in seen["cmd"]) < 32_767


def test_a_cli_reported_error_is_not_filed_as_done(monkeypatch):
    """is_error is the CLI's own verdict on the turn. Reading only the exit code
    would file a refusal or a recovered API error as 'done', with an explanation
    string where the payload should be."""
    _capture_cmd(monkeypatch, payload={"result": "Credit balance too low", "is_error": True})
    status, raw, _steps, payload, _extras = campaign_mod._invoke_claude_code(
        {}, object(), FIXTURE_META, "m", "L1", 300)
    assert status == "error"
    assert payload is None
    assert "Credit balance" in raw


def test_a_fixture_without_a_system_prompt_is_refused(monkeypatch):
    _capture_cmd(monkeypatch)
    with pytest.raises(RuntimeError, match="system_prompt"):
        campaign_mod._invoke_claude_code({}, object(), {"meta": {}, "body": "B"},
                                         "m", "L1", 300)


def test_the_fixture_of_this_arm_does_declare_one():
    """The guard above is only a guard if the fixture it runs on satisfies it."""
    from runner.runner import _load_fixture
    _dir, _sol, _exp, meta = _load_fixture(campaign_mod.BLOCKS[HAIKU_BLOCK]["fixture_id"])
    assert (meta.get("meta") or {}).get("system_prompt")


# ---------------------------------------------------------------------------
# The consecutive-failure breaker (2026-09-01)
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _reset_the_breaker():
    """The counter is module state and a test that trips it would otherwise leave
    the next one one row from the threshold."""
    campaign_mod._reset_breaker()
    yield
    campaign_mod._reset_breaker()


def _row(status):
    return {"cell": HAIKU_CELL, "mode": HAIKU_MODE, "rendering": "L1",
            "input": "r01", "rep": 1, "status": status}


def test_failures_short_of_the_threshold_do_not_stop_the_run():
    for _ in range(campaign_mod.MAX_CONSECUTIVE_FAILURES - 1):
        campaign_mod._note_row_outcome(_row("error"))


def test_the_breaker_fires_on_a_run_of_failures():
    """A rate limit, an expired session or an outage fails every row it touches,
    in seconds each, and an `error` row is never retried by the resume -- so an
    unattended run would turn a pause into 280 rows the dataset cannot have."""
    with pytest.raises(campaign_mod.CampaignAborted) as exc:
        for _ in range(campaign_mod.MAX_CONSECUTIVE_FAILURES):
            campaign_mod._note_row_outcome(_row("error"))
    assert "--force" in str(exc.value), "the message must carry the recovery"


def test_one_completed_row_clears_the_count():
    """Scattered failures are not an outage. Only a run of them is."""
    for _ in range(campaign_mod.MAX_CONSECUTIVE_FAILURES - 1):
        campaign_mod._note_row_outcome(_row("error"))
    campaign_mod._note_row_outcome(_row("done"))
    for _ in range(campaign_mod.MAX_CONSECUTIVE_FAILURES - 1):
        campaign_mod._note_row_outcome(_row("error"))


def test_a_skipped_window_row_is_neither_a_failure_nor_a_success():
    """It is the bench declining to spend a run it measured as unrunnable -- a
    property of the prompt, not of the backend. Counting it would abort a GPU cell
    whose window is simply too small for a stretch of the grid; clearing on it
    would let a real outage through between two skips."""
    for _ in range(campaign_mod.MAX_CONSECUTIVE_FAILURES - 1):
        campaign_mod._note_row_outcome(_row("error"))
    campaign_mod._note_row_outcome(_row("skipped-window"))
    with pytest.raises(campaign_mod.CampaignAborted):
        campaign_mod._note_row_outcome(_row("error"))
