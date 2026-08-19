#!/usr/bin/env python3
"""
sample_pool.py — stratified random pool for the minimum-context campaign.

Draws 300 items from the NLBSE'24 issues_test.csv (1500 rows, 5 repos x 3
labels, perfectly balanced), stratified by repo x label so every product and
every intent is represented, with a FIXED SEED (reproducible draw — no manual
item selection, per doc/experiment-minimum-context.md SS4.3).

The 300 are then split 50/50 into MAIN and REPLICATION, stratified again so
both halves keep the repo x label balance, with a SECOND fixed seed.

Outputs:
  - <fixture>/pool-manifest.json   (COMMITTED — zero third-party text: id,
    repo, nlbse_label, split, hashes, and placeholders for the manual
    verification)
  - data-local/pool-main.json       (LOCAL, gitignored — WITH full text)
  - data-local/pool-replication.json (LOCAL, gitignored — WITH full text;
    SEALED — no analysis script may read this before the MAIN conclusion is
    written, SS8.3 of the protocol)
  - data-local/verification-sheet.csv (LOCAL, gitignored — for Gianni: id,
    repo, nlbse_label, title, body (truncated), corrected_label, tolerant)

Usage:
    python3 tests/scripts/sample_pool.py
    python3 tests/scripts/sample_pool.py --csv tests/data-local/nlbse2024/issues_test.csv
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CSV = REPO_ROOT / "tests" / "data-local" / "nlbse2024" / "issues_test.csv"
DATA_LOCAL = REPO_ROOT / "tests" / "data-local"
FIXTURE_DIR = REPO_ROOT / "tests" / "fixtures" / "w2-branching" / "support-intake"

# Frozen constants — do not change after the first draw (SS8.1: frozen artefacts).
SEED_POOL = 42          # draws the 300 items, stratified by repo x label
SEED_SPLIT = 1337        # splits the 300 into MAIN/REPLICATION, stratified again
ITEMS_PER_STRATUM_DRAW = 20    # 20 x (5 repos x 3 labels) = 300
ITEMS_PER_STRATUM_SPLIT = 10   # 10/10 per stratum -> 150 MAIN / 150 REPLICATION
BODY_TRUNCATE_FOR_SHEET = 2000  # chars, readability only — pool-main.json keeps full text


def _hash(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def _load_rows(csv_path: Path) -> list[dict]:
    with csv_path.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    expected_cols = {"repo", "created_at", "label", "title", "body"}
    if not expected_cols.issubset(reader.fieldnames or []):
        raise SystemExit(
            f"Unexpected CSV schema in {csv_path}: {reader.fieldnames} "
            f"(expected superset of {sorted(expected_cols)})"
        )
    return rows


def _stratify(rows: list[dict]) -> dict[tuple[str, str], list[dict]]:
    strata: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for row in rows:
        strata[(row["repo"], row["label"])].append(row)
    return strata


def draw_pool(rows: list[dict], seed: int, per_stratum: int) -> list[dict]:
    """Stratified draw: exactly `per_stratum` rows from each (repo, label) cell."""
    strata = _stratify(rows)
    rng = random.Random(seed)
    drawn: list[dict] = []
    for key in sorted(strata.keys()):
        cell = strata[key]
        if len(cell) < per_stratum:
            raise SystemExit(f"Stratum {key} has only {len(cell)} rows, need {per_stratum}")
        drawn.extend(rng.sample(cell, per_stratum))
    return drawn


def split_main_replication(pool: list[dict], seed: int, per_stratum: int) -> tuple[list[dict], list[dict]]:
    """Stratified 50/50 split so both halves keep the repo x label balance."""
    strata = _stratify(pool)
    rng = random.Random(seed)
    main: list[dict] = []
    repl: list[dict] = []
    for key in sorted(strata.keys()):
        cell = strata[key]
        if len(cell) != 2 * per_stratum:
            raise SystemExit(
                f"Stratum {key} has {len(cell)} pool items, expected {2 * per_stratum}"
            )
        shuffled = cell[:]
        rng.shuffle(shuffled)
        main.extend(shuffled[:per_stratum])
        repl.extend(shuffled[per_stratum:])
    return main, repl


def build_manifest_entry(idx: int, row: dict, split: str) -> dict:
    return {
        "id": f"item-{idx:03d}",
        "repo": row["repo"],
        "nlbse_label": row["label"],
        "created_at": row.get("created_at"),
        "title_hash": _hash(row["title"]),
        "body_hash": _hash(row["body"]),
        "split": split,
        # Filled in by Gianni during manual verification (todo 2.6). NLBSE labels
        # are maintainer-assigned, not gold (SS4.3) -- this converts that known
        # noise into declared ground truth, or confirms it unchanged.
        "verified_label": None,
        "tolerant": False,
        "tolerant_alt_label": None,  # the second acceptable intent, when tolerant=true
        "verified": False,
    }


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--csv", type=Path, default=DEFAULT_CSV, help="Path to issues_test.csv")
    args = p.parse_args()

    if not args.csv.exists():
        raise SystemExit(f"CSV not found: {args.csv}. Download it first (see doc/experiment-minimum-context.md SS4.2).")

    rows = _load_rows(args.csv)
    pool = draw_pool(rows, SEED_POOL, ITEMS_PER_STRATUM_DRAW)
    main_rows, repl_rows = split_main_replication(pool, SEED_SPLIT, ITEMS_PER_STRATUM_SPLIT)

    # Stable ids: sort pool by (repo, label, title) before numbering, so re-running
    # this script (same seeds, same CSV) reproduces identical ids and hashes.
    pool_sorted = sorted(pool, key=lambda r: (r["repo"], r["label"], r["title"]))
    main_keys = {(r["repo"], r["label"], r["title"]) for r in main_rows}

    manifest = []
    main_full = []
    repl_full = []
    sheet_rows = []

    for idx, row in enumerate(pool_sorted, start=1):
        split = "MAIN" if (row["repo"], row["label"], row["title"]) in main_keys else "REPLICATION"
        entry = build_manifest_entry(idx, row, split)
        manifest.append(entry)

        full_row = {
            "id": entry["id"],
            "repo": row["repo"],
            "nlbse_label": row["label"],
            "title": row["title"],
            "body": row["body"],
        }
        (main_full if split == "MAIN" else repl_full).append(full_row)

        sheet_rows.append({
            "id": entry["id"],
            "repo": row["repo"],
            "nlbse_label": row["label"],
            "split": split,
            "title": row["title"],
            "body_excerpt": (row["body"] or "")[:BODY_TRUNCATE_FOR_SHEET],
            "corrected_label": "",
            "tolerant": "",
            "tolerant_alt_label": "",
        })

    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    DATA_LOCAL.mkdir(parents=True, exist_ok=True)

    (FIXTURE_DIR / "pool-manifest.json").write_text(
        json.dumps({
            "seed_pool": SEED_POOL,
            "seed_split": SEED_SPLIT,
            "source_csv": "nlbse2024/issue-report-classification: data/issues_test.csv",
            "n_items": len(manifest),
            "items": manifest,
        }, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    (DATA_LOCAL / "pool-main.json").write_text(
        json.dumps(main_full, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (DATA_LOCAL / "pool-replication.json").write_text(
        json.dumps(repl_full, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    with (DATA_LOCAL / "verification-sheet.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=[
            "id", "repo", "nlbse_label", "split", "title", "body_excerpt",
            "corrected_label", "tolerant", "tolerant_alt_label",
        ])
        w.writeheader()
        w.writerows(sheet_rows)

    print(f"Pool: {len(manifest)} items ({len(main_full)} MAIN / {len(repl_full)} REPLICATION)")
    print(f"  pool-manifest.json      -> {FIXTURE_DIR / 'pool-manifest.json'}  (commit this)")
    print(f"  pool-main.json          -> {DATA_LOCAL / 'pool-main.json'}  (local, gitignored)")
    print(f"  pool-replication.json   -> {DATA_LOCAL / 'pool-replication.json'}  (SEALED, gitignored)")
    print(f"  verification-sheet.csv  -> {DATA_LOCAL / 'verification-sheet.csv'}  (for Gianni, item 2.6)")


if __name__ == "__main__":
    main()
