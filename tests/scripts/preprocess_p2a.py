#!/usr/bin/env python3
"""
preprocess_p2a.py — P2a: neutral AI condensation. WRITTEN, NOT RUN.

*** NOT EXECUTED ON THE CORPUS THIS SESSION. ***
doc/experiment-minimum-context.md SS5.2 / SS8.1: P1 and P2a are frozen,
pre-computed offline corpora. This script exists so P2a *can* be produced
later, in its own step, after the pool is finally verified (item 2.6) --
running it now would burn API budget on a provisional pool that will be
regenerated.

A model cleans and condenses each item's title+body, WITHOUT access to the
product catalog (catalog.json is never shown to it) and WITHOUT being told
what the downstream task is. It supplies clean text, never pre-comprehension
-- if the preprocessor already resolved product/intent, the fixture would
stop measuring SOL (this is why P2b -- AI that knows the products -- is
excluded entirely, SS3).

Reuses the same tests/env.json mode convention as the rest of tests/runner/
(--mode reads key/url/model/backend from tests/env.json) but does NOT touch
the fixture/runner pipeline: this is a plain text transform, not a SOL
execution, so it talks to the API directly rather than through
RunRecord/checker.

Usage (when actually run, in its own step):
    python3 tests/scripts/preprocess_p2a.py \\
        --pool tests/data-local/pool-main.json \\
        --mode claude-api-thinking
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

REPO_ROOT = Path(__file__).resolve().parents[2]
ENV_PATH = REPO_ROOT / "tests" / "env.json"

SYSTEM_PROMPT = (
    "You clean and condense raw software issue-tracker text. Output ONLY the "
    "condensed text, no preamble, no markdown fences, no commentary. "
    "Preserve every fact needed to later classify the issue's TYPE (is it "
    "reporting a bug, requesting a feature, or asking a question?) and its "
    "technical substance. Remove noise: greetings, signatures, repeated "
    "template boilerplate, and redundant phrasing. "
    "Do NOT guess or state what software project, product, or library this "
    "issue is about -- you do not have that information and must not invent "
    "it. Do not add labels, categories, or any text beyond the condensed "
    "issue itself."
)

USER_TEMPLATE = "Title: {title}\n\nBody:\n{body}"


def _approx_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def _load_mode(mode: str) -> tuple[str, str, str, str]:
    if not ENV_PATH.exists():
        sys.exit(f"env.json not found at {ENV_PATH}")
    env = json.loads(ENV_PATH.read_text(encoding="utf-8"))
    for entry in env.get("modes", []):
        if entry.get("mode") == mode:
            return entry.get("key", ""), entry.get("url", "https://api.anthropic.com"), \
                entry.get("model", "claude-opus-4-8"), entry.get("backend", "anthropic")
    sys.exit(f"Mode '{mode}' not found in env.json")


def _condense_one(api_key: str, api_url: str, model: str, title: str, body: str) -> str:
    """Single condensation call via the anthropic SDK (falls back to urllib),
    mirroring tests/runner/api_executor.py's minimal HTTP path."""
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key, base_url=api_url)
        resp = client.messages.create(
            model=model, max_tokens=1024, system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": USER_TEMPLATE.format(title=title, body=body)}],
        )
        return "".join(b.text for b in resp.content if getattr(b, "type", None) == "text")
    except ImportError:
        import urllib.request
        payload = json.dumps({
            "model": model, "max_tokens": 1024, "system": SYSTEM_PROMPT,
            "messages": [{"role": "user", "content": USER_TEMPLATE.format(title=title, body=body)}],
        }).encode()
        req = urllib.request.Request(
            api_url.rstrip("/") + "/v1/messages", data=payload,
            headers={"x-api-key": api_key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            out = json.loads(resp.read().decode())
        return "".join(b.get("text", "") for b in out.get("content", []) if b.get("type") == "text")


def process_pool(pool: list[dict], api_key: str, api_url: str, model: str, sleep_s: float) -> tuple[list[dict], list[dict]]:
    corpus, report = [], []
    for row in pool:
        body_before = row["body"] or ""
        condensed = _condense_one(api_key, api_url, model, row["title"], body_before)
        corpus.append({"id": row["id"], "title": row["title"], "body": condensed})
        tok_before = _approx_tokens(row["title"]) + _approx_tokens(body_before)
        tok_after = _approx_tokens(row["title"]) + _approx_tokens(condensed)
        report.append({
            "id": row["id"], "chars_before": len(body_before), "chars_after": len(condensed),
            "approx_tokens_before": tok_before, "approx_tokens_after": tok_after,
            "approx_tokens_saved": tok_before - tok_after,
        })
        if sleep_s:
            time.sleep(sleep_s)
    return corpus, report


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--pool", required=True, type=Path)
    p.add_argument("--mode", required=True, help="Mode name from tests/env.json")
    p.add_argument("--sleep", type=float, default=0.0, help="Seconds to sleep between calls (rate limiting)")
    p.add_argument("--out", type=Path, default=None)
    p.add_argument("--report", type=Path, default=None)
    args = p.parse_args()

    if not args.pool.exists():
        sys.exit(f"Pool file not found: {args.pool}")

    api_key, api_url, model, backend = _load_mode(args.mode)
    if backend != "anthropic":
        sys.exit(f"P2a condensation requires an anthropic-compatible backend, got '{backend}'")

    pool = json.loads(args.pool.read_text(encoding="utf-8"))
    corpus, report = process_pool(pool, api_key, api_url, model, args.sleep)

    out_path = args.out or args.pool.with_suffix(".p2a.json")
    report_path = args.report or args.pool.with_suffix(".p2a-report.json")
    out_path.write_text(json.dumps(corpus, indent=2, ensure_ascii=False), encoding="utf-8")
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"P2a corpus: {len(corpus)} items -> {out_path}")


if __name__ == "__main__":
    main()
