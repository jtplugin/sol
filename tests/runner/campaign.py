#!/usr/bin/env python3
"""
campaign.py -- resumable driver for MAIN's cell x mode x rendering x queue x rep
matrix. Two subcommands:

  plan  Enumerate the complete worst-case coordinate space (every cell x mode
        x all 7 renderings x 10 queues x 3 reps) from tests/campaign-cells.json and
        tests/fixtures/w2-branching/support-intake/queues-manifest.json, and
        write tests/results-main/campaign-plan.json. It rebuilds rather than
        appends, so it REFUSES when the existing plan has rows that already ran
        -- `--force` overrides, and puts every one of them back to pending.

  run   Execute pending rows, one cell at a time: start llama-server for the
        cell, run an acceptance probe, then execute every pending row of each
        (mode, queue) pair across ALL SEVEN renderings -- no early stop --
        checkpointing campaign-plan.json after EVERY single run so an
        interruption never loses more than the run in flight. After every row
        it kicks off a background rebuild of dashboard.html (--no-dashboard
        turns that off).

  smoke Stratified pre-flight over the same chain, on a SEPARATE results root
        (tests/results-smoke/), executed cell by cell. Its runs are throwaway by
        construction -- see _use_results_root and cmd_smoke. Each block is
        stratified over what its own smoke has never tried: MAIN over the two
        prose renderings, 3 sampled (queue, rep) pairs each = 36 rows; routing
        over all seven renderings x its five actions = 210 rows, since none of
        support-routing's documents has met a model.

The adaptive ladder was removed on 2026-08-22: climbing L and stopping
at the first level above threshold assumes fidelity is monotone in L, i.e. that
a threshold exists -- which is the conclusion the campaign is meant to
establish, not its premise. The full grid yields a fidelity curve per level
instead of a threshold table. Recorded as an amendment in
doc/experiment-minimum-context.md SS12.

`campaign.py run` is meant to be launched OUTSIDE the pipeline session --
`python tests/runner/campaign.py run` in its own terminal, potentially for
hours. There is no dedicated resume flag: relaunching the same command IS the
resume. At startup it loads the existing campaign-plan.json (does not
regenerate it) and reconciles any row still "pending" against
tests/results-main/index.jsonl -- a row whose exact coordinates already have a
"done" entry in the index is marked done without rerunning. Supervise a live
campaign by opening tests/results-main/dashboard.html, rebuilt in the
background after every row and at any moment by hand with
`python scripts/dashboard.py`; campaign-plan.json and index.jsonl remain the
underlying record. MAIN writes to tests/results-main/, NOT tests/results/, which
holds the pilot and the earlier fixture work -- see MAIN_RESULTS_DIR. Do not keep
a wizard.py session open for the campaign's duration (see
doc/experiment-minimum-context.md).

Cell order is execution order. qwen3.5-9b runs as TWO cells, nothink first and
think last (2026-08-23): the thinking mode spent its whole 13,024-token budget
deliberating on all of MAIN's first rows without beginning an answer, so its 210
rows are worth roughly fourteen hours of probable no-output. Last means the five
models that do answer are measured first, and the decision about this one can be
taken with their results in hand. It costs one extra load of the same gguf.

Server lifecycle is Windows-specific (llama-server.exe under C:\\srv\\llama,
taskkill). The start/kill/wait/prefill pattern is ported from the pilot's
probe scripts, not imported: production code does not depend on scratch
tooling.

Two kinds of cell since 2026-08-31, and the cell says which it is (`runner_type`,
mandatory in both cell tables). An `api` cell is the original one: a gguf, a
context, a llama-server started and stopped around its rows, an acceptance probe
before any of them are spent. A `claude-code` cell has no weights and no server
-- its rows are `claude -p` invocations against a hosted model, driven by
_invoke_claude_code -- and it lives in tests/campaign-cells-frontier.json, a table
no pre-existing block reads. Everything downstream of the invocation is shared:
same prompt builder, same renderings, same oracle, same records, same index.

Usage:
    python3 tests/runner/campaign.py plan
    python3 tests/runner/campaign.py run
    python3 tests/runner/campaign.py smoke --plan | --run | --clean
    python3 tests/runner/campaign.py plan --block routing-notrace-haiku
"""
from __future__ import annotations

import argparse
import json
import random
import shutil
import subprocess
import sys
import tempfile
from collections import Counter
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "tests"))

import runner.runner as runner_mod
from runner.schema import Config, Execution, Output, RunRecord, Trace, Usage
from runner.checker import check
from runner.runner import (
    FIXTURES_DIR, RESULTS_DIR, INDEX_PATH,
    _load_fixture, _load_input, _stage,
    _record_path, _score_path, _append_index,
    _parse_trace, _extract_payload,
    assert_queue_alignment, assert_request_alignment,
)
from runner.api_executor import (
    _invoke_api, _normalize_rendering, _load_mode, _build_prompt_e0, DEFAULT_TIMEOUT_S,
    RENDERINGS, PROSE,
)

CELLS_PATH = REPO_ROOT / "tests" / "campaign-cells.json"
# The hosted cells, in a table of their own -- see the _comment inside the file
# for why they are not in campaign-cells.json. Read only by a block that names it
# through `cells_path`; every block that existed before 2026-08-31 keeps reading
# CELLS_PATH and its grid is unchanged.
FRONTIER_CELLS_PATH = REPO_ROOT / "tests" / "campaign-cells-frontier.json"
PLAN_PATH = RESULTS_DIR / "campaign-plan.json"
SUPPORT_INTAKE_FIXTURE_ID = "w2-branching/support-intake"
SUPPORT_ROUTING_FIXTURE_ID = "w2-branching/support-routing"
SUPPORT_ROUTING_NOTRACE_FIXTURE_ID = "w2-branching/support-routing-notrace"
SUPPORT_ROUTING_REPL_FIXTURE_ID = "w2-branching/support-routing-repl"
SUPPORT_ROUTING_NOTRACE_REPL_FIXTURE_ID = "w2-branching/support-routing-notrace-repl"

# The cells the SS8.3 replication reruns (SS12, 2026-08-27): the ones the
# campaign's conclusions actually rest on -- the per-item winner (ministral),
# the ceiling configuration (qwen-think), and the two remaining modes that
# emitted the trace and therefore carry the A/B effect (gemma, qwen-nothink).
# granite and phi4-mini support no headline claim and stay out.
DECISIVE_CELLS = ["qwen3.5-9b-nothink", "ministral-3-8b", "gemma-4-12b", "qwen3.5-9b-think"]
QUEUES_MANIFEST_PATH = FIXTURES_DIR / "w2-branching" / "support-intake" / "queues-manifest.json"
REQUESTS_MANIFEST_PATH = FIXTURES_DIR / "w2-branching" / "support-routing" / "items-manifest.json"

# The seven cells of doc/experiment-minimum-context.md: the five collateral levels
# of SS5.1 and the two prose renderings of SS5.4. One selector, seven values, not a
# grid -- imported from api_executor so the driver and the prompt builder cannot
# disagree about what a cell is.
REPS_PER_RENDERING = 3
SPEC_VERSION = "0.6"  # matches runner.schema.Config.spec_version's default -- used for index matching

# The campaign runs in blocks: one fixture, one plan file, one set of staged
# inputs, one repetition count. They share a results root and an index -- every
# index row carries fixture_id and staged_input_id, and the dashboard already
# filters by fixture, so the blocks separate themselves without being kept
# apart (SS7.6). What they cannot share is the plan: MAIN's is a frozen record of
# a run that happened, and rows for a second fixture do not belong in it.
#
# The values below are rebound by _use_block. The module-level defaults are
# MAIN's, so a caller that never mentions a block gets exactly what it got
# before blocks existed.
FIXTURE_ID = SUPPORT_INTAKE_FIXTURE_ID
DEFAULT_BLOCK = "main"

# The acceptability threshold (FR-22, 0.90) is deliberately NOT a constant here:
# with the full grid the driver never reads a score to decide what to run next.
# It is an analysis threshold (doc/experiment-minimum-context.md SS8.1), and
# keeping it in the driver would suggest otherwise.

# Dashboard regeneration during a run (--no-dashboard turns it off). MAIN is a
# ~20-hour job; a page rebuilt only when it ends is a report, not a monitor.
# Rebuilt after every row, in the background -- see _regen_dashboard. The
# timeout is not the 30s api_executor uses for its single end-of-batch rebuild:
# it also bounds the blocking rebuild that closes the run.
DASHBOARD_SCRIPT = REPO_ROOT / "scripts" / "dashboard.py"
DASHBOARD_TIMEOUT_S = 300
_dashboard_enabled = True
_dashboard_proc = None

# MAIN writes to a root of its own, alongside tests/results rather than inside
# it. The 576 runs already in tests/results are the pilot and the earlier fixture
# work: mixing them in would blend every KPI and every chart on the page with
# measurements taken on other fixtures, other models and code that has since
# changed. Separate roots keep the campaign's dashboard the campaign's, and leave
# the historical record exactly where the seven documents in doc/ say it is.
MAIN_RESULTS_DIR = REPO_ROOT / "tests" / "results-main"

SMOKE_RESULTS_DIR = REPO_ROOT / "tests" / "results-smoke"
SMOKE_PLAN_PATH = SMOKE_RESULTS_DIR / "campaign-smoke-plan.json"
SMOKE_RUNS_PER_COMBO = 3
# The smoke proves what has never run. On MAIN that was the prose cells and only
# them: new code over new documents, while L0..L4 travelled the same invoke ->
# score -> index chain the toolchain suite already covers end to end. Narrowing
# the smoke to prose was a declared choice about MAIN, not a standing property of
# smokes -- see BLOCKS, where each block names the renderings its own smoke has
# reason to cover.
SMOKE_RENDERINGS = PROSE
SMOKE_SEED = 20260822

# One draw per stratum per (mode, rendering) combination, for a block whose smoke
# stratifies by something other than the input id. Three would triple the bill to
# say the same thing: within a stratum the runs answer one question -- does a
# model reading this rendering emit a parseable trace for this kind of decision --
# and the stratum, not the repetition, is what carries the coverage.
SMOKE_RUNS_PER_STRATUM = 1

LLAMA_DIR = Path(r"C:\srv\llama")
SERVER_HOST = "127.0.0.1"
SERVER_PORT = 8090
SERVER_URL = f"http://{SERVER_HOST}:{SERVER_PORT}"
SERVER_STARTUP_TIMEOUT_S = 300
VRAM_RELEASE_TIMEOUT_S = 60
ACCEPTANCE_MAX_TOKENS = 16
PREFILL_TPS_THRESHOLD = 1000  # FR-17: sole binding acceptance criterion -- UNCHANGED on 2026-08-22

# 2026-08-22. The threshold above was calibrated on real ~15,000-token
# prefills; the probe that measured it sent 18 tokens, on which
# prompt_per_second reports the request's fixed overhead and not the prefill --
# so no cell could ever pass. Measured the same instant on the same server
# (Qwen3.5-9B, ctx 32768, KV q8_0):
#
#     18 tokens ->     7.1 t/s     2,688 tokens -> 1,861.7 t/s
#                                  6,525 tokens -> 1,900.9 t/s
#
# The regime is stable well below 2,700 tokens (the two large prefills differ by
# 2%, the short one by two orders of magnitude). What changes here is the INPUT
# the criterion is measured on, which is what it always meant.
PROBE_MIN_PROMPT_TOKENS = 2500
# Conservative chars-per-token budget for sizing the probe. Measured on Qwen it
# is 4.91 (6,596 chars x 2 = 2,688 tokens); 6.0 leaves room for the four less
# dense tokenizers. This is a sizing figure, not a measurement: validity is
# certified at runtime by the server-reported prompt_n (see _acceptance_check).
PROBE_CHARS_PER_TOKEN = 6.0
PROBE_MIN_PROMPT_CHARS = int(PROBE_MIN_PROMPT_TOKENS * PROBE_CHARS_PER_TOKEN)


# ---------------------------------------------------------------------------
# plan
# ---------------------------------------------------------------------------

def _load_cells(path: Path | None = None) -> list[dict]:
    """The cell table at `path`, campaign-cells.json by default.

    The default is the GPU grid, and it stays the default so every caller that
    means "the campaign's cells" -- the toolchain suite included -- keeps meaning
    exactly what it meant. A block that runs somewhere else names its own table."""
    return json.loads((path or CELLS_PATH).read_text(encoding="utf-8"))


def _load_queue_ids() -> list[str]:
    manifest = json.loads(QUEUES_MANIFEST_PATH.read_text(encoding="utf-8"))
    return [q["queue_id"] for q in manifest["queues"]]


def _load_request_ids(manifest_path: Path = REQUESTS_MANIFEST_PATH) -> list[str]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    return [r["request_id"] for r in manifest["requests"]]


def _routing_action_strata(fixture_id: str = SUPPORT_ROUTING_FIXTURE_ID) -> dict[str, list[str]]:
    """The routing requests grouped by the action their expectation names.

    The composition is deliberately lopsided -- ten ASSIGN against one
    NEEDS_INFO -- because that is what a realistic queue looks like, and MAIN's
    smoke draws (input, rep) pairs uniformly. Uniform over twenty requests, three
    draws per combination, gives a given combination a 28% chance of ever seeing
    an UNASSIGNED: the action that exists because P4 is accepted by no team, and
    the one thing in this fixture with no counterpart in support-intake. A smoke
    that reports green without having tried it is answering a question nobody
    asked.

    Read off expectations.json rather than a list kept here: the actions are the
    oracle's own output, and a second copy of them would drift. Intersected with
    the manifest so a case the plan does not stage -- r00-malformed, which has no
    action at all -- cannot be drawn."""
    expectations = json.loads(
        (FIXTURES_DIR / fixture_id / "expectations.json")
        .read_text(encoding="utf-8"))
    planned = set(_load_request_ids(FIXTURES_DIR / fixture_id / "items-manifest.json"))

    strata: dict[str, list[str]] = {}
    for case in expectations["cases"]:
        request_id = Path(case["input"]).stem
        if request_id not in planned:
            continue
        item = (case.get("expected_output") or {}).get("item") or {}
        action = item.get("action")
        if action:
            strata.setdefault(action, []).append(request_id)
    return strata


BLOCKS = {
    # MAIN: fifteen items in one invocation, ten queues, three repetitions.
    "main": {
        "fixture_id": SUPPORT_INTAKE_FIXTURE_ID,
        "plan_name": "campaign-plan.json",
        "reps": 3,
        "inputs": _load_queue_ids,
        "smoke_plan_name": "campaign-smoke-plan.json",
        "smoke_renderings": PROSE,
        "smoke_strata": None,          # uniform draw over (queue, rep)
    },
    # The per-item block (SS4.5, SS7.6). Twenty stratified requests, two
    # repetitions: each request is already an independent trial, so repeating
    # one three times buys redundancy rather than a second variance component --
    # but one repetition would measure no stochastic noise at all.
    #
    # Its smoke covers all seven renderings, where MAIN's covered two. The reason
    # MAIN left L0..L4 out was that its L documents had already been through a
    # live model and only the prose branch had not; for support-routing none of
    # the seven has -- the fixture has never met a model at all (2026-08-23) --
    # so there is no rendering here that another run has already vouched for.
    "routing": {
        "fixture_id": SUPPORT_ROUTING_FIXTURE_ID,
        "plan_name": "campaign-plan-routing.json",
        "reps": 2,
        "inputs": _load_request_ids,
        "smoke_plan_name": "campaign-smoke-plan-routing.json",
        "smoke_renderings": RENDERINGS,
        "smoke_strata": _routing_action_strata,
    },
    # The untracked arm (SS10): support-routing with the Emit-verbatim steps
    # removed and nothing else changed -- same requests, same expectations, same
    # grid, so the A/B against `routing` is between treatments, not between
    # documents. Its runs carry no trace by construction: comprehension,
    # conditional fidelity and sequence are structurally unobservable, and the
    # endpoint of the comparison is quality alone. Prediction registered in
    # advance (SS10): if the tracking competes with the primary task, this arm
    # scores HIGHER quality than `routing`.
    "routing-notrace": {
        "fixture_id": SUPPORT_ROUTING_NOTRACE_FIXTURE_ID,
        "plan_name": "campaign-plan-routing-notrace.json",
        "reps": 2,
        "inputs": lambda: _load_request_ids(
            FIXTURES_DIR / SUPPORT_ROUTING_NOTRACE_FIXTURE_ID / "items-manifest.json"),
        "smoke_plan_name": "campaign-smoke-plan-routing-notrace.json",
        "smoke_renderings": RENDERINGS,
        "smoke_strata": lambda: _routing_action_strata(SUPPORT_ROUTING_NOTRACE_FIXTURE_ID),
    },
    # The SS8.3 replication arms: the same twenty frozen strata and worlds as
    # `routing` / `routing-notrace`, the items drawn from the sealed REPLICATION
    # half of the pool instead (build_requests.py --repl, seed 20260827), the
    # grid restricted to the decisive cells. Everything else -- documents,
    # renderings, reps, oracle -- is the tracked/untracked pair unchanged, so
    # each repl block reads against its MAIN-pool counterpart one-to-one.
    "routing-repl": {
        "fixture_id": SUPPORT_ROUTING_REPL_FIXTURE_ID,
        "plan_name": "campaign-plan-routing-repl.json",
        "reps": 2,
        "cells": DECISIVE_CELLS,
        "inputs": lambda: _load_request_ids(
            FIXTURES_DIR / SUPPORT_ROUTING_REPL_FIXTURE_ID / "items-manifest.json"),
        "smoke_plan_name": "campaign-smoke-plan-routing-repl.json",
        "smoke_renderings": RENDERINGS,
        "smoke_strata": lambda: _routing_action_strata(SUPPORT_ROUTING_REPL_FIXTURE_ID),
    },
    "routing-notrace-repl": {
        "fixture_id": SUPPORT_ROUTING_NOTRACE_REPL_FIXTURE_ID,
        "plan_name": "campaign-plan-routing-notrace-repl.json",
        "reps": 2,
        "cells": DECISIVE_CELLS,
        "inputs": lambda: _load_request_ids(
            FIXTURES_DIR / SUPPORT_ROUTING_NOTRACE_REPL_FIXTURE_ID / "items-manifest.json"),
        "smoke_plan_name": "campaign-smoke-plan-routing-notrace-repl.json",
        "smoke_renderings": RENDERINGS,
        "smoke_strata": lambda: _routing_action_strata(SUPPORT_ROUTING_NOTRACE_REPL_FIXTURE_ID),
    },
    # The frontier arm (2026-08-31, Gianni's request): the untracked fixture again,
    # unchanged in every coordinate -- same twenty requests, same seven renderings,
    # same two repetitions, same oracle -- run through `claude -p --model
    # claude-haiku-4-5` instead of a local llama-server. It is the campaign's own
    # everyday use case, and its only job is to be a term of comparison: what the
    # six 4-to-12B cells score against what a hosted small model scores on exactly
    # the same documents.
    #
    # A block of its own rather than a seventh cell of `routing-notrace`, for two
    # reasons that both matter. campaign-plan-routing-notrace.json is a frozen
    # record of a run that happened, and `plan` rebuilds rather than appends: the
    # only way to add a cell to it is --force, which puts every executed row back
    # to pending. And the cell table it reads is not the same one -- see
    # FRONTIER_CELLS_PATH. The results root and the index are shared as usual, so
    # the two arms still read one-to-one off `mode`.
    "routing-notrace-haiku": {
        "fixture_id": SUPPORT_ROUTING_NOTRACE_FIXTURE_ID,
        "plan_name": "campaign-plan-routing-notrace-haiku.json",
        "reps": 2,
        "cells_path": FRONTIER_CELLS_PATH,
        "cells": ["claude-code-haiku"],
        "inputs": lambda: _load_request_ids(
            FIXTURES_DIR / SUPPORT_ROUTING_NOTRACE_FIXTURE_ID / "items-manifest.json"),
        "smoke_plan_name": "campaign-smoke-plan-routing-notrace-haiku.json",
        "smoke_renderings": RENDERINGS,
        "smoke_strata": lambda: _routing_action_strata(SUPPORT_ROUTING_NOTRACE_FIXTURE_ID),
    },
    # The other two rungs of the hosted ladder (2026-09-01, Gianni's request),
    # planned before any row of them ran: the same arm again on Sonnet 5 and on
    # Opus 5. Everything the haiku block holds fixed stays fixed -- fixture,
    # twenty requests, seven renderings, two repetitions, oracle, results root,
    # index -- and the model id is the only coordinate that moves, which is what
    # makes the three readable against each other and against the six GPU cells.
    #
    # One block and one plan file each, for the reason the haiku block already
    # states: `plan` rebuilds rather than appends, so a cell added to an existing
    # plan can only be had with --force, and --force puts 280 executed rows back
    # to pending. Each block names its cell through `cells` because the frontier
    # table now holds three of them.
    "routing-notrace-sonnet": {
        "fixture_id": SUPPORT_ROUTING_NOTRACE_FIXTURE_ID,
        "plan_name": "campaign-plan-routing-notrace-sonnet.json",
        "reps": 2,
        "cells_path": FRONTIER_CELLS_PATH,
        "cells": ["claude-code-sonnet"],
        "inputs": lambda: _load_request_ids(
            FIXTURES_DIR / SUPPORT_ROUTING_NOTRACE_FIXTURE_ID / "items-manifest.json"),
        "smoke_plan_name": "campaign-smoke-plan-routing-notrace-sonnet.json",
        "smoke_renderings": RENDERINGS,
        "smoke_strata": lambda: _routing_action_strata(SUPPORT_ROUTING_NOTRACE_FIXTURE_ID),
    },
    "routing-notrace-opus": {
        "fixture_id": SUPPORT_ROUTING_NOTRACE_FIXTURE_ID,
        "plan_name": "campaign-plan-routing-notrace-opus.json",
        "reps": 2,
        "cells_path": FRONTIER_CELLS_PATH,
        "cells": ["claude-code-opus"],
        "inputs": lambda: _load_request_ids(
            FIXTURES_DIR / SUPPORT_ROUTING_NOTRACE_FIXTURE_ID / "items-manifest.json"),
        "smoke_plan_name": "campaign-smoke-plan-routing-notrace-opus.json",
        "smoke_renderings": RENDERINGS,
        "smoke_strata": lambda: _routing_action_strata(SUPPORT_ROUTING_NOTRACE_FIXTURE_ID),
    },
}

_ACTIVE_BLOCK: dict = {}


def _block_cells() -> list[dict]:
    """The cells the active block runs: its `cells_path` table (campaign-cells.json
    unless the block names another), filtered by the block's optional `cells` list.
    A block without either key runs the whole GPU grid -- every block before the
    replication arms, unchanged."""
    cells = _load_cells(_ACTIVE_BLOCK.get("cells_path"))
    wanted = _ACTIVE_BLOCK.get("cells")
    if not wanted:
        return cells
    return [c for c in cells if c["cell"] in wanted]


def _use_block(name: str) -> dict:
    """Point the driver at one block, and its results root at MAIN's.

    Same idiom as _use_results_root, and for the same reason: the fixture and
    the repetition count are read at call time by functions several frames down,
    so rebinding them here reaches all of them without threading a parameter
    through eight signatures that have no other use for it.
    """
    global FIXTURE_ID, REPS_PER_RENDERING, _ACTIVE_BLOCK
    block = BLOCKS[name]
    _ACTIVE_BLOCK = block
    FIXTURE_ID = block["fixture_id"]
    REPS_PER_RENDERING = block["reps"]
    _use_results_root(MAIN_RESULTS_DIR, block["plan_name"])
    return block


def _input_of(row: dict) -> str:
    """The staged input a plan row names.

    Written as `input` since 2026-08-23 and read either way: MAIN's plan file
    was already running with `queue`, and the resume matches on this value.
    """
    return row.get("input", row.get("queue"))


def build_plan(cells: list[dict], input_ids: list[str], reps: int | None = None) -> list[dict]:
    """FR-12: enumerate the complete coordinate space before any GPU spend."""
    rows = []
    for cell in cells:
        for mode in cell["modes"]:
            for rendering in RENDERINGS:
                for input_id in input_ids:
                    for rep in range(1, (reps or REPS_PER_RENDERING) + 1):
                        rows.append({
                            "cell": cell["cell"], "mode": mode,
                            "rendering": rendering, "input": input_id,
                            "rep": rep, "status": "pending",
                        })
    return rows


def _save_plan(plan: list[dict]) -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    PLAN_PATH.write_text(json.dumps(plan, indent=2, ensure_ascii=False), encoding="utf-8")


def cmd_plan(args: argparse.Namespace) -> None:
    """Build the plan. Refuses to overwrite one that has already run.

    The name reads like an inspection and the command is not one: it rebuilds
    from the cell table and writes, so on a campaign in progress every executed
    row goes back to `pending`. On MAIN that was 421 done, 3 error and 3
    skipped-window reset in one call. The done rows would come back from
    index.jsonl on the next resume; `error` and `skipped-window` would not,
    having no index row to be credited from, and a `skipped-window` row buys the
    same refusal again -- its prompt does not fit the model's window."""
    block = _use_block(getattr(args, "block", None) or DEFAULT_BLOCK)
    if PLAN_PATH.exists() and not getattr(args, "force", False):
        try:
            existing = json.loads(PLAN_PATH.read_text(encoding="utf-8"))
        except Exception:
            existing = []
        started = [r for r in existing if r.get("status") != "pending"]
        if started:
            counts = Counter(r.get("status") for r in started)
            summary = ", ".join(f"{n} {s}" for s, n in sorted(counts.items()))
            sys.exit(
                f"{PLAN_PATH.name} has {len(started)} rows already run ({summary}).\n"
                f"Rebuilding would reset every one of them to pending. Pass --force "
                f"if that is what you want, or delete the file first.")
    rows = build_plan(_block_cells(), block["inputs"]())
    _save_plan(rows)
    try:
        where = PLAN_PATH.relative_to(REPO_ROOT)
    except ValueError:      # a plan under a tmp root, as the tests build
        where = PLAN_PATH
    print(f"Plan: {len(rows)} rows -> {where}")


# ---------------------------------------------------------------------------
# mode config (tests/modes.json, cached per mode name)
# ---------------------------------------------------------------------------

_MODE_CACHE: dict[str, dict] = {}


def _mode_config(mode: str) -> dict:
    if mode not in _MODE_CACHE:
        (key, url, model, backend, reasoning_budget, temperature,
         thinking, ctx_size, kv_cache_type, n_parallel) = _load_mode(mode)
        _MODE_CACHE[mode] = {
            "key": key, "url": url, "model": model, "backend": backend,
            "reasoning_budget": reasoning_budget, "temperature": temperature,
            "thinking": thinking, "ctx_size": ctx_size,
            "kv_cache_type": kv_cache_type, "n_parallel": n_parallel,
        }
    return _MODE_CACHE[mode]


# ---------------------------------------------------------------------------
# resume — reconcile plan against index.jsonl (FR-14)
# ---------------------------------------------------------------------------

def _index_done_counts() -> dict[tuple, int]:
    """{coordinate tuple -> number of 'done' index.jsonl rows matching it}.
    The match tuple (FR-14/FR-07) has no per-rep component, so a rendering's
    N done index entries satisfy the first N pending plan rows (by rep
    order) at that same (cell, mode, rendering, queue) coordinate.

    `mode` is part of the coordinate since 2026-08-23. Without it
    llama-qwen3.5-9b-think and llama-qwen3.5-9b-nothink are indistinguishable --
    same gguf, same backend, same reasoning_budget of 12000, and `thinking` was
    in neither key. Seven think runs duly satisfied nothink's coordinates too,
    and the resume marked five nothink rows done that had never run. A row the
    plan calls done is a row nobody looks at again."""
    counts: dict[tuple, int] = {}
    if not INDEX_PATH.exists():
        return counts
    for line in INDEX_PATH.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if row.get("status") != "done":
            continue
        key = (
            row.get("fixture_id"), row.get("staged_input_id"), row.get("context"),
            row.get("model_id"), row.get("spec_version"), row.get("backend"),
            row.get("reasoning_budget"), row.get("process_rendering") or "",
            row.get("mode") or "",
        )
        counts[key] = counts.get(key, 0) + 1
    return counts


def _index_key_for(mode: str, rendering: str, input_id: str) -> tuple:
    mode_cfg = _mode_config(mode)
    return (
        FIXTURE_ID, input_id, "E0", mode_cfg["model"],
        SPEC_VERSION, mode_cfg["backend"], mode_cfg["reasoning_budget"],
        _normalize_rendering(rendering),
        mode,
    )


def _reconcile_with_index(plan: list[dict]) -> None:
    """Mark pending rows done when index.jsonl proves the run already happened.

    The index entries a coordinate already spent on rows the plan ITSELF records
    as done must be subtracted first (2026-08-22). Without that
    subtraction the tally double-counts on every resume: a plan row marked done
    before the interruption still has its index entry, and that entry would go on
    to satisfy a *different*, never-executed pending row at the same coordinate.
    The run would be reported done without anyone running it -- a silent hole in
    the dataset, and one that grows with every resume. MAIN is 13-18 hours and
    will be resumed."""
    counts = _index_done_counts()

    consumed: dict[tuple, int] = {}
    groups: dict[tuple, list[dict]] = {}
    for row in plan:
        key = _index_key_for(row["mode"], row["rendering"], _input_of(row))
        if row["status"] == "pending":
            groups.setdefault(key, []).append(row)
        elif row["status"] == "done":
            consumed[key] = consumed.get(key, 0) + 1

    for index_key, rows in groups.items():
        available = counts.get(index_key, 0) - consumed.get(index_key, 0)
        if available <= 0:
            continue
        rows.sort(key=lambda r: r["rep"])
        for row in rows[:available]:
            row["status"] = "done"


# ---------------------------------------------------------------------------
# llama-server lifecycle (Windows) — ported from proto/cella.py, proto/vramprobe.py
# ---------------------------------------------------------------------------

def _start_server(cell: dict) -> subprocess.Popen:
    log = LLAMA_DIR / f"campaign-{cell['cell']}.log"
    err = LLAMA_DIR / f"campaign-{cell['cell']}.err"
    # The child gets its own duplicated handles at spawn time, so the parent's
    # copies are closed as soon as Popen returns: a campaign starts five servers
    # and MAIN runs for 13-18 hours -- releasing them is not left to refcounting.
    with open(log, "w") as out, open(err, "w") as errout:
        return subprocess.Popen(
            [str(LLAMA_DIR / "llama-server.exe"), "-m", "ai-models\\" + cell["gguf"],
             "--ctx-size", str(cell["ctx_size"]), "--n-gpu-layers", "999",
             "-np", str(cell["n_parallel"]),
             "--cache-type-k", cell["kv_cache_type"], "--cache-type-v", cell["kv_cache_type"],
             "--host", SERVER_HOST, "--port", str(SERVER_PORT)],
            cwd=str(LLAMA_DIR),
            stdout=out, stderr=errout,
        )


def _wait_for_server(timeout: int = SERVER_STARTUP_TIMEOUT_S) -> bool:
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            r = json.loads(urllib.request.urlopen(f"{SERVER_URL}/v1/models", timeout=5).read())
            if r.get("data"):
                return True
        except (urllib.error.URLError, urllib.error.HTTPError, OSError, ValueError):
            pass
        time.sleep(3)
    return False


def _vram() -> tuple[int | None, int | None]:
    """Informational only (FR-17) — never blocks the acceptance decision."""
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.used,memory.free", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, check=True,
        ).stdout.strip().splitlines()[0]
        used, free = (int(x.strip()) for x in out.split(","))
        return used, free
    except Exception:
        return None, None


def _acceptance_probe_prompt(fixture_meta: dict) -> str:
    """Probe body: the fixture body repeated until it reaches campaign size.

    prompt_per_second only measures prefill throughput once there is a prefill
    worth measuring. The fixture body is the natural yardstick: it IS
    what every run of the campaign prefills."""
    body = (fixture_meta or {}).get("body") or ""
    if not body.strip():
        raise RuntimeError(
            "acceptance probe cannot be built: fixture body is empty -- "
            "a probe with no prefill measures nothing"
        )
    parts = [body]
    size = len(body)
    while size < PROBE_MIN_PROMPT_CHARS:
        parts.append(body)
        size += len(body) + 2  # the "\n\n" joiner
    return "\n\n".join(parts)


def _acceptance_check(fixture_meta: dict) -> bool:
    """FR-17: prompt_per_second > 1000 on a real-sized prefill probe is the ONLY
    binding criterion. VRAM is read and logged, never blocking.

    Two readings, not one: prompt_n says whether the measurement is valid at
    all, prompt_per_second is the verdict. Conflating them is what made the
    2026-08-22 launch reject five healthy cells without saying why."""
    used, free = _vram()
    print(f"  vram used={used} free={free} MiB (informational, not blocking)")

    try:
        models_resp = json.loads(urllib.request.urlopen(f"{SERVER_URL}/v1/models", timeout=10).read())
        model_id = models_resp["data"][0]["id"]
    except Exception as exc:
        print(f"  acceptance probe failed: could not read /v1/models ({exc})")
        return False

    system_prompt = (fixture_meta.get("meta") or {}).get("system_prompt", "")
    payload = {
        "model": model_id,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": _acceptance_probe_prompt(fixture_meta)},
        ],
        "max_tokens": ACCEPTANCE_MAX_TOKENS,
    }
    req = urllib.request.Request(
        f"{SERVER_URL}/v1/chat/completions",
        data=json.dumps(payload).encode(),
        headers={"content-type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            out = json.loads(resp.read().decode())
    except (urllib.error.URLError, urllib.error.HTTPError, OSError, ValueError) as exc:
        print(f"  acceptance probe failed: {exc}")
        return False

    timings = out.get("timings") or {}
    tps = timings.get("prompt_per_second")
    prompt_n = timings.get("prompt_n")

    if not prompt_n or prompt_n < PROBE_MIN_PROMPT_TOKENS:
        print(f"  acceptance probe INVALID: prompt_n={prompt_n} < {PROBE_MIN_PROMPT_TOKENS} "
              f"minimum -- measurement does not reflect prefill, not a hardware verdict "
              f"(prompt_per_second={tps})")
        return False

    print(f"  acceptance probe: prompt_n={prompt_n} prompt_per_second={tps} "
          f"(threshold {PREFILL_TPS_THRESHOLD})")
    return bool(tps and tps > PREFILL_TPS_THRESHOLD)


def _stop_server() -> None:
    """taskkill then wait for VRAM release, same rationale as
    proto/vramprobe.py::kill — the driver frees memory after the process
    exits, not at taskkill's return."""
    subprocess.run(["taskkill", "/F", "/IM", "llama-server.exe"], capture_output=True, text=True)
    t0 = time.time()
    while time.time() - t0 < VRAM_RELEASE_TIMEOUT_S:
        time.sleep(2)
        used, _free = _vram()
        if used is not None and used <= 200:
            return
    # Informational timeout only — proceeds regardless (same rationale as _acceptance_check's VRAM read).


# ---------------------------------------------------------------------------
# single-row execution (import diretto — same process, no subprocess per run)
# ---------------------------------------------------------------------------

WINDOW_OVERFLOW_MARKER = "exceeds the available context size"

# Minimum room a run must have left for its answer after the prompt is in.
# Measured 2026-08-22 on queue-07 at L4: gemma's prompt tokenises to 42,960 in a
# 43,008 window and the model got 48 tokens to answer in; Ministral's to 37,487
# in 38,912 and it was cut off at exactly the 1,425 that were left. Both runs
# reported 'done' and entered the results as if they measured the model. They
# measured the bench. A run whose answer cannot fit is refused BEFORE it is
# spent, and declared -- which is what the whole card is about.
MIN_GENERATION_ROOM = 2048


def _prompt_token_count(text: str) -> int | None:
    """Exact prompt length from the loaded cell's own tokenizer (/tokenize).

    Exact, not estimated: the same prompt is 37,961 tokens for Qwen and 42,960
    for gemma, so a single chars-per-token ratio cannot be used to decide
    whether a row fits. Returns None if the endpoint is unavailable -- the run
    then proceeds as before rather than being skipped on a failed measurement."""
    try:
        req = urllib.request.Request(
            f"{SERVER_URL}/tokenize",
            data=json.dumps({"content": text}).encode(),
            headers={"content-type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            return len(json.loads(resp.read().decode()).get("tokens") or [])
    except (urllib.error.URLError, urllib.error.HTTPError, OSError, ValueError, TypeError):
        return None


def _window_room(cell: dict, mode_cfg: dict, sol_doc: dict, bundle, fixture_meta: dict,
                 rendering: str) -> tuple[int | None, int | None]:
    """(prompt_tokens, room_left) for this row, or (None, None) if unmeasurable."""
    prompt = _build_prompt_e0(sol_doc, bundle, (fixture_meta or {}).get("body", ""),
                              level=rendering,
                              prose_bodies=(fixture_meta or {}).get("prose"))
    system_prompt = ((fixture_meta or {}).get("meta") or {}).get("system_prompt", "")
    n = _prompt_token_count(system_prompt + "\n" + prompt if system_prompt else prompt)
    if n is None:
        return None, None
    return n, cell["ctx_size"] - n


def _is_window_overflow(raw: str | None) -> bool:
    """llama-server refused the request because the prompt is larger than
    --ctx-size, before computing anything.

    This is not a failure of the run and not a verdict on the model: it is the
    bench declaring that this (queue, rendering) does not fit this cell's window.
    Measured 2026-08-22: queue-07 is an outlier at 24,908 tokens
    already at L0 against 6,177-15,792 for the other nine, and 37,116 at L4.
    Contexts were raised to the VRAM ceiling of each cell the same day; what
    still does not fit is a property of an 8 GB card, and it is reported as
    such rather than buried among execution errors."""
    return bool(raw and WINDOW_OVERFLOW_MARKER in raw)


# The directory `claude -p` is launched from. Neutral by construction: at E0 the
# CLI is given no tools, so it has nothing to read there, and --safe-mode means
# nothing in it is loaded as configuration either. Same choice executor.py makes,
# through the one stdlib call that answers on every platform instead of a chain
# of environment variables.
CLAUDE_CODE_CWD = Path(tempfile.gettempdir()).resolve()


def _invoke_claude_code(sol_doc: dict, bundle, fixture_meta: dict, model: str,
                        rendering: str, timeout_s: int
                        ) -> tuple[str, str, list[str], object | None, dict]:
    """One `claude -p` run at E0. Same return contract as _invoke_api.

    The prompt comes from api_executor._build_prompt_e0 -- the same builder, the
    same rendering, the same L1 instruction -- so the two arms differ by the
    runner and the model, not by the document. executor.py is deliberately not
    reused here: it has no --level and always builds L1, which would collapse the
    seven renderings into one and file six of them under labels they never had.

    Three flags carry the comparability, and none of them is cosmetic:

      --safe-mode  Without it the CLI loads the host machine's ~/.claude/CLAUDE.md,
          its SessionStart hooks and its plugins. On the machine this campaign runs
          on, that means every row would open with "CAVEMAN MODE ACTIVE" and a
          standing order to answer in Italian, reaching the model before the fixture
          does. The runs would measure the operator's shell, not the model.
      --system-prompt  Replaces Claude Code's default system prompt with the
          fixture's own -- which is exactly what the API arm sends as `system`.
          Appending it instead would leave the coding-agent persona underneath.
      --tools ""  E0. No tools, the input pre-injected into the prompt.

    The prompt travels on stdin, not as an argv element, and that is not a style
    choice. Windows caps a command line at 32,767 characters; this fixture's
    prompt is 10,414 at L0 and 45,469 at L4, so L3 and L4 overflow it. What
    CreateProcess raises there is ERROR_FILENAME_EXCED_RANGE, which Python
    surfaces as FileNotFoundError -- the same exception a missing executable
    raises. Measured 2026-08-31: the smoke ran L1 and died on the next row
    claiming the claude CLI was not installed. Two of the seven renderings were
    unrunnable and the bench said the wrong thing about why.

    No window check precedes this call: there is no /tokenize endpoint to measure
    against and no --ctx-size to measure into. A prompt too large for the model is
    an API error, and arrives here as a non-zero exit filed as 'error'.
    """
    meta = (fixture_meta or {}).get("meta", {})
    system_prompt = meta.get("system_prompt")
    if not system_prompt:
        raise RuntimeError(
            f"fixture {FIXTURE_ID} declares no system_prompt: the claude-code arm "
            f"replaces Claude Code's default system prompt with the fixture's, and "
            f"an empty one would leave the run with no persona where the API arm has one")

    prompt = _build_prompt_e0(sol_doc, bundle, (fixture_meta or {}).get("body", ""),
                              level=rendering,
                              prose_bodies=(fixture_meta or {}).get("prose"))
    messages = [{"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}]
    cmd = [
        "claude", "-p",
        "--output-format", "json",
        "--model", model,
        "--system-prompt", system_prompt,
        "--tools", "",
        "--safe-mode",
        "--no-session-persistence",
    ]

    try:
        result = subprocess.run(
            cmd, input=prompt,
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=timeout_s, cwd=str(CLAUDE_CODE_CWD),
        )
    except subprocess.TimeoutExpired:
        return "timeout", f"[timeout after {timeout_s}s]", [], None, {"request_messages": messages}
    except FileNotFoundError as exc:
        sys.exit(f"could not launch the claude CLI: {exc}. The prompt travels on stdin, "
                 f"so this is not the command-line length limit -- check that `claude` is "
                 f"on PATH for the process running the campaign.")

    if result.returncode != 0:
        err = result.stderr.strip() or result.stdout.strip() or "non-zero exit"
        return "error", err, [], None, {"request_messages": messages}

    try:
        out = json.loads(result.stdout)
    except json.JSONDecodeError:
        return "error", result.stdout.strip(), [], None, {"request_messages": messages}

    # is_error is the CLI's own verdict on the turn (an API error it recovered
    # from, a refusal, a budget stop). Reading only the exit code would file those
    # as 'done' with an explanation string where the payload should be.
    if out.get("is_error"):
        return ("error",
                str(out.get("result") or out.get("api_error_status") or "claude reported is_error"),
                [], None, {"request_messages": messages})

    raw_text = out.get("result") or ""
    # The top-level `usage` block, not modelUsage: modelUsage aggregates every
    # call the CLI made in the invocation, including the small side calls it
    # makes for its own bookkeeping, and would inflate the scored turn's prompt
    # by them. total_cost_usd does cover the whole invocation, and is recorded as
    # such -- it is a bill, not a measurement of the run.
    #
    # tokens_in is the sum of the three prompt counters, not input_tokens alone.
    # The CLI caches the prompt, so most of it is billed once as
    # cache_creation_input_tokens and read back afterwards as
    # cache_read_input_tokens; input_tokens then holds only what fell outside the
    # cached prefix. Measured 2026-08-31 on a 5,355-token prompt: input_tokens 9,
    # cache_creation 5,346. Reading the first field alone would have entered a
    # 5,000-token prompt in the dataset as a 9-token one.
    usage = out.get("usage") or {}
    extras = {
        "tokens_in": ((usage.get("input_tokens") or 0)
                      + (usage.get("cache_creation_input_tokens") or 0)
                      + (usage.get("cache_read_input_tokens") or 0)) or None,
        "tokens_out": usage.get("output_tokens"),
        "cost": out.get("total_cost_usd"),
        "request_messages": messages,
        "reasoning": "",
        "stop_reason": out.get("stop_reason"),
    }
    return "done", raw_text, _parse_trace(raw_text), _extract_payload(raw_text), extras


def _execute_row(row: dict, cell: dict, mode: str, rendering: str, input_id: str,
                 fixture_dir: Path, sol_doc: dict, expectations: dict, fixture_meta: dict):
    """Runs exactly one (cell, mode, rendering, queue, rep) coordinate through the
    same invoke -> score -> save -> index pipeline as api_executor.run_headless_api,
    and exposes the ScoreRecord to its caller. Mutates row['status'] and returns
    the ScoreRecord, or None on a non-'done' execution status.

    The ScoreRecord used to feed the adaptive ladder's stop decision; since the
    ladder was removed it only feeds the progress line. It stays in the return type because
    it is what makes a live campaign readable while it runs.

    Which of the two runners is used is the cell's own declaration, not something
    inferred from the model id or from the presence of a gguf: see
    tests/campaign-cells-frontier.json."""
    mode_cfg = _mode_config(mode)
    bundle = _load_input(fixture_dir, input_id)
    runner_type = cell["runner_type"]

    if runner_type == "api":
        n_prompt, room = _window_room(cell, mode_cfg, sol_doc, bundle, fixture_meta, rendering)
        if room is not None and room < MIN_GENERATION_ROOM:
            row["status"] = "skipped-window"
            print(f"  [{cell['cell']}/{mode}/{rendering}/{input_id}#{row['rep']}] skipped-window "
                  f"prompt={n_prompt} ctx={cell['ctx_size']} room={room} < {MIN_GENERATION_ROOM} "
                  f"-- bench limit, no run spent")
            return None

    sandbox, staged = _stage(bundle)
    t0 = datetime.now(timezone.utc)
    try:
        if runner_type == "api":
            status, raw, steps, payload, extras = _invoke_api(
                sol_doc, bundle, staged, sandbox,
                mode_cfg["model"], "E0", mode_cfg["key"], mode_cfg["url"], DEFAULT_TIMEOUT_S,
                mode_cfg["backend"],
                reasoning_budget=mode_cfg["reasoning_budget"],
                fixture_meta=fixture_meta,
                temperature=mode_cfg["temperature"],
                thinking=mode_cfg["thinking"],
                level=rendering,
            )
        else:
            status, raw, steps, payload, extras = _invoke_claude_code(
                sol_doc, bundle, fixture_meta, mode_cfg["model"], rendering,
                DEFAULT_TIMEOUT_S,
            )
    finally:
        shutil.rmtree(sandbox, ignore_errors=True)
    elapsed_ms = int((datetime.now(timezone.utc) - t0).total_seconds() * 1000)

    ts = datetime.now(timezone.utc)
    run_id = (
        f"{FIXTURE_ID.replace('/', '-')}-{input_id}-"
        f"{ts.strftime('%Y%m%dT%H%M%S')}-{cell['cell']}-{mode}-{rendering}-rep{row['rep']:02d}"
    )
    config = Config(
        fixture_id=FIXTURE_ID,
        context="E0",
        model_id=mode_cfg["model"],
        spec_version=SPEC_VERSION,
        env_realization="emulated",
        process_rendering=_normalize_rendering(rendering),
        mode=mode,
        runner_type=runner_type,
        # runner.schema.Config: api_base_url is "set only for runner_type='api'".
        # A claude-code mode carries url "" precisely because there is no endpoint.
        api_base_url=mode_cfg["url"] if runner_type == "api" else None,
        backend=mode_cfg["backend"],
        reasoning_budget=mode_cfg["reasoning_budget"],
        temperature=mode_cfg["temperature"],
        thinking=mode_cfg["thinking"],
        ctx_size=mode_cfg["ctx_size"],
        kv_cache_type=mode_cfg["kv_cache_type"],
        n_parallel=mode_cfg["n_parallel"],
    )
    record = RunRecord(
        run_id=run_id,
        timestamp=ts.isoformat(),
        config=config,
        staged_input_id=input_id,
        execution=Execution(status=status,
                            wall_clock_ms=elapsed_ms if status == "done" else None,
                            stop_reason=extras.get("stop_reason")),
        trace=Trace(steps=steps, request_messages=extras.get("request_messages", [])),
        output=Output(raw=raw,
                      returned_payload=payload if status == "done" else None,
                      reasoning=extras.get("reasoning", "")),
        # cost is None on every api row -- _invoke_api has no bill to report --
        # and the CLI's total_cost_usd on a claude-code one.
        usage=Usage(tokens_in=extras.get("tokens_in"), tokens_out=extras.get("tokens_out"),
                    cost=extras.get("cost")),
    )
    score = check(record, expectations)

    rec_path = _record_path(config, run_id)
    record.save(rec_path)
    score.save(_score_path(rec_path))
    _append_index(record, score)

    if status == "done":
        row["status"] = "done"
    elif _is_window_overflow(raw):
        row["status"] = "skipped-window"
    else:
        row["status"] = "error"
    print(f"  [{cell['cell']}/{mode}/{rendering}/{input_id}#{row['rep']}] {row['status']} "
          f"quality={score.quality.result} fidelity={score.fidelity.result} "
          f"conditional_rate={score.fidelity.conditional_rate}")
    return score if status == "done" else None


# ---------------------------------------------------------------------------
# full grid (2026-08-22, replaces the adaptive ladder)
# ---------------------------------------------------------------------------

# The consecutive-failure breaker (2026-09-01). Eight is above anything the arms
# have produced -- the haiku arm of 2026-08-31 closed 280/280 done, and the GPU
# grid's worst cell never failed twice in a row for a reason other than its own
# window, which is not counted here.
MAX_CONSECUTIVE_FAILURES = 8


class CampaignAborted(RuntimeError):
    """The breaker fired: the run stops where it is, with rows left pending."""


_consecutive_failures = 0


def _reset_breaker() -> None:
    global _consecutive_failures
    _consecutive_failures = 0


def _note_row_outcome(row: dict) -> None:
    """Stop the whole run after MAX_CONSECUTIVE_FAILURES rows in a row that did
    not complete.

    Why a breaker exists here at all: an `error` row is NOT retried by the
    resume. _reconcile_with_index only turns pending into done, so a failure is
    permanent until somebody rebuilds the plan with --force. On a local cell that
    is academic -- llama-server either serves or fails its acceptance probe. On a
    hosted cell it is not: a rate limit, an expired session or an outage fails
    every row it touches, in seconds each, and an unattended overnight run would
    convert a pause that would have cleared by itself into 280 rows the dataset
    can never have. Eight consecutive is well past noise and still leaves the arm
    recoverable.

    'skipped-window' is not a failure: it is the bench declining to spend a run it
    has measured as unrunnable, and it is a property of the prompt, not of the
    backend. It neither trips the breaker nor clears it.

    Recovery is the documented one, and it loses nothing: `campaign.py plan
    --block <block> --force` rebuilds, the resume re-credits every row
    index.jsonl proves was run, and only the failed ones go back to pending."""
    global _consecutive_failures
    status = row["status"]
    if status == "skipped-window":
        return
    if status == "done":
        _consecutive_failures = 0
        return
    _consecutive_failures += 1
    if _consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
        raise CampaignAborted(
            f"{_consecutive_failures} consecutive rows failed (last: "
            f"{row['cell']}/{row['mode']}/{row['rendering']}/{_input_of(row)}"
            f"#{row['rep']} -> {status}). Stopping before the rest of the plan is "
            f"spent the same way. Resume with 'campaign.py plan --block <block> "
            f"--force' (re-credits every row the index proves was run, puts the "
            f"failed ones back to pending) then 'campaign.py run --block <block>'.")


def _run_rows(cell: dict, mode: str, input_id: str, plan: list[dict],
              fixture_dir: Path, sol_doc: dict, expectations: dict, fixture_meta: dict) -> None:
    """Execute every pending row of one (cell, mode, queue) triple, all seven renderings.

    No early stop on a score and no score is read to decide what runs next: the
    driver executes a list. _execute_row still returns (and prints) its
    ScoreRecord -- the caller simply has no decision left to make with it. The one
    thing that does stop the driver is a run of consecutive failures; see
    _note_row_outcome."""
    for rendering in RENDERINGS:
        rows = sorted(
            (r for r in plan if r["cell"] == cell["cell"] and r["mode"] == mode
             and _input_of(r) == input_id and r["rendering"] == rendering),
            key=lambda r: r["rep"],
        )
        for row in rows:
            if row["status"] != "pending":
                continue
            _execute_row(row, cell, mode, rendering, input_id,
                         fixture_dir, sol_doc, expectations, fixture_meta)
            _save_plan(plan)
            _regen_dashboard()
            _note_row_outcome(row)


# ---------------------------------------------------------------------------
# per-cell lifecycle (FR-15)
# ---------------------------------------------------------------------------

def _dashboard_cmd() -> list[str]:
    """RESULTS_DIR and INDEX_PATH are read at call time, not captured: campaign.py
    runs on two roots (see _use_results_root). api_executor has a function of the
    same name, deliberately not reused -- it takes no arguments and therefore always
    builds tests/results."""
    return [sys.executable, str(DASHBOARD_SCRIPT),
            "--index", str(INDEX_PATH),
            "--output", str(RESULTS_DIR / "dashboard.html"),
            "--csv", str(RESULTS_DIR / "index.csv")]


def _regen_dashboard() -> None:
    """Rebuild the dashboard in the background, after every single row.

    Not blocking, and that is the whole point. A rebuild costs about a second now
    and near two by the end of MAIN; blocking on 1260 of them would leave the GPU
    idle for the better part of half an hour. Spawned and left alone, it runs on
    another core while the next row is already in flight, so the page trails the
    run by one row instead of by twenty minutes at no cost in wall clock.

    If the previous rebuild is still running the call is skipped rather than
    queued: two dashboard.py at once would race on dashboard.html and, worse, on
    index.csv, which is read-then-rewritten. Skipping loses nothing -- the next row
    rebuilds from the same index a moment later.

    Fail-soft. A dashboard is something to read the run with; it must not be able
    to stop a twenty-hour run.
    """
    global _dashboard_proc
    if not _dashboard_enabled or not DASHBOARD_SCRIPT.exists():
        return
    if _dashboard_proc is not None and _dashboard_proc.poll() is None:
        return
    try:
        _dashboard_proc = subprocess.Popen(
            _dashboard_cmd(), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as exc:
        print(f"  dashboard: regeneration skipped ({exc})")


def _finish_dashboard() -> None:
    """One last rebuild, blocking, so the page on disk is the whole run.

    The background rebuilds are best-effort by design: the last rows of a campaign
    can land while one is already in flight and get skipped. Without this the page
    would sit a few runs short of the data it claims to show -- and that page is
    what gets read afterwards.
    """
    global _dashboard_proc
    if not _dashboard_enabled or not DASHBOARD_SCRIPT.exists():
        return
    try:
        if _dashboard_proc is not None and _dashboard_proc.poll() is None:
            _dashboard_proc.wait(timeout=DASHBOARD_TIMEOUT_S)
        result = subprocess.run(_dashboard_cmd(), capture_output=True, text=True,
                                timeout=DASHBOARD_TIMEOUT_S)
        if result.returncode == 0:
            print(f"  dashboard: {_rel(RESULTS_DIR / 'dashboard.html')}")
        else:
            print(f"  dashboard: regeneration failed -- {result.stderr.strip()[:160]}")
    except Exception as exc:
        print(f"  dashboard: regeneration skipped ({exc})")


def _run_modes(cell: dict, plan: list[dict], fixture_dir: Path, sol_doc: dict,
               expectations: dict, fixture_meta: dict) -> None:
    """Every (mode, input) pair the plan holds for this cell. The body both cell
    kinds share, once the question of a server has been settled."""
    cell_name = cell["cell"]
    for mode in cell["modes"]:
        input_ids = sorted({_input_of(r) for r in plan
                            if r["cell"] == cell_name and r["mode"] == mode})
        for input_id in input_ids:
            _run_rows(cell, mode, input_id, plan, fixture_dir, sol_doc, expectations, fixture_meta)


def _run_cell(cell: dict, plan: list[dict], fixture_dir: Path, sol_doc: dict,
             expectations: dict, fixture_meta: dict) -> None:
    cell_name = cell["cell"]
    pending = [r for r in plan if r["cell"] == cell_name and r["status"] == "pending"]
    if not pending:
        print(f"[{cell_name}] no pending rows -- skipping (server not started)")
        return

    if cell["runner_type"] == "claude-code":
        # No server to start and no acceptance probe to run. The probe is a
        # llama-server measurement -- prompt_per_second off /v1/chat/completions
        # against a 2,500-token prefill -- and it has nothing to say about a model
        # running on Anthropic's infrastructure. Skipping it is not a relaxed
        # gate: there is no cell here that could fail it.
        print(f"[{cell_name}] hosted cell -- no llama-server, no acceptance probe")
        _run_modes(cell, plan, fixture_dir, sol_doc, expectations, fixture_meta)
        return

    print(f"[{cell_name}] starting llama-server ({cell['gguf']}, ctx={cell['ctx_size']})")
    _start_server(cell)
    try:
        loaded = _wait_for_server()
        accepted = loaded and _acceptance_check(fixture_meta)
        if not accepted:
            print(f"[{cell_name}] acceptance check failed -- skipping cell, no run spent")
            for row in pending:
                row["status"] = "skipped-acceptance"
            _save_plan(plan)
            return

        _run_modes(cell, plan, fixture_dir, sol_doc, expectations, fixture_meta)
    finally:
        print(f"[{cell_name}] stopping llama-server")
        _stop_server()


# ---------------------------------------------------------------------------
# run
# ---------------------------------------------------------------------------

def _assert_plan_is_runnable(plan: list[dict]) -> None:
    """Refuse to 'run' a plan every row of which a previous run rejected.

    2026-08-22: the failed launch left campaign-plan.json with 899
    'skipped-acceptance' rows and 1 'done'. With the acceptance gate fixed, that
    plan still has zero pending rows, so a run would print 'no pending rows' for
    all five cells and close with 'all cells processed' -- a no-op
    indistinguishable from a completed campaign. A legitimately exhausted plan
    (everything 'done') is not this case and still closes silently."""
    pending = sum(1 for r in plan if r["status"] == "pending")
    rejected = sum(1 for r in plan if r["status"] == "skipped-acceptance")
    if pending == 0 and rejected > 0:
        sys.exit(
            f"{PLAN_PATH.name} has 0 pending rows and {rejected} marked "
            f"'skipped-acceptance' -- a previous run rejected every cell. "
            f"Regenerate the plan with 'campaign.py plan' before launching MAIN "
            f"(regenerating loses nothing: the resume re-marks 'done' whatever "
            f"index.jsonl proves was already run)."
        )

    # A cell the plan has never heard of is not an empty cell. _run_cell reports
    # both as "no pending rows -- skipping", so a plan built before the cells were
    # renamed or reordered would print that line for every cell and close with
    # "all cells processed" -- a campaign that ran nothing, indistinguishable from
    # one that finished. Same failure shape as the check above, different cause.
    planned = {r["cell"] for r in plan}
    unknown = [c["cell"] for c in _block_cells() if c["cell"] not in planned]
    if unknown:
        table = (_ACTIVE_BLOCK.get("cells_path") or CELLS_PATH).name
        sys.exit(
            f"{PLAN_PATH.name} has no rows for {', '.join(unknown)} -- the plan "
            f"predates the current tests/{table}. Regenerate it with "
            f"'campaign.py plan' (regenerating loses nothing: the resume re-marks "
            f"'done' whatever index.jsonl proves was already run)."
        )


def _run_plan(plan_path: Path) -> None:
    """Shared body of 'run' and 'smoke --run': whichever results root and plan
    are in effect when it is called."""
    fixture_dir = FIXTURES_DIR / FIXTURE_ID
    check_alignment = (assert_queue_alignment if FIXTURE_ID == SUPPORT_INTAKE_FIXTURE_ID
                       else assert_request_alignment)
    try:
        check_alignment(fixture_dir)
    except RuntimeError as exc:
        sys.exit(f"{check_alignment.__name__} failed -- aborting before any server "
                 f"or plan row: {exc}")

    if not plan_path.exists():
        sys.exit(f"{plan_path} not found -- run 'python tests/runner/campaign.py plan' first.")
    plan = json.loads(plan_path.read_text(encoding="utf-8"))

    _reconcile_with_index(plan)
    _save_plan(plan)
    _assert_plan_is_runnable(plan)

    _fixture_dir, sol_doc, expectations, fixture_meta = _load_fixture(FIXTURE_ID)

    _reset_breaker()
    try:
        for cell in _block_cells():
            _run_cell(cell, plan, _fixture_dir, sol_doc, expectations, fixture_meta)
    except CampaignAborted as exc:
        _save_plan(plan)
        _finish_dashboard()
        sys.exit(f"campaign aborted: {exc}")

    _finish_dashboard()
    print("Campaign run: all cells processed.")


def cmd_run(args: argparse.Namespace) -> None:
    _use_block(getattr(args, "block", None) or DEFAULT_BLOCK)
    _run_plan(PLAN_PATH)


# ---------------------------------------------------------------------------
# smoke — stratified pre-flight on a separate results root
# ---------------------------------------------------------------------------

def _use_results_root(root: Path, plan_name: str | None = None) -> None:
    """Point the whole write path at `root` instead of tests/results.

    This works because runner.runner._record_path and runner.runner._append_index
    resolve RESULTS_DIR / INDEX_PATH as globals of their own module at call
    time, not at import time -- so rebinding them here redirects every record,
    score and index line written afterwards. campaign's own copies (imported by
    value) are rebound too, plus PLAN_PATH, which is derived from RESULTS_DIR.

    Deliberately global, and used by both subcommands to keep three bodies of
    data apart. The smoke's runs are throwaway (SV decision, 2026-08-22) and must
    never reach MAIN's index, where the resume would count them as already done
    and where a later fix would leave runs produced by different code inside the
    dataset. MAIN in turn stays out of tests/results, which holds the pilot and
    the earlier fixture work -- see MAIN_RESULTS_DIR."""
    global RESULTS_DIR, INDEX_PATH, PLAN_PATH
    runner_mod.RESULTS_DIR = root
    runner_mod.INDEX_PATH = root / "index.jsonl"
    RESULTS_DIR = root
    INDEX_PATH = root / "index.jsonl"
    PLAN_PATH = root / (plan_name or PLAN_PATH.name)


def _rel(path: Path) -> str:
    """Repo-relative for the log line, absolute when it is not under the repo
    (a test pointing the smoke root at a tmp dir, typically)."""
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def build_smoke_plan(cells: list[dict], input_ids: list[str],
                     seed: int = SMOKE_SEED,
                     renderings: tuple[str, ...] | None = None,
                     strata: dict[str, list[str]] | None = None) -> list[dict]:
    """Stratified sample: every (mode, rendering) combination gets its own draw,
    so no combination is left uncovered by chance.

    Not a plain random sample: the pilot covered exactly one combination
    -- a single queue at L1 -- so stratifying is what makes the smoke a proof that
    the chain holds everywhere rather than more runs of what already worked.

    Two stratifications, one per block, chosen by whether `strata` is given:

      without it, the combination is the only stratum and SMOKE_RUNS_PER_COMBO
          (queue, rep) pairs are drawn uniformly inside it -- MAIN's shape: 6
          modes x 2 prose renderings x 3 = 36 rows;

      with it, the combination is subdivided again by the caller's labels and
          each gets SMOKE_RUNS_PER_STRATUM draws, so every label meets every mode
          and every rendering. routing passes its five actions: 6 x 7 x 5 = 210
          rows, and the two UNASSIGNED requests are reached by construction
          instead of with probability 0.28. See _routing_action_strata.

    Labels are walked in sorted order and each stratum draws from its own rng
    stream position, so the plan is a function of the seed either way.

    `renderings` defaults to SMOKE_RENDERINGS. Each block names its own; see
    BLOCKS."""
    rng = random.Random(seed)

    def _pairs(ids):
        return [(i, rep) for i in ids for rep in range(1, REPS_PER_RENDERING + 1)]

    uniform_pairs = _pairs(input_ids)
    stratified = ({label: _pairs(ids) for label, ids in sorted(strata.items())}
                  if strata else None)

    rows = []
    for cell in cells:
        for mode in cell["modes"]:
            for rendering in renderings or SMOKE_RENDERINGS:
                if stratified is None:
                    drawn = sorted(rng.sample(uniform_pairs, SMOKE_RUNS_PER_COMBO))
                else:
                    drawn = []
                    for pairs in stratified.values():
                        drawn.extend(rng.sample(pairs, min(SMOKE_RUNS_PER_STRATUM,
                                                           len(pairs))))
                    drawn.sort()
                for input_id, rep in drawn:
                    rows.append({
                        "cell": cell["cell"], "mode": mode,
                        "rendering": rendering, "input": input_id,
                        "rep": rep, "status": "pending",
                    })
    return rows


def cmd_smoke(args: argparse.Namespace) -> None:
    if args.clean:
        if SMOKE_RESULTS_DIR.exists():
            shutil.rmtree(SMOKE_RESULTS_DIR, ignore_errors=True)
            print(f"Smoke: removed {_rel(SMOKE_RESULTS_DIR)}")
        else:
            print(f"Smoke: {_rel(SMOKE_RESULTS_DIR)} does not exist -- nothing to remove")
        return

    # Order matters and is not incidental: _use_block points the results root at
    # MAIN's, which is right for `run` and wrong for every smoke. Selecting the
    # block first and redirecting after is what keeps a smoke's throwaway runs out
    # of MAIN's index while still letting it run the block's fixture -- before
    # blocks reached the smoke, FIXTURE_ID kept its module default here and a
    # routing smoke would have run support-intake.
    block = _use_block(getattr(args, "block", None) or DEFAULT_BLOCK)
    _use_results_root(SMOKE_RESULTS_DIR, block["smoke_plan_name"])

    if args.plan:
        make_strata = block["smoke_strata"]
        rows = build_smoke_plan(_block_cells(), block["inputs"](),
                                renderings=block["smoke_renderings"],
                                strata=make_strata() if make_strata else None)
        _save_plan(rows)
        combos = {(r["mode"], r["rendering"]) for r in rows}
        print(f"Smoke plan: {len(rows)} rows over {len(combos)} (mode, rendering) combinations "
              f"-> {_rel(PLAN_PATH)}")
        return

    # args.run
    if SMOKE_RESULTS_DIR not in INDEX_PATH.parents:
        sys.exit(f"smoke refuses to run: index would be written to {INDEX_PATH}, "
                 f"outside {SMOKE_RESULTS_DIR}. Smoke runs are throwaway and must "
                 f"never reach MAIN's index.")
    print(f"Smoke: results root {_rel(SMOKE_RESULTS_DIR)} "
          f"(throwaway -- discard with 'campaign.py smoke --clean' before MAIN)")
    _run_plan(PLAN_PATH)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

BLOCK_HELP = ("which block to plan/run: 'main' is the batched support-intake campaign, 'routing' the per-item support-routing one, 'routing-notrace-{haiku,sonnet,opus}' the same untracked fixture through 'claude -p --model <hosted id>' instead of a local llama-server -- one block per rung of the hosted ladder. They share the results root and the index and keep separate plan files.")


def main(argv=None) -> None:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = p.add_subparsers(dest="command", required=True)
    p_plan = sub.add_parser("plan", help="Generate/regenerate the campaign plan")
    p_plan.add_argument("--block", choices=sorted(BLOCKS), default=DEFAULT_BLOCK,
                        help=BLOCK_HELP)
    p_plan.add_argument("--force", action="store_true",
                        help="rebuild even when the existing plan has rows that "
                             "already ran -- every one of them goes back to pending")
    run_p = sub.add_parser("run", help="Execute pending rows, cell by cell, resumable")
    run_p.add_argument("--block", choices=sorted(BLOCKS), default=DEFAULT_BLOCK,
                       help=BLOCK_HELP)
    run_p.add_argument("--no-dashboard", action="store_true",
                       help="Do not rebuild dashboard.html after every row")
    smoke = sub.add_parser(
        "smoke", help="Stratified pre-flight on tests/results-smoke/ (throwaway runs)")
    smoke.add_argument("--block", choices=sorted(BLOCKS), default=DEFAULT_BLOCK,
                       help=BLOCK_HELP + " Each block's smoke keeps its own plan "
                            "file inside the throwaway root and covers the "
                            "renderings it has reason to cover.")
    smoke.add_argument("--no-dashboard", action="store_true",
                       help="Do not rebuild dashboard.html between queue groups")
    what = smoke.add_mutually_exclusive_group(required=True)
    what.add_argument("--plan", action="store_true",
                      help="Sample the stratified plan (90 rows) and write it")
    what.add_argument("--run", action="store_true",
                      help="Execute the smoke plan, cell by cell, resumable")
    what.add_argument("--clean", action="store_true",
                      help="Discard tests/results-smoke/ entirely")
    args = p.parse_args(argv)

    global _dashboard_enabled
    _dashboard_enabled = not getattr(args, "no_dashboard", False)

    if args.command == "plan":
        cmd_plan(args)
    elif args.command == "smoke":
        cmd_smoke(args)
    else:
        cmd_run(args)


if __name__ == "__main__":
    main()
