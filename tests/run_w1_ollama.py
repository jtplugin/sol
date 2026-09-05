#!/usr/bin/env python3
"""
Batch runner: all w1-linear fixtures × all ollama modes × N runs.

Usage:
    python tests/run_w1_ollama.py            # 10 runs, E0, all ollama modes
    python tests/run_w1_ollama.py --runs 3
    python tests/run_w1_ollama.py --context E1
    python tests/run_w1_ollama.py --modes ollama-qwen3-small ollama-gemma
    python tests/run_w1_ollama.py --fixtures w1-linear/cart-total
    python tests/run_w1_ollama.py --dry-run
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
RUN_PY    = REPO_ROOT / "tests" / "runner" / "run.py"

OLLAMA_MODES = [
    "ollama-qwen3-small",
    "ollama-qwen3-mid",
    "ollama-qwen25-coder",
    "ollama-deepseek-coder",
    "ollama-mistral",
    "ollama-gemma",
]

W1_FIXTURES = [
    "w1-linear/cart-total",
    "w1-linear/cart-summary",
    "w1-linear/sales-summary",
]


def main() -> None:
    p = argparse.ArgumentParser(description="Batch w1 ollama runner")
    p.add_argument("--runs",    type=int, default=10)
    p.add_argument("--context", default="E0", choices=["E0", "E1"])
    p.add_argument("--modes",   nargs="+", default=OLLAMA_MODES,
                   metavar="MODE", help="Subset of ollama modes to run")
    p.add_argument("--fixtures", nargs="+", default=W1_FIXTURES,
                   metavar="FIXTURE", help="Subset of fixtures to run")
    p.add_argument("--dry-run", action="store_true",
                   help="Pass --dry-run to each executor (score but no files written)")
    args = p.parse_args()

    combos = [(m, f) for m in args.modes for f in args.fixtures]
    total  = len(combos)

    print()
    print("=" * 70)
    print("  SOL Batch Runner — w1-linear × ollama")
    print("=" * 70)
    print(f"  Modes    : {', '.join(args.modes)}")
    print(f"  Fixtures : {', '.join(args.fixtures)}")
    print(f"  Context  : {args.context}")
    print(f"  Runs/case: {args.runs}")
    print(f"  Combos   : {total}")
    if args.dry_run:
        print("  [DRY RUN — results not saved]")
    print()

    def _unload(url: str, model: str) -> None:
        """Force-evict model from Ollama memory (keep_alive=0). Best-effort."""
        payload = json.dumps({"model": model, "keep_alive": 0}).encode()
        req = urllib.request.Request(
            f"{url.rstrip('/')}/api/generate",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                resp.read()
        except Exception as exc:
            print(f"  [warn] unload request failed: {exc}")

    # Read ollama URL from modes.json for the first ollama mode found.
    import json as _json
    _modes = _json.loads((REPO_ROOT / "tests" / "modes.json").read_text(encoding="utf-8"))
    _mode_map = {e["mode"]: e for e in _modes.get("modes", [])}

    def _ollama_url(mode: str) -> str:
        return _mode_map.get(mode, {}).get("url", "http://localhost:11434")

    def _ollama_model(mode: str) -> str:
        return _mode_map.get(mode, {}).get("model", mode)

    prev_mode = None
    for i, (mode, fixture) in enumerate(combos, 1):
        if prev_mode is not None and mode != prev_mode:
            prev_model = _ollama_model(prev_mode)
            url = _ollama_url(prev_mode)
            print(f"  [model switch] unloading {prev_model} from {url}...", flush=True)
            _unload(url, prev_model)
            print("  [unload sent — proceeding immediately]")
        prev_mode = mode

        print(f"[{i}/{total}] {mode} × {fixture}")
        cmd = [
            sys.executable, str(RUN_PY),
            "--fixture", fixture,
            "--all-inputs",
            "--context", args.context,
            "--mode", mode,
            "--runs", str(args.runs),
        ]
        if args.dry_run:
            cmd.append("--dry-run")
        result = subprocess.run(cmd, cwd=str(REPO_ROOT))
        if result.returncode not in (0, 1):
            print(f"  [warn] exit {result.returncode} — continuing")

    print()
    print("=" * 70)
    print(f"  Done. {total} combos completed.")
    print("=" * 70)
    print()


if __name__ == "__main__":
    main()
