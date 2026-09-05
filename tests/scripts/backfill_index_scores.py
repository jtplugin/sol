#!/usr/bin/env python3
"""
Backfill the continuous metrics into an existing index.jsonl.

`_append_index` learned to write conditional_rate, comprehension_rate,
sequence_rate and traced on 2026-08-23, after MAIN had already produced 459 rows
without them. The data was never lost -- every run writes a sibling
`<run_id>.score.json` carrying the full ScoreRecord -- it simply never reached the
index, and therefore never reached the dashboard. This script joins the two by
run_id and rewrites the index in place.

It carries the three verdicts (quality, fidelity, degradation_mode) as well as
the four rates, because a rescore moves those too.

Pass --refresh to overwrite values the index already carries: after a run of
tests/scripts/rescore.py the score files hold newer verdicts than the index, and
without it every row counts as "already" and nothing moves.

Rows whose score file is missing are left exactly as they are: absent is a
readable state, and inventing a rate for a run nobody scored would be worse than
a blank column. Rows that already carry the fields are left alone too, so a
second run is a no-op.

The rewrite is atomic (temp file + replace) and keeps a `.bak` alongside. Do NOT
run it while a campaign is executing: campaign.py appends to the index after
every row, and any row appended between the read and the replace would be lost.

Usage:
    python tests/scripts/backfill_index_scores.py [--index PATH] [--dry-run]
"""
from __future__ import annotations
import argparse
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

FIELDS = ("conditional_rate", "comprehension_rate", "sequence_rate", "traced",
          "quality", "quality_rate", "fidelity", "degradation_mode")


def collect_scores(results_root: Path) -> dict[str, dict]:
    """{run_id -> the index's score fields}, read from every .score.json."""
    out: dict[str, dict] = {}
    for path in results_root.rglob("*.score.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            print(f"  SKIP (read error): {path.name} -- {exc}")
            continue
        run_id = data.get("run_id")
        if not run_id:
            continue
        fid = data.get("fidelity") or {}
        comp = data.get("comprehension") or {}
        qual = data.get("quality") or {}
        out[run_id] = {
            "conditional_rate":   fid.get("conditional_rate"),
            "comprehension_rate": comp.get("rate"),
            "sequence_rate":      fid.get("sequence_rate"),
            "traced":             bool(fid.get("observed_sequence")),
            # The verdicts move too. They did not on 2026-08-23, when this
            # script was written for four rates the index had never carried;
            # they do after a rescore that changed what the checker was given
            # -- the payload re-extraction of the same day rewrote 236 records,
            # and quality and degradation_mode are read straight off it.
            "quality":            qual.get("result"),
            "quality_rate":       qual.get("rate"),
            "fidelity":           fid.get("result"),
            "degradation_mode":   data.get("degradation_mode"),
        }
    return out


def backfill(index_path: Path, dry_run: bool = False, refresh: bool = False) -> int:
    if not index_path.exists():
        print(f"no such index: {index_path}")
        return 1

    results_root = index_path.parent
    scores = collect_scores(results_root)
    print(f"score files: {len(scores)} under {results_root}")

    rows = []
    with open(index_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    print(f"index rows : {len(rows)}")

    filled = already = missing = 0
    for row in rows:
        if all(k in row for k in FIELDS) and not refresh:
            already += 1
            continue
        metrics = scores.get(row.get("run_id", ""))
        if metrics is None:
            missing += 1
            continue
        row.update(metrics)
        filled += 1

    print(f"  filled  : {filled}")
    print(f"  already : {already}")
    print(f"  no score: {missing}")

    if dry_run:
        print("dry run -- nothing written")
        return 0
    if not filled:
        print("nothing to do")
        return 0

    backup = index_path.with_suffix(index_path.suffix + ".bak")
    backup.write_bytes(index_path.read_bytes())

    tmp = index_path.with_suffix(index_path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    os.replace(tmp, index_path)
    print(f"written {index_path}  (backup: {backup.name})")
    return 0


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--index", type=Path,
                    default=REPO_ROOT / "tests" / "results-main" / "index.jsonl",
                    help="index.jsonl to rewrite (default: MAIN's)")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--refresh", action="store_true",
                    help="overwrite the fields even where the index already has them "
                         "-- for after tests/scripts/rescore.py, when the score files "
                         "hold newer values than the index does")
    args = ap.parse_args()
    sys.exit(backfill(args.index, dry_run=args.dry_run, refresh=args.refresh))


if __name__ == "__main__":
    main()
