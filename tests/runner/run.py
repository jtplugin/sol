#!/usr/bin/env python3
"""
SOL unified runner — single entry point for all test execution modes.

Reads tests/env.json to determine how to run: if the mode's runner_type is
"api", delegates to api_executor; if "claude-code", delegates to executor
(claude -p CLI).

Usage:
    python3 tests/runner/run.py \\
        --fixture w2-branching/release-gate \\
        --all-inputs \\
        --context E0 \\
        --mode claude-api \\
        --runs 3

    python3 tests/runner/run.py \\
        --fixture w1-linear/log-classifier \\
        --input i1-info \\
        --context E1 \\
        --mode claude-code-local \\
        --dry-run

The --mode field must exist in tests/env.json and must have a runner_type field
("api" | "claude-code").
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
ENV_PATH  = REPO_ROOT / "tests" / "env.json"
sys.path.insert(0, str(REPO_ROOT / "tests"))

# Force UTF-8 stdout/stderr on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from runner.runner import FIXTURES_DIR
from runner.api_executor import run_headless_api, _list_inputs as _list_inputs_api, DEFAULT_TIMEOUT_S as API_TIMEOUT
from runner.executor import run_headless, _list_inputs as _list_inputs_cli, DEFAULT_TIMEOUT_S as CLI_TIMEOUT


def _load_env_entry(mode: str) -> dict:
    if not ENV_PATH.exists():
        sys.exit(f"env.json not found at {ENV_PATH}")
    try:
        env = json.loads(ENV_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        sys.exit(f"env.json is not valid JSON: {exc}")
    for entry in env.get("modes", []):
        if entry.get("mode") == mode:
            return entry
    known = [e.get("mode") for e in env.get("modes", [])]
    sys.exit(f"Mode '{mode}' not found in env.json. Available: {known}")


def main(argv=None) -> None:
    p = argparse.ArgumentParser(
        description="SOL unified runner — dispatches to api or claude-code executor based on env.json",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--fixture", required=True,
                   help="Fixture ID, e.g. w2-branching/release-gate")

    grp = p.add_mutually_exclusive_group(required=True)
    grp.add_argument("--input",
                     help="Input ID, e.g. i1-blocked")
    grp.add_argument("--all-inputs", action="store_true",
                     help="Run all inputs in the fixture's inputs/ directory")

    p.add_argument("--context", default="E0",
                   choices=["E0", "E1"],
                   help="Execution context: E0 (no tools) | E1 (Bash/cat) [default: E0]")
    p.add_argument("--mode", required=True,
                   help="Mode name from tests/env.json (determines runner_type, model, credentials)")
    p.add_argument("--model", default=None,
                   help="Model ID override [default: from env.json mode]")
    p.add_argument("--runs", type=int, default=1,
                   help="Number of runs per input [default: 1]")
    p.add_argument("--timeout", type=int, default=None,
                   help="Timeout per run in seconds [default: 600 for api, 120 for claude-code]")
    p.add_argument("--dry-run", action="store_true",
                   help="Execute and score but do not write any files")
    p.add_argument("--reasoning", type=int, default=None,
                   help="Extended thinking budget in tokens (0=off) [default: from env.json]")
    p.add_argument("--temperature", type=float, default=None,
                   help="Sampling temperature (api runner_type only) [default: from env.json]")
    p.add_argument("--level", default="L1", choices=["L0", "L1", "L2", "L3", "L4"],
                   help="Predictability-layer scale (api runner_type only) [default: L1]")
    args = p.parse_args(argv)

    entry = _load_env_entry(args.mode)
    runner_type = entry.get("runner_type")
    if runner_type not in ("api", "claude-code"):
        sys.exit(
            f"Mode '{args.mode}' has runner_type={runner_type!r}. "
            f"Must be 'api' or 'claude-code'."
        )

    model_id = args.model or entry.get("model", "claude-opus-4-8")
    reasoning_budget = args.reasoning if args.reasoning is not None else int(entry.get("reasoning", 0))
    env_temperature = entry.get("temperature")
    env_temperature = float(env_temperature) if env_temperature is not None else None
    temperature = args.temperature if args.temperature is not None else env_temperature

    fixture_dir = FIXTURES_DIR / args.fixture
    if not fixture_dir.is_dir():
        sys.exit(f"Fixture not found: {fixture_dir}")

    if args.all_inputs:
        input_ids = _list_inputs_api(fixture_dir)
        if not input_ids:
            sys.exit(f"No inputs found in {fixture_dir / 'inputs'}")
    else:
        input_ids = [args.input]

    if runner_type == "api":
        backend = entry.get("backend", "anthropic")
        api_key = entry.get("key", "") or os.environ.get("ANTHROPIC_API_KEY", "")
        api_url = entry.get("url", "https://api.anthropic.com")
        if not api_key and backend not in ("ollama", "openai"):
            sys.exit(
                f"Mode '{args.mode}' has no key. Set 'key' in env.json or ANTHROPIC_API_KEY env var."
            )
        run_headless_api(
            fixture_id=args.fixture,
            input_ids=input_ids,
            context=args.context,
            model_id=model_id,
            runs=args.runs,
            timeout_s=args.timeout or API_TIMEOUT,
            api_key=api_key,
            api_url=api_url,
            backend=backend,
            dry_run=args.dry_run,
            reasoning_budget=reasoning_budget,
            temperature=temperature,
            level=args.level,
        )
    else:
        run_headless(
            fixture_id=args.fixture,
            input_ids=input_ids,
            context=args.context,
            model_id=model_id,
            runs=args.runs,
            timeout_s=args.timeout or CLI_TIMEOUT,
            dry_run=args.dry_run,
            reasoning_budget=reasoning_budget,
        )


if __name__ == "__main__":
    main()
