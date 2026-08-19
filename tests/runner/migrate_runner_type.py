#!/usr/bin/env python3
"""
Backfill runner_type and api_base_url into existing RunRecord files and index.jsonl.

All records produced before this migration were created by the `claude -p` session
runner, so they get runner_type="claude-code" and api_base_url=None.

Safe to run multiple times (idempotent).

Usage:
    python3 tests/runner/migrate_runner_type.py [--dry-run]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

REPO_ROOT   = Path(__file__).resolve().parents[2]
RESULTS_DIR = REPO_ROOT / "tests" / "results"
INDEX_PATH  = RESULTS_DIR / "index.jsonl"


def _migrate_run_records(dry_run: bool) -> int:
    updated = 0
    for p in sorted(RESULTS_DIR.rglob("*.json")):
        if p.name.endswith(".score.json"):
            continue
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        cfg = d.get("config")
        if not isinstance(cfg, dict):
            continue
        changed = False
        if "runner_type" not in cfg:
            cfg["runner_type"] = "claude-code"
            changed = True
        if "api_base_url" not in cfg:
            cfg["api_base_url"] = None
            changed = True
        if changed:
            updated += 1
            if not dry_run:
                p.write_text(json.dumps(d, indent=2, ensure_ascii=False), encoding="utf-8")
            else:
                print(f"  would update: {p.relative_to(REPO_ROOT)}")
    return updated


def _migrate_index(dry_run: bool) -> int:
    if not INDEX_PATH.exists():
        return 0
    rows = []
    updated = 0
    for line in INDEX_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            rows.append(line)
            continue
        changed = False
        if "runner_type" not in row:
            row["runner_type"] = "claude-code"
            changed = True
        if "api_base_url" not in row:
            row["api_base_url"] = None
            changed = True
        if changed:
            updated += 1
        rows.append(json.dumps(row, ensure_ascii=False))
    if updated and not dry_run:
        INDEX_PATH.write_text("\n".join(rows) + "\n", encoding="utf-8")
    return updated


def main() -> None:
    ap = argparse.ArgumentParser(description="Backfill runner_type into existing SOL test results")
    ap.add_argument("--dry-run", action="store_true", help="Show what would change without writing")
    args = ap.parse_args()

    if args.dry_run:
        print("DRY RUN — no files will be written\n")

    rec_updated = _migrate_run_records(args.dry_run)
    idx_updated = _migrate_index(args.dry_run)

    tag = "(would update)" if args.dry_run else "updated"
    print(f"Run records {tag}: {rec_updated}")
    print(f"Index rows  {tag}: {idx_updated}")


if __name__ == "__main__":
    main()
