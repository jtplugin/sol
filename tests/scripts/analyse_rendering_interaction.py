#!/usr/bin/env python3
"""
Does the rendering effect differ by model, and does prose-generated help the weak
at the strong's expense? (SS4.5 of the report, SS12 2026-08-29.)

The claim under test was asserted from an ordering of six points: prose-generated
beats the SOL ladder by +21pp for phi4-mini and loses 8pp for ministral-8b, and the
six per-mode deltas rank as the exact reverse of the six baselines. Six points and a
perfect reversal is the shape of a result and also the shape of an artefact, so this
script separates them.

THE UNIT IS THE ITEM. All twenty requests are run in every cell of the grid, so a
comparison between renderings is paired within item and the runs inside one item are
not independent of each other. Every interval here is a percentile bootstrap over
items resampled with replacement (twenty clusters, which is few -- the intervals are
correspondingly wide, and that is the honest width).

THE TRAP: delta-against-baseline is biased. `delta_m = P(pass | prose-generated) -
P(pass | SOL ladder)` shares its second term with the baseline it is plotted against,
so the two are negatively correlated before any model behaviour enters. Regression to
the mean alone would produce the reversal. Two independent baselines are used instead:

  (a) split-half -- baseline from rep01 of the SOL ladder, delta from rep02 only;
  (b) the untracked arm -- the same twenty items, same modes, same renderings, a
      wholly separate block (`support-routing-notrace`), so no run is shared.

A negative correlation that survives both is about the models. One that appears only
against the coupled baseline is arithmetic.

Floor and ceiling are a separate distortion and are not removed by an independent
baseline: a mode at 4% has more room above it than a mode at 63%. The correlation is
therefore reported on the log-odds scale as well, where equal odds-ratios are equal
distances, with the Haldane-Anscombe 0.5 correction for the empty cells.

Usage:
    python tests/scripts/analyse_rendering_interaction.py [--index PATH] [--boot N]
"""
from __future__ import annotations
import argparse
import collections
import json
import pathlib
import sys

import numpy as np

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]

ROUTING = "w2-branching/support-routing"
NOTRACE = "w2-branching/support-routing-notrace"
SOL_LADDER = [f"L{i}" for i in range(5)]
GENERATED = "prose-generated"
MECHANICAL = "prose-mechanical"


def load(index_path: pathlib.Path):
    """rows[fixture][mode][rendering][item] -> list of 0/1, one per repetition."""
    rows = collections.defaultdict(
        lambda: collections.defaultdict(
            lambda: collections.defaultdict(lambda: collections.defaultdict(list))))
    items = collections.defaultdict(set)
    with index_path.open(encoding="utf-8") as fh:
        for line in fh:
            r = json.loads(line)
            fix = r["fixture_id"]
            if fix not in (ROUTING, NOTRACE):
                continue
            iid = r["staged_input_id"]
            rows[fix][r["mode"]][r["process_rendering"]][iid].append(
                1 if r.get("quality") == "pass" else 0)
            items[fix].add(iid)
    return rows, {f: sorted(v) for f, v in items.items()}


def _rate(block, renderings, item_ids, reps=None):
    """Pass rate over the given renderings and items. `reps` selects repetition
    indices (None = all), which is how the split-half baseline is taken."""
    hit = tot = 0
    for d in renderings:
        for iid in item_ids:
            v = block.get(d, {}).get(iid, [])
            v = v if reps is None else [v[i] for i in reps if i < len(v)]
            hit += sum(v)
            tot += len(v)
    return (hit / tot) if tot else float("nan")


def _logit(p, hit=None, tot=None):
    """Log-odds with the Haldane-Anscombe correction when a cell is empty or full."""
    if hit is not None and tot:
        p = (hit + 0.5) / (tot + 1.0)
    p = min(max(p, 1e-9), 1 - 1e-9)
    return float(np.log(p / (1 - p)))


def _rate_logit(block, renderings, item_ids, reps=None):
    hit = tot = 0
    for d in renderings:
        for iid in item_ids:
            v = block.get(d, {}).get(iid, [])
            v = v if reps is None else [v[i] for i in reps if i < len(v)]
            hit += sum(v)
            tot += len(v)
    return _logit(None, hit, tot)


def statistics(rows, modes, item_ids, other_items, target=ROUTING, other=NOTRACE):
    """Every quantity this script reports, computed from one (possibly resampled)
    list of items. `target` is the block under test; `other` supplies the independent
    baseline of model strength -- the two arms share items, modes and renderings and
    no run appears in both. Returned flat so the bootstrap can stack it."""
    out = {}
    routing = rows[target]
    notrace = rows[other]
    for m in modes:
        b = routing[m]
        sol = _rate(b, SOL_LADDER, item_ids)
        gen = _rate(b, [GENERATED], item_ids)
        mech = _rate(b, [MECHANICAL], item_ids)
        out[f"sol:{m}"] = sol
        out[f"gen:{m}"] = gen
        out[f"mech:{m}"] = mech
        out[f"delta:{m}"] = gen - sol                       # the claim's quantity
        out[f"mech_minus_sol:{m}"] = mech - sol             # SOL == prose-mechanical?
        out[f"delta_logit:{m}"] = (_rate_logit(b, [GENERATED], item_ids)
                                   - _rate_logit(b, SOL_LADDER, item_ids))
        # independent baselines
        out[f"base_half:{m}"] = _rate(b, SOL_LADDER, item_ids, reps=[0])
        out[f"delta_half:{m}"] = gen - _rate(b, SOL_LADDER, item_ids, reps=[1])
        out[f"base_notrace:{m}"] = _rate(notrace[m], SOL_LADDER, other_items)

    deltas = np.array([out[f"delta:{m}"] for m in modes])
    out["spread"] = float(deltas.max() - deltas.min())
    return out


def _spearman(x, y):
    x, y = np.asarray(x, float), np.asarray(y, float)
    if np.isnan(x).any() or np.isnan(y).any():
        return float("nan")

    def rank(a):
        order = a.argsort()
        r = np.empty(len(a), float)
        r[order] = np.arange(len(a), dtype=float)
        # average ties
        for v in np.unique(a):
            k = a == v
            if k.sum() > 1:
                r[k] = r[k].mean()
        return r
    rx, ry = rank(x), rank(y)
    if rx.std() == 0 or ry.std() == 0:
        return float("nan")
    return float(np.corrcoef(rx, ry)[0, 1])


def _exact_spearman_p(rho, n):
    """Two-sided p by exhaustive permutation. n<=8 only -- 8! = 40,320."""
    from itertools import permutations
    base = np.arange(n, dtype=float)
    hits = tot = 0
    for perm in permutations(range(n)):
        r = _spearman(base, np.array(perm, float))
        tot += 1
        if abs(r) >= abs(rho) - 1e-12:
            hits += 1
    return hits / tot


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--index", type=pathlib.Path,
                    default=REPO_ROOT / "tests" / "results-main" / "index.jsonl")
    ap.add_argument("--boot", type=int, default=20000)
    ap.add_argument("--seed", type=int, default=20260829)
    ap.add_argument("--block", choices=("tracked", "untracked"), default="tracked",
                    help="which arm carries the renderings under test; the other arm "
                         "supplies the independent baseline")
    args = ap.parse_args()

    rows, items = load(args.index)
    target, other = ((ROUTING, NOTRACE) if args.block == "tracked"
                     else (NOTRACE, ROUTING))
    if target not in rows:
        print(f"no {target} rows in {args.index}", file=sys.stderr)
        return 1
    modes = sorted(rows[target])
    item_ids = items[target]
    notrace_items = items[other]
    print(f"index      : {args.index}")
    print(f"under test : {target}")
    print(f"baseline   : {other}  (independent -- no run is shared)")
    print(f"modes      : {len(modes)}   items: {len(item_ids)}   bootstrap: {args.boot}")

    point = statistics(rows, modes, item_ids, notrace_items, target, other)

    rng = np.random.default_rng(args.seed)
    keys = sorted(point)
    draws = {k: np.empty(args.boot) for k in keys}
    corr = {k: np.empty(args.boot) for k in ("coupled", "half", "notrace", "logit")}
    idx = np.arange(len(item_ids))
    for b in range(args.boot):
        take = [item_ids[i] for i in rng.choice(idx, len(idx), replace=True)]
        nt = [notrace_items[i] for i in rng.choice(len(notrace_items),
                                                   len(notrace_items), replace=True)]
        s = statistics(rows, modes, take, nt, target, other)
        for k in keys:
            draws[k][b] = s[k]
        d = [s[f"delta:{m}"] for m in modes]
        corr["coupled"][b] = _spearman([s[f"sol:{m}"] for m in modes], d)
        corr["half"][b] = _spearman([s[f"base_half:{m}"] for m in modes],
                                    [s[f"delta_half:{m}"] for m in modes])
        corr["notrace"][b] = _spearman([s[f"base_notrace:{m}"] for m in modes], d)
        corr["logit"][b] = _spearman([s[f"base_notrace:{m}"] for m in modes],
                                     [s[f"delta_logit:{m}"] for m in modes])

    def ci(a):
        a = a[~np.isnan(a)]
        return np.percentile(a, 2.5), np.percentile(a, 97.5)

    print("\n=== 1. Per mode: prose-generated minus the SOL ladder (percentage points)")
    print(f"{'mode':26s}{'SOL':>8s}{'p-gen':>8s}{'delta':>9s}{'95% CI':>18s}")
    for m in modes:
        lo, hi = ci(draws[f"delta:{m}"])
        star = "  *" if lo > 0 or hi < 0 else ""
        print(f"{m[:26]:26s}{100*point[f'sol:{m}']:7.1f}%{100*point[f'gen:{m}']:7.1f}%"
              f"{100*point[f'delta:{m}']:+8.1f}  [{100*lo:+6.1f},{100*hi:+6.1f}]{star}")
    print("   * = interval excludes zero")

    print("\n=== 2. Is the SOL ladder the same as prose-mechanical? (mech minus SOL)")
    for m in modes:
        lo, hi = ci(draws[f"mech_minus_sol:{m}"])
        star = "  *" if lo > 0 or hi < 0 else ""
        print(f"{m[:26]:26s}{100*point[f'mech_minus_sol:{m}']:+8.1f}"
              f"  [{100*lo:+6.1f},{100*hi:+6.1f}]{star}")

    print("\n=== 3. The crossover as a pre-specified contrast")
    order = sorted(modes, key=lambda m: point[f"sol:{m}"])
    weak, strong = order[0], order[-1]
    d = draws[f"delta:{weak}"] - draws[f"delta:{strong}"]
    lo, hi = ci(d)
    obs = point[f"delta:{weak}"] - point[f"delta:{strong}"]
    print(f"   weakest on the ladder : {weak} ({100*point[f'sol:{weak}']:.1f}%)")
    print(f"   strongest             : {strong} ({100*point[f'sol:{strong}']:.1f}%)")
    print(f"   delta difference      : {100*obs:+.1f} pp   95% CI [{100*lo:+.1f},{100*hi:+.1f}]"
          f"   {'EXCLUDES 0' if lo > 0 or hi < 0 else 'includes 0'}")
    lo, hi = ci(draws["spread"])
    print(f"   spread of the six deltas: {100*point['spread']:.1f} pp"
          f"   95% CI [{100*lo:.1f},{100*hi:.1f}]")

    print("\n=== 4. 'Helps the weak, costs the strong': the correlation, three baselines")
    labels = {
        "coupled": "baseline = SOL rate (COUPLED -- biased, shown to be discounted)",
        "half":    "baseline = SOL rep01, delta from rep02 (split-half, independent)",
        "notrace": "baseline = the OTHER arm (separate block, fully independent)",
        "logit":   "as above, delta on the log-odds scale (floor/ceiling)",
    }
    base_pt = {
        "coupled": ([point[f"sol:{m}"] for m in modes], [point[f"delta:{m}"] for m in modes]),
        "half":    ([point[f"base_half:{m}"] for m in modes],
                    [point[f"delta_half:{m}"] for m in modes]),
        "notrace": ([point[f"base_notrace:{m}"] for m in modes],
                    [point[f"delta:{m}"] for m in modes]),
        "logit":   ([point[f"base_notrace:{m}"] for m in modes],
                    [point[f"delta_logit:{m}"] for m in modes]),
    }
    n = len(modes)
    for k, lab in labels.items():
        rho = _spearman(*base_pt[k])
        lo, hi = ci(corr[k])
        p = _exact_spearman_p(rho, n)
        print(f"   rho = {rho:+.3f}   95% CI [{lo:+.3f},{hi:+.3f}]   exact p = {p:.4f}   {lab}")
    import math
    print(f"\n   n = {n} modes. With six points the tightest a two-sided exact test can reach is"
          f" p = {2/math.factorial(n):.4f}, and that is what a PERFECT reversal buys."
          "\n   The ceiling of the evidence is set by the grid, not by the effect.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
