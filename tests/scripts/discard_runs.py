#!/usr/bin/env python3
"""
Discard runs produced by an artefact that has since been superseded.

When a fixture, a prompt or a reader is corrected, the runs made before the
correction are not bad data to be filtered later -- they answer a different
question from the ones made after, and leaving them in the index means the
campaign's own resume will count them as done and never run the replacements.
Section 12 of doc/experiment-minimum-context.md has discarded runs on this ground
twice: nine rows on 2026-08-23 when the reader could not see a thinking block, and
the `prose-generated` rows of the same day, whose document forbade the trace lines
its oracle reads.

Three things have to move together or the campaign will not redo the work:

  1. the record and its .score.json are deleted from the results root
  2. the matching rows are removed from index.jsonl
  3. the matching plan rows go back to `pending`

Doing only (3) leaves the index rows in place, and _index_done_counts credits them
to the pending rows by coordinate on the next resume -- the rows read as done and
nothing runs. Doing only (1) and (2) leaves the plan claiming work that has no
record behind it.

The deleted files are recoverable from git as long as the results root is tracked
and the discarded runs were committed, which for tests/results-main they are.

Do NOT run while a campaign is executing.

Usage:
    python tests/scripts/discard_runs.py --rendering prose-generated [--dry-run]
    python tests/scripts/discard_runs.py --mode llama-qwen3.5-9b-think --dry-run
"""
from __future__ import annotations
import argparse
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

# index field <- plan field, for the filters that name a campaign coordinate
COORDS = {
    "rendering": ("process_rendering", "rendering"),
    "mode":      ("mode", "mode"),
    "queue":     ("staged_input_id", "queue"),
}


def _record_path(results_root: Path, row: dict) -> Path:
    model = row.get("model_id", "").replace("/", "_").replace(":", "_")
    ctx = (row.get("context") or "E0").replace("+", "plus")
    return (results_root / row.get("fixture_id", "") / ctx / model
            / (row.get("spec_version") or "0.6") / f"{row['run_id']}.json")


def discard(results_root: Path, plan_path: Path, filters: dict,
            dry_run: bool = False) -> int:
    index_path = results_root / "index.jsonl"
    if not index_path.exists():
        print(f"no such index: {index_path}")
        return 1

    rows = [json.loads(l) for l in index_path.read_text(encoding="utf-8").splitlines() if l.strip()]

    def matches_index(r: dict) -> bool:
        return all(r.get(COORDS[k][0]) == v for k, v in filters.items())

    doomed = [r for r in rows if matches_index(r)]
    kept = [r for r in rows if not matches_index(r)]
    print(f"index: {len(rows)} rows, {len(doomed)} match {filters}")

    files = []
    for r in doomed:
        rec = _record_path(results_root, r)
        for p in (rec, rec.with_name(rec.stem + ".score.json")):
            if p.exists():
                files.append(p)
    print(f"files: {len(files)} to delete")

    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    plan_rows = plan if isinstance(plan, list) else plan["rows"]

    def matches_plan(r: dict) -> bool:
        return all(r.get(COORDS[k][1]) == v for k, v in filters.items())

    reset = [r for r in plan_rows if matches_plan(r) and r.get("status") != "pending"]
    print(f"plan : {len(reset)} rows back to pending "
          f"(of {sum(1 for r in plan_rows if matches_plan(r))} matching)")

    if dry_run:
        print("dry run -- nothing written")
        return 0
    if not doomed and not reset:
        print("nothing to do")
        return 0

    for p in files:
        p.unlink()

    index_path.with_suffix(".jsonl.bak").write_bytes(index_path.read_bytes())
    tmp = index_path.with_suffix(".jsonl.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        for r in kept:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    os.replace(tmp, index_path)

    for r in reset:
        r["status"] = "pending"
    plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"deleted {len(files)} files, index now {len(kept)} rows, "
          f"{len(reset)} plan rows pending again")
    return 0


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--results-root", type=Path,
                    default=REPO_ROOT / "tests" / "results-main")
    ap.add_argument("--plan", type=Path, default=None,
                    help="campaign-plan.json [default: beside the results root]")
    for name in COORDS:
        ap.add_argument(f"--{name}", default=None)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    filters = {k: getattr(args, k) for k in COORDS if getattr(args, k) is not None}
    if not filters:
        ap.error("give at least one of " + ", ".join(f"--{k}" for k in COORDS)
                 + " -- this tool deletes, and an empty filter matches every run")

    plan_path = args.plan or (args.results_root / "campaign-plan.json")
    sys.exit(discard(args.results_root, plan_path, filters, dry_run=args.dry_run))


if __name__ == "__main__":
    main()
