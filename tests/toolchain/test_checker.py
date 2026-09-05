"""
R1 tests for checker.py — fully deterministic, no model, no I/O.
The checker is the scoring engine for R3; testing it in isolation here
confirms it correctly maps RunRecord + expectations -> ScoreRecord.
"""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "tests"))

from runner.schema import Config, Execution, Output, RunRecord, Trace, Usage
from runner.checker import check, _find_case

# Expectations structure that mirrors tests/fixtures/w2-branching/release-gate/expectations.json
EXPECTATIONS = {
    "cases": [
        {"input": "inputs/i1-blocked.json",
         "expected_output": {"verdict": "BLOCKED"},
         "branch": "WHEN[0] blocking_bugs > 0",
         "trace_branch_label": "branch-0"},
        {"input": "inputs/i2-insufficient-coverage.json",
         "expected_output": {"verdict": "INSUFFICIENT_COVERAGE"},
         "branch": "WHEN[1] coverage < 80",
         "trace_branch_label": "branch-1"},
        {"input": "inputs/i3-security-hold.json",
         "expected_output": {"verdict": "SECURITY_HOLD"},
         "branch": "WHEN[2] security_review != passed",
         "trace_branch_label": "branch-2"},
        {"input": "inputs/i4-ready.json",
         "expected_output": {"verdict": "READY"},
         "branch": "WHEN.else",
         "trace_branch_label": "branch-else"},
    ]
}


def make_record(input_id="i1-blocked", status="done", payload=None, raw=""):
    return RunRecord(
        run_id="test-run",
        timestamp="2026-01-01T00:00:00+00:00",
        config=Config(
            fixture_id="w2-branching/release-gate",
            context="E1",
            model_id="test-model",
        ),
        staged_input_id=input_id,
        execution=Execution(status=status),
        trace=Trace(),
        output=Output(raw=raw, returned_payload=payload),
        usage=Usage(),
    )


# ---------------------------------------------------------------------------
# Quality — pass
# ---------------------------------------------------------------------------

def test_correct_verdict_quality_pass():
    score = check(make_record(payload={"verdict": "BLOCKED"}), EXPECTATIONS)
    assert score.quality.result == "pass"
    assert score.quality.got == {"verdict": "BLOCKED"}
    assert score.quality.expected == {"verdict": "BLOCKED"}


def test_correct_verdict_degradation_none():
    score = check(make_record(payload={"verdict": "BLOCKED"}), EXPECTATIONS)
    assert score.degradation_mode == "none"


def test_all_branches_pass():
    cases = [
        ("i1-blocked",               "BLOCKED"),
        ("i2-insufficient-coverage", "INSUFFICIENT_COVERAGE"),
        ("i3-security-hold",         "SECURITY_HOLD"),
        ("i4-ready",                 "READY"),
    ]
    for input_id, verdict in cases:
        score = check(make_record(input_id=input_id, payload={"verdict": verdict}), EXPECTATIONS)
        assert score.quality.result == "pass",  f"quality fail on {input_id}"
        assert score.degradation_mode == "none", f"wrong degrade on {input_id}"


# ---------------------------------------------------------------------------
# Quality — fail / degradation modes
# ---------------------------------------------------------------------------

def test_wrong_verdict_quality_fail():
    score = check(make_record(payload={"verdict": "READY"}), EXPECTATIONS)
    assert score.quality.result == "fail"
    assert score.quality.expected == {"verdict": "BLOCKED"}
    assert score.quality.got == {"verdict": "READY"}


def test_wrong_verdict_degradation_wrong_value():
    score = check(make_record(payload={"verdict": "READY"}), EXPECTATIONS)
    assert score.degradation_mode == "wrong-value"


def test_no_payload_quality_not_checkable():
    score = check(make_record(payload=None), EXPECTATIONS)
    assert score.quality.result == "not_checkable"


def test_no_payload_degradation_no_output():
    score = check(make_record(payload=None, raw=""), EXPECTATIONS)
    assert score.degradation_mode == "no-output"


def test_refusal_in_raw_output():
    score = check(make_record(payload=None, raw="I cannot execute this process."), EXPECTATIONS)
    assert score.degradation_mode == "refused"


def test_wrong_payload_missing_expected_key():
    score = check(make_record(payload={"wrong_key": "x"}), EXPECTATIONS)
    assert score.quality.result == "fail"
    assert score.degradation_mode == "wrong-value"


def test_garbled_payload_non_dict():
    score = check(make_record(payload="BLOCKED"), EXPECTATIONS)
    assert score.degradation_mode == "garbled-output"


# ---------------------------------------------------------------------------
# Status handling (na / error)
# ---------------------------------------------------------------------------

def test_na_status_all_not_checkable():
    score = check(make_record(status="na"), EXPECTATIONS)
    assert score.quality.result == "not_checkable"
    assert score.fidelity.result == "not_checkable"
    assert score.degradation_mode == "na"


def test_error_status_quality_fail():
    score = check(make_record(status="error"), EXPECTATIONS)
    assert score.quality.result == "fail"
    assert score.degradation_mode == "execution-error"


# ---------------------------------------------------------------------------
# Fidelity (not_checkable without trace, but expected_branch is propagated)
# ---------------------------------------------------------------------------

def test_fidelity_not_checkable_without_trace():
    score = check(make_record(payload={"verdict": "BLOCKED"}), EXPECTATIONS)
    assert score.fidelity.result == "not_checkable"
    assert score.fidelity.expected_branch == "WHEN[0] blocking_bugs > 0"


# ---------------------------------------------------------------------------
# Score-record metadata
# ---------------------------------------------------------------------------

def test_score_metadata_propagated():
    score = check(make_record(), EXPECTATIONS)
    assert score.fixture_id == "w2-branching/release-gate"
    assert score.staged_input_id == "i1-blocked"
    assert score.context == "E1"
    assert score.model_id == "test-model"
    assert score.run_id == "test-run"


# ---------------------------------------------------------------------------
# _find_case helper
# ---------------------------------------------------------------------------

def test_find_case_normalizes_path():
    case = _find_case(EXPECTATIONS, "i1-blocked")
    assert case is not None
    assert case["expected_output"] == {"verdict": "BLOCKED"}


def test_find_case_returns_none_for_unknown():
    assert _find_case(EXPECTATIONS, "i99-unknown") is None


# ---------------------------------------------------------------------------
# Tie R1 to R2: score the fixture against its own real expectations.json
# ---------------------------------------------------------------------------

def test_checker_against_real_expectations():
    import json
    exp_path = (
        REPO_ROOT / "tests" / "fixtures" / "w2-branching"
        / "release-gate" / "expectations.json"
    )
    expectations = json.loads(exp_path.read_text(encoding="utf-8"))
    score = check(
        make_record(input_id="i4-ready", payload={"verdict": "READY"}),
        expectations,
    )
    assert score.quality.result == "pass"
    assert score.degradation_mode == "none"


# ---------------------------------------------------------------------------
# Fidelity — with trace
# ---------------------------------------------------------------------------

def make_record_with_trace(input_id="i1-blocked", trace_steps=None, payload=None):
    steps = trace_steps or []
    return RunRecord(
        run_id="test-run",
        timestamp="2026-01-01T00:00:00+00:00",
        config=Config(
            fixture_id="w2-branching/release-gate",
            context="E1",
            model_id="test-model",
        ),
        staged_input_id=input_id,
        execution=Execution(status="done"),
        trace=Trace(steps=steps),
        output=Output(raw="\n".join(steps), returned_payload=payload),
        usage=Usage(),
    )


def test_fidelity_pass_correct_branch_trace():
    steps = ["[fixture-w2-release-gate][main] BRANCH: branch-0"]
    score = check(
        make_record_with_trace(input_id="i1-blocked", trace_steps=steps,
                               payload={"verdict": "BLOCKED"}),
        EXPECTATIONS,
    )
    assert score.fidelity.result == "pass"
    assert score.fidelity.expected_branch == "WHEN[0] blocking_bugs > 0"
    assert score.fidelity.observed_branch == "branch-0"


def test_fidelity_fail_wrong_branch_trace():
    # Agent took branch-1 but input calls for branch-0
    steps = ["[fixture-w2-release-gate][main] BRANCH: branch-1"]
    score = check(
        make_record_with_trace(input_id="i1-blocked", trace_steps=steps,
                               payload={"verdict": "BLOCKED"}),
        EXPECTATIONS,
    )
    assert score.fidelity.result == "fail"
    assert score.fidelity.observed_branch == "branch-1"


def test_fidelity_pass_all_branches():
    cases = [
        ("i1-blocked",               "branch-0", "BLOCKED"),
        ("i2-insufficient-coverage", "branch-1", "INSUFFICIENT_COVERAGE"),
        ("i3-security-hold",         "branch-2", "SECURITY_HOLD"),
        ("i4-ready",                 "branch-else", "READY"),
    ]
    for input_id, label, verdict in cases:
        steps = [f"[fixture-w2-release-gate][main] BRANCH: {label}"]
        score = check(
            make_record_with_trace(input_id=input_id, trace_steps=steps,
                                   payload={"verdict": verdict}),
            EXPECTATIONS,
        )
        assert score.fidelity.result == "pass",  f"fidelity fail on {input_id}"
        assert score.quality.result  == "pass",  f"quality fail on {input_id}"


def test_fidelity_uses_last_branch_entry():
    # Multiple BRANCH lines — checker uses the last one
    steps = [
        "[fixture-w2-release-gate][main] BRANCH: branch-0",
        "[fixture-w2-release-gate][main] BRANCH: branch-0",  # duplicate, still correct
    ]
    score = check(
        make_record_with_trace(trace_steps=steps, payload={"verdict": "BLOCKED"}),
        EXPECTATIONS,
    )
    assert score.fidelity.result == "pass"


def test_fidelity_not_checkable_trace_present_no_label():
    """Trace has a BRANCH line but expectations has no trace_branch_label."""
    exp_no_label = {
        "cases": [{"input": "inputs/i1-blocked.json",
                   "expected_output": {"verdict": "BLOCKED"},
                   "branch": "WHEN[0] blocking_bugs > 0"}]  # no trace_branch_label
    }
    steps = ["[fixture-w2-release-gate][main] BRANCH: branch-0"]
    score = check(
        make_record_with_trace(trace_steps=steps, payload={"verdict": "BLOCKED"}),
        exp_no_label,
    )
    assert score.fidelity.result == "not_checkable"
    assert score.fidelity.observed_branch == "branch-0"  # still captured


def test_fidelity_not_checkable_without_trace():
    score = check(make_record(payload={"verdict": "BLOCKED"}), EXPECTATIONS)
    assert score.fidelity.result == "not_checkable"
    assert score.fidelity.expected_branch == "WHEN[0] blocking_bugs > 0"


# ---------------------------------------------------------------------------
# Sequence oracle (W2 state-accumulation fixtures, e.g. support-intake).
# Self-contained synthetic fixture -- does NOT depend on the generated
# support-intake pool/queues, so this suite stays deterministic even before
# the pool is manually verified (item 2.6 of the build plan).
# ---------------------------------------------------------------------------

SEQ_CATALOG = {
    "budget_hours": 5,
    "hours_table": {
        "P1": {"BUG": 2, "FEATURE": 4, "QUESTION": 1},
        "P2": {"BUG": 3, "FEATURE": 4, "QUESTION": 1},
    },
}

# A 3-item queue: i1 ASSIGN (P1/FEATURE, 4h, remaining 5->1),
# i2 ESCALATE (P2/BUG, 3h, NOFIT against remaining=1 -> halt),
# i3 never reached.
SEQ_EXPECTATIONS = {
    "catalog": SEQ_CATALOG,
    "cases": [{
        "input": "inputs/q1.json",
        "expected_sequence": ["item=i1 action=ASSIGN", "item=i2 action=ESCALATE"],
        "expected_output": {"status": "OK",
                            "items": [{"id": "i1", "action": "ASSIGN"}, {"id": "i2", "action": "ESCALATE"}],
                            "remaining_hours": 1, "halted_at": "i2"},
        "comprehension_ground_truth": [
            {"id": "i1", "product": "P1", "intent": "FEATURE", "tolerant": False, "tolerant_alt_label": None},
            {"id": "i2", "product": "P2", "intent": "BUG", "tolerant": False, "tolerant_alt_label": None},
        ],
    }],
}


def _seq_record(steps, payload=None, input_id="q1"):
    return RunRecord(
        run_id="seq-test", timestamp="2026-01-01T00:00:00+00:00",
        config=Config(fixture_id="w2-branching/support-intake", context="E0", model_id="test-model"),
        staged_input_id=input_id, execution=Execution(status="done"),
        trace=Trace(steps=steps),
        output=Output(raw="\n".join(steps), returned_payload=payload),
        usage=Usage(),
    )


PERFECT_STEPS = [
    "[fixture-w2-support-intake][main] EVAL: item=i1 product=P1 intent=FEATURE",
    "[fixture-w2-support-intake][main] BRANCH: item=i1 action=ASSIGN remaining=1",
    "[fixture-w2-support-intake][main] EVAL: item=i2 product=P2 intent=BUG",
    "[fixture-w2-support-intake][main] BRANCH: item=i2 action=ESCALATE remaining=1",
]
PERFECT_PAYLOAD = SEQ_EXPECTATIONS["cases"][0]["expected_output"]


def test_sequence_fidelity_perfect_run():
    score = check(_seq_record(PERFECT_STEPS, PERFECT_PAYLOAD), SEQ_EXPECTATIONS)
    assert score.fidelity.result == "pass"
    assert score.fidelity.sequence_rate == 1.0
    assert score.fidelity.observed_sequence == ["item=i1 action=ASSIGN", "item=i2 action=ESCALATE"]


def test_conditional_fidelity_perfect_run_matches_own_classifications():
    score = check(_seq_record(PERFECT_STEPS, PERFECT_PAYLOAD), SEQ_EXPECTATIONS)
    # Re-running the oracle on the model's OWN (correct) EVAL classifications
    # reproduces the same sequence it actually executed -> rate 1.0.
    assert score.fidelity.conditional_rate == 1.0
    assert score.fidelity.conditional_expected_sequence == ["item=i1 action=ASSIGN", "item=i2 action=ESCALATE"]


def test_comprehension_perfect_run():
    score = check(_seq_record(PERFECT_STEPS, PERFECT_PAYLOAD), SEQ_EXPECTATIONS)
    assert score.comprehension is not None
    assert score.comprehension.rate == 1.0
    assert score.comprehension.result == "pass"


def test_comprehension_partial_misclassification():
    # Model misreads i2's product (P1 instead of P2) but the action sequence
    # it executes is still correct (e.g. by luck, or because it estimated
    # effort right despite the wrong product) -- this is exactly the
    # "60% comprehension / 100% conditional fidelity" case the protocol
    # calls out as the informative cell (SS6.2).
    steps = [
        "[fixture-w2-support-intake][main] EVAL: item=i1 product=P1 intent=FEATURE",
        "[fixture-w2-support-intake][main] BRANCH: item=i1 action=ASSIGN remaining=1",
        "[fixture-w2-support-intake][main] EVAL: item=i2 product=P1 intent=BUG",
        "[fixture-w2-support-intake][main] BRANCH: item=i2 action=ESCALATE remaining=1",
    ]
    score = check(_seq_record(steps, PERFECT_PAYLOAD), SEQ_EXPECTATIONS)
    assert score.comprehension.rate == 0.5
    # P1 BUG = 2h, which still doesn't fit remaining=1 -> still ESCALATE:
    # the wrong classification happened to preserve the right control flow.
    assert score.fidelity.sequence_rate == 1.0


def test_no_eval_line_at_all_is_not_checkable_not_zero():
    """A run that never said what it thought has not been measured. Scoring it 0.0
    puts it where a model that named every product and missed every one sits, and
    those are opposite findings.

    215 of MAIN's 493 runs landed here (2026-08-23). granite-4.1-8b answers with a
    markdown table instead of the trace lines: read off the payload it does return,
    it classifies at 0.59, and it was reading 0.00 on every row."""
    steps = ["[fixture-w2-support-intake][main] BRANCH: item=i1 action=ASSIGN remaining=1"]
    score = check(_seq_record(steps, PERFECT_PAYLOAD), SEQ_EXPECTATIONS)
    assert score.comprehension is not None
    assert score.comprehension.rate is None
    assert score.comprehension.result == "not_checkable"


def test_a_partial_trace_is_still_scored_over_every_item():
    """The other half of the rule. One EVAL line out of two is a model that engaged
    with the instruction and stopped, and the item it never spoke about is its own
    doing -- unlike silence, which is the bench learning nothing."""
    steps = [
        "[fixture-w2-support-intake][main] EVAL: item=i1 product=P1 intent=FEATURE",
        "[fixture-w2-support-intake][main] BRANCH: item=i1 action=ASSIGN remaining=1",
    ]
    score = check(_seq_record(steps, PERFECT_PAYLOAD), SEQ_EXPECTATIONS)
    assert score.comprehension.rate == 0.5    # 1 right of 2 items, not 1 of 1
    assert score.comprehension.result == "fail"


def test_conditional_fidelity_isolates_control_flow_from_comprehension():
    # Model misclassifies i2 as P1/QUESTION (1h, which WOULD fit remaining=1)
    # but its own BRANCH trace still says ESCALATE (inconsistent with what it
    # itself claimed to classify) -- conditional fidelity re-derives what
    # SHOULD happen given the model's own (wrong) classification and catches
    # the inconsistency, even though ground-truth sequence_rate looks fine
    # only by coincidence.
    steps = [
        "[fixture-w2-support-intake][main] EVAL: item=i1 product=P1 intent=FEATURE",
        "[fixture-w2-support-intake][main] BRANCH: item=i1 action=ASSIGN remaining=1",
        "[fixture-w2-support-intake][main] EVAL: item=i2 product=P1 intent=QUESTION",
        "[fixture-w2-support-intake][main] BRANCH: item=i2 action=ESCALATE remaining=1",
    ]
    score = check(_seq_record(steps, PERFECT_PAYLOAD), SEQ_EXPECTATIONS)
    # Given its OWN classification (P1/QUESTION, 1h, fits remaining=1), the
    # correct action was ASSIGN, not ESCALATE -- conditional fidelity fails.
    assert score.fidelity.conditional_expected_sequence == ["item=i1 action=ASSIGN", "item=i2 action=ASSIGN"]
    assert score.fidelity.conditional_rate == 0.5
    # But ground-truth sequence fidelity still reads 1.0 (right answer, wrong reasoning).
    assert score.fidelity.sequence_rate == 1.0


def test_degradation_no_halt_overran():
    # Model ignores the ESCALATE and keeps processing past the halt point.
    steps = PERFECT_STEPS[:2] + [
        "[fixture-w2-support-intake][main] EVAL: item=i2 product=P2 intent=BUG",
        "[fixture-w2-support-intake][main] BRANCH: item=i2 action=ASSIGN remaining=-2",
        "[fixture-w2-support-intake][main] EVAL: item=i3 product=P1 intent=QUESTION",
        "[fixture-w2-support-intake][main] BRANCH: item=i3 action=ASSIGN remaining=-3",
    ]
    score = check(_seq_record(steps, {"status": "OK", "items": [], "remaining_hours": -3, "halted_at": None}),
                  SEQ_EXPECTATIONS)
    assert score.degradation_mode == "no-halt"


# ---------------------------------------------------------------------------
# no-halt needs a queue, 2026-08-29
#
# `support-routing` delivers one item per invocation (SS4.5), so its expected
# sequence has length 1. There is no queue to run past and no arrest to miss,
# but the label fired anyway: any action other than ESCALATE at position 0 read
# as a failure to halt. It carried 57 labels on routing, 55 of them a model
# answering ASSIGN where the oracle said ESCALATE. Worse, it overwrote what the
# payload comparison had already found -- 13 of the 57 had returned no payload
# at all and were `no-output` until the sequence oracle relabelled them.
# ---------------------------------------------------------------------------

# The per-item shape, in the suite's synthetic terms: one item, expected
# ESCALATE, nothing after it.
PER_ITEM_EXPECTATIONS = {
    "catalog": SEQ_CATALOG,
    "cases": [{
        "input": "inputs/r1.json",
        "expected_sequence": ["item=i1 action=ESCALATE"],
        "expected_output": {"status": "OK",
                            "items": [{"id": "i1", "action": "ESCALATE"}],
                            "remaining_hours": 1, "halted_at": "i1"},
        "comprehension_ground_truth": [
            {"id": "i1", "product": "P2", "intent": "BUG", "tolerant": False, "tolerant_alt_label": None},
        ],
    }],
}


def test_a_wrong_action_on_a_single_item_is_not_a_missed_halt():
    """The 55. One item, expected ESCALATE, model says ASSIGN: a wrong answer,
    not a queue that ran away. It belongs to the payload comparison."""
    steps = [
        "[fixture-w2-support-routing][main] EVAL: item=i1 product=P2 intent=BUG",
        "[fixture-w2-support-routing][main] BRANCH: item=i1 action=ASSIGN remaining=1",
    ]
    payload = {"status": "OK", "items": [{"id": "i1", "action": "ASSIGN"}],
               "remaining_hours": 1, "halted_at": None}
    score = check(_seq_record(steps, payload, input_id="r1"), PER_ITEM_EXPECTATIONS)
    assert score.degradation_mode == "wrong-value"


def test_a_single_item_run_that_returned_nothing_keeps_its_own_label():
    """The 13. No payload is a delivery failure, and the sequence oracle used to
    overwrite it with a fidelity label -- hiding the more basic thing that went
    wrong."""
    steps = [
        "[fixture-w2-support-routing][main] EVAL: item=i1 product=P2 intent=BUG",
        "[fixture-w2-support-routing][main] BRANCH: item=i1 action=ASSIGN remaining=1",
    ]
    score = check(_seq_record(steps, None, input_id="r1"), PER_ITEM_EXPECTATIONS)
    assert score.degradation_mode == "no-output"


def test_extra_branch_lines_on_a_single_item_are_not_a_missed_halt():
    """The 2. A second BRANCH line for an item that had one is redundant trace,
    which `redundancy_ratio` already measures. Still not a queue."""
    steps = [
        "[fixture-w2-support-routing][main] EVAL: item=i1 product=P2 intent=BUG",
        "[fixture-w2-support-routing][main] BRANCH: item=i1 action=ESCALATE remaining=1",
        "[fixture-w2-support-routing][main] EVAL: item=i1 product=P2 intent=BUG",
        "[fixture-w2-support-routing][main] BRANCH: item=i1 action=ASSIGN remaining=-2",
    ]
    payload = PER_ITEM_EXPECTATIONS["cases"][0]["expected_output"]
    score = check(_seq_record(steps, payload, input_id="r1"), PER_ITEM_EXPECTATIONS)
    assert score.degradation_mode != "no-halt"


def test_the_queue_case_is_untouched_by_the_restriction():
    """Intake's 458 labels sit on queues of six to eleven items. The guard is on
    the length of the expected sequence, and must not reach them."""
    score = check(_seq_record(PERFECT_STEPS[:2] + [
        "[fixture-w2-support-intake][main] EVAL: item=i2 product=P2 intent=BUG",
        "[fixture-w2-support-intake][main] BRANCH: item=i2 action=ASSIGN remaining=-2",
    ], {"status": "OK", "items": [], "remaining_hours": -2, "halted_at": None}), SEQ_EXPECTATIONS)
    assert score.degradation_mode == "no-halt"


# ---------------------------------------------------------------------------
# halt-not-taken, 2026-08-24
#
# Found by asking why qwen3.5-9b-nothink never once passed on MAIN. It was not
# improbable, it was impossible: 0 of 213 runs returned a payload with the right
# number of items, and 154 of 181 readable payloads carried all fifteen. Yet 46
# of those named the CORRECT halted_at while doing it -- the model knows where
# the queue stops, says so, and hands back the whole queue anyway.
#
# The finding this label carries is that the failure is not ignorance of the
# rule. The process is a REPEAT with a RETURN nested three levels inside it, and
# the model read that RETURN as a fact to report rather than an exit to take.
# The payload contradicts itself, and that contradiction is the observation.
# ---------------------------------------------------------------------------

def _overran_payload(halted_at):
    """Three items where two were expected -- the queue was never truncated."""
    return {"status": "OK",
            "items": [{"id": "i1", "action": "ASSIGN"},
                      {"id": "i2", "action": "ESCALATE"},
                      {"id": "i3", "action": "DEFER"}],
            "remaining_hours": 1, "halted_at": halted_at}


def test_degradation_halt_not_taken_when_the_payload_names_the_right_halt():
    score = check(_seq_record(PERFECT_STEPS, _overran_payload("i2")), SEQ_EXPECTATIONS)
    assert score.degradation_mode == "halt-not-taken"


def test_halt_not_taken_needs_no_trace_at_all():
    """Why the label is read off the payload and not off the trace.

    granite-4.1-8b emits no trace on most of its campaign, so the trace-based
    no-halt can barely see it: 5 labels in 189 runs. Read off the payload, the
    same model shows 14 halt-not-taken. A model that answers in JSON and skips
    the scaffolding is still telling us what it did with the loop."""
    score = check(_seq_record([], _overran_payload("i2")), SEQ_EXPECTATIONS)
    assert score.degradation_mode == "halt-not-taken"


def test_a_wrong_halted_at_is_plain_no_halt_not_halt_not_taken():
    """The boundary. What makes this label worth having is the CONTRADICTION --
    right stopping point, wrong delivery. A model that overran without ever
    locating the halt has made an ordinary mistake and keeps the ordinary
    label."""
    overran_steps = PERFECT_STEPS + [
        "[fixture-w2-support-intake][main] EVAL: item=i3 product=P1 intent=QUESTION",
        "[fixture-w2-support-intake][main] BRANCH: item=i3 action=DEFER remaining=1",
    ]
    for named in ("i3", None):
        score = check(_seq_record(overran_steps, _overran_payload(named)), SEQ_EXPECTATIONS)
        assert score.degradation_mode == "no-halt"
        # And with no trace to overrun, it falls through to the ordinary
        # payload comparison rather than borrowing either halt label.
        score = check(_seq_record([], _overran_payload(named)), SEQ_EXPECTATIONS)
        assert score.degradation_mode != "halt-not-taken"


def test_stopping_at_the_right_length_is_never_halt_not_taken():
    """Overrunning is half the definition: a payload of the expected length has
    taken the halt, whatever else may be wrong with it."""
    score = check(_seq_record(PERFECT_STEPS, PERFECT_PAYLOAD), SEQ_EXPECTATIONS)
    assert score.degradation_mode != "halt-not-taken"


def test_halt_not_taken_takes_precedence_over_no_halt():
    """It is a strictly more informative sub-case, so it must be checked first;
    otherwise the 82 runs that carry the contradiction disappear into the 722
    that merely overran."""
    payload = _overran_payload("i2")
    score = check(_seq_record(PERFECT_STEPS + [
        "[fixture-w2-support-intake][main] EVAL: item=i3 product=P1 intent=QUESTION",
        "[fixture-w2-support-intake][main] BRANCH: item=i3 action=DEFER remaining=1",
    ], payload), SEQ_EXPECTATIONS)
    assert score.degradation_mode == "halt-not-taken"


def test_degradation_partial_sequence():
    steps = [
        "[fixture-w2-support-intake][main] EVAL: item=i1 product=P1 intent=FEATURE",
        "[fixture-w2-support-intake][main] BRANCH: item=i1 action=DEFER remaining=5",
        "[fixture-w2-support-intake][main] EVAL: item=i2 product=P2 intent=BUG",
        "[fixture-w2-support-intake][main] BRANCH: item=i2 action=ESCALATE remaining=1",
    ]
    score = check(_seq_record(steps, PERFECT_PAYLOAD), SEQ_EXPECTATIONS)
    assert score.degradation_mode == "partial-sequence"
    assert 0 < score.fidelity.sequence_rate < 1


def test_degradation_budget_drift():
    bad_payload = dict(PERFECT_PAYLOAD)
    bad_payload["remaining_hours"] = 99  # right actions, wrong bookkeeping
    score = check(_seq_record(PERFECT_STEPS, bad_payload), SEQ_EXPECTATIONS)
    assert score.degradation_mode == "budget-drift"
    assert score.fidelity.sequence_rate == 1.0


def test_sequence_case_does_not_affect_scalar_fixtures():
    """_check_sequence_fidelity must return None (opt out) for cases without
    `expected_sequence` -- release-gate-style scoring is untouched."""
    score = check(make_record(payload={"verdict": "BLOCKED"}), EXPECTATIONS)
    assert score.fidelity.sequence_rate is None
    assert score.fidelity.conditional_rate is None
    assert score.comprehension is None


# ---------------------------------------------------------------------------
# decompose_variance — within-queue vs. between-queue (SS6.3/SS7.2)
# ---------------------------------------------------------------------------

def test_decompose_variance_groups_by_staged_input_id():
    from runner.schema import FidelityCheck, QualityCheck, EfficiencyRecord, ScoreRecord
    from runner.checker import decompose_variance

    def sr(qid, rate):
        return ScoreRecord(
            run_id="r", fixture_id="f", staged_input_id=qid, context="E0", model_id="m",
            fidelity=FidelityCheck("pass" if rate == 1.0 else "fail", conditional_rate=rate),
            quality=QualityCheck("pass"), efficiency=EfficiencyRecord(), degradation_mode="none",
        )

    scores = [sr("q1", 0.9), sr("q1", 0.95), sr("q1", 0.92),
              sr("q2", 0.4), sr("q2", 0.35), sr("q2", 0.42)]
    d = decompose_variance(scores, metric="conditional_rate")
    assert d["n_queues"] == 2
    assert d["per_queue_mean"]["q1"] > d["per_queue_mean"]["q2"]
    # Built so between-queue spread dominates stochastic within-queue noise.
    assert d["between_queue_variance"] > d["mean_within_queue_variance"]


def test_decompose_variance_ignores_none_values():
    from runner.schema import FidelityCheck, QualityCheck, EfficiencyRecord, ScoreRecord
    from runner.checker import decompose_variance

    scores = [ScoreRecord(
        run_id="r", fixture_id="f", staged_input_id="q1", context="E0", model_id="m",
        fidelity=FidelityCheck("not_checkable"), quality=QualityCheck("not_checkable"),
        efficiency=EfficiencyRecord(), degradation_mode="na",
    )]
    d = decompose_variance(scores, metric="conditional_rate")
    assert d["n_queues"] == 0
    assert d["grand_mean"] is None


# ---------------------------------------------------------------------------
# Tie R1 to R2 for support-intake: the real generated expectations.json must
# be structurally usable by the checker (even before the pool is manually
# verified -- this only proves the pipeline, not the ground truth's accuracy).
# ---------------------------------------------------------------------------

def test_checker_against_real_support_intake_expectations():
    import json
    exp_path = (
        REPO_ROOT / "tests" / "fixtures" / "w2-branching"
        / "support-intake" / "expectations.json"
    )
    if not exp_path.exists():
        return  # queues not generated in this checkout -- not an R1 failure
    expectations = json.loads(exp_path.read_text(encoding="utf-8"))
    case = next(c for c in expectations["cases"] if "expected_sequence" in c)
    input_id = case["input"].removeprefix("inputs/").removesuffix(".json")

    steps = []
    for item, label in zip(case["comprehension_ground_truth"], case["expected_sequence"]):
        steps.append(f"[fixture-w2-support-intake][main] EVAL: item={item['id']} "
                     f"product={item['product']} intent={item['intent']}")
        steps.append(f"[fixture-w2-support-intake][main] BRANCH: {label} remaining=0")

    record = RunRecord(
        run_id="real-test", timestamp="2026-01-01T00:00:00+00:00",
        config=Config(fixture_id="w2-branching/support-intake", context="E0", model_id="test-model"),
        staged_input_id=input_id, execution=Execution(status="done"),
        trace=Trace(steps=steps),
        output=Output(raw="\n".join(steps), returned_payload=case["expected_output"]),
        usage=Usage(),
    )
    score = check(record, expectations)
    assert score.fidelity.sequence_rate == 1.0
    assert score.fidelity.conditional_rate == 1.0
    assert score.comprehension.rate == 1.0
    assert score.degradation_mode == "none"


# ---------------------------------------------------------------------------
# sequence oracle, label shapes (2026-08-22)
# ---------------------------------------------------------------------------

def test_sequence_oracle_reads_bare_branch_labels():
    """A fixture whose BRANCH labels are bare words must be able to pass.

    Until 2026-08-22 the sequence oracle read only the keyed shape
    ('item=<id> action=<a> remaining=<n>'), so a run that emitted exactly the
    expected labels observed an EMPTY sequence and scored 0.0 -- 'fail' on a
    perfect run. polarity-flip's expected_sequence is ['parse', 'flip']: it
    could not pass by construction, and no result of it would have been about
    the model."""
    from runner.checker import _check_sequence_fidelity

    class Trace:
        steps = ["[fixture-w0-polarity-flip][main] BRANCH: parse",
                 "[fixture-w0-polarity-flip][main] BRANCH: flip"]

    fidelity = _check_sequence_fidelity(Trace(), {"expected_sequence": ["parse", "flip"]})
    assert fidelity.observed_sequence == ["parse", "flip"]
    assert fidelity.sequence_rate == 1.0
    assert fidelity.result == "pass"


def test_sequence_oracle_still_drops_the_budget_from_keyed_labels():
    """The keyed shape carries `remaining=`, expected_sequence never does: the
    running budget is data, not a control-flow decision. Generalising the
    extractor must not start comparing it."""
    from runner.checker import _check_sequence_fidelity

    class Trace:
        steps = ["[fixture-w2-support-intake][main] BRANCH: item=i1 action=ASSIGN remaining=17",
                 "[fixture-w2-support-intake][main] BRANCH: item=i2 action=DEFER remaining=17"]

    fidelity = _check_sequence_fidelity(
        Trace(), {"expected_sequence": ["item=i1 action=ASSIGN", "item=i2 action=DEFER"]})
    assert fidelity.observed_sequence == ["item=i1 action=ASSIGN", "item=i2 action=DEFER"]
    assert fidelity.result == "pass"


# ---------------------------------------------------------------------------
# Quality rate — field-level agreement (SS12 2026-08-25)
# ---------------------------------------------------------------------------

from runner.checker import _field_rate  # noqa: E402

ROUTING_EXPECTED = {
    "status": "OK",
    "item": {"id": "item-041", "product": "P1", "intent": "BUG",
             "hours": 3, "team": "T1", "action": "ASSIGN"},
    "remaining_hours": 17,
}


def test_field_rate_perfect_payload_is_one():
    assert _field_rate(ROUTING_EXPECTED, ROUTING_EXPECTED) == 1.0


def test_field_rate_one_wrong_leaf_of_eight():
    got = {**ROUTING_EXPECTED,
           "item": {**ROUTING_EXPECTED["item"], "team": "T2"}}
    assert _field_rate(got, ROUTING_EXPECTED) == 7 / 8


def test_field_rate_strict_like_the_binary_verdict():
    # "17" against 17 is a miss here exactly as wrong-format is a fail there.
    got = {**ROUTING_EXPECTED, "remaining_hours": "17"}
    assert _field_rate(got, ROUTING_EXPECTED) == 7 / 8


def test_field_rate_missing_nested_object_costs_all_its_leaves():
    got = {"status": "OK", "remaining_hours": 17}
    assert _field_rate(got, ROUTING_EXPECTED) == 2 / 8


def test_field_rate_expected_null_matches_missing_key():
    # INVALID_INPUT case: item null, remaining null. A payload without the
    # keys compares as None — the binary check's behaviour, kept on purpose.
    expected = {"status": "INVALID_INPUT", "item": None, "remaining_hours": None}
    assert _field_rate({"status": "INVALID_INPUT"}, expected) == 1.0


def test_field_rate_lists_by_position():
    expected = {"items": [{"id": "a"}, {"id": "b"}]}
    assert _field_rate({"items": [{"id": "a"}, {"id": "x"}]}, expected) == 0.5
    assert _field_rate({"items": [{"id": "a"}]}, expected) == 0.5  # short list


def test_field_rate_non_dict_payload_is_zero():
    assert _field_rate(["not", "a", "dict"], ROUTING_EXPECTED) == 0.0


def test_quality_rate_lands_in_score_record():
    score = check(make_record(payload={"verdict": "BLOCKED"}), EXPECTATIONS)
    assert score.quality.rate == 1.0
    score = check(make_record(payload={"verdict": "READY"}), EXPECTATIONS)
    assert score.quality.rate == 0.0


def test_quality_rate_absent_when_no_payload():
    score = check(make_record(payload=None, raw=""), EXPECTATIONS)
    assert score.quality.rate is None


def test_quality_rate_reaches_the_index_from_the_writer(tmp_path, monkeypatch):
    """It used to reach index.jsonl only through backfill_index_scores.py, never
    from _append_index, so every run wrote a row without it and the column stayed
    blank until somebody remembered to backfill. Noticed 2026-08-31 on 280 fresh
    rows. The graded measure is what tells a wrong answer from a right answer with
    one field off; a run that has to be remembered is a run that will not be."""
    import json
    import runner.runner as runner_mod

    monkeypatch.setattr(runner_mod, "RESULTS_DIR", tmp_path)
    monkeypatch.setattr(runner_mod, "INDEX_PATH", tmp_path / "index.jsonl")

    record = make_record(payload={"verdict": "BLOCKED"})
    score = check(record, EXPECTATIONS)
    runner_mod._append_index(record, score)

    row = json.loads((tmp_path / "index.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert "quality_rate" in row, "the graded quality never reaches the analysis surface"
    assert row["quality_rate"] == score.quality.rate == 1.0
