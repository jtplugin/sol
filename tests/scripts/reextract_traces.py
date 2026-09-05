#!/usr/bin/env python3
"""
Re-derive `trace.steps` from `output.raw` in records already on disk.

`trace.steps` is not an observation. The observation is `raw` -- the model's
text, byte for byte -- and the steps are the lines the runner picked out of it.
When the picking was wrong, the record holds a wrong derivation of a right
answer, and re-deriving it costs nothing on the GPU. Same principle, and the
same three-step chain, as the 2026-08-23 payload correction.

Written for the 2026-08-24 decoration correction. `_parse_trace` matched with
`_TRACE_LINE_RE.match(line.strip())`, anchored at position 0, so a trace line
wrapped in markdown --

    `[fixture-w2-support-intake][main] EVAL: item=item-241 product=P5 intent=BUG`
    - `[fixture-w2-support-intake][main] EVAL: item=item-213 product=P4 intent=FEATURE`

-- never reached the trace at all. The run then scored traced=False,
sequence_rate 0.0, comprehension and conditional not_checkable: not a bad run, an
unmeasurable one, which on a dashboard is indistinguishable from a model that
ignored the process. 61 of MAIN's runs carry a real trace under a wrapper, 60 of
them ministral-8b -- 29% of that model's campaign.

Two more recover only unsubstituted templates ('item={{item.id}}'). Those are not
executions, and once visible they score as wrong rather than absent. That is the
honest reading and it is not a side effect to be suppressed: the model did emit a
line, and the line is not an execution.

Affects everything read off the trace -- traced, sequence_rate, conditional_rate,
comprehension. `quality` and `degradation_mode` are read off the returned payload
and are not touched by this.

Order of operations, and none of it while a campaign is executing:

    python tests/scripts/reextract_traces.py   --results-root tests/results-main
    python tests/scripts/rescore.py            --results-root tests/results-main
    python tests/scripts/backfill_index_scores.py --index tests/results-main/index.jsonl --refresh

Usage:
    python tests/scripts/reextract_traces.py [--results-root PATH] [--dry-run]
"""
from __future__ import annotations
import argparse
import json
import sys
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "tests"))

from runner.runner import _parse_trace  # noqa: E402


def _kind(steps: list[str]) -> str:
    """A label for what the trace became, so the summary says more than a count."""
    if not steps:
        return "none"
    if all("{{" in s for s in steps):
        return "templates-only"
    if any("{{" in s for s in steps):
        return "mixed"
    return "real-values"


def reextract(results_root: Path, dry_run: bool = False) -> int:
    records = [p for p in sorted(results_root.rglob("*.json"))
               if not p.name.endswith(".score.json")
               and not p.name.startswith("campaign-")
               and not p.name.startswith(".")]
    print(f"records: {len(records)} under {results_root}")

    moves = Counter()
    stats = Counter()
    recovered_by_model = Counter()

    for path in records:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            print(f"  SKIP (unreadable): {path.name} -- {exc}")
            stats["unreadable"] += 1
            continue
        if not isinstance(data, dict) or "trace" not in data:
            stats["not a run record"] += 1
            continue

        raw = (data.get("output") or {}).get("raw") or ""
        # A run with no output has nothing to re-derive; leave it as it is
        # rather than writing an empty list over an empty list.
        if not raw.strip():
            stats["no raw"] += 1
            continue

        trace = data["trace"] or {}
        before = trace.get("steps") or []
        after = _parse_trace(raw)
        if before == after:
            stats["unchanged"] += 1
            continue

        moves[(_kind(before), _kind(after))] += 1
        stats["changed"] += 1
        if not before and after:
            model = (data.get("config") or {}).get("model_id", "?")
            recovered_by_model[model] += 1
        if dry_run:
            continue

        trace["steps"] = after
        data["trace"] = trace
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2),
                       encoding="utf-8")
        tmp.replace(path)

    print()
    for key, n in stats.most_common():
        print(f"  {key:20} {n:5}")
    if moves:
        print()
        print("  was -> is                              n")
        for (a, b), n in moves.most_common():
            print(f"    {a:16} -> {b:16} {n:5}")
    if recovered_by_model:
        print()
        print("  runs that gained a trace where they had none:")
        for model, n in recovered_by_model.most_common():
            print(f"    {model:52} {n:5}")
    if dry_run:
        print("\n[dry-run] nothing written")
    elif stats["changed"]:
        print(f"\nrewrote {stats['changed']} records. "
              f"Now run rescore.py, then backfill_index_scores.py --refresh.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--results-root", default=str(REPO_ROOT / "tests" / "results-main"),
                    type=Path)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    if not args.results_root.exists():
        print(f"no such results root: {args.results_root}", file=sys.stderr)
        return 1
    return reextract(args.results_root, args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
