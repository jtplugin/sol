#!/usr/bin/env python3
"""
build_requests.py — the 20 stratified requests of w2-branching/support-routing.

Deterministic, frozen seed, no network and no model. Regenerating it on a clean
checkout produces the same twenty requests, which is what makes the artefact a
frozen one (SS8.1 item 8 of doc/experiment-minimum-context.md).

WHY STRATIFIED AND NOT SAMPLED. A single draw over the pool lands three quarters
of its mass on the easy branch: an owner that is OPEN, a budget with room, a
product somebody accepts. The strata below are the decision points of the
process, and each one is written here with the world state that reaches it. The
draw only chooses WHICH verified item fills a stratum, never which strata exist.

WHAT IS EXCLUDED, AND WHY.
  - unverified pool items: the ground truth would be the raw NLBSE label, and
    the whole case turns on it;
  - `tolerant` items: they legitimately admit two intents (SS10), and intent
    decides both the hours and whether a LIMITED owner takes the request. In a
    queue of fifteen a tolerant item costs one comparison; here it would make
    the expected action of an entire run ambiguous.

TWO SYNTHETIC CASES, both declared as such in the manifest:
  - one off-catalog request, because no item drawn from five real repositories
    can ever be UNKNOWN, and NEEDS_INFO would otherwise be reachable only
    through a model's mistake -- a stratum nothing can sample;
  - one malformed payload, which is structural and sits outside the twenty,
    exactly as support-intake's i0-malformed does.

Usage:
    python tests/scripts/build_requests.py [--check]

`--check` recomputes everything and reports whether the files on disk match,
without writing -- for the test suite and for anyone auditing the frozen set.
Then: python tests/scripts/hydrate.py --mode requests
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import random
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
INTAKE_DIR = REPO_ROOT / "tests" / "fixtures" / "w2-branching" / "support-intake"
ROUTING_DIR = REPO_ROOT / "tests" / "fixtures" / "w2-branching" / "support-routing"

SEED = 20260823
REPL_SEED = 20260827   # the REPLICATION draw (SS8.3 step 5); declared in SS12 before any run
REPL_ROUTING_DIR = REPO_ROOT / "tests" / "fixtures" / "w2-branching" / "support-routing-repl"
REPL_NOTRACE_DIR = REPO_ROOT / "tests" / "fixtures" / "w2-branching" / "support-routing-notrace-repl"

OPEN3 = {"T1": "OPEN", "T2": "OPEN", "T3": "OPEN"}


def _world(remaining: int, **states) -> dict:
    teams = dict(OPEN3)
    teams.update(states)
    return {"remaining_hours": remaining, "teams": teams}


# The frozen composition. Every stratum of SS7.6 appears at least twice, the
# precedence trap three times. `product`/`intent` select the pool item; `world`
# is what reaches the branch.
STRATA = [
    ("r01", "owner-open",            "P1", "BUG",      _world(20)),
    ("r02", "owner-open",            "P3", "QUESTION", _world(20)),
    ("r03", "owner-open",            "P5", "FEATURE",  _world(20)),

    ("r04", "owner-closed-backup",   "P2", "FEATURE",  _world(20, T1="CLOSED")),
    ("r05", "owner-closed-backup",   "P3", "BUG",      _world(20, T2="CLOSED")),

    ("r06", "trap-limited-bug",      "P2", "BUG",      _world(20, T1="LIMITED")),
    ("r07", "trap-limited-bug",      "P5", "BUG",      _world(20, T3="LIMITED")),
    ("r08", "trap-limited-bug",      "P3", "BUG",      _world(20, T2="LIMITED")),

    ("r09", "limited-nonbug-backup", "P2", "FEATURE",  _world(20, T1="LIMITED")),
    ("r10", "limited-nonbug-backup", "P3", "QUESTION", _world(20, T2="LIMITED")),

    # One stratum, three ways to reach it: nobody eligible is taking work. The
    # third is the one worth having -- a backup that is LIMITED rather than
    # CLOSED reads as available, and a model that fails only that one has a
    # different defect from a model that fails all three. Which is which is
    # recoverable from each case's world state, recorded with it.
    ("r11", "no-team-available",     "P2", "BUG",      _world(20, T1="CLOSED", T2="CLOSED")),
    ("r12", "no-team-available",     "P1", "FEATURE",  _world(20, T1="CLOSED")),
    ("r13", "no-team-available",     "P5", "FEATURE",  _world(20, T3="LIMITED", T2="LIMITED")),

    ("r14", "accepted-by-nobody",    "P4", "BUG",      _world(20)),
    ("r15", "accepted-by-nobody",    "P4", "FEATURE",  _world(20)),

    ("r16", "bug-over-budget",       "P1", "BUG",      _world(2)),
    ("r17", "bug-over-budget",       "P5", "BUG",      _world(1)),

    ("r18", "nonbug-over-budget",    "P2", "FEATURE",  _world(3)),
    ("r19", "nonbug-over-budget",    "P3", "QUESTION", _world(0)),

    ("r20", "off-catalog",           None, "QUESTION", _world(20)),
]

# The one request written rather than drawn. Deliberately far from all five
# personas: no rendering, no tensors, no repository, no image -- a model that
# answers anything other than UNKNOWN has matched on the word "system".
SYNTHETIC = {
    "id": "item-synth-01",
    "title": "How do I change the number of vacation days accrued per month?",
    "body": ("Our HR administrator needs to raise the monthly accrual from 1.75 days to 2 days "
             "for staff past their fifth year. I can see the current figure on the employee "
             "record but the field is read-only for my role. Who can change it, and does the "
             "change apply to days already accrued this year or only from the next payroll "
             "period onwards?"),
}

MALFORMED = {
    "input": "inputs/r00-malformed.json",
    "structural": True,
    "rationale": ("the request carries no 'remaining_hours' and its item has no 'body' -- the "
                  "guard must fire before any classification happens"),
    "expected_output": {"status": "OK"},   # replaced below; kept explicit in _build
}


def _load_reference():
    spec = importlib.util.spec_from_file_location(
        "_routing_reference", ROUTING_DIR / "reference.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _eligible(pool_items: list[dict], repo_of: dict, product: str, intent: str,
              split: str = "MAIN") -> list[dict]:
    return sorted(
        (i for i in pool_items
         if i["split"] == split
         and i.get("verified")
         and not i.get("tolerant")
         and i.get("verified_label")
         and repo_of[i["repo"]] == product
         and i["verified_label"].upper() == intent),
        key=lambda i: i["id"],
    )


def _build(split: str = "MAIN", seed: int = SEED,
           fixture_name: str = "fixture-w2-support-routing") -> tuple[dict, dict]:
    ref = _load_reference()
    catalog = json.loads((ROUTING_DIR / "catalog.json").read_text(encoding="utf-8"))
    repo_of = {v: k for k, v in catalog["product_to_repo"].items()}
    pool = json.loads((INTAKE_DIR / "pool-manifest.json").read_text(encoding="utf-8"))["items"]

    rng = random.Random(seed)
    used: set[str] = set()
    requests, cases = [], []

    for req_id, stratum, product, intent, world in STRATA:
        if product is None:
            item_id = SYNTHETIC["id"]
            truth_product = "UNKNOWN"
        else:
            pool_choices = [i for i in _eligible(pool, repo_of, product, intent, split)
                            if i["id"] not in used]
            if not pool_choices:
                raise SystemExit(
                    f"{req_id}: no verified, non-tolerant {split} item left for "
                    f"{product}/{intent}. The pool cannot fill this stratum.")
            item_id = rng.choice(pool_choices)["id"]
            truth_product = product
        used.add(item_id)

        classification = {"id": item_id, "product": truth_product, "intent": intent}
        result = ref.route_item(classification, world["remaining_hours"],
                                world["teams"], catalog)

        requests.append({
            "request_id": req_id,
            "stratum": stratum,
            "item_id": item_id,
            "synthetic": product is None,
            "world": world,
            "ground_truth": {"product": truth_product, "intent": intent},
            "expected_action": result["item"]["action"],
            "expected_team": result["item"]["team"],
        })
        cases.append({
            "input": f"inputs/{req_id}.json",
            "rationale": f"stratum {stratum}: {truth_product}/{intent} against "
                         f"{world['teams']} with {world['remaining_hours']}h left",
            "world": world,
            "expected_sequence": [ref.action_label(result)],
            "expected_output": result,
            "comprehension_ground_truth": [
                {"id": item_id, "product": truth_product, "intent": intent, "tolerant": False}],
        })

    malformed = dict(MALFORMED)
    malformed["expected_output"] = {"status": "INVALID_INPUT", "item": None,
                                    "remaining_hours": None}

    manifest = {
        "_comment": __doc__.strip().splitlines()[0],
        "seed": seed,
        # `split` appears only on the REPLICATION arms: MAIN's manifest is a
        # frozen artefact (SS8.1) and must keep reproducing byte-identically.
        **({"split": split} if split != "MAIN" else {}),
        "source_pool": "../support-intake/pool-manifest.json",
        "synthetic_item": SYNTHETIC,
        "requests": requests,
    }
    expectations = {
        "fixture": fixture_name,
        "workload_class": "W2",
        "concern": ("control-flow fidelity on a single request decided against an injected world "
                    "state, decomposed into comprehension / conditional fidelity / end-to-end "
                    "outcome. Routing is set membership, not arithmetic."),
        "min_environment": "E0",
        "oracle": "route_item",
        "catalog": {"hours_table": catalog["hours_table"], "teams": catalog["teams"]},
        "cases": [malformed] + cases,
    }
    return manifest, expectations


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true",
                    help="recompute and compare with what is on disk; write nothing")
    ap.add_argument("--repl", action="store_true",
                    help="build the REPLICATION arms instead (SS8.3 step 5): same twenty "
                         "frozen strata and worlds, items drawn from the sealed pool with "
                         f"seed {REPL_SEED}, written to support-routing-repl and "
                         "support-routing-notrace-repl. Requires the drawn strata to be "
                         "fillable with verified, non-tolerant REPLICATION items.")
    args = ap.parse_args()

    if args.repl:
        manifest, expectations = _build("REPLICATION", REPL_SEED,
                                        "fixture-w2-support-routing")
        _, expectations_nt = _build("REPLICATION", REPL_SEED,
                                    "fixture-w2-support-routing-notrace")
        targets = [(REPL_ROUTING_DIR / "items-manifest.json", manifest),
                   (REPL_ROUTING_DIR / "expectations.json", expectations),
                   (REPL_NOTRACE_DIR / "items-manifest.json", manifest),
                   (REPL_NOTRACE_DIR / "expectations.json", expectations_nt)]
    else:
        manifest, expectations = _build()
        targets = [(ROUTING_DIR / "items-manifest.json", manifest),
                   (ROUTING_DIR / "expectations.json", expectations)]

    if args.check:
        stale = []
        for path, data in targets:
            if not path.exists():
                stale.append(f"{path.name}: not on disk")
            elif json.loads(path.read_text(encoding="utf-8")) != data:
                stale.append(f"{path.name}: differs from what this script produces")
        if stale:
            sys.exit("\n".join(stale))
        print("items-manifest.json and expectations.json match the generator.")
        return

    for path, data in targets:
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n",
                        encoding="utf-8")
        print(f"  {path.relative_to(REPO_ROOT)}")

    actions = {}
    for r in manifest["requests"]:
        actions[r["expected_action"]] = actions.get(r["expected_action"], 0) + 1
    print(f"{len(manifest['requests'])} requests, seed {manifest['seed']}: " +
          ", ".join(f"{n} {a}" for a, n in sorted(actions.items())))
    print("Next: python tests/scripts/hydrate.py --mode requests"
          + (" --routing-dir tests/fixtures/w2-branching/support-routing-repl (e poi "
             "--routing-dir .../support-routing-notrace-repl)" if args.repl else ""))


if __name__ == "__main__":
    main()
