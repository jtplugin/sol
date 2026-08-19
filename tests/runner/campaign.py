#!/usr/bin/env python3
"""
campaign.py -- resumable driver for MAIN's cell x mode x level x queue x rep
matrix. Two subcommands:

  plan  Enumerate the complete worst-case coordinate space (every cell x mode
        x L0..L4 x 10 queues x 3 reps) from tests/campaign-cells.json and
        tests/fixtures/w2-branching/support-intake/queues-manifest.json, and
        write tests/results/campaign-plan.json (gitignored, overwritten every
        time this runs -- never append).

  run   Execute pending rows, one cell at a time: start llama-server for the
        cell, run an acceptance probe, then walk each (mode, queue) pair up
        the level ladder adaptively, checkpointing campaign-plan.json after
        EVERY single run so an interruption never loses more than the run in
        flight.

`campaign.py run` is meant to be launched OUTSIDE the pipeline session --
`python tests/runner/campaign.py run` in its own terminal, potentially for
hours. There is no dedicated resume flag: relaunching the same command IS the
resume. At startup it loads the existing campaign-plan.json (does not
regenerate it) and reconciles any row still "pending" against
tests/results/index.jsonl -- a row whose exact coordinates already have a
"done" entry in the index is marked done without rerunning. Supervise a live
campaign by reading campaign-plan.json / index.jsonl; do not keep an
interactive agent session open for the campaign's duration (see doc/experiment-minimum-context.md).

Server lifecycle is Windows-specific (llama-server.exe under LLAMA_DIR,
taskkill). Set LLAMA_DIR below to the directory that holds llama-server.exe
and its ai-models/ folder before running a campaign.

Usage:
    python3 tests/runner/campaign.py plan
    python3 tests/runner/campaign.py run
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
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

from runner.schema import Config, Execution, Output, RunRecord, Trace, Usage
from runner.checker import check
from runner.runner import (
    FIXTURES_DIR, RESULTS_DIR, INDEX_PATH,
    _load_fixture, _load_input, _stage,
    _record_path, _score_path, _append_index,
    assert_queue_alignment,
)
from runner.api_executor import _invoke_api, _layers_for_level, _load_mode, DEFAULT_TIMEOUT_S

CELLS_PATH = REPO_ROOT / "tests" / "campaign-cells.json"
PLAN_PATH = RESULTS_DIR / "campaign-plan.json"
SUPPORT_INTAKE_FIXTURE_ID = "w2-branching/support-intake"
QUEUES_MANIFEST_PATH = FIXTURES_DIR / "w2-branching" / "support-intake" / "queues-manifest.json"

LEVELS = ["L0", "L1", "L2", "L3", "L4"]
REPS_PER_LEVEL = 3
ACCEPTABILITY_THRESHOLD = 0.90  # FR-22, frozen 2026-08-17 (see doc/experiment-minimum-context.md SS8.1)
SPEC_VERSION = "0.6"  # matches runner.schema.Config.spec_version's default -- used for index matching

LLAMA_DIR = Path(r"\your\llama\path")
SERVER_HOST = "127.0.0.1"
SERVER_PORT = 8090
SERVER_URL = f"http://{SERVER_HOST}:{SERVER_PORT}"
SERVER_STARTUP_TIMEOUT_S = 300
VRAM_RELEASE_TIMEOUT_S = 60
ACCEPTANCE_MAX_TOKENS = 16
PREFILL_TPS_THRESHOLD = 1000  # FR-17: sole binding acceptance criterion


# ---------------------------------------------------------------------------
# plan
# ---------------------------------------------------------------------------

def _load_cells() -> list[dict]:
    return json.loads(CELLS_PATH.read_text(encoding="utf-8"))


def _load_queue_ids() -> list[str]:
    manifest = json.loads(QUEUES_MANIFEST_PATH.read_text(encoding="utf-8"))
    return [q["queue_id"] for q in manifest["queues"]]


def build_plan(cells: list[dict], queue_ids: list[str]) -> list[dict]:
    """FR-12: enumerate the complete coordinate space before any GPU spend."""
    rows = []
    for cell in cells:
        for mode in cell["modes"]:
            for level in LEVELS:
                for queue_id in queue_ids:
                    for rep in range(1, REPS_PER_LEVEL + 1):
                        rows.append({
                            "cell": cell["cell"], "mode": mode, "level": level,
                            "queue": queue_id, "rep": rep, "status": "pending",
                        })
    return rows


def _save_plan(plan: list[dict]) -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    PLAN_PATH.write_text(json.dumps(plan, indent=2, ensure_ascii=False), encoding="utf-8")


def cmd_plan(_args: argparse.Namespace) -> None:
    rows = build_plan(_load_cells(), _load_queue_ids())
    _save_plan(rows)
    print(f"Plan: {len(rows)} rows -> {PLAN_PATH.relative_to(REPO_ROOT)}")


# ---------------------------------------------------------------------------
# mode config (tests/env.json, cached per mode name)
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
    The match tuple (FR-14/FR-07) has no per-rep component, so a level's
    N done index entries satisfy the first N pending plan rows (by rep
    order) at that same (cell, mode, level, queue) coordinate."""
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
            row.get("reasoning_budget"), tuple(row.get("predictability_layers") or []),
        )
        counts[key] = counts.get(key, 0) + 1
    return counts


def _reconcile_with_index(plan: list[dict]) -> None:
    counts = _index_done_counts()
    groups: dict[tuple, list[dict]] = {}
    for row in plan:
        if row["status"] != "pending":
            continue
        key = (row["cell"], row["mode"], row["level"], row["queue"])
        groups.setdefault(key, []).append(row)

    for (_cell, mode, level, queue_id), rows in groups.items():
        mode_cfg = _mode_config(mode)
        index_key = (
            SUPPORT_INTAKE_FIXTURE_ID, queue_id, "E0", mode_cfg["model"],
            SPEC_VERSION, mode_cfg["backend"], mode_cfg["reasoning_budget"],
            tuple(_layers_for_level(level)),
        )
        available = counts.get(index_key, 0)
        rows.sort(key=lambda r: r["rep"])
        for row in rows[:available]:
            row["status"] = "done"


# ---------------------------------------------------------------------------
# llama-server lifecycle (Windows) — ported from proto/cella.py, proto/vramprobe.py
# ---------------------------------------------------------------------------

def _start_server(cell: dict) -> subprocess.Popen:
    log = LLAMA_DIR / f"campaign-{cell['cell']}.log"
    err = LLAMA_DIR / f"campaign-{cell['cell']}.err"
    return subprocess.Popen(
        [str(LLAMA_DIR / "llama-server.exe"), "-m", "ai-models\\" + cell["gguf"],
         "--ctx-size", str(cell["ctx_size"]), "--n-gpu-layers", "999",
         "-np", str(cell["n_parallel"]),
         "--cache-type-k", cell["kv_cache_type"], "--cache-type-v", cell["kv_cache_type"],
         "--host", SERVER_HOST, "--port", str(SERVER_PORT)],
        cwd=str(LLAMA_DIR),
        stdout=open(log, "w"), stderr=open(err, "w"),
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


def _acceptance_check(fixture_meta: dict) -> bool:
    """FR-17: prompt_per_second > 1000 on a short prefill probe is the ONLY
    binding criterion. VRAM is read and logged, never blocking."""
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
            {"role": "user", "content": "Reply with the single word: ready."},
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

    tps = (out.get("timings") or {}).get("prompt_per_second")
    print(f"  acceptance probe: prompt_per_second={tps}")
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

def _execute_row(row: dict, cell: dict, mode: str, level: str, queue_id: str,
                 fixture_dir: Path, sol_doc: dict, expectations: dict, fixture_meta: dict):
    """Runs exactly one (cell, mode, level, queue, rep) coordinate through the
    same invoke -> score -> save -> index pipeline as api_executor.run_headless_api,
    but exposes the ScoreRecord so the adaptive ladder (FR-16) can read
    conditional_rate right away. Mutates row['status'] and returns the
    ScoreRecord, or None on a non-'done' execution status."""
    mode_cfg = _mode_config(mode)
    bundle = _load_input(fixture_dir, queue_id)
    sandbox, staged = _stage(bundle)
    t0 = datetime.now(timezone.utc)
    try:
        status, raw, steps, payload, extras = _invoke_api(
            sol_doc, bundle, staged, sandbox,
            mode_cfg["model"], "E0", mode_cfg["key"], mode_cfg["url"], DEFAULT_TIMEOUT_S,
            mode_cfg["backend"],
            reasoning_budget=mode_cfg["reasoning_budget"],
            fixture_meta=fixture_meta,
            temperature=mode_cfg["temperature"],
            thinking=mode_cfg["thinking"],
            level=level,
        )
    finally:
        shutil.rmtree(sandbox, ignore_errors=True)
    elapsed_ms = int((datetime.now(timezone.utc) - t0).total_seconds() * 1000)

    ts = datetime.now(timezone.utc)
    run_id = (
        f"{SUPPORT_INTAKE_FIXTURE_ID.replace('/', '-')}-{queue_id}-"
        f"{ts.strftime('%Y%m%dT%H%M%S')}-{cell['cell']}-{mode}-{level}-rep{row['rep']:02d}"
    )
    config = Config(
        fixture_id=SUPPORT_INTAKE_FIXTURE_ID,
        context="E0",
        model_id=mode_cfg["model"],
        spec_version=SPEC_VERSION,
        env_realization="emulated",
        predictability_layers=_layers_for_level(level),
        runner_type="api",
        api_base_url=mode_cfg["url"],
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
        staged_input_id=queue_id,
        execution=Execution(status=status, wall_clock_ms=elapsed_ms if status == "done" else None),
        trace=Trace(steps=steps, request_messages=extras.get("request_messages", [])),
        output=Output(raw=raw, returned_payload=payload if status == "done" else None),
        usage=Usage(tokens_in=extras.get("tokens_in"), tokens_out=extras.get("tokens_out"), cost=None),
    )
    score = check(record, expectations)

    rec_path = _record_path(config, run_id)
    record.save(rec_path)
    score.save(_score_path(rec_path))
    _append_index(record, score)

    row["status"] = "done" if status == "done" else "error"
    print(f"  [{cell['cell']}/{mode}/{level}/{queue_id}#{row['rep']}] {row['status']} "
          f"quality={score.quality.result} fidelity={score.fidelity.result} "
          f"conditional_rate={score.fidelity.conditional_rate}")
    return score if status == "done" else None


# ---------------------------------------------------------------------------
# adaptive ladder (FR-16)
# ---------------------------------------------------------------------------

def _skip_higher_levels(plan: list[dict], cell_name: str, mode: str, queue_id: str, from_level: str) -> None:
    idx = LEVELS.index(from_level)
    for lvl in LEVELS[idx + 1:]:
        for row in plan:
            if (row["cell"] == cell_name and row["mode"] == mode
                    and row["queue"] == queue_id and row["level"] == lvl
                    and row["status"] == "pending"):
                row["status"] = "skipped-adaptive"
    _save_plan(plan)


def _run_ladder(cell: dict, mode: str, queue_id: str, plan: list[dict],
                fixture_dir: Path, sol_doc: dict, expectations: dict, fixture_meta: dict) -> None:
    for level in LEVELS:
        rows = sorted(
            (r for r in plan if r["cell"] == cell["cell"] and r["mode"] == mode
             and r["queue"] == queue_id and r["level"] == level),
            key=lambda r: r["rep"],
        )
        rates = []
        for row in rows:
            if row["status"] != "pending":
                continue
            score = _execute_row(row, cell, mode, level, queue_id,
                                 fixture_dir, sol_doc, expectations, fixture_meta)
            _save_plan(plan)
            if score is not None and score.fidelity.conditional_rate is not None:
                rates.append(score.fidelity.conditional_rate)
        if not rates:
            continue
        mean_rate = sum(rates) / len(rates)
        if mean_rate >= ACCEPTABILITY_THRESHOLD:
            _skip_higher_levels(plan, cell["cell"], mode, queue_id, level)
            return


# ---------------------------------------------------------------------------
# per-cell lifecycle (FR-15)
# ---------------------------------------------------------------------------

def _run_cell(cell: dict, plan: list[dict], fixture_dir: Path, sol_doc: dict,
             expectations: dict, fixture_meta: dict) -> None:
    cell_name = cell["cell"]
    pending = [r for r in plan if r["cell"] == cell_name and r["status"] == "pending"]
    if not pending:
        print(f"[{cell_name}] no pending rows -- skipping (server not started)")
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

        for mode in cell["modes"]:
            queue_ids = sorted({r["queue"] for r in plan
                                if r["cell"] == cell_name and r["mode"] == mode})
            for queue_id in queue_ids:
                _run_ladder(cell, mode, queue_id, plan, fixture_dir, sol_doc, expectations, fixture_meta)
    finally:
        print(f"[{cell_name}] stopping llama-server")
        _stop_server()


# ---------------------------------------------------------------------------
# run
# ---------------------------------------------------------------------------

def cmd_run(_args: argparse.Namespace) -> None:
    fixture_dir = FIXTURES_DIR / SUPPORT_INTAKE_FIXTURE_ID
    try:
        assert_queue_alignment(fixture_dir)
    except RuntimeError as exc:
        sys.exit(f"assert_queue_alignment failed -- aborting before any server or plan row: {exc}")

    if not PLAN_PATH.exists():
        sys.exit(f"{PLAN_PATH} not found -- run 'python tests/runner/campaign.py plan' first.")
    plan = json.loads(PLAN_PATH.read_text(encoding="utf-8"))

    _reconcile_with_index(plan)
    _save_plan(plan)

    _fixture_dir, sol_doc, expectations, fixture_meta = _load_fixture(SUPPORT_INTAKE_FIXTURE_ID)

    for cell in _load_cells():
        _run_cell(cell, plan, _fixture_dir, sol_doc, expectations, fixture_meta)

    print("Campaign run: all cells processed.")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv=None) -> None:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("plan", help="Generate/regenerate tests/results/campaign-plan.json")
    sub.add_parser("run", help="Execute pending rows, cell by cell, resumable")
    args = p.parse_args(argv)

    if args.command == "plan":
        cmd_plan(args)
    else:
        cmd_run(args)


if __name__ == "__main__":
    main()
