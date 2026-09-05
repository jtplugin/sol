#!/usr/bin/env python3
"""
build_queues.py and hydrate.py --mode queues always run in sequence, this one
second: build_queues.py regenerates queues-manifest.json/expectations.json
first, then hydrate.py --mode queues regenerates the staged inputs/queue-NN.json
from it. Never run one without the other — runner.py's assert_queue_alignment()
is the net if someone forgets, but it only catches the drift after the fact.

hydrate.py — reconstructs runnable text from the local NLBSE CSV using the
committed, dehydrated manifests. Zero third-party text ever lives in git;
this script is the only place that puts it back together, and only on the
local machine that has the CSV.

Two independent jobs:

  --mode pool    pool-manifest.json (committed: id/repo/label/hashes) + the
                 local CSV -> data-local/pool-main.json / pool-replication.json
                 (WITH text), hash-VERIFIED against the manifest. Use this to
                 regenerate the local pool files on a fresh checkout, or after
                 pool-manifest.json's verified_label fields are edited.

  --mode queues  queues-manifest.json (committed: ordered item ids per queue)
                 + data-local/pool-main.json -> fixture inputs/queue-01.json
                 .. queue-10.json (id/title/body ONLY -- no product/intent,
                 the model must classify).

  --mode requests support-routing's items-manifest.json + data-local/pool-main.json
                 -> that fixture's inputs/r01.json .. r20.json, one item each
                 plus the world state it is decided against.

Usage:
    python3 tests/scripts/hydrate.py --mode pool
    python3 tests/scripts/hydrate.py --mode queues
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_DIR = REPO_ROOT / "tests" / "fixtures" / "w2-branching" / "support-intake"
ROUTING_DIR = REPO_ROOT / "tests" / "fixtures" / "w2-branching" / "support-routing"
DATA_LOCAL = REPO_ROOT / "tests" / "data-local"
DEFAULT_CSV = DATA_LOCAL / "nlbse2024" / "issues_test.csv"


def _hash(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def hydrate_pool(csv_path: Path) -> None:
    manifest = json.loads((FIXTURE_DIR / "pool-manifest.json").read_text(encoding="utf-8"))
    with csv_path.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    # Index CSV rows by (repo, title_hash, body_hash) for exact lookup.
    by_hash: dict[tuple[str, str, str], dict] = {}
    for row in rows:
        key = (row["repo"], _hash(row["title"]), _hash(row["body"]))
        by_hash[key] = row

    main_rows, repl_rows = [], []
    missing = []
    for entry in manifest["items"]:
        key = (entry["repo"], entry["title_hash"], entry["body_hash"])
        row = by_hash.get(key)
        if row is None:
            missing.append(entry["id"])
            continue
        full = {
            "id": entry["id"],
            "repo": entry["repo"],
            "nlbse_label": entry["nlbse_label"],
            "title": row["title"],
            "body": row["body"],
            "tolerant": entry.get("tolerant", False),
        }
        (main_rows if entry["split"] == "MAIN" else repl_rows).append(full)

    if missing:
        sys.exit(f"Hash mismatch / not found in CSV for {len(missing)} item(s): {missing[:10]}...")

    DATA_LOCAL.mkdir(parents=True, exist_ok=True)
    (DATA_LOCAL / "pool-main.json").write_text(
        json.dumps(main_rows, indent=2, ensure_ascii=False), encoding="utf-8")
    (DATA_LOCAL / "pool-replication.json").write_text(
        json.dumps(repl_rows, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Hydrated pool: {len(main_rows)} MAIN / {len(repl_rows)} REPLICATION, all hashes verified.")


def hydrate_queues() -> None:
    manifest = json.loads((FIXTURE_DIR / "queues-manifest.json").read_text(encoding="utf-8"))
    pool_main_path = DATA_LOCAL / "pool-main.json"
    if not pool_main_path.exists():
        sys.exit(f"{pool_main_path} not found -- run 'hydrate.py --mode pool' or sample_pool.py first.")
    pool_main = {row["id"]: row for row in json.loads(pool_main_path.read_text(encoding="utf-8"))}

    inputs_dir = FIXTURE_DIR / "inputs"
    inputs_dir.mkdir(parents=True, exist_ok=True)

    for q in manifest["queues"]:
        queue_items = []
        for item_id in q["item_ids"]:
            row = pool_main.get(item_id)
            if row is None:
                sys.exit(f"{item_id} (queue {q['queue_id']}) not found in pool-main.json")
            queue_items.append({"id": row["id"], "title": row["title"], "body": row["body"]})
        out_path = inputs_dir / f"{q['queue_id']}.json"
        out_path.write_text(
            json.dumps({"queue": queue_items}, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"  {out_path.relative_to(REPO_ROOT)}  ({len(queue_items)} items, gitignored)")

    print(f"Hydrated {len(manifest['queues'])} queues into {inputs_dir.relative_to(REPO_ROOT)}/")


def hydrate_requests(routing_dir: Path | None = None) -> None:
    """support-routing's twenty staged requests, one item each.

    Same shape as hydrate_queues, one item instead of fifteen, plus the world
    state that item is decided against -- the hours left and the state of the
    three teams. That state is computed by build_requests.py from the oracle and
    written into items-manifest.json; it is never carried over from a previous
    request's answer, which is what keeps the twenty runs independent (SS4.5).

    The off-catalog request is written rather than drawn -- no item from five
    real repositories can be UNKNOWN -- so its text lives in the manifest and
    needs no pool lookup.
    """
    routing_dir = routing_dir or ROUTING_DIR
    manifest = json.loads((routing_dir / "items-manifest.json").read_text(encoding="utf-8"))
    # The MAIN arms draw from pool-main.json; the REPLICATION arms (manifest
    # `split` == "REPLICATION") from pool-replication.json -- the sealed half,
    # openable only at SS8.3 step 5. Never merged: an id resolving in the wrong
    # pool would be a split leak, and the loud KeyError is the guard.
    pool_name = ("pool-replication.json" if manifest.get("split") == "REPLICATION"
                 else "pool-main.json")
    pool_path = DATA_LOCAL / pool_name
    if not pool_path.exists():
        sys.exit(f"{pool_path} not found -- run 'hydrate.py --mode pool' first.")
    pool_main = {row["id"]: row for row in json.loads(pool_path.read_text(encoding="utf-8"))}
    synthetic = manifest["synthetic_item"]

    inputs_dir = routing_dir / "inputs"
    inputs_dir.mkdir(parents=True, exist_ok=True)

    for req in manifest["requests"]:
        if req["synthetic"]:
            row = synthetic
        else:
            row = pool_main.get(req["item_id"])
            if row is None:
                sys.exit(f"{req['item_id']} ({req['request_id']}) not found in {pool_name}")
        payload = {
            "item": {"id": row["id"], "title": row["title"], "body": row["body"]},
            "remaining_hours": req["world"]["remaining_hours"],
            "teams": req["world"]["teams"],
        }
        out_path = inputs_dir / f"{req['request_id']}.json"
        out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False),
                            encoding="utf-8")

    print(f"Hydrated {len(manifest['requests'])} requests into "
          f"{inputs_dir.relative_to(REPO_ROOT)}/")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--mode", required=True, choices=["pool", "queues", "requests"])
    p.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    p.add_argument("--routing-dir", type=Path, default=None,
                   help="requests mode only: fixture dir to hydrate "
                        "[default: support-routing]. Use for the -repl arms.")
    args = p.parse_args()

    if args.mode == "pool":
        if not args.csv.exists():
            sys.exit(f"CSV not found: {args.csv}")
        hydrate_pool(args.csv)
    elif args.mode == "queues":
        hydrate_queues()
    else:
        hydrate_requests(args.routing_dir)


if __name__ == "__main__":
    main()
