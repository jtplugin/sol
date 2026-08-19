#!/usr/bin/env python3
"""
One-shot backfill: reconstruct trace.request_messages for existing result JSONs.

For each run JSON where trace.request_messages is empty, this script:
  - loads the fixture sol_doc and staged input
  - rebuilds the initial messages list using the same prompt builder as api_executor.py
  - writes request_messages back into the JSON file

Only modifies api runner results (runner_type == "api"); skips claude-code runs
(those don't have a structured messages list to reconstruct).

Usage:
    python tests/scripts/backfill_request_messages.py [--dry-run]
"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "tests"))

from runner.runner import FIXTURES_DIR, RESULTS_DIR, _load_fixture, _load_input
from runner.api_executor import _build_prompt_e0, _build_prompt_e1


def backfill(dry_run: bool = False) -> None:
    result_files = sorted(RESULTS_DIR.rglob("*.json"))
    result_files = [f for f in result_files if not f.name.endswith(".score.json")]

    total = len(result_files)
    skipped_runner = 0
    skipped_already = 0
    skipped_error = 0
    updated = 0

    for path in result_files:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"  SKIP (read error): {path.name} — {e}")
            skipped_error += 1
            continue

        cfg = data.get("config", {})
        runner_type = cfg.get("runner_type", "")

        if runner_type != "api":
            skipped_runner += 1
            continue

        trace = data.get("trace", {})
        if trace.get("request_messages"):
            skipped_already += 1
            continue

        fixture_id    = cfg.get("fixture_id", "")
        input_id      = data.get("staged_input_id", "")
        context       = cfg.get("context", "E0")

        if not fixture_id or not input_id:
            print(f"  SKIP (missing ids): {path.name}")
            skipped_error += 1
            continue

        try:
            fixture_dir, sol_doc, _, fixture_meta = _load_fixture(fixture_id)
            input_data = _load_input(fixture_dir, input_id)
        except Exception as e:
            print(f"  SKIP (fixture load): {path.name} — {e}")
            skipped_error += 1
            continue

        fixture_body = (fixture_meta or {}).get("body", "")
        if context == "E0":
            prompt = _build_prompt_e0(sol_doc, input_data, fixture_body)
        else:
            # E1: staged_path not recoverable; use a placeholder that shows the structure
            prompt = _build_prompt_e1(sol_doc, Path(f"<staged/{input_id}>"))

        messages = [{"role": "user", "content": prompt}]
        data["trace"]["request_messages"] = messages

        if not dry_run:
            path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

        updated += 1
        print(f"  {'[DRY] ' if dry_run else ''}updated: {path.relative_to(REPO_ROOT)}")

    print()
    print(f"Total files : {total}")
    print(f"Updated     : {updated}")
    print(f"Already set : {skipped_already}")
    print(f"Non-api     : {skipped_runner}")
    print(f"Errors/skip : {skipped_error}")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Backfill trace.request_messages in result JSONs")
    p.add_argument("--dry-run", action="store_true", help="Print what would be changed, no writes")
    args = p.parse_args()
    backfill(dry_run=args.dry_run)
