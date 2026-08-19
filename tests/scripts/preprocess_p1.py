#!/usr/bin/env python3
"""
preprocess_p1.py — P1: deterministic Python cleaning, no LLM.

Regex and parsers only: GitHub issue-template headers (HTML comments), code
blocks -> [code], stack traces, images and URLs -> [image], quoted replies,
signatures, whitespace collapsing, truncation to a fixed character budget.

Deliberately no LLM here: a model instructed to "just clean" still makes
semantic choices, and deciding what counts as noise is already half of
comprehension (doc/experiment-minimum-context.md SS5.2). Only a deterministic
cleaner can be audited line by line and honestly called frozen.

Emits a per-item token-savings report (a char/4 heuristic -- NOT a real
tokenizer; documented as an approximation, no new dependency for it).

Usage:
    python3 tests/scripts/preprocess_p1.py --pool tests/data-local/pool-main.json
    python3 tests/scripts/preprocess_p1.py --pool tests/data-local/pool-main.json --budget 800
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BUDGET = 800  # chars, title excluded -- see doc/experiment-minimum-context.md SS4.1/SS8.1 (card notes 6)

_HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
_CODE_FENCE_RE = re.compile(r"```.*?```", re.DOTALL)
_MD_IMAGE_RE = re.compile(r"!\[[^\]]*\]\([^)]+\)")
_URL_RE = re.compile(r"https?://\S+")
_SIGNOFF_RE = re.compile(r"\n--\s*\n.*", re.DOTALL)
# Common stack-trace line shapes: "  at foo (bar.js:12:3)", "Traceback (most recent call last):",
# "  File \"x.py\", line 3, in <module>", "    at java.base/... "
_STACK_LINE_RE = re.compile(
    r"^\s*(at\s+\S+.*\(.*:\d+.*\)|File \"[^\"]+\", line \d+|Traceback \(most recent call last\):)"
)


def _approx_tokens(text: str) -> int:
    """Rough char/4 heuristic -- NOT a real tokenizer. Good enough for a
    relative before/after comparison, not for absolute budgeting."""
    return max(1, len(text) // 4)


def _collapse_stack_traces(text: str) -> str:
    out_lines: list[str] = []
    in_trace = False
    for line in text.splitlines():
        if _STACK_LINE_RE.match(line):
            if not in_trace:
                out_lines.append("[stacktrace]")
                in_trace = True
            continue
        in_trace = False
        out_lines.append(line)
    return "\n".join(out_lines)


def clean_body(body: str, budget: int) -> tuple[str, bool]:
    text = body or ""
    text = _HTML_COMMENT_RE.sub("", text)
    text = _CODE_FENCE_RE.sub("[code]", text)
    text = _collapse_stack_traces(text)
    text = _MD_IMAGE_RE.sub("[image]", text)
    text = _URL_RE.sub("[image]", text)  # protocol SS5.2: images AND URLs -> [image]
    text = "\n".join(line for line in text.splitlines() if not line.strip().startswith(">"))
    text = _SIGNOFF_RE.sub("", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = text.strip()
    truncated = len(text) > budget
    return text[:budget], truncated


def process_pool(pool: list[dict], budget: int) -> tuple[list[dict], list[dict]]:
    corpus = []
    report = []
    for row in pool:
        title = row["title"]
        body_before = row["body"] or ""
        body_after, truncated = clean_body(body_before, budget)

        corpus.append({
            "id": row["id"],
            "title": title,
            "body": body_after,
        })
        tok_before = _approx_tokens(title) + _approx_tokens(body_before)
        tok_after = _approx_tokens(title) + _approx_tokens(body_after)
        report.append({
            "id": row["id"],
            "chars_before": len(body_before),
            "chars_after": len(body_after),
            "approx_tokens_before": tok_before,
            "approx_tokens_after": tok_after,
            "approx_tokens_saved": tok_before - tok_after,
            "truncated": truncated,
        })
    return corpus, report


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--pool", required=True, type=Path, help="pool-main.json (or -replication.json)")
    p.add_argument("--budget", type=int, default=DEFAULT_BUDGET, help="char budget for the cleaned body")
    p.add_argument("--out", type=Path, default=None, help="output corpus path [default: <pool>.p1.json next to input]")
    p.add_argument("--report", type=Path, default=None, help="output report path [default: <pool>.p1-report.json]")
    args = p.parse_args()

    if not args.pool.exists():
        sys.exit(f"Pool file not found: {args.pool}")

    pool = json.loads(args.pool.read_text(encoding="utf-8"))
    corpus, report = process_pool(pool, args.budget)

    out_path = args.out or args.pool.with_suffix(".p1.json")
    report_path = args.report or args.pool.with_suffix(".p1-report.json")
    out_path.write_text(json.dumps(corpus, indent=2, ensure_ascii=False), encoding="utf-8")
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    total_saved = sum(r["approx_tokens_saved"] for r in report)
    avg_saved = total_saved / len(report) if report else 0
    n_truncated = sum(1 for r in report if r["truncated"])
    print(f"P1 corpus: {len(corpus)} items -> {out_path}")
    print(f"Report: {report_path}")
    print(f"Approx tokens saved: {total_saved} total, {avg_saved:.1f} avg/item, {n_truncated}/{len(report)} truncated")


if __name__ == "__main__":
    main()
