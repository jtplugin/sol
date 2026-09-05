#!/usr/bin/env python3
"""
select_repl_candidates.py — the REPLICATION items to verify before the repl draw.

SS8.3 step 5 opens the sealed half of the pool, and the routing strata need
verified, non-tolerant items exactly as MAIN's did (build_requests.py). None of
the 150 REPLICATION items has been manually verified — verification on MAIN was
restricted to the items a model actually consumes, and REPLICATION consumed
nothing. This script picks WHO gets verified, before any judgment is made:

  for each (product, intent) pair the frozen strata require, take the pair's
  REPLICATION candidates (by their NLBSE label), shuffle with the declared
  seed, keep need + 2.

The +2 is headroom: a manual judgment can flip an item's label or mark it
tolerant, and either removes it from the eligible set. If a pair still runs
short after verification, rerun with --headroom 4 and verify only the new ids.

Selection precedes judgment, which is what keeps the two-stage procedure
unbiased: the seed chooses the candidates, the human judges them blind to any
model behaviour (no model has ever seen a REPLICATION item), and the draw in
build_requests.py --repl then operates on the verified survivors only.

Output: tests/data-local/repl-candidates.json (gitignored — ids only, no text).
Usage:
    python tests/scripts/select_repl_candidates.py [--headroom 2]
Then: python tests/scripts/build_verification_html.py --repl
"""
from __future__ import annotations

import argparse
import json
import random
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
INTAKE_DIR = REPO_ROOT / "tests" / "fixtures" / "w2-branching" / "support-intake"
ROUTING_DIR = REPO_ROOT / "tests" / "fixtures" / "w2-branching" / "support-routing"
DATA_LOCAL = REPO_ROOT / "tests" / "data-local"

SEED = 20260827   # same declared seed as the repl draw (build_requests.REPL_SEED)


def needed_pairs() -> Counter:
    """(product, intent) -> how many distinct items the frozen strata consume.

    Read from build_requests.STRATA rather than restated, so the two can never
    drift. The off-catalog stratum (product None) draws no pool item.
    """
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "_build_requests", Path(__file__).parent / "build_requests.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    need = Counter()
    for _req, _stratum, product, intent, _world in mod.STRATA:
        if product is not None:
            need[(product, intent)] += 1
    return need


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--headroom", type=int, default=2,
                    help="extra candidates per (product, intent) pair beyond the "
                         "strata's need [default: 2]")
    args = ap.parse_args()

    pool = json.loads((INTAKE_DIR / "pool-manifest.json").read_text(encoding="utf-8"))["items"]
    catalog = json.loads((ROUTING_DIR / "catalog.json").read_text(encoding="utf-8"))
    repo_of = {v: k for k, v in catalog["product_to_repo"].items()}

    need = needed_pairs()
    rng = random.Random(SEED)
    picked: dict[str, list[str]] = {}
    short = []
    for (product, intent), n in sorted(need.items()):
        cands = sorted(
            i["id"] for i in pool
            if i["split"] == "REPLICATION"
            and repo_of[i["repo"]] == product
            and i["nlbse_label"].upper() == intent)
        rng.shuffle(cands)
        take = cands[: n + args.headroom]
        if len(take) < n:
            short.append(f"{product}/{intent}: need {n}, only {len(take)} candidates")
        picked[f"{product}/{intent}"] = take

    if short:
        raise SystemExit("pool cannot cover the strata:\n  " + "\n  ".join(short))

    ids = sorted({i for lst in picked.values() for i in lst})
    out = {
        "_comment": __doc__.strip().splitlines()[0],
        "seed": SEED,
        "headroom": args.headroom,
        "pairs": picked,
        "ids": ids,
    }
    out_path = DATA_LOCAL / "repl-candidates.json"
    out_path.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{len(ids)} candidates over {len(picked)} pairs -> {out_path.relative_to(REPO_ROOT)}")
    print("Next: python tests/scripts/build_verification_html.py --repl")


if __name__ == "__main__":
    main()
