#!/usr/bin/env python3
"""
SOL headless executor — runs a fixture case N times via `claude -p`.

Each run:
  1. Stage the input to a temp file
  2. Build a prompt that presents the SOL doc and the staged path
  3. Invoke `claude -p <prompt> --output-format json`
  4. Parse trace lines + JSON payload from the response
  5. Score via checker; save RunRecord + ScoreRecord; append to index.jsonl

Context emulation (--context flag):
  E0  — no tools (--tools ""); file content pre-injected into the prompt
  E1  — Bash only (--tools "Bash"); agent runs `cat` itself  [default]

Usage:
    python3 tests/runner/executor.py \\
        --fixture w2-branching/release-gate \\
        --input i1-blocked \\
        --context E1 \\
        --model claude-opus-4-8 \\
        --runs 3

    python3 tests/runner/executor.py \\
        --fixture w2-branching/release-gate \\
        --all-inputs \\
        --context E1 \\
        --model claude-opus-4-8 \\
        --runs 1
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "tests"))

from runner.schema import Config, Execution, Output, RunRecord, Trace, Usage
from runner.checker import check
from runner.runner import (
    FIXTURES_DIR, RESULTS_DIR,
    InputBundle,
    _load_fixture, _load_input, _stage,
    _record_path, _score_path, _append_index,
    _parse_trace, _extract_payload,
    L1_INSTRUCTION,
)

DEFAULT_TIMEOUT_S = 120


# ---------------------------------------------------------------------------
# Input discovery
# ---------------------------------------------------------------------------

def _list_inputs(fixture_dir: Path) -> list[str]:
    inputs_dir = fixture_dir / "inputs"
    ids = {p.stem for p in inputs_dir.glob("*.json")}
    ids |= {p.name for p in inputs_dir.iterdir() if p.is_dir()}
    return sorted(ids)


# ---------------------------------------------------------------------------
# Prompt builders
# ---------------------------------------------------------------------------

def _build_prompt_e0(sol_doc: dict, bundle: InputBundle, fixture_body: str) -> str:
    """E0: no tools — file content injected into the markdown fixture template.

    This runner has no --level flag, so it builds the documented default of the
    collateral-context scale: L1, i.e. the fixture body (input data + the SOL
    script) plus the minimal instruction. See api_executor._build_prompt_e0.
    """
    body = fixture_body
    if bundle.mode == "single":
        fc = json.dumps(bundle.payload, indent=2, ensure_ascii=False)
        body = body.replace("{{file_content}}", fc)
    else:
        for stem, text in bundle.files.items():
            body = body.replace("{{" + stem + "}}", text)
    return body + "\n\n" + L1_INSTRUCTION


def _build_prompt_e1(sol_doc: dict, staged_path: Path) -> str:
    sol_text = json.dumps(sol_doc, ensure_ascii=False)
    return (
        f"SOL. record_path={staged_path}\n"
        f"{sol_text}\n"
        "TODO→verbatim. end: RETURN json. no markdown."
    )


# ---------------------------------------------------------------------------
# Claude invocation
# ---------------------------------------------------------------------------

def _build_cmd(
    model: str, context: str, sandbox: Path,
    reasoning_budget: int = 0,
) -> list[str]:
    """The command, without the prompt: it goes on stdin (see _invoke).

    Windows caps a command line at 32,767 characters and raises
    ERROR_FILENAME_EXCED_RANGE past it, which Python surfaces as
    FileNotFoundError -- indistinguishable from a missing executable. This runner
    only ever built L1 prompts and stayed under the cap by luck; campaign.py's
    L3/L4 prompts (38k and 45k characters on the routing fixture) do not, and hit
    it on 2026-08-31. Passing the prompt on stdin removes the ceiling for both.
    """
    cmd = [
        "claude", "-p",
        "--output-format", "json",
        "--model", model,
        "--add-dir", str(sandbox),
    ]
    if context == "E0":
        # No tools: agent reasons from the pre-injected file content.
        cmd += ["--tools", ""]
    else:
        # E1: Bash restricted to `cat` — enough to execute RUN steps.
        cmd += ["--tools", "Bash", "--allowed-tools", "Bash(cat *)"]
    if reasoning_budget > 0:
        # There is no --thinking flag on the claude CLI (checked against
        # `claude --help`, 2026-08-31), so this branch used to build a command
        # the CLI rejects with "unknown option" -- a non-zero exit that the
        # caller files as an execution error of the model. A mode that asks this
        # runner for a thinking budget is misconfigured, and says so here rather
        # than turning into a column of red runs.
        sys.exit(
            f"reasoning_budget={reasoning_budget} was asked of the claude-code runner, "
            f"which has no way to set one: the CLI exposes no thinking-budget flag. "
            f"Set 'reasoning': 0 on the mode, or run it through the api runner."
        )
    return cmd


def _invoke(
    sol_doc: dict,
    bundle: InputBundle,
    staged_path: Path,
    sandbox: Path,
    model: str,
    context: str,
    timeout_s: int,
    reasoning_budget: int = 0,
    fixture_meta: dict | None = None,
) -> tuple[str, str, list[str], object | None, dict]:
    """
    Returns (status, raw_text, trace_steps, payload, extras).
    status: 'done' | 'error'
    extras: dict with optional 'cost' and 'duration_ms' from claude JSON output.
    """
    fixture_body = (fixture_meta or {}).get("body", "")
    if context == "E0":
        prompt = _build_prompt_e0(sol_doc, bundle, fixture_body)
    else:
        prompt = _build_prompt_e1(sol_doc, staged_path)

    cmd = _build_cmd(model, context, sandbox, reasoning_budget=reasoning_budget)

    try:
        result = subprocess.run(
            cmd,
            input=prompt,
            capture_output=True,
            text=True,
            timeout=timeout_s,
            cwd=str(Path(os.environ.get("TEMP", os.environ.get("TMP", str(Path.home())))).resolve()),
        )
    except subprocess.TimeoutExpired:
        return "timeout", f"[timeout after {timeout_s}s]", [], None, {}
    except FileNotFoundError:
        sys.exit("'claude' CLI not found — is Claude Code installed and on PATH?")

    if result.returncode != 0:
        err = result.stderr.strip() or result.stdout.strip() or "non-zero exit"
        return "error", err, [], None, {}

    try:
        out = json.loads(result.stdout)
    except json.JSONDecodeError:
        raw_text = result.stdout.strip()
        return "done", raw_text, _parse_trace(raw_text), _extract_payload(raw_text), {}

    raw_text = out.get("result") or ""

    model_usage = out.get("modelUsage") or {}
    tokens_in = sum(m.get("inputTokens", 0) for m in model_usage.values()) or None
    tokens_out = sum(m.get("outputTokens", 0) for m in model_usage.values()) or None
    cost = out.get("cost_usd") or out.get("total_cost_usd")

    extras = {
        "cost": cost,
        "duration_ms": out.get("duration_ms"),
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
    }
    return "done", raw_text, _parse_trace(raw_text), _extract_payload(raw_text), extras


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def _inputs_without_expectation(expectations: dict, input_ids: list[str]) -> list[str]:
    """Input ids that have no matching case in expectations.json.

    Mirrors the checker's _find_case matching. An input with no case is scored
    against expected_verdict=None, so ANY returned verdict reads as wrong-value
    — a silently misleading result. The executor surfaces this up front.
    """
    cased = set()
    for c in expectations.get("cases", []):
        raw = c.get("input", "")
        cased.add(raw.removeprefix("inputs/").removesuffix(".json"))
    return [iid for iid in input_ids if iid not in cased]


def run_headless(
    fixture_id: str,
    input_ids: list[str],
    context: str,
    model_id: str,
    runs: int,
    timeout_s: int,
    dry_run: bool = False,
    reasoning_budget: int = 0,
) -> None:
    fixture_dir, sol_doc, expectations, fixture_meta = _load_fixture(fixture_id)
    total = len(input_ids) * runs

    missing = _inputs_without_expectation(expectations, input_ids)
    if missing:
        print()
        print("!" * 70)
        print("  WARNING — inputs with NO case in expectations.json:")
        for iid in missing:
            print(f"    - {iid}")
        print()
        print("  These run fine, but the checker compares the returned verdict")
        print("  against None, so quality will read as 'wrong-value' no matter")
        print("  what the model actually returns. Add a case with the expected")
        print("  verdict to expectations.json BEFORE trusting the score.")
        print("!" * 70)

    print()
    print("=" * 70)
    print("  SOL Headless Executor" + ("  [DRY RUN — results not saved]" if dry_run else ""))
    print("=" * 70)
    print(f"  Fixture  : {fixture_id}")
    print(f"  Inputs   : {', '.join(input_ids)}")
    print(f"  Context  : {context}")
    print(f"  Model    : {model_id}")
    print(f"  Reasoning: {reasoning_budget} tokens" if reasoning_budget > 0 else "  Reasoning: off")
    print(f"  Runs     : {runs} × {len(input_ids)} input(s) = {total} total")
    print()
    print(f"  {'#':<5} {'Input':<35} {'Q':<6} {'F':<6} {'Time':<8} {'Tok':<8} Degrade")
    print("  " + "-" * 80)

    done_count = 0
    pass_q = 0
    pass_f = 0
    fid_eligible = 0

    for input_id in input_ids:
        bundle = _load_input(fixture_dir, input_id)

        for run_n in range(1, runs + 1):
            sandbox, staged = _stage(bundle)
            t0 = datetime.now(timezone.utc)

            try:
                status, raw, steps, payload, extras = _invoke(
                    sol_doc, bundle, staged, sandbox,
                    model_id, context, timeout_s,
                    reasoning_budget=reasoning_budget,
                    fixture_meta=fixture_meta,
                )
            finally:
                shutil.rmtree(sandbox, ignore_errors=True)

            elapsed_ms = extras.get("duration_ms") or int(
                (datetime.now(timezone.utc) - t0).total_seconds() * 1000
            )

            ts = datetime.now(timezone.utc)
            run_id = (
                f"{fixture_id.replace('/', '-')}-{input_id}-"
                f"{ts.strftime('%Y%m%dT%H%M%S')}-r{run_n:02d}"
            )

            config = Config(
                fixture_id=fixture_id,
                context=context,
                model_id=model_id,
                env_realization="native",
                reasoning_budget=reasoning_budget,
            )
            record = RunRecord(
                run_id=run_id,
                timestamp=ts.isoformat(),
                config=config,
                staged_input_id=input_id,
                execution=Execution(
                    status=status,
                    wall_clock_ms=elapsed_ms if status == "done" else None,
                ),
                trace=Trace(steps=steps),
                output=Output(
                    raw=raw,
                    returned_payload=payload if status == "done" else None,
                ),
                usage=Usage(
                    tokens_in=extras.get("tokens_in"),
                    tokens_out=extras.get("tokens_out"),
                    cost=extras.get("cost"),
                ),
            )

            score = check(record, expectations)

            if not dry_run:
                rec_path = _record_path(config, run_id)
                record.save(rec_path)
                score.save(_score_path(rec_path))
                _append_index(record, score)

            q_sym = {"pass": "✓", "fail": "✗"}.get(score.quality.result, "–")
            f_sym = {"pass": "✓", "fail": "✗"}.get(score.fidelity.result, "–")
            done_count += 1

            if score.quality.result == "pass":
                pass_q += 1
            if score.fidelity.result == "pass":
                pass_f += 1
            if score.fidelity.result != "not_checkable":
                fid_eligible += 1

            label = f"{input_id} #{run_n}"
            ms = score.efficiency.wall_clock_ms
            time_str = f"{ms/1000:.1f}s" if ms and ms >= 1000 else (f"{ms}ms" if ms else "—")
            tok_in = extras.get("tokens_in") or 0
            tok_out = extras.get("tokens_out") or 0
            tok_str = str(tok_in + tok_out) if (tok_in or tok_out) else "—"
            print(f"  {done_count:<5} {label:<35} {q_sym:<6} {f_sym:<6} {time_str:<8} {tok_str:<8} {score.degradation_mode}")

    print("  " + "-" * 80)
    pct_q = 100 * pass_q // total if total else 0
    pct_f = 100 * pass_f // fid_eligible if fid_eligible else 0
    print(f"  Quality  : {pass_q}/{total} pass ({pct_q}%)")
    fid_label = f"{pass_f}/{fid_eligible}" if fid_eligible else "n/a"
    print(f"  Fidelity : {fid_label} pass ({pct_f}%)"
          + ("" if fid_eligible else "  [no trace emitted]"))
    if dry_run:
        print(f"  (dry run — nothing written to disk)")
    else:
        print(f"  Index    : {(RESULTS_DIR / 'index.jsonl').relative_to(REPO_ROOT)}")
        _regen_dashboard()
    print()


def _regen_dashboard() -> None:
    dashboard_script = REPO_ROOT / "scripts" / "dashboard.py"
    if not dashboard_script.exists():
        return
    try:
        result = subprocess.run(
            [sys.executable, str(dashboard_script)],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode == 0:
            print(f"  Dashboard: tests/results/dashboard.html  (regenerated)")
        else:
            print(f"  Dashboard: regeneration failed — {result.stderr.strip()[:120]}")
    except Exception as exc:
        print(f"  Dashboard: regeneration skipped ({exc})")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv=None) -> None:
    p = argparse.ArgumentParser(
        description="SOL headless executor",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--fixture", required=True,
                   help="Fixture ID, e.g. w2-branching/release-gate")

    grp = p.add_mutually_exclusive_group(required=True)
    grp.add_argument("--input",
                     help="Input ID, e.g. i1-blocked")
    grp.add_argument("--all-inputs", action="store_true",
                     help="Run all inputs in the fixture's inputs/ directory")

    p.add_argument("--context", default="E1",
                   choices=["E0", "E1"],
                   help="Execution context: E0 (no tools) | E1 (Bash) [default: E1]")
    p.add_argument("--model", default="claude-opus-4-8",
                   help="Model ID [default: claude-opus-4-8]")
    p.add_argument("--runs", type=int, default=1,
                   help="Number of runs per input [default: 1]")
    p.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT_S,
                   help=f"Timeout per run in seconds [default: {DEFAULT_TIMEOUT_S}]")
    p.add_argument("--dry-run", action="store_true",
                   help="Execute and score but do not write any files (probe/debug mode)")
    args = p.parse_args(argv)

    fixture_dir = FIXTURES_DIR / args.fixture
    if not fixture_dir.is_dir():
        sys.exit(f"Fixture not found: {fixture_dir}")

    if args.all_inputs:
        input_ids = _list_inputs(fixture_dir)
        if not input_ids:
            sys.exit(f"No inputs found in {fixture_dir / 'inputs'}")
    else:
        input_ids = [args.input]

    run_headless(
        fixture_id=args.fixture,
        input_ids=input_ids,
        context=args.context,
        model_id=args.model,
        runs=args.runs,
        timeout_s=args.timeout,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
