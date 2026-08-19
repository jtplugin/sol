#!/usr/bin/env python3
"""
reference.py — the oracle for w2-branching/support-intake.

Pure Python, no I/O beyond the CLI. Given a queue of items already classified
(product, intent) -- either the VERIFIED ground truth or the classifications a
model itself produced -- deterministically reproduces the exact sequence of
actions, the running budget, and the halt point that the SOL script must
follow if executed faithfully.

Used in two ways:
  1. With ground-truth classifications -> generates expectations.json's
     `expected_sequence` (the fidelity oracle) and `expected_output` (the
     end-to-end oracle).
  2. With the MODEL's OWN classifications (extracted from its EVAL trace
     lines by checker.py) -> re-derives what the model *should* have done
     given what it understood, isolating conditional fidelity (pure
     control-flow) from comprehension.

Mirrors support-intake.md's SOL script instruction-for-instruction; any
change to the ROUTINE's branching logic must be mirrored here.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Optional, TypedDict


class Classification(TypedDict):
    id: str
    product: str   # "P1".."P5" | "UNKNOWN"
    intent: str    # "BUG" | "FEATURE" | "QUESTION"


class ActionRecord(TypedDict):
    id: str
    product: str
    intent: str
    hours: Optional[float]
    action: str    # "ASSIGN" | "DEFER" | "NEEDS_INFO" | "ESCALATE"


class QueueResult(TypedDict):
    status: str
    items: list
    remaining_hours: Optional[float]
    halted_at: Optional[str]


def run_queue(items: list[Classification], budget_hours: float, hours_table: dict) -> QueueResult:
    """The oracle. items must already carry {id, product, intent} -- this
    function does not classify, only executes the control flow that follows
    classification (estimate-effort, check-budget, WHEN), exactly as
    support-intake.md's SOL script specifies it."""
    remaining = budget_hours
    halted_at: Optional[str] = None
    out: list[ActionRecord] = []

    for item in items:
        product = item["product"]
        intent = item["intent"]

        if product == "UNKNOWN":
            out.append({"id": item["id"], "product": "UNKNOWN", "intent": intent,
                        "hours": None, "action": "NEEDS_INFO"})
            continue

        hours = hours_table[product][intent]
        fits = hours <= remaining

        if intent == "BUG" and not fits:
            halted_at = item["id"]
            out.append({"id": item["id"], "product": product, "intent": intent,
                        "hours": hours, "action": "ESCALATE"})
            break
        elif fits:
            remaining -= hours
            out.append({"id": item["id"], "product": product, "intent": intent,
                        "hours": hours, "action": "ASSIGN"})
        else:
            out.append({"id": item["id"], "product": product, "intent": intent,
                        "hours": hours, "action": "DEFER"})

    return {"status": "OK", "items": out, "remaining_hours": remaining, "halted_at": halted_at}


def action_sequence(result: QueueResult) -> list[str]:
    """The fidelity oracle: one label per processed item, in order.
    Matches the BRANCH trace format checker.py parses:
    'item=<id> action=<action>'."""
    return [f"item={r['id']} action={r['action']}" for r in result["items"]]


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--queue", required=True, type=Path,
                   help="JSON file: either {'queue': [{id,title,body},...]} with a sibling "
                        "'--classifications' file, or directly [{id,product,intent},...]")
    p.add_argument("--classifications", type=Path, default=None,
                   help="JSON file: [{id, product, intent}, ...], one per queue item, in order")
    p.add_argument("--catalog", required=True, type=Path,
                   help="catalog.json (hours_table + budget_hours)")
    args = p.parse_args()

    catalog = json.loads(args.catalog.read_text(encoding="utf-8"))
    hours_table = catalog["hours_table"]
    budget_hours = catalog["budget_hours"]

    raw = json.loads(args.queue.read_text(encoding="utf-8"))
    if isinstance(raw, dict) and "queue" in raw:
        if not args.classifications:
            raise SystemExit("--classifications is required when --queue is a raw {id,title,body} queue")
        items = json.loads(args.classifications.read_text(encoding="utf-8"))
    else:
        items = raw

    result = run_queue(items, budget_hours, hours_table)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    print()
    print("Sequence:", " | ".join(action_sequence(result)))


if __name__ == "__main__":
    main()
