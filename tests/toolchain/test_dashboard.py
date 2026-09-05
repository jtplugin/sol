"""R1 tests for scripts/dashboard.py as a monitor of the campaign (2026-08-22).

MAIN runs 1260 rows over roughly twenty hours. The dashboard was written for the
pilot: it read index.jsonl and showed fixture, model, env -- but not
`process_rendering`, the one selector the campaign actually varies, and not the
mode, without which qwen3.5-9b think and nothink are the same row (same gguf,
differing only by `thinking`, a field other models carry set for no reason).

What can break quietly, and therefore gets a test:

  the two dimensions -- if the columns silently stopped being emitted, the page
      would still render and still look complete;
  deduplication -- 96.6% of the detail payload is the same prompts and queue
      files repeated. Inlined per run the page projected to 127 MB, which a
      browser must parse whole before painting anything;
  the incremental rebuild -- campaign.py rebuilds after every row, so a cache
      that ever disagreed with a cold build would put wrong data on the page
      for the whole campaign;
  data that closes the script block -- several staged inputs carry a literal
      '</script>', which ends the inline block early and kills the page;
  the CSV header migration -- the only part of this that can DESTROY data.
      index.csv is appended to; adding a column without rewriting the header
      would misalign every row written from then on;
  the results root -- _load_detail_data resolves record files through a module
      global. When that global did not follow --index, a dashboard built for
      tests/results-smoke came out with every detail panel empty;
  non-blocking, fail-soft regeneration -- a dashboard is for reading a run
      with. It must neither stop one nor slow it down.

No GPU, no server, no live model: everything runs on tmp_path.
"""
import csv
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "tests"))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import dashboard as dash
import runner.campaign as campaign_mod


def _row(run_id, **over):
    row = {
        "run_id": run_id,
        "fixture_id": "w2-branching/support-intake",
        "staged_input_id": "queue-01",
        "context": "E0",
        "model_id": "ai-models/Qwen3.5-9B-Q4_K_M.gguf",
        "mode": "llama-qwen3.5-9b-think",
        "process_rendering": "prose-mechanical",
        "spec_version": "0.6",
        "env_realization": "emulated",
        "runner_type": "api",
        "status": "done",
        "quality": "pass",
        "fidelity": "fail",
        "degradation_mode": "none",
        "conditional_rate": 0.75,
        "comprehension_rate": 0.5,
        "sequence_rate": 0.25,
        "traced": True,
        "wall_clock_ms": 1234,
        "tokens_in": 100,
        "tokens_out": 50,
        "timestamp": "2026-08-22T10:00:00+00:00",
    }
    row.update(over)
    return row


@pytest.fixture(autouse=True)
def no_rebuild_in_flight():
    """campaign._dashboard_proc is module state. A test that leaves a live-looking
    process behind would make the NEXT test's rebuild silently skip."""
    campaign_mod._dashboard_proc = None
    yield
    campaign_mod._dashboard_proc = None


@pytest.fixture
def restore_dashboard_globals():
    """main() rebinds RESULTS_DIR and ASSETS_DIR. Put them back, or a test that
    redirected them would poison every test after it in the same session."""
    saved = (dash.RESULTS_DIR, dash.ASSETS_DIR)
    try:
        yield
    finally:
        dash.RESULTS_DIR, dash.ASSETS_DIR = saved


# ---------------------------------------------------------------------------
# the two dimensions the campaign varies
# ---------------------------------------------------------------------------

def test_rows_carry_rendering_and_mode():
    html = dash.build_html([_row("r1")])
    rows = json.loads(html.split("const ROWS   = ", 1)[1].split(";\n", 1)[0])
    assert rows[0]["rendering"] == "prose-mechanical"
    assert rows[0]["mode"] == "llama-qwen3.5-9b-think"


def test_a_run_recorded_before_the_fields_existed_reads_as_absent():
    """The 576 historical runs have neither field. Blank is the honest rendering:
    inferring a rendering from a run that never recorded one would invent data."""
    old = _row("old")
    del old["mode"]
    del old["process_rendering"]
    html = dash.build_html([old])
    rows = json.loads(html.split("const ROWS   = ", 1)[1].split(";\n", 1)[0])
    assert rows[0]["rendering"] == ""
    assert rows[0]["mode"] == ""


def test_the_page_exposes_both_as_filters_and_columns():
    html = dash.build_html([_row("r1")])
    assert 'id="fRendering"' in html
    assert 'id="fMode"' in html
    assert "<th>Rendering</th>" in html
    assert "<th>Mode</th>" in html
    assert 'id="chartRendering"' in html


# ---------------------------------------------------------------------------
# filters that survive a reload (2026-08-24)
#
# campaign.py rebuilds this page after every row, so following a run means
# reloading it every few seconds. Before this, each reload dropped the filter
# and put the reader back at "all 1,236 rows" -- the dashboard was least usable
# exactly while a campaign was running, which is what it is for.
#
# Asserted against DASHBOARD_JS, the source, rather than against build_html:
# the page links the script as an asset (assets/dashboard.js) instead of
# inlining it, so the behaviour is not in the HTML at all.
#
# These are string assertions on generated JS, which is a weak test and is why
# each one names a specific way the feature dies quietly: state written but
# never read, state read but the page still booting unfiltered, the cascade
# restored out of order so a saved fixture has no option to select, or the whole
# page failing to render on a browser that refuses storage to a file:// origin.
# ---------------------------------------------------------------------------

NL_BRACE = chr(10) + "}"


def test_the_page_saves_and_restores_its_filters():
    js = dash.DASHBOARD_JS
    assert "function saveFilters()" in js
    assert "function restoreFilters()" in js
    assert "sol-dashboard-filters" in js


def test_the_state_is_written_on_every_filter_change():
    """applyFilters is the single funnel every change handler and the reset
    button route through. Saving anywhere else means one control that silently
    does not persist."""
    js = dash.DASHBOARD_JS
    body = js.split("function applyFilters()", 1)[1].split(NL_BRACE, 1)[0]
    assert "saveFilters();" in body


def test_the_state_is_restored_before_the_first_render():
    """Restoring after applyFilters would set the dropdowns and leave the table,
    the KPIs and every chart showing the unfiltered set -- the page would look
    filtered and not be."""
    js = dash.DASHBOARD_JS
    boot = js.rsplit("populateEnvs();", 1)[1]
    assert boot.index("restoreFilters()") < boot.index("applyFilters();")


def test_the_cascade_is_restored_in_dependency_order():
    """Fixture options are derived from the chosen workflow and input options
    from the chosen fixture. Setting a saved fixture before its list is rebuilt
    finds no matching option and silently drops it."""
    js = dash.DASHBOARD_JS
    body = js.split("function restoreFilters()", 1)[1].split(NL_BRACE, 1)[0]
    order = [body.index(t) for t in
             ("set(fWorkflow", "populateFixtures()", "set(fFixture",
              "populateInputs()", "set(fInput")]
    assert order == sorted(order)


def test_a_saved_value_with_no_matching_option_is_dropped_not_forced():
    """A fixture that has left the index, or an input excluded by a narrower
    workflow. Forcing it would leave a filter naming a value no row carries, and
    an empty table with no visible reason."""
    js = dash.DASHBOARD_JS
    body = js.split("function restoreFilters()", 1)[1].split(NL_BRACE, 1)[0]
    assert "o.value === v" in body


def test_neither_storage_path_can_stop_the_page():
    """file:// is a hostile storage origin: some browsers refuse localStorage on
    it and history.replaceState can raise SecurityError. Forgetting a dropdown
    is acceptable; a blank dashboard is not."""
    js = dash.DASHBOARD_JS
    save = js.split("function saveFilters()", 1)[1].split(chr(10) + "function", 1)[0]
    assert save.count("try {") >= 2 and save.count("catch") >= 2
    boot = js.rsplit("populateEnvs();", 1)[1]
    assert "try { restoreFilters(); }" in boot


def test_the_search_box_does_not_push_a_history_entry_per_keystroke():
    """fSearch saves on `input`. Assigning location.hash would leave the reader
    needing one Back press per character typed."""
    js = dash.DASHBOARD_JS
    save = js.split("function saveFilters()", 1)[1].split(chr(10) + "function", 1)[0]
    # Comments stripped: the block explains why location.hash is not assigned,
    # and a test that reads its own rationale as the code proves nothing.
    code = chr(10).join(l for l in save.splitlines() if not l.strip().startswith("//"))
    assert "history.replaceState" in code
    assert "location.hash =" not in code


def test_the_detail_row_spans_the_whole_table():
    """A detail panel narrower than the header leaves the table ragged on every
    open row. Counted on "<th" rather than "<th>": Cond and Comp carry a title
    attribute, being the two headers whose meaning is not in their name."""
    html = dash.build_html([_row("r1")])
    header = html.split("<thead>", 1)[1].split("</thead>", 1)[0]
    assert header.count("<th") == 15
    # the body rows are built client-side, so the span lives in the JS asset
    assert 'colspan="15"' in dash.DASHBOARD_JS


# ---------------------------------------------------------------------------
# deduplication of the detail payload
# ---------------------------------------------------------------------------

def _plant(root: Path, run_id: str, prompt: str, queue: str = "queue-01") -> dict:
    """Write the record file a run's detail panel reads, and return its index row."""
    model_dir = root / "w2-branching/support-intake/E0/ai-models_Qwen3.5-9B-Q4_K_M.gguf/0.6"
    model_dir.mkdir(parents=True, exist_ok=True)
    (model_dir / f"{run_id}.json").write_text(json.dumps({
        "output": {"raw": f"raw of {run_id}", "returned_payload": None},
        "trace": {"request_messages": [{"role": "user", "content": prompt}]},
    }), encoding="utf-8")
    return _row(run_id, staged_input_id=queue)


def test_runs_sharing_a_prompt_store_it_once(tmp_path, monkeypatch,
                                             restore_dashboard_globals):
    """MAIN's prompt is a function of (rendering, queue): 1260 runs carry 70
    distinct prompts, and its staged inputs are 10 queue files. Inlined per run
    that came to a 127 MB page -- which a browser must parse whole before painting
    anything. Interned, under 10 MB."""
    root = tmp_path / "results"
    rows = [_plant(root, "a", "SAME PROMPT"),
            _plant(root, "b", "SAME PROMPT"),
            _plant(root, "c", "OTHER PROMPT")]
    monkeypatch.setattr(dash, "RESULTS_DIR", root)

    detail, blobs = dash._load_detail_data(rows)

    assert detail["a"]["req"] == detail["b"]["req"] != detail["c"]["req"]
    # two distinct prompts, plus queue-01.json shared by all three runs
    assert len(blobs) == 3
    # the output stays per-run: it is genuinely different every time
    assert detail["a"]["output_raw"] != detail["b"]["output_raw"]


def test_the_key_leads_back_to_the_original_content(tmp_path, monkeypatch,
                                                    restore_dashboard_globals):
    root = tmp_path / "results"
    rows = [_plant(root, "a", "THE PROMPT")]
    monkeypatch.setattr(dash, "RESULTS_DIR", root)

    detail, blobs = dash._load_detail_data(rows)

    assert blobs[detail["a"]["req"]] == [{"role": "user", "content": "THE PROMPT"}]


def test_the_page_ships_the_blob_store(tmp_path, monkeypatch,
                                       restore_dashboard_globals):
    """The panel resolves d.req through BLOBS; a page without it would open every
    detail on '(not recorded)'."""
    root = tmp_path / "results"
    rows = [_plant(root, "a", "THE PROMPT")]
    monkeypatch.setattr(dash, "RESULTS_DIR", root)

    html = dash.build_html(rows)

    assert "const BLOBS  = " in html
    assert "THE PROMPT" in html
    assert "BLOBS[d.req]" in dash.DASHBOARD_JS


def test_a_run_with_no_record_on_disk_holds_no_keys(tmp_path, monkeypatch,
                                                    restore_dashboard_globals):
    """Empty is not a blob. Interning '' would give every recordless run the same
    key and make the panel show a stored value where there is none."""
    monkeypatch.setattr(dash, "RESULTS_DIR", tmp_path / "empty")

    detail, blobs = dash._load_detail_data([_row("ghost")])

    assert detail["ghost"]["req"] is None
    assert detail["ghost"]["mermaid"] is None


# ---------------------------------------------------------------------------
# incremental rebuild
# ---------------------------------------------------------------------------

def test_a_rebuild_reads_only_the_records_it_has_not_seen(tmp_path, monkeypatch,
                                                          restore_dashboard_globals):
    """campaign.py rebuilds after every row. Rereading all ~1836 records each time
    would be 2.3 million file reads over MAIN, on the machine running inference."""
    root = tmp_path / "results"
    rows = [_plant(root, "a", "P1"), _plant(root, "b", "P2")]
    monkeypatch.setattr(dash, "RESULTS_DIR", root)

    dash._load_detail_data(rows)                       # cold: reads both

    opened = []
    real_read = Path.read_text

    def spy(self, *a, **k):
        opened.append(self.name)
        return real_read(self, *a, **k)

    monkeypatch.setattr(Path, "read_text", spy)
    rows.append(_plant(root, "c", "P3"))
    detail, _ = dash._load_detail_data(rows)

    assert "c.json" in opened
    assert "a.json" not in opened and "b.json" not in opened
    assert set(detail) == {"a", "b", "c"}


def test_the_cache_does_not_change_what_the_page_says(tmp_path, monkeypatch,
                                                      restore_dashboard_globals):
    """The only thing that would make this cache worth removing is if a warm
    rebuild ever differed from a cold one."""
    root = tmp_path / "results"
    rows = [_plant(root, "a", "P1"), _plant(root, "b", "P1"), _plant(root, "c", "P2")]
    monkeypatch.setattr(dash, "RESULTS_DIR", root)

    cold = dash._load_detail_data(rows, use_cache=False)
    dash._load_detail_data(rows[:2])                   # seed the cache partially
    warm = dash._load_detail_data(rows)

    assert warm == cold


def test_a_run_whose_record_is_not_on_disk_yet_is_not_cached(tmp_path, monkeypatch,
                                                             restore_dashboard_globals):
    """Caching the empty reading would make it permanent: the record may simply not
    have been written when this rebuild ran."""
    root = tmp_path / "results"
    monkeypatch.setattr(dash, "RESULTS_DIR", root)
    root.mkdir(parents=True)

    dash._load_detail_data([_row("late")])
    assert "late" not in dash._read_cache()[0]

    rows = [_plant(root, "late", "ARRIVED LATE")]
    detail, blobs = dash._load_detail_data(rows)
    assert blobs[detail["late"]["req"]] == [{"role": "user", "content": "ARRIVED LATE"}]


def test_a_corrupt_cache_costs_a_full_rebuild_and_nothing_else(tmp_path, monkeypatch,
                                                               restore_dashboard_globals):
    root = tmp_path / "results"
    rows = [_plant(root, "a", "P1")]
    monkeypatch.setattr(dash, "RESULTS_DIR", root)
    (root / dash.DETAIL_CACHE_NAME).write_text("{not json", encoding="utf-8")

    detail, blobs = dash._load_detail_data(rows)

    assert blobs[detail["a"]["req"]] == [{"role": "user", "content": "P1"}]


def test_blob_keys_survive_a_rebuild(tmp_path, monkeypatch, restore_dashboard_globals):
    """The key is the content digest, not a counter. A counter numbers blobs by the
    order runs happen to be read, so a cached entry would point at nothing after the
    index grew."""
    root = tmp_path / "results"
    monkeypatch.setattr(dash, "RESULTS_DIR", root)
    first, _ = dash._load_detail_data([_plant(root, "a", "STABLE")])
    rows = [_plant(root, "z", "OTHER"), _plant(root, "a", "STABLE")]
    second, blobs = dash._load_detail_data(rows)

    assert second["a"]["req"] == first["a"]["req"]
    assert blobs[second["a"]["req"]] == [{"role": "user", "content": "STABLE"}]


def test_a_blob_no_longer_referenced_is_dropped(tmp_path, monkeypatch,
                                                restore_dashboard_globals):
    """Otherwise the cache only ever grows, carrying prompts of runs the index no
    longer lists."""
    root = tmp_path / "results"
    monkeypatch.setattr(dash, "RESULTS_DIR", root)
    dash._load_detail_data([_plant(root, "a", "GONE"), _plant(root, "b", "KEPT")])

    _, blobs = dash._load_detail_data([_row("b")])

    assert len(blobs) == 2          # b's prompt + the shared queue-01 input
    assert not any(v == [{"role": "user", "content": "GONE"}] for v in blobs.values())


# ---------------------------------------------------------------------------
# data that closes the script block
# ---------------------------------------------------------------------------

def test_a_closing_script_tag_in_the_data_does_not_kill_the_page(tmp_path, monkeypatch,
                                                                 restore_dashboard_globals):
    """Several of the campaign's staged inputs are real GitHub issues carrying a
    literal '</script>'. Emitted raw into the inline block it closes it early: the
    browser reads the rest of the JSON as markup and the page dies with
    'SyntaxError: Invalid or unexpected token' -- every chart empty, every filter
    unpopulated, and nothing on the page to say why. Observed on the smoke
    dashboard, 2026-08-22, before MAIN had run."""
    root = tmp_path / "results"
    model_dir = root / "w2-branching/support-intake/E0/ai-models_Qwen3.5-9B-Q4_K_M.gguf/0.6"
    model_dir.mkdir(parents=True)
    hostile = "<!--[if lte IE 9]><script src='x.js'></script><![endif]-->"
    (model_dir / "r1.json").write_text(json.dumps({
        "output": {"raw": hostile, "returned_payload": None},
        "trace": {"request_messages": []},
    }), encoding="utf-8")

    monkeypatch.setattr(dash, "RESULTS_DIR", root)
    html = dash.build_html([_row("r1")])

    body = html.split("<script>\n", 1)[1].split("\n</script>", 1)[0]
    assert "</script" not in body
    # and it is still the same string once the browser parses it
    detail = json.loads(body.split("const DETAIL = ", 1)[1].rsplit(";", 1)[0])
    assert detail["r1"]["output_raw"] == hostile


def test_the_page_names_the_index_it_was_built_from():
    html = dash.build_html([_row("r1")], index_label="tests/results-smoke/index.jsonl")
    assert "source: tests/results-smoke/index.jsonl" in html


# ---------------------------------------------------------------------------
# the CSV header migration -- the only destructive path in this change
# ---------------------------------------------------------------------------

OLD_COLUMNS = [
    "run_id", "timestamp", "fixture_id", "staged_input_id", "context",
    "model_id", "spec_version", "env_realization", "runner_type",
    "status", "quality", "fidelity", "degradation_mode",
    "wall_clock_ms", "tokens_in", "tokens_out", "api_base_url", "reasoning_budget",
]


def _write_old_csv(path: Path, run_ids: list[str]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=OLD_COLUMNS, extrasaction="ignore")
        w.writeheader()
        for rid in run_ids:
            w.writerow({c: _row(rid).get(c, "") for c in OLD_COLUMNS})


def test_a_stale_header_is_migrated_without_losing_a_row(tmp_path):
    csv_path = tmp_path / "index.csv"
    _write_old_csv(csv_path, ["h1", "h2", "h3"])

    dash.sync_csv([_row("h1"), _row("h2"), _row("h3"), _row("new")],
                  csv_path, tmp_path)

    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        assert list(reader.fieldnames) == dash.CSV_COLUMNS
        rows = list(reader)
    assert [r["run_id"] for r in rows] == ["h1", "h2", "h3", "new"]
    # a migrated row still in the index is rebuilt from it, so the columns the old
    # header lacked come back filled rather than blank -- see the orphan test below
    # for the case where there is no index entry to rebuild from
    assert all(r["mode"] == "llama-qwen3.5-9b-think" for r in rows)
    assert all(r["conditional_rate"] == "0.75" for r in rows)
    assert all(r["fixture_id"] == "w2-branching/support-intake" for r in rows)


def test_a_stale_header_is_migrated_even_with_nothing_new_to_add(tmp_path):
    """Otherwise the file would sit on the old header until a new run happened to
    arrive, and the first append after that would be the misaligned one."""
    csv_path = tmp_path / "index.csv"
    _write_old_csv(csv_path, ["h1"])

    dash.sync_csv([_row("h1")], csv_path, tmp_path)

    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        assert list(reader.fieldnames) == dash.CSV_COLUMNS
        assert [r["run_id"] for r in reader] == ["h1"]


def test_a_current_header_is_appended_to_not_rewritten(tmp_path):
    csv_path = tmp_path / "index.csv"
    dash.sync_csv([_row("a")], csv_path, tmp_path)
    added = dash.sync_csv([_row("a"), _row("b")], csv_path, tmp_path)

    assert added == 1
    with open(csv_path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert [r["run_id"] for r in rows] == ["a", "b"]


# ---------------------------------------------------------------------------
# the results root follows --index
# ---------------------------------------------------------------------------

def test_details_resolve_under_the_root_of_the_index_given(tmp_path, monkeypatch,
                                                           restore_dashboard_globals):
    """Before this, RESULTS_DIR was pinned to tests/results whatever --index said,
    so a smoke dashboard came out with every detail panel empty."""
    root = tmp_path / "results-elsewhere"
    model_dir = root / "w2-branching/support-intake/E0/ai-models_Qwen3.5-9B-Q4_K_M.gguf/0.6"
    model_dir.mkdir(parents=True)
    (model_dir / "r1.json").write_text(json.dumps({
        "output": {"raw": "THE RAW OUTPUT", "returned_payload": {"ok": True}},
        "trace": {"request_messages": []},
    }), encoding="utf-8")

    index = root / "index.jsonl"
    index.write_text(json.dumps(_row("r1")) + "\n", encoding="utf-8")
    out = tmp_path / "out.html"

    monkeypatch.setattr(sys, "argv",
                        ["dashboard.py", "--index", str(index), "--output", str(out)])
    dash.main()

    assert "THE RAW OUTPUT" in out.read_text(encoding="utf-8")
    assert (root / "assets" / "dashboard.js").exists()
    assert (root / "index.csv").exists()   # --csv defaulted beside the index


# ---------------------------------------------------------------------------
# regeneration during a run must not be able to stop one
# ---------------------------------------------------------------------------

def test_regen_is_silent_when_the_script_is_missing(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(campaign_mod, "DASHBOARD_SCRIPT", tmp_path / "nope.py")
    campaign_mod._regen_dashboard()
    assert capsys.readouterr().out == ""


class _FakeProc:
    """Popen stand-in. `alive` decides what poll() reports."""

    def __init__(self, alive=False):
        self.alive = alive
        self.waited = False

    def poll(self):
        return None if self.alive else 0

    def wait(self, timeout=None):
        self.waited = True
        self.alive = False


def test_regen_does_not_block_the_run(monkeypatch, tmp_path):
    """A rebuild costs about a second, near two by the end of MAIN. Blocking on
    1260 of them would leave the GPU idle for the better part of half an hour."""
    monkeypatch.setattr(campaign_mod.subprocess, "run",
                        lambda *a, **k: pytest.fail("blocked on the rebuild"))
    spawned = []
    monkeypatch.setattr(campaign_mod.subprocess, "Popen",
                        lambda cmd, **k: spawned.append(cmd) or _FakeProc())
    monkeypatch.setattr(campaign_mod, "RESULTS_DIR", tmp_path)
    monkeypatch.setattr(campaign_mod, "INDEX_PATH", tmp_path / "index.jsonl")

    campaign_mod._regen_dashboard()

    assert len(spawned) == 1
    assert str(tmp_path / "index.jsonl") in spawned[0]
    assert str(tmp_path / "dashboard.html") in spawned[0]
    assert str(tmp_path / "index.csv") in spawned[0]


def test_a_rebuild_still_running_is_not_joined_by_a_second(monkeypatch):
    """Two dashboard.py at once would race on dashboard.html and, worse, on
    index.csv, which is read-then-rewritten. Skipping loses nothing: the next row
    rebuilds from the same index a moment later."""
    monkeypatch.setattr(campaign_mod, "_dashboard_proc", _FakeProc(alive=True))
    spawned = []
    monkeypatch.setattr(campaign_mod.subprocess, "Popen",
                        lambda cmd, **k: spawned.append(cmd) or _FakeProc())

    campaign_mod._regen_dashboard()

    assert spawned == []


def test_regen_survives_a_spawn_that_fails(monkeypatch, capsys):
    def boom(*a, **k):
        raise OSError("no process for you")
    monkeypatch.setattr(campaign_mod.subprocess, "Popen", boom)
    campaign_mod._regen_dashboard()            # must not raise
    assert "dashboard" in capsys.readouterr().out


def test_the_run_closes_on_a_blocking_rebuild(monkeypatch, tmp_path, capsys):
    """The background rebuilds are best-effort: the last rows can land while one is
    in flight and get skipped. Without this the page would sit a few runs short of
    the data it claims to show -- and that page is what gets read afterwards."""
    inflight = _FakeProc(alive=True)
    monkeypatch.setattr(campaign_mod, "_dashboard_proc", inflight)

    class Done:
        returncode = 0
        stderr = ""

    ran = []
    monkeypatch.setattr(campaign_mod.subprocess, "run",
                        lambda cmd, **k: ran.append(cmd) or Done())
    monkeypatch.setattr(campaign_mod, "RESULTS_DIR", tmp_path)
    monkeypatch.setattr(campaign_mod, "INDEX_PATH", tmp_path / "index.jsonl")

    campaign_mod._finish_dashboard()

    assert inflight.waited, "did not wait for the rebuild already in flight"
    assert len(ran) == 1
    assert "dashboard" in capsys.readouterr().out


def test_no_dashboard_flag_turns_regeneration_off(monkeypatch):
    called = []
    monkeypatch.setattr(campaign_mod.subprocess, "Popen",
                        lambda *a, **k: called.append(1))
    monkeypatch.setattr(campaign_mod.subprocess, "run",
                        lambda *a, **k: called.append(1))
    monkeypatch.setattr(campaign_mod, "_dashboard_enabled", False)
    campaign_mod._regen_dashboard()
    campaign_mod._finish_dashboard()
    assert called == []

def test_a_migrated_orphan_keeps_its_old_values(tmp_path):
    """A row that reached the CSV without ever being in index.jsonl has no index
    entry to rebuild from, and the CSV is the last copy of it there is. It is
    carried over as it stands, blank in the columns it never had."""
    csv_path = tmp_path / "index.csv"
    _write_old_csv(csv_path, ["gone", "still-here"])

    dash.sync_csv([_row("still-here")], csv_path, tmp_path)

    with open(csv_path, newline="", encoding="utf-8") as f:
        rows = {r["run_id"]: r for r in csv.DictReader(f)}
    assert set(rows) == {"gone", "still-here"}
    assert rows["gone"]["conditional_rate"] == ""
    assert rows["gone"]["fixture_id"] == "w2-branching/support-intake"
    assert rows["still-here"]["conditional_rate"] == "0.75"


# ---------------------------------------------------------------------------
# the continuous metrics (2026-08-23)
# ---------------------------------------------------------------------------

def _rows_from(html):
    return json.loads(html.split("const ROWS   = ", 1)[1].split(";" + chr(10), 1)[0])


def test_the_rows_carry_the_continuous_metrics():
    """quality and fidelity are binary and, on a fixture that scores comprehension
    alongside control flow, can only read fail -- MAIN produced 459 runs of
    unbroken red while conditional_rate ranged from 0.41 to 0.81 underneath."""
    html = dash.build_html([_row("r1")])
    rows = _rows_from(html)
    assert rows[0]["cond"] == 0.75
    assert rows[0]["comp"] == 0.5
    assert rows[0]["seq"] == 0.25
    assert rows[0]["traced"] is True


def test_a_run_recorded_before_the_metrics_existed_carries_none():
    """Not zero. A rate of zero is a model that was scored and got everything
    wrong; absent is a run nobody scored, and the table shows a dash for it."""
    bare = _row("old")
    for k in ("conditional_rate", "comprehension_rate", "sequence_rate", "traced"):
        del bare[k]
    rows = _rows_from(dash.build_html([bare]))
    assert rows[0]["cond"] is None
    assert rows[0]["comp"] is None
    assert rows[0]["traced"] is None


def test_the_table_and_charts_expose_the_metrics():
    html = dash.build_html([_row("r1")])
    assert "<th title=" in html and ">Cond</th>" in html and ">Comp</th>" in html
    assert 'id="chartRateModel"' in html
    assert 'id="chartRateRendering"' in html
    assert 'id="kpi-cond"' in html
    assert "meanRatesBy" in dash.DASHBOARD_JS
    assert "rateChartConfig" in dash.DASHBOARD_JS


def test_the_untraced_runs_can_be_isolated():
    """granite-4.1-8b answered 35 runs of 36 with a markdown table instead of the
    EVAL/BRANCH lines the oracle reads. Those runs are unmeasurable rather than
    bad, and telling the two apart needs a control of its own."""
    html = dash.build_html([_row("r1")])
    assert 'id="fTraced"' in html
    assert '<option value="no">no trace</option>' in html
    assert "fTraced" in dash.DASHBOARD_JS
    assert "fTraced.value" in dash.DASHBOARD_JS


def test_an_unscored_run_is_left_out_of_the_means_not_counted_as_zero():
    """The exclusion is the whole point of meanRatesBy: it is precisely the cells
    that emit no trace whose means a null-as-zero rule would flatten, and they
    would then read as a model that executed the process and got it wrong."""
    js = dash.DASHBOARD_JS
    body = js.split("function meanRatesBy", 1)[1].split("function dayData", 1)[0]
    assert "typeof r.cond === 'number'" in body
    assert "typeof r.comp === 'number'" in body


def test_the_metrics_reach_the_csv(tmp_path):
    csv_path = tmp_path / "index.csv"
    dash.sync_csv([_row("a")], csv_path, tmp_path)
    with open(csv_path, newline="", encoding="utf-8") as f:
        row = next(csv.DictReader(f))
    assert row["conditional_rate"] == "0.75"
    assert row["comprehension_rate"] == "0.5"
    assert row["traced"] == "True"

# ---------------------------------------------------------------------------
# the glossary is rendered from doc/measures.md, not a second copy of it
# ---------------------------------------------------------------------------

MEASURES = (REPO_ROOT / "doc" / "measures.md").read_text(encoding="utf-8")


def test_every_measure_in_the_document_reaches_the_page():
    """The point of the file is that there is one statement of these, not two.
    A term added to the document and not to the page would be a second copy
    again, arrived at by omission."""
    html = dash.build_html([_row("r1")])
    terms = [l[4:].strip() for l in MEASURES.splitlines() if l.startswith("### ")]
    assert len(terms) >= 20, terms      # ten or more, twice over
    # escaped the way the renderer escapes them -- one heading carries an "&"
    missing = [x for x in terms if f"<h4>{dash._esc(x)}</h4>" not in html]
    assert not missing, missing


def test_the_document_names_functions_that_exist():
    """Each measure says which function computes it, so a reader can go and read
    the authority instead of trusting the prose. A name that has been renamed
    away sends them looking for nothing."""
    import re
    import runner.checker as checker
    named = set(re.findall(r"`(_?[a-z][a-z0-9_]*)\(\)`", MEASURES))
    assert named, "the document names no function at all"
    missing = [n for n in sorted(named) if not hasattr(checker, n)]
    assert not missing, missing


def test_the_renderer_covers_what_the_document_uses():
    """A markdown construct outside the subset comes through as its own literal
    text. Visible rather than silent, which is the failure mode to prefer -- and
    this is what makes it loud."""
    import re
    # outside code spans: a `###` inside one is the document quoting markdown at
    # the reader on purpose, which is exactly what a code span is for
    html = re.sub(r"<code>.*?</code>", "", dash._glossary_html(), flags=re.S)
    for leftover in ("**", "###", "|---|"):
        assert leftover not in html, leftover
    assert "&amp;lt;" not in html    # a pre-escaped entity escaped a second time


def test_a_missing_document_says_so_instead_of_vanishing(monkeypatch, tmp_path):
    """A glossary that silently disappears leaves a page that looks complete and
    explains nothing."""
    monkeypatch.setattr(dash, "MEASURES_PATH", tmp_path / "gone.md")
    html = dash._glossary_html()
    assert "measures.md" in html and "glossary" in html

def test_the_two_halves_define_the_same_terms():
    """English is the official text and the Italian is a working translation, both
    in one file so that changing one and not the other has to be a decision. The
    term headings are identical on purpose -- they are the dashboard's own column
    names -- and comparing the two lists is what catches the halves falling out of
    step. Prose that drifts underneath an unchanged heading it cannot catch."""
    parts = dash.split_versions(MEASURES)
    assert len(parts) == 2, len(parts)
    en, it = [[l[4:].strip() for l in x.splitlines() if l.startswith("### ")]
              for x in parts]
    assert en == it, (set(en) ^ set(it)) or "same terms, different order"


def test_the_language_switch_needs_no_javascript():
    """Radio inputs and sibling selectors, not a script. The glossary is rebuilt
    into a page the campaign regenerates after every row, and a scripted toggle
    that threw would leave an empty panel where the definitions were; without the
    stylesheet this degrades to both versions stacked, which still reads."""
    html = dash._glossary_html()
    assert html.count('type="radio"') == 2
    assert 'id="glang-en"' in html and 'id="glang-it"' in html
    assert 'class="glang glang-en"' in html and 'class="glang glang-it"' in html
    assert "<script" not in html
    css = dash.DASHBOARD_CSS
    assert "#glang-en:checked ~ .glang-en" in css
    assert "#glang-it:checked ~ .glang-it" in css


def test_a_document_with_one_version_still_renders(monkeypatch, tmp_path):
    """A half deleted by accident should cost the switch, not the glossary."""
    doc = tmp_path / "measures.md"
    doc.write_text("# Only one" + chr(10) * 2 + "## S" + chr(10) * 2 + "### Status"
                   + chr(10) * 2 + "text", encoding="utf-8")
    monkeypatch.setattr(dash, "MEASURES_PATH", doc)
    html = dash._glossary_html()
    assert "<h4>Status</h4>" in html
    assert html.count('type="radio"') == 1
