#!/usr/bin/env python3
"""
build_queues.py and hydrate.py --mode queues always run in sequence, this one
first: build_queues.py regenerates queues-manifest.json/expectations.json,
hydrate.py --mode queues regenerates the staged inputs/queue-NN.json from it.
Never run one without the other — runner.py's assert_queue_alignment() is the
net if someone forgets, but it only catches the drift after the fact.

build_queues.py — K=10 queue generation via rejection sampling.

Draws K queues of `queue_size` items each from the MAIN pool, using a fixed
seed, and REJECTS any draw that does not satisfy the structural criterion
frozen in queue-criterion.json (SS4.4 of doc/experiment-minimum-context.md).
The criterion concerns queue INFORMATIVENESS (does it exercise ESCALATE in a
useful window), never difficulty for any particular model.

Ground truth for rejection-sampling purposes comes from pool-main.json's
`repo`/`nlbse_label` fields via catalog.json's product_to_repo mapping --
this is available even before Gianni's manual verification (item 2.6), but
queues generated before that verification are PROVISIONAL and must be
regenerated once the pool is final (this is declared loudly on stdout).

Outputs (both under the fixture dir, both COMMITTED, zero third-party text):
  - queues-manifest.json  — for each of the K queues: the ordered list of
    item ids that compose it, the accepted reference.py result, and whether
    the pool was verified at generation time.
  - expectations.json     — cases for i0-malformed + one case per queue,
    each carrying `expected_sequence` (the BRANCH label sequence) and
    `expected_output` (the full end-to-end payload), both computed by
    reference.run_queue on the ground-truth classifications.

Usage:
    python3 tests/scripts/build_queues.py
    python3 tests/scripts/build_queues.py --k 10 --max-attempts 20000
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

# Force UTF-8 stdout/stderr on Windows (cp1252 can't encode em-dash etc.)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_DIR = REPO_ROOT / "tests" / "fixtures" / "w2-branching" / "support-intake"
DATA_LOCAL = REPO_ROOT / "tests" / "data-local"

sys.path.insert(0, str(FIXTURE_DIR))
from reference import run_queue, action_sequence  # noqa: E402

SEED_QUEUES = 2024  # frozen (SS8.1) — do not change once queues are accepted


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _ground_truth_classifications(
    pool_main: list[dict], catalog: dict, pool_manifest: dict
) -> dict[str, dict]:
    """id -> {id, product, intent} using repo->product mapping. Intent is
    verified_label (Gianni's human judgment) where verified==True, else falls
    back to the raw NLBSE label. Items outside the needed set may still be
    unverified when this runs -- they cannot affect any accepted queue's
    output since the needed set is by definition every item consumed before
    a queue's halt."""
    repo_to_product = {v: k for k, v in catalog["product_to_repo"].items()}
    manifest_by_id = {it["id"]: it for it in pool_manifest["items"]}
    out = {}
    for row in pool_main:
        product = repo_to_product.get(row["repo"], "UNKNOWN")
        m = manifest_by_id[row["id"]]
        intent = (m["verified_label"] if m.get("verified") else row["nlbse_label"]).upper()
        out[row["id"]] = {"id": row["id"], "product": product, "intent": intent}
    return out


def _draw_and_check(
    pool_ids: list[str],
    classifications: dict[str, dict],
    rng: random.Random,
    queue_size: int,
    budget_hours: float,
    hours_table: dict,
    criterion: dict,
) -> tuple[list[str], dict] | None:
    drawn_ids = rng.sample(pool_ids, queue_size)
    items = [classifications[i] for i in drawn_ids]
    result = run_queue(items, budget_hours, hours_table)

    if not criterion["must_halt"]:
        return drawn_ids, result
    if result["halted_at"] is None:
        return None
    position = next(
        (idx for idx, rec in enumerate(result["items"], start=1) if rec["id"] == result["halted_at"]),
        None,
    )
    if position is None:
        return None
    if not (criterion["halt_position_min"] <= position <= criterion["halt_position_max"]):
        return None
    return drawn_ids, result


def build_queues(k: int, max_attempts: int) -> None:
    pool_manifest = _load_json(FIXTURE_DIR / "pool-manifest.json")
    catalog = _load_json(FIXTURE_DIR / "catalog.json")
    criterion_doc = _load_json(FIXTURE_DIR / "queue-criterion.json")
    criterion = criterion_doc["criterion"]
    queue_size = criterion_doc["queue_size"]

    pool_main_path = DATA_LOCAL / "pool-main.json"
    if not pool_main_path.exists():
        sys.exit(f"{pool_main_path} not found — run sample_pool.py first.")
    pool_main = _load_json(pool_main_path)

    main_items = [it for it in pool_manifest["items"] if it["split"] == "MAIN"]
    main_verified = sum(1 for it in main_items if it.get("verified"))
    if main_verified < len(main_items):
        print("!" * 70)
        print(f"  WARNING — MAIN split not fully verified ({main_verified}/{len(main_items)} items).")
        print("  Unverified MAIN items fall back to the raw NLBSE label; queues built")
        print("  from them may still be PROVISIONAL if any such item ends up processed")
        print("  before a queue's halt. REPLICATION stays sealed/unverified by design.")
        print("!" * 70)
        print()

    classifications = _ground_truth_classifications(pool_main, catalog, pool_manifest)
    pool_ids = [row["id"] for row in pool_main]

    rng = random.Random(SEED_QUEUES)
    queues = []
    attempts_used = 0
    for qn in range(1, k + 1):
        found = None
        for _ in range(max_attempts):
            attempts_used += 1
            found = _draw_and_check(
                pool_ids, classifications, rng, queue_size,
                catalog["budget_hours"], catalog["hours_table"], criterion,
            )
            if found:
                break
        if not found:
            sys.exit(f"Could not find an accepted queue #{qn} within {max_attempts} attempts.")
        drawn_ids, result = found
        queues.append({
            "queue_id": f"queue-{qn:02d}",
            "item_ids": drawn_ids,
            "halted_at": result["halted_at"],
            "remaining_hours": result["remaining_hours"],
            "n_processed": len(result["items"]),
        })

    manifest = {
        "seed_queues": SEED_QUEUES,
        "k": k,
        "queue_size": queue_size,
        "pool_verified_at_generation": main_verified == len(main_items),
        "attempts_used": attempts_used,
        "queues": queues,
    }
    (FIXTURE_DIR / "queues-manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    # expectations.json — malformed case + one case per queue.
    # tolerant/tolerant_alt_label live in pool-manifest.json (committed), not
    # in pool-main.json (which only carries id/repo/nlbse_label/title/body).
    id_to_row = {it["id"]: it for it in pool_manifest["items"]}
    cases = [{
        "input": "inputs/i0-malformed.json",
        "structural": True,
        "rationale": "queue item x1 is missing 'body' -- guard must fire before any REPEAT iteration",
        "expected_output": {"status": "INVALID_INPUT", "items": [], "remaining_hours": None, "halted_at": None},
    }]
    for q in queues:
        items = [classifications[i] for i in q["item_ids"]]
        result = run_queue(items, catalog["budget_hours"], catalog["hours_table"])
        cases.append({
            "input": f"inputs/{q['queue_id']}.json",
            "expected_sequence": action_sequence(result),
            "expected_output": {
                "status": "OK",
                "items": result["items"],
                "remaining_hours": result["remaining_hours"],
                "halted_at": result["halted_at"],
            },
            # Only the items actually PROCESSED (result["items"], up to and
            # including any ESCALATE halt) -- a faithfully-executing model
            # never reaches items past the halt, so it cannot have classified
            # them; scoring comprehension against the full 15-item queue
            # would wrongly punish a model that halted correctly.
            "comprehension_ground_truth": [
                {"id": r["id"], "product": r["product"], "intent": r["intent"],
                 "tolerant": id_to_row[r["id"]].get("tolerant", False),
                 "tolerant_alt_label": id_to_row[r["id"]].get("tolerant_alt_label")}
                for r in result["items"]
            ],
        })

    expectations = {
        "fixture": "fixture-w2-support-intake",
        "workload_class": "W2",
        "concern": "control-flow fidelity over state accumulated across REPEAT iterations, "
                   "decomposed into comprehension / conditional fidelity / end-to-end outcome",
        "min_environment": "E0",
        # Embedded so checker.py can re-run the queue oracle on the MODEL's own
        # classifications (conditional fidelity) without importing this fixture's
        # reference.py -- keeps the generic checker fixture-agnostic. checker.py's
        # _run_queue_oracle() must stay algorithmically in sync with reference.py's
        # run_queue(); both are covered by R1 tests.
        "catalog": {"budget_hours": catalog["budget_hours"], "hours_table": catalog["hours_table"]},
        "cases": cases,
    }
    (FIXTURE_DIR / "expectations.json").write_text(
        json.dumps(expectations, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    print(f"Built {k} queues in {attempts_used} attempts -> {FIXTURE_DIR / 'queues-manifest.json'}")
    print(f"Wrote expectations.json ({len(cases)} cases) -> {FIXTURE_DIR / 'expectations.json'}")
    for q in queues:
        print(f"  {q['queue_id']}: halted_at={q['halted_at']} remaining={q['remaining_hours']} "
              f"n_processed={q['n_processed']}")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--k", type=int, default=10)
    p.add_argument("--max-attempts", type=int, default=20000)
    args = p.parse_args()
    build_queues(args.k, args.max_attempts)


if __name__ == "__main__":
    main()
