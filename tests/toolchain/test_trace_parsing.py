"""R1 tests for _parse_trace -- no model, no server, no GPU.

The function decides what counts as a trace line, and everything the fidelity
oracles measure is read off what it returns. When it drops a line, the run does
not score badly: it scores UNMEASURABLE (traced=False, sequence_rate 0.0,
comprehension and conditional not_checkable), which reads on a dashboard exactly
like a model that never followed the process.

That is what made the 2026-08-24 defect expensive and quiet at once. A model that
wrapped its trace lines in markdown -- a backtick span, a list bullet -- had the
whole of its fidelity discarded, with the content correct underneath: 61 of
MAIN's 1,236 runs, 60 of them ministral-8b.

The decision these tests record is Gianni's, 2026-08-24: tolerance must be at
least as high on the trace as on the payload, and in fact higher, because the
trace lines are additional control instructions rather than the deliverable.
_extract_payload has always accepted a fenced object; this function refusing a
backtick was the inconsistency.
"""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "tests"))

from runner.runner import _parse_trace, _undecorate  # noqa: E402

CLEAN = "[fixture-w2-support-intake][main] EVAL: item=item-241 product=P5 intent=BUG"
BRANCH = ("[fixture-w2-support-routing][main] BRANCH: item=item-041 "
          "action=ASSIGN team=T1 remaining=17")


# ---------------------------------------------------------------------------
# what already worked must go on working
# ---------------------------------------------------------------------------

def test_a_bare_trace_line_is_still_read():
    assert _parse_trace(CLEAN) == [CLEAN]


def test_lines_keep_their_order_and_their_text():
    raw = f"some preamble\n{CLEAN}\n{BRANCH}\nand a closing sentence"
    assert _parse_trace(raw) == [CLEAN, BRANCH]


def test_prose_around_the_trace_is_not_collected():
    raw = "I will now process the queue.\nHere is the result:\n{\"status\": \"OK\"}"
    assert _parse_trace(raw) == []


def test_a_line_missing_the_double_bracket_header_is_not_a_trace_line():
    assert _parse_trace("EVAL: item=item-241 product=P5 intent=BUG") == []


def test_an_unknown_verb_is_not_a_trace_line():
    assert _parse_trace("[fixture][main] MUSING: item=item-241") == []


# ---------------------------------------------------------------------------
# the wrapper, which is the point
# ---------------------------------------------------------------------------

def test_a_code_span_no_longer_hides_the_line():
    """The exact shape ministral produced on 60 of MAIN's rows."""
    assert _parse_trace(f"`{CLEAN}`") == [CLEAN]


def test_a_list_bullet_no_longer_hides_the_line():
    assert _parse_trace(f"- `{CLEAN}`") == [CLEAN]
    assert _parse_trace(f"* {CLEAN}") == [CLEAN]
    assert _parse_trace(f"+ {CLEAN}") == [CLEAN]


def test_a_numbered_list_marker_no_longer_hides_the_line():
    assert _parse_trace(f"1. {CLEAN}") == [CLEAN]
    assert _parse_trace(f"2) `{CLEAN}`") == [CLEAN]


def test_bold_and_italics_no_longer_hide_the_line():
    assert _parse_trace(f"**{CLEAN}**") == [CLEAN]
    assert _parse_trace(f"_{CLEAN}_") == [CLEAN]


def test_a_blockquote_no_longer_hides_the_line():
    assert _parse_trace(f"> {CLEAN}") == [CLEAN]
    assert _parse_trace(f">> `{CLEAN}`") == [CLEAN]


def test_leading_whitespace_survives_as_it_always_did():
    assert _parse_trace(f"    {CLEAN}") == [CLEAN]
    assert _parse_trace(f"  - `{CLEAN}`") == [CLEAN]


# ---------------------------------------------------------------------------
# the captures downstream depend on
# ---------------------------------------------------------------------------

def test_a_trailing_backtick_does_not_reach_the_last_field():
    """The reason normalisation happens here and not by loosening each oracle.

    checker.py reads the last field with (\\S+). A backtick is not whitespace, so
    a line merely *found* inside its wrapper would hand the oracle 'BUG`' and
    'T1`' -- matched, parsed, and compared against ground truth that says 'BUG'.
    A wrong answer where there had been a missing one is not an improvement."""
    parsed = _parse_trace(f"`{CLEAN}`")
    assert parsed[0].endswith("intent=BUG")
    assert "`" not in parsed[0]

    parsed = _parse_trace(f"`{BRANCH}`")
    assert parsed[0].endswith("remaining=17")
    assert "`" not in parsed[0]


def test_the_routing_team_field_survives_undecoration():
    """support-routing's oracle is selected by a team= the checker must see."""
    assert _parse_trace(f"- **{BRANCH}**") == [BRANCH]
    assert "team=T1" in _parse_trace(f"`{BRANCH}`")[0]


def test_undecorating_a_clean_line_changes_nothing():
    for line in (CLEAN, BRANCH):
        assert _undecorate(line) == line


# ---------------------------------------------------------------------------
# what tolerance must NOT do
# ---------------------------------------------------------------------------

def test_an_unsubstituted_template_is_read_as_what_it_is():
    """Two of MAIN's 63 recoveries are granite emitting the template verbatim,
    placeholders and all. Tolerating the wrapper makes these visible, and they
    then score as wrong rather than as absent -- which is the honest reading: the
    model did emit a line, and the line is not an execution."""
    template = ("[fixture-w2-support-intake][main] BRANCH: item={{item.id}} "
                "action=ASSIGN remaining={{remaining_hours}}")
    assert _parse_trace(f"`{template}`") == [template]


def test_a_fenced_block_of_trace_lines_is_read_line_by_line():
    """A fence is not a wrapper on any single line -- the ``` sits on its own
    row. The lines inside were always readable; this asserts the fence markers
    themselves do not become trace lines."""
    raw = f"```\n{CLEAN}\n{BRANCH}\n```"
    assert _parse_trace(raw) == [CLEAN, BRANCH]


def test_a_trace_line_buried_mid_sentence_is_still_not_collected():
    """The boundary of the new tolerance, and it is deliberate.

    What was loosened is the WRAPPER -- decoration that hugs a line a model
    meant to emit on its own row. The match stays anchored after undecoration,
    so a line quoted inside prose is still not a trace line. Switching to a
    search would admit every model that narrates what it is about to do, and
    'the model said it would emit this' is not 'the model emitted this'."""
    assert _parse_trace(f"I emitted: {CLEAN}") == []
    assert _parse_trace(f"The process asks for {CLEAN} at this point") == []
