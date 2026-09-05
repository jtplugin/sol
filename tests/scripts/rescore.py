#!/usr/bin/env python3
"""
Re-run the checker over records already on disk, without re-running inference.

A run record holds everything the checker reads -- the trace, the returned payload,
the config -- so a correction to `checker.py` can be applied to runs already made
instead of costing another pass on the GPU. This rewrites each `<run_id>.score.json`
from its `<run_id>.json`, leaving the record itself untouched.

Written for the 2026-08-23 comprehension correction, where 196 of MAIN's 485 runs
carried `comprehension.rate = 0.0` for having emitted no EVAL line at all -- the
absence of a measurement recorded where a result goes. Nothing about those runs
changed; what the oracle says about them did.

After this, run `backfill_index_scores.py` to carry the new values into the index:
this script does not touch index.jsonl, so the two files disagree until it has.

Do NOT run either while a campaign is executing.

Usage:
    python tests/scripts/rescore.py [--results-root PATH] [--dry-run]
"""
from __future__ import annotations
import argparse
import json
import sys
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "tests"))

from runner.schema import RunRecord            # noqa: E402
from runner.checker import check               # noqa: E402

FIXTURES_DIR = REPO_ROOT / "tests" / "fixtures"


def _expectations_for(fixture_id: str, cache: dict) -> dict | None:
    if fixture_id not in cache:
        path = FIXTURES_DIR / fixture_id / "expectations.json"
        try:
            cache[fixture_id] = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            cache[fixture_id] = None
    return cache[fixture_id]


def rescore(results_root: Path, dry_run: bool = False) -> int:
    records = [p for p in sorted(results_root.rglob("*.json"))
               if not p.name.endswith(".score.json")
               # every block has its own plan file beside the records
               # Every block writes its own plan file, and the smoke writes
               # "campaign-smoke-plan[-<block>].json" -- not "campaign-plan".
               # Matching the narrower prefix left those read as run records
               # and reported unreadable on every pass. Same defect as e31517b.
               and not p.name.startswith("campaign-")
               # the dashboard's cache lives beside the records and is not one
               and not p.name.startswith(".")]
    print(f"records: {len(records)} under {results_root}")

    cache: dict = {}
    stats = Counter()
    changes: list[str] = []

    for path in records:
        try:
            record = RunRecord.load(path)
        except Exception as exc:
            print(f"  SKIP (unreadable): {path.name} -- {exc}")
            stats["unreadable"] += 1
            continue

        expectations = _expectations_for(record.config.fixture_id, cache)
        if expectations is None:
            stats["no expectations"] += 1
            continue

        score_path = path.with_name(path.stem + ".score.json")
        before = None
        if score_path.exists():
            try:
                before = json.loads(score_path.read_text(encoding="utf-8"))
            except Exception:
                before = None

        try:
            score = check(record, expectations)
        except Exception as exc:
            print(f"  SKIP (checker raised): {path.name} -- {exc}")
            stats["checker error"] += 1
            continue

        after = score.to_dict()
        if before == after:
            stats["unchanged"] += 1
            continue

        stats["changed"] += 1
        if len(changes) < 5:
            b = ((before or {}).get("comprehension") or {}).get("rate")
            a = (after.get("comprehension") or {}).get("rate")
            changes.append(f"    {path.stem[:64]}  comprehension {b} -> {a}")

        if not dry_run:
            score.save(score_path)

    print("  " + ", ".join(f"{k}: {v}" for k, v in sorted(stats.items())))
    if changes:
        print("  esempi:")
        print("\n".join(changes))
    if dry_run:
        print("dry run -- nothing written")
    return 0


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--results-root", type=Path,
                    default=REPO_ROOT / "tests" / "results-main",
                    help="directory holding the run records (default: MAIN's)")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    sys.exit(rescore(args.results_root, dry_run=args.dry_run))


if __name__ == "__main__":
    main()
