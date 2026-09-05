#!/usr/bin/env python3
"""
Re-derive `output.returned_payload` from `output.raw` in records already on disk.

`returned_payload` is not an observation. The observation is `raw` -- the model's
text, byte for byte -- and the payload is what the runner cut out of it. When the
cutting was wrong, the record holds a wrong derivation of a right answer, and
re-deriving it costs nothing on the GPU.

Written for the 2026-08-23 extraction correction. `_extract_payload` matched
braces with a non-greedy regex, so on the shape every tracing model produced --

    [fixture-...][main] EVAL: ...
    {"status": "OK", "items": [{"id": "item-241", ...}, ...], ...}

-- it stopped at the closing brace of the first item, failed to parse, resumed
after it, and returned the SECOND item as the payload. A well-formed dict, and
not the answer. 204 of MAIN's 1023 non-thinking runs were scored against a
fragment of their own output; qwen3.5-9b-nothink looked like it returned a
payload 27% of the time when the true figure is 85%.

Only `quality` and `degradation_mode` were affected. Everything read off the
trace -- comprehension, sequence_rate, conditional_rate, traced -- never touched
this field.

Order of operations, and none of it while a campaign is executing:

    python tests/scripts/reextract_payloads.py --results-root tests/results-main
    python tests/scripts/rescore.py            --results-root tests/results-main
    python tests/scripts/backfill_index_scores.py --index tests/results-main/index.jsonl --refresh

Usage:
    python tests/scripts/reextract_payloads.py [--results-root PATH] [--dry-run]
"""
from __future__ import annotations
import argparse
import json
import sys
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "tests"))

from runner.runner import _extract_payload  # noqa: E402


def _shape(payload) -> str:
    """A label for what came out, so the summary says more than a count."""
    if payload is None:
        return "none"
    if not isinstance(payload, dict):
        return "not-a-dict"
    if "status" in payload:
        return "returned-object"
    if "id" in payload and "action" in payload:
        return "item-fragment"
    return "other"


def reextract(results_root: Path, dry_run: bool = False) -> int:
    records = [p for p in sorted(results_root.rglob("*.json"))
               if not p.name.endswith(".score.json")
               and not p.name.startswith("campaign-")
               and not p.name.startswith(".")]
    print(f"records: {len(records)} under {results_root}")

    moves = Counter()
    stats = Counter()

    for path in records:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            print(f"  SKIP (unreadable): {path.name} -- {exc}")
            stats["unreadable"] += 1
            continue
        if not isinstance(data, dict) or "output" not in data:
            stats["not a run record"] += 1
            continue

        output = data["output"] or {}
        raw = output.get("raw") or ""
        # A run with no output has nothing to re-derive; leave it as it is
        # rather than writing null over null.
        if not raw.strip():
            stats["no raw"] += 1
            continue

        before = output.get("returned_payload")
        after = _extract_payload(raw)
        if before == after:
            stats["unchanged"] += 1
            continue

        moves[(_shape(before), _shape(after))] += 1
        stats["changed"] += 1
        if dry_run:
            continue

        output["returned_payload"] = after
        data["output"] = output
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2),
                       encoding="utf-8")
        tmp.replace(path)

    print()
    for key, n in stats.most_common():
        print(f"  {key:20} {n:5}")
    if moves:
        print()
        print("  was -> is                            n")
        for (a, b), n in moves.most_common():
            print(f"    {a:16} -> {b:16} {n:5}")
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
