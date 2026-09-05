"""
Checker: RunRecord + expectations.json  →  ScoreRecord.
Pure Python, no model, no I/O — testable in full isolation (R1).
"""
from __future__ import annotations
import re
import statistics
from collections import defaultdict
from typing import Optional

from runner.schema import (
    RunRecord, ScoreRecord,
    FidelityCheck, QualityCheck, EfficiencyRecord,
)

_REFUSAL_RE = re.compile(
    r"\b(cannot|can'?t|unable to|don'?t have access|not able to|"
    r"impossible|I cannot|I'?m unable)\b",
    re.I,
)

# Parses: [<fixture>][<scope>] BRANCH: <label>
_BRANCH_RE = re.compile(r"\[[^\]]+\]\[[^\]]+\]\s+BRANCH:\s*(.+)")

# --- Sequence-oracle parsing (W2 state-accumulation fixtures, e.g. support-intake) ---
# Parses: [<fixture>][<scope>] EVAL: item=<id> product=<p> intent=<i>
_EVAL_ITEM_RE = re.compile(r"EVAL:\s*item=(\S+)\s+product=(\S+)\s+intent=(\S+)")
# Parses: [<fixture>][<scope>] BRANCH: item=<id> action=<action> [team=<t>] remaining=<n>
# `team=` is optional and appears only on support-routing, which chooses one
# (SS4.5 of the protocol). support-intake emits no team and its labels are
# unaffected: the group is None and the label is built without it.
_BRANCH_ITEM_RE = re.compile(r"BRANCH:\s*item=(\S+)\s+action=(\S+)(?:\s+team=(\S+))?\s+remaining=(\S+)")


def check(record: RunRecord, expectations: dict) -> ScoreRecord:
    """Score a single run-record against the fixture's expectations."""
    fid   = record.config.fixture_id
    iid   = record.staged_input_id
    ctx   = record.config.context
    model = record.config.model_id

    case = _find_case(expectations, iid)

    efficiency = EfficiencyRecord(
        wall_clock_ms=record.execution.wall_clock_ms,
        tokens_in=record.usage.tokens_in,
        tokens_out=record.usage.tokens_out,
        cost=record.usage.cost,
    )

    # --- N/A: was not attempted ---
    if record.execution.status == "na":
        return ScoreRecord(
            run_id=record.run_id, fixture_id=fid, staged_input_id=iid,
            context=ctx, model_id=model,
            fidelity=FidelityCheck("not_checkable"),
            quality=QualityCheck("not_checkable"),
            efficiency=efficiency,
            degradation_mode="na",
        )

    # --- execution error / timeout / connection error ---
    if record.execution.status in ("error", "timeout", "connection-error"):
        expected_output = case.get("expected_output") if case else None
        degrade = {
            "timeout":          "timeout",
            "connection-error": "connection-error",
        }.get(record.execution.status, "execution-error")
        return ScoreRecord(
            run_id=record.run_id, fixture_id=fid, staged_input_id=iid,
            context=ctx, model_id=model,
            fidelity=FidelityCheck("not_checkable"),
            quality=QualityCheck("fail", expected=expected_output),
            efficiency=efficiency,
            degradation_mode=degrade,
        )

    # --- normal run ---
    expected_output = case.get("expected_output") if case else None
    payload = record.output.returned_payload

    # Quality: compare full payload against expected_output object
    if payload is None:
        raw = record.output.raw or ""
        degrade = "refused" if _REFUSAL_RE.search(raw) else "no-output"
        quality = QualityCheck("not_checkable", expected=expected_output, got=None)
    elif not isinstance(payload, dict):
        quality = QualityCheck("fail", expected=expected_output, got=payload)
        degrade = "garbled-output"
    elif expected_output is None:
        quality = QualityCheck("not_checkable", expected=None, got=payload)
        degrade = "none"
    else:
        match = all(payload.get(k) == v for k, v in expected_output.items())
        if match:
            extra_keys = set(payload.keys()) - set(expected_output.keys())
            degrade = "extra-fields" if extra_keys else "none"
            quality = QualityCheck("pass", expected=expected_output, got=payload)
        elif _match_format_coerced(payload, expected_output):
            quality = QualityCheck("fail", expected=expected_output, got=payload)
            degrade = "wrong-format"
        elif _match_nested(payload, expected_output):
            quality = QualityCheck("fail", expected=expected_output, got=payload)
            degrade = "wrong-structure"
        else:
            quality = QualityCheck("fail", expected=expected_output, got=payload)
            degrade = "wrong-value"

    # Field-level agreement (SS12 2026-08-25): the graded reading of the same
    # comparison. Only where there is a measurement to make -- an expected
    # object and a returned payload; a run that returned nothing keeps None,
    # absence of a measurement rather than a zero (the comprehension lesson,
    # SS12 2026-08-23).
    if expected_output is not None and payload is not None:
        quality.rate = _field_rate(payload, expected_output)

    # Fidelity: check BRANCH trace entry against expected trace_branch_label
    fidelity = _check_fidelity(record.trace, case)
    comprehension = None

    # Sequence-oracle path (W2 state-accumulation fixtures): only engages when
    # the case carries `expected_sequence` -- single-branch fixtures (scalar
    # `trace_branch_label`) are untouched and keep the fidelity computed above.
    seq_fidelity = _check_sequence_fidelity(record.trace, case)
    if seq_fidelity is not None:
        fidelity = seq_fidelity
        cond = _check_conditional_fidelity(
            record.trace, expectations.get("catalog"), case,
            expectations.get("oracle", "run_queue"))
        fidelity.conditional_rate = cond["conditional_rate"]
        fidelity.conditional_expected_sequence = cond["conditional_expected_sequence"]
        fidelity.conditional_observed_sequence = cond["conditional_observed_sequence"]

        comprehension = _check_comprehension(record.trace, case)

        seq_degrade = _sequence_degradation_mode(fidelity, payload, expected_output)
        if seq_degrade:
            degrade = seq_degrade

    return ScoreRecord(
        run_id=record.run_id, fixture_id=fid, staged_input_id=iid,
        context=ctx, model_id=model,
        fidelity=fidelity, quality=quality, efficiency=efficiency,
        degradation_mode=degrade, comprehension=comprehension,
    )


def _field_agreement(got, expected) -> tuple[int, int]:
    """(matched, total) leaf fields of `expected` that `got` reproduces exactly.

    Walks the expected object; every scalar (null included) is one leaf. Dicts
    recurse by key, lists by position -- an element the payload does not have
    counts against every leaf under it. Equality is strict, the same standard as
    the binary verdict: "17" against 17 is a miss here exactly as it is there.
    A missing key compares as None, which matches an expected null -- also the
    binary check's behaviour (`payload.get(k) == v`)."""
    if isinstance(expected, dict):
        m = t = 0
        for k, v in expected.items():
            gm, gt = _field_agreement(got.get(k) if isinstance(got, dict) else None, v)
            m += gm; t += gt
        return m, t
    if isinstance(expected, list):
        m = t = 0
        for i, v in enumerate(expected):
            g = got[i] if isinstance(got, list) and i < len(got) else None
            gm, gt = _field_agreement(g, v)
            m += gm; t += gt
        return m, t
    return (1 if got == expected else 0), 1


def _field_rate(payload, expected) -> float:
    """Fraction of expected leaf fields the payload gets right (SS12 2026-08-25).

    Grades what the binary quality verdict thresholds: a payload wrong in one
    field of eight and one wrong in all eight are both `fail`, and 0.875 vs 0.0
    is the difference. rate == 1.0 iff the binary verdict on the same pair can
    pass (modulo extra keys, which neither measure penalises)."""
    matched, total = _field_agreement(payload, expected)
    return matched / total if total else 1.0


def _match_format_coerced(payload: dict, expected: dict) -> bool:
    """True if all expected fields are present with values that match after
    case-folding (strings) or numeric coercion (str↔number)."""
    for k, v in expected.items():
        got = payload.get(k)
        if got == v:
            continue
        if isinstance(v, str) and isinstance(got, str) and v.lower() == got.lower():
            continue
        if isinstance(v, (int, float)) and isinstance(got, str):
            try:
                if type(v)(got) == v:
                    continue
            except (ValueError, TypeError):
                pass
        if isinstance(got, (int, float)) and isinstance(v, str):
            try:
                if type(got)(v) == got:
                    continue
            except (ValueError, TypeError):
                pass
        return False
    return True


def _match_nested(payload: dict, expected: dict) -> bool:
    """True if any top-level value of payload is a dict containing all
    expected fields with exact values (one level of nesting only)."""
    for v in payload.values():
        if isinstance(v, dict) and all(v.get(k) == ev for k, ev in expected.items()):
            return True
    return False


def _find_case(expectations: dict, input_id: str) -> Optional[dict]:
    for c in expectations.get("cases", []):
        raw = c.get("input", "")
        normalized = raw.removeprefix("inputs/").removesuffix(".json")
        if normalized == input_id:
            return c
    return None


def _check_fidelity(trace, case: Optional[dict]) -> FidelityCheck:
    expected_branch = case.get("branch") if case else None
    trace_label     = case.get("trace_branch_label") if case else None

    if not trace or not trace.steps:
        return FidelityCheck("not_checkable", expected_branch=expected_branch)

    # Extract BRANCH entries from the trace spine.
    observed_labels = []
    for step in trace.steps:
        m = _BRANCH_RE.match(step.strip())
        if m:
            observed_labels.append(m.group(1).strip())

    if not observed_labels:
        return FidelityCheck("not_checkable", expected_branch=expected_branch)

    # Use the last BRANCH entry (the one before RETURN).
    observed = observed_labels[-1]

    if trace_label is None:
        # Trace present but fixture has no machine-readable label — informational.
        return FidelityCheck("not_checkable",
                             expected_branch=expected_branch,
                             observed_branch=observed)

    result = "pass" if observed == trace_label else "fail"
    return FidelityCheck(result, expected_branch=expected_branch, observed_branch=observed)


# ---------------------------------------------------------------------------
# Sequence oracle (W2 state-accumulation fixtures, e.g. support-intake)
# ---------------------------------------------------------------------------
#
# release-gate/task-router emit ONE bare BRANCH label per run and
# _check_fidelity above compares it as a scalar. support-intake-shaped
# fixtures emit an EVAL+BRANCH pair PER QUEUE ITEM (up to ~15 per run) and
# need the full ordered sequence compared, plus a second pass re-derived from
# the model's own classifications (conditional fidelity). This is genuinely
# new logic, not an extension of _check_fidelity's scalar path -- kept as
# separate functions so the scalar fixtures are provably untouched.

def _extract_eval_sequence(trace) -> list[dict]:
    """[{"id":..., "product":..., "intent":...}, ...] in emission order."""
    if not trace or not trace.steps:
        return []
    out = []
    for step in trace.steps:
        m = _EVAL_ITEM_RE.search(step.strip())
        if m:
            out.append({"id": m.group(1), "product": m.group(2), "intent": m.group(3)})
    return out


def _extract_branch_item_sequence(trace) -> list[dict]:
    """[{"id":..., "action":..., "team": str|None, "remaining": str}, ...] in
    emission order. `team` is None for a fixture that emits no team."""
    if not trace or not trace.steps:
        return []
    out = []
    for step in trace.steps:
        m = _BRANCH_ITEM_RE.search(step.strip())
        if m:
            out.append({"id": m.group(1), "action": m.group(2),
                        "team": m.group(3), "remaining": m.group(4)})
    return out


def _action_labels(items: list[dict]) -> list[str]:
    """The label the sequence oracles compare, built the same way from an
    oracle's output and from a model's trace.

    The team is part of it when there is one. support-routing's whole second
    decision axis is which team a request goes to; a label that dropped it
    would score a model that routed every request to the wrong team as
    perfect. Fixtures that name no team produce the label unchanged.
    """
    out = []
    for i in items:
        label = f"item={i['id']} action={i['action']}"
        if i.get("team") is not None:
            label += f" team={i['team']}"
        out.append(label)
    return out


def _observed_sequence(trace) -> list[str]:
    """The BRANCH labels a run emitted, in order, as the sequence oracle sees them.

    Two shapes, because the fixtures emit two. A keyed line
    ('BRANCH: item=<id> action=<a> [team=<t>] remaining=<n>') is reduced to
    'item=<id> action=<a>', plus ' team=<t>' where a team was named -- the
    running budget is data, not a control-flow decision, and
    expected_sequence never carries it; the team is a decision and does. Any other BRANCH line
    contributes its label as written ('BRANCH: parse' -> 'parse').

    Before 2026-08-22 only the keyed shape was read, so a fixture whose labels
    are bare words observed an EMPTY sequence and scored rate 0.0 -- 'fail' on
    a perfectly executed run. polarity-flip, whose expected_sequence is
    ['parse', 'flip'], could not pass by construction. A bench that cannot
    record a success is not measuring the model.
    """
    if not trace or not trace.steps:
        return []
    out = []
    for step in trace.steps:
        line = step.strip()
        keyed = _BRANCH_ITEM_RE.search(line)
        if keyed:
            label = f"item={keyed.group(1)} action={keyed.group(2)}"
            if keyed.group(3) is not None:
                label += f" team={keyed.group(3)}"
            out.append(label)
            continue
        generic = _BRANCH_RE.match(line)
        if generic:
            out.append(generic.group(1).strip())
    return out


def _check_sequence_fidelity(trace, case: Optional[dict]) -> Optional[FidelityCheck]:
    """None if this case is not a sequence-oracle case (no `expected_sequence`)
    -- caller falls back to the scalar _check_fidelity result in that case.

    Two-metric oracle: sequence_rate's denominator is
    max(len(expected), len(observed)), not just len(expected) -- a run that
    never halts keeps emitting actions past the expected end, and capping the
    comparison window at len(expected) let those runs score an inflated rate
    (degenerate no-halt runs were being rewarded). redundancy_ratio =
    len(observed)/len(expected) is reported alongside it so the two read
    together: rate low + ratio ~=1 -> wrong actions at the right cadence;
    rate low + ratio high -> loop (no-halt, observed keeps growing past
    expected); rate low + ratio <1 -> stopped early. redundancy_ratio is None
    when expected_sequence is empty (division guard, mirrors `rate`'s guard).
    """
    if not case or "expected_sequence" not in case:
        return None

    expected_sequence = case["expected_sequence"]
    observed_labels = _observed_sequence(trace)

    n = max(len(expected_sequence), len(observed_labels))
    matches = sum(
        1 for i in range(min(len(observed_labels), n))
        if i < len(expected_sequence) and observed_labels[i] == expected_sequence[i]
    )
    rate = (matches / n) if n else None
    result = "not_checkable" if rate is None else ("pass" if rate == 1.0 else "fail")
    redundancy_ratio = (
        len(observed_labels) / len(expected_sequence) if expected_sequence else None
    )

    return FidelityCheck(
        result,
        sequence_rate=rate,
        redundancy_ratio=redundancy_ratio,
        expected_sequence=expected_sequence,
        observed_sequence=observed_labels,
    )


def _run_queue_oracle(items: list[dict], budget_hours: float, hours_table: dict) -> tuple[list[dict], float, Optional[str]]:
    """Same algorithm as support-intake/reference.py's run_queue(), duplicated
    here so the generic checker never imports a specific fixture's Python
    module. The two must be kept in sync -- both covered by R1 tests, and
    test_checker.py cross-checks this copy against reference.py directly."""
    remaining = budget_hours
    halted_at: Optional[str] = None
    out: list[dict] = []

    for item in items:
        product, intent = item["product"], item["intent"]
        if product == "UNKNOWN":
            out.append({"id": item["id"], "action": "NEEDS_INFO"})
            continue

        hours = hours_table.get(product, {}).get(intent)
        if hours is None:
            # Model emitted a product/intent combination outside the known
            # catalog -- garbled classification, treat like UNKNOWN for the
            # oracle re-run (it cannot have a well-defined FITS/NOFIT here).
            out.append({"id": item["id"], "action": "NEEDS_INFO"})
            continue

        fits = hours <= remaining
        if intent == "BUG" and not fits:
            halted_at = item["id"]
            out.append({"id": item["id"], "action": "ESCALATE"})
            break
        elif fits:
            remaining -= hours
            out.append({"id": item["id"], "action": "ASSIGN"})
        else:
            out.append({"id": item["id"], "action": "DEFER"})

    return out, remaining, halted_at


def _route_item_oracle(items: list[dict], world: dict, catalog: dict) -> list[dict]:
    """Same algorithm as support-routing/reference.py's route_item(), duplicated
    here for the same reason _run_queue_oracle is: the generic checker never
    imports a specific fixture's Python module. The two must be kept in sync --
    test_checker.py cross-checks this copy against reference.py directly.

    Every item is decided against the SAME world state. There is one item per
    request by construction; a model that emits several has repeated itself, and
    deciding the extras against a world its own earlier answer moved would be
    chaining, which SS4.5 rules out. redundancy_ratio is what reports the
    repetition.
    """
    teams = catalog["teams"]
    hours_table = catalog["hours_table"]
    remaining = world["remaining_hours"]
    states = world["teams"]
    out: list[dict] = []

    for item in items:
        product, intent = item["product"], item["intent"]

        if product == "UNKNOWN":
            out.append({"id": item["id"], "action": "NEEDS_INFO", "team": "-"})
            continue

        owner = next((t["id"] for t in teams if product in t["accepts"]), None)
        if owner is None:
            out.append({"id": item["id"], "action": "UNASSIGNED", "team": "-"})
            continue

        hours = hours_table.get(product, {}).get(intent)
        if hours is None:
            # Model emitted a product/intent combination outside the known
            # catalog -- garbled classification, treated like UNKNOWN, exactly
            # as _run_queue_oracle treats it.
            out.append({"id": item["id"], "action": "NEEDS_INFO", "team": "-"})
            continue

        if hours > remaining:
            out.append({"id": item["id"],
                        "action": "ESCALATE" if intent == "BUG" else "DEFER",
                        "team": "-"})
            continue

        state = states.get(owner)
        if state == "OPEN" or (state == "LIMITED" and intent == "BUG"):
            team = owner
        else:
            backup = next((t["id"] for t in teams if product in t["backs_up"]), None)
            team = backup if backup is not None and states.get(backup) == "OPEN" else None

        if team is None:
            out.append({"id": item["id"], "action": "DEFER", "team": "-"})
        else:
            out.append({"id": item["id"], "action": "ASSIGN", "team": team})

    return out


def _check_conditional_fidelity(trace, catalog: Optional[dict],
                                case: Optional[dict] = None,
                                oracle: str = "run_queue") -> dict:
    """Re-derive the expected action sequence using the MODEL's OWN
    classifications (EVAL trace lines), then compare against what it
    actually did (BRANCH trace lines). Isolates pure control-flow
    correctness from comprehension errors (SS6.2 of the protocol).

    `oracle` names which control flow to re-run, and comes from the top-level
    `oracle` key of expectations.json (default `run_queue`, which is what
    support-intake has always used). It is named rather than inferred from the
    shape of the data: two fixtures whose catalogs happen to look alike would
    otherwise be scored against each other's algorithm without saying so, and
    an unknown name raises here instead of scoring quietly against the wrong
    one.
    """
    empty = {"conditional_rate": None, "conditional_expected_sequence": None,
             "conditional_observed_sequence": None}
    if not catalog:
        return empty

    evals = _extract_eval_sequence(trace)
    if not evals:
        return empty

    if oracle == "run_queue":
        oracle_items, _remaining, _halted = _run_queue_oracle(
            evals, catalog["budget_hours"], catalog["hours_table"]
        )
    elif oracle == "route_item":
        world = (case or {}).get("world")
        if not world:
            # The case names no world state, so there is nothing to decide the
            # request against. Unmeasurable, not zero.
            return empty
        oracle_items = _route_item_oracle(evals, world, catalog)
    else:
        raise ValueError(
            f"expectations.json names an oracle this checker does not implement: "
            f"{oracle!r}. Known: 'run_queue', 'route_item'."
        )

    conditional_expected = _action_labels(oracle_items)

    observed_items = _extract_branch_item_sequence(trace)
    observed_labels = _action_labels(observed_items)

    n = len(conditional_expected)
    matches = sum(
        1 for i in range(min(len(observed_labels), n))
        if observed_labels[i] == conditional_expected[i]
    )
    rate = (matches / n) if n else None

    return {
        "conditional_rate": rate,
        "conditional_expected_sequence": conditional_expected,
        "conditional_observed_sequence": observed_labels,
    }


def _check_comprehension(trace, case: Optional[dict]) -> Optional[QualityCheck]:
    """Domain comprehension: (product, intent) extracted from EVAL trace
    lines vs. verified ground truth, per item -- independent of SOL
    control-flow (SS6.2). `tolerant` items accept either the primary or the
    `tolerant_alt_label` intent (ambiguous items, SS10 of the protocol)."""
    if not case:
        return None
    ground_truth = case.get("comprehension_ground_truth")
    if not ground_truth:
        return None

    evals_by_id = {e["id"]: e for e in _extract_eval_sequence(trace)}
    if not evals_by_id:
        # No EVAL line at all: nothing was observed, so there is nothing to be
        # right or wrong about. Dividing zero correct by fifteen items would
        # write 0.0 into the column where results go, and 0.0 is the score of a
        # model that named every product and missed every one. On MAIN 196 runs
        # of 485 emitted no trace and carried that zero; read off the payload
        # they returned, the same runs sit at 0.59 to 0.81. A partial trace is
        # left alone below -- five lines out of fifteen is an observation, and
        # the ten missing are the model's doing. Only silence is silence.
        return QualityCheck("not_checkable", expected=ground_truth, got=[], rate=None)
    n = len(ground_truth)
    correct = 0
    for gt in ground_truth:
        obs = evals_by_id.get(gt["id"])
        if obs is None:
            continue
        product_ok = obs["product"] == gt["product"]
        intent_ok = obs["intent"] == gt["intent"] or (
            gt.get("tolerant") and obs["intent"] == gt.get("tolerant_alt_label")
        )
        if product_ok and intent_ok:
            correct += 1

    rate = (correct / n) if n else None
    result = "not_checkable" if rate is None else ("pass" if rate == 1.0 else "fail")
    return QualityCheck(result, expected=ground_truth,
                        got=[dict(e) for e in evals_by_id.values()], rate=rate)


def _sequence_degradation_mode(
    fidelity: FidelityCheck, payload, expected_output
) -> Optional[str]:
    """New degradation modes specific to the sequence oracle. Returns None to
    let the caller's existing payload-comparison degrade label stand."""
    if fidelity is None or fidelity.expected_sequence is None:
        return None

    expected_seq = fidelity.expected_sequence
    observed_seq = fidelity.observed_sequence or []

    # halt-not-taken: the model named the right stopping point in `halted_at`
    # and then delivered the whole queue anyway. A strictly more informative
    # sub-case of no-halt, so it is checked first, and read off the PAYLOAD
    # rather than the trace -- a model that emits no trace at all can still
    # exhibit it, and granite does: 14 runs on MAIN, against 5 no-halt labels
    # in its whole campaign.
    #
    # What it records is not a missed rule but a misread task. The process is
    # a REPEAT with a RETURN nested inside it; the model read that RETURN as a
    # fact to report rather than an exit to take, answered "here is the whole
    # queue, and by the way it would have stopped at X", and its own halted_at
    # contradicts its own items list. 82 runs of MAIN's 1,236, 46 of them
    # qwen3.5-9b with thinking disabled.
    if isinstance(payload, dict) and isinstance(expected_output, dict):
        items = payload.get("items")
        expected_items = expected_output.get("items")
        halted_at = payload.get("halted_at")
        if (isinstance(items, list) and isinstance(expected_items, list)
                and len(items) > len(expected_items)
                and halted_at is not None
                and halted_at == expected_output.get("halted_at")):
            return "halt-not-taken"

    # no-halt: the expected sequence ends in an ESCALATE (the queue should
    # have stopped there), but the model kept going past that point, or
    # produced something other than ESCALATE at that position.
    #
    # Only where there is a queue to stop. A per-item fixture has an expected
    # sequence of length 1 (`support-routing`, SS4.5): a single item is not a
    # queue, and no arrest can be missed inside it. Unrestricted, the label
    # read every wrong action on such a fixture as a failure to halt -- of the
    # 57 it carried on routing, 55 were a model answering ASSIGN where the
    # oracle said ESCALATE and 2 emitted a second BRANCH line for an item that
    # had only one. Wrong answers and redundant trace, neither a runaway
    # queue; they fall through to the payload comparison, where a wrong action
    # is a wrong value. Restricted 2026-08-29 (SS12). Intake is untouched:
    # all 458 of its labels sit on queues of six to eleven items.
    expects_halt = len(expected_seq) > 1 and "action=ESCALATE" in expected_seq[-1]
    if expects_halt:
        halt_index = len(expected_seq) - 1
        overran = len(observed_seq) > len(expected_seq)
        missed_escalate = (
            len(observed_seq) > halt_index
            and "action=ESCALATE" not in observed_seq[halt_index]
        )
        if overran or missed_escalate:
            return "no-halt"

    # partial-sequence: executed but drifted partway through.
    if fidelity.sequence_rate is not None and 0 < fidelity.sequence_rate < 1:
        return "partial-sequence"

    # budget-drift: every action in the sequence is right, but the running
    # accumulator in the final payload doesn't match -- right decisions,
    # wrong bookkeeping.
    if (
        fidelity.sequence_rate == 1.0
        and isinstance(payload, dict)
        and isinstance(expected_output, dict)
        and payload.get("remaining_hours") != expected_output.get("remaining_hours")
    ):
        return "budget-drift"

    return None


# ---------------------------------------------------------------------------
# Variance decomposition (dentro-coda vs fra-code, SS6.3/SS7.2 of the protocol)
# ---------------------------------------------------------------------------

def decompose_variance(scores: list[ScoreRecord], metric: str = "conditional_rate") -> dict:
    """ANOVA-style within-queue vs. between-queue variance decomposition over
    N runs of a K x R design (K queues x R repetitions per queue). Groups by
    `staged_input_id` (the queue id for support-intake). `metric` selects
    which FidelityCheck field to decompose -- default is conditional_rate,
    the primary campaign outcome (pure control-flow fidelity).

    - dispersion WITHIN a queue  = stochastic noise (same input, R repeats)
    - dispersion BETWEEN queues  = sensitivity to queue composition
    """
    groups: dict[str, list[float]] = defaultdict(list)
    for s in scores:
        val = getattr(s.fidelity, metric, None)
        if val is not None:
            groups[s.staged_input_id].append(val)

    per_queue_mean = {q: statistics.fmean(vals) for q, vals in groups.items() if vals}
    within_queue_variance = {
        q: (statistics.pvariance(vals) if len(vals) > 1 else 0.0)
        for q, vals in groups.items()
    }
    all_means = list(per_queue_mean.values())
    between_queue_variance = statistics.pvariance(all_means) if len(all_means) > 1 else 0.0
    mean_within_queue_variance = (
        statistics.fmean(within_queue_variance.values()) if within_queue_variance else 0.0
    )

    return {
        "metric": metric,
        "n_queues": len(groups),
        "per_queue_mean": per_queue_mean,
        "within_queue_variance": within_queue_variance,
        "mean_within_queue_variance": mean_within_queue_variance,
        "between_queue_variance": between_queue_variance,
        "grand_mean": statistics.fmean(all_means) if all_means else None,
    }
