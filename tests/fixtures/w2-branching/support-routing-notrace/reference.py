#!/usr/bin/env python3
"""
reference.py — the oracle for w2-branching/support-routing.

Pure Python, no I/O beyond the CLI. Given ONE request already classified
(product, intent) -- either the VERIFIED ground truth or the classification a
model itself produced -- and the world state that request is decided against
(the hours left in the budget and the current state of the three teams),
deterministically reproduces the action, the team, and the resulting budget
that the SOL script must produce if executed faithfully.

Used in two ways, exactly as support-intake/reference.py is:
  1. With ground-truth classifications -> generates expectations.json's
     `expected_sequence` (the fidelity oracle) and `expected_output` (the
     end-to-end oracle).
  2. With the MODEL's OWN classification (extracted from its EVAL trace line
     by checker.py) -> re-derives what the model *should* have done given what
     it understood, isolating conditional fidelity (pure control flow) from
     comprehension.

The world state is an INPUT here and never an output fed back in. Chaining one
request's result into the next would make the runs dependent -- a wrong
decision on request 3 hands request 4 a false world, and twenty independent
trials collapse into one observation (SS4.5 of the protocol). The oracle
computes each request's world state, and the runner injects it.

Mirrors support-routing.md's SOL script instruction-for-instruction; any change
to the ROUTINE's branching logic must be mirrored here. checker.py carries its
own copy of this algorithm (it must never import a fixture's Python module) and
tests/toolchain/test_checker.py cross-checks the two.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Optional, TypedDict

NO_TEAM = "-"          # what the trace line carries where a team would go


class Classification(TypedDict):
    id: str
    product: str   # "P1".."P5" | "UNKNOWN"
    intent: str    # "BUG" | "FEATURE" | "QUESTION"


class Decision(TypedDict):
    id: str
    product: str
    intent: str
    hours: Optional[float]
    team: Optional[str]
    action: str    # ASSIGN | DEFER | NEEDS_INFO | ESCALATE | UNASSIGNED


class RequestResult(TypedDict):
    status: str
    item: Optional[Decision]
    remaining_hours: Optional[float]


def owner_of(product: str, teams: list[dict]) -> Optional[str]:
    """The team that accepts `product`, or None if no team does.

    Exactly one team accepts any product that is accepted at all -- the
    capability matrix is built that way and test_fixtures asserts it -- so the
    first match is the only match. None is not an error state: it is the
    structural gap that produces UNASSIGNED.
    """
    for team in teams:
        if product in team["accepts"]:
            return team["id"]
    return None


def pick_team(product: str, intent: str, teams: list[dict],
              team_states: dict) -> Optional[str]:
    """The routing decision, as set membership rather than arithmetic.

    Precedence, and this order is the point of the fixture: the team that owns
    the product comes before any team that merely backs it up, even when the
    owner is under strain and a backup is idle. A backup absorbs overflow only
    while OPEN -- a team already limited does not take other teams' work.
    """
    owner = owner_of(product, teams)
    if owner is None:
        return None
    owner_state = team_states.get(owner)
    if owner_state == "OPEN":
        return owner
    if owner_state == "LIMITED" and intent == "BUG":
        return owner
    for team in sorted(teams, key=lambda t: t["id"]):
        if product in team["backs_up"] and team_states.get(team["id"]) == "OPEN":
            return team["id"]
    return None


def route_item(item: Classification, remaining_hours: float, team_states: dict,
               catalog: dict) -> RequestResult:
    """The oracle. `item` must already carry {id, product, intent} -- this
    function does not classify, only executes the control flow that follows
    classification, exactly as support-routing.md's SOL script specifies it."""
    teams = catalog["teams"]
    hours_table = catalog["hours_table"]
    product, intent = item["product"], item["intent"]

    def decided(action: str, hours=None, team=None) -> RequestResult:
        return {"status": "OK",
                "item": {"id": item["id"], "product": product, "intent": intent,
                         "hours": hours, "team": team, "action": action},
                "remaining_hours": remaining_hours}

    if product == "UNKNOWN":
        return {"status": "OK",
                "item": {"id": item["id"], "product": "UNKNOWN", "intent": intent,
                         "hours": None, "team": None, "action": "NEEDS_INFO"},
                "remaining_hours": remaining_hours}

    if owner_of(product, teams) is None:
        return decided("UNASSIGNED")

    hours = hours_table[product][intent]
    fits = hours <= remaining_hours

    if intent == "BUG" and not fits:
        return decided("ESCALATE", hours=hours)
    if not fits:
        return decided("DEFER", hours=hours)

    team = pick_team(product, intent, teams, team_states)
    if team is None:
        return decided("DEFER", hours=hours)

    return {"status": "OK",
            "item": {"id": item["id"], "product": product, "intent": intent,
                     "hours": hours, "team": team, "action": "ASSIGN"},
            "remaining_hours": remaining_hours - hours}


def action_label(result: RequestResult) -> str:
    """The fidelity oracle's single label, matching the BRANCH trace format
    checker.py parses: 'item=<id> action=<action> team=<team>'.

    The team is part of the label because the team IS the decision this fixture
    adds. Left out of it, conditional fidelity would score a model that routed
    every request to the wrong team as perfect.
    """
    d = result["item"]
    return f"item={d['id']} action={d['action']} team={d['team'] or NO_TEAM}"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--request", required=True, type=Path,
                   help="JSON file: {'item': {id,title,body}, 'remaining_hours': n, "
                        "'teams': {T1: STATE, ...}} -- the staged payload, with "
                        "--classification supplying {product, intent}; or the same "
                        "object whose item already carries product and intent")
    p.add_argument("--classification", type=Path, default=None,
                   help="JSON file: {'product': ..., 'intent': ...} for the request")
    p.add_argument("--catalog", required=True, type=Path,
                   help="catalog.json (hours_table + teams)")
    args = p.parse_args()

    catalog = json.loads(args.catalog.read_text(encoding="utf-8"))
    payload = json.loads(args.request.read_text(encoding="utf-8"))
    item = dict(payload["item"])

    if args.classification:
        item.update(json.loads(args.classification.read_text(encoding="utf-8")))
    if "product" not in item or "intent" not in item:
        raise SystemExit("--classification is required when the item carries no "
                         "product/intent of its own")

    result = route_item(item, payload["remaining_hours"], payload["teams"], catalog)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    print()
    print("Sequence:", action_label(result))


if __name__ == "__main__":
    main()
