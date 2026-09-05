"""
R1 tests for `_extract_payload` — no server, no model, no GPU.

The function turns a model's raw text into the object the process returned. It
is the one place where a correct answer can be recorded as a wrong one, because
its failure produces a well-formed dict rather than an error: the first version
matched braces with `\\{.*?\\}`, stopped at the closing brace of the first item
inside `items`, resumed after it, and returned that item. 204 of MAIN's runs
were scored against a fragment of their own answer, and nothing in the pipeline
could notice — `quality` compared two dicts, as it always had.

So these tests are written against shapes observed in MAIN's raw outputs, not
against invented ones.
"""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "tests"))

from runner.runner import _extract_payload  # noqa: E402

PAYLOAD = (
    '{"status": "OK", "items": ['
    '{"id": "item-241", "product": "P5", "intent": "BUG", "hours": 3, "action": "ASSIGN"}, '
    '{"id": "item-095", "product": "P2", "intent": "FEATURE", "hours": 4, "action": "ASSIGN"}'
    '], "remaining_hours": 0, "halted_at": "item-137"}'
)

TRACE = (
    "[fixture-w2-support-intake][main] EVAL: item=item-241 product=P5 intent=BUG\n"
    "[fixture-w2-support-intake][main] BRANCH: item=item-241 action=ASSIGN remaining=17\n"
)


def _is_the_payload(obj):
    return isinstance(obj, dict) and obj.get("halted_at") == "item-137" \
        and len(obj.get("items", [])) == 2


# ---------------------------------------------------------------------------
# The regression the function exists to prevent
# ---------------------------------------------------------------------------

def test_trace_then_bare_payload_returns_the_payload_not_an_item():
    """The shape every tracing model produced. Under the old regex this
    returned `{"id": "item-095", ...}` — a dict, valid JSON, and not the
    answer."""
    assert _is_the_payload(_extract_payload(TRACE + "\n" + PAYLOAD))


def test_a_nested_item_is_never_returned():
    got = _extract_payload(TRACE + "\n" + PAYLOAD)
    assert "id" not in got, f"returned an item instead of the payload: {got}"


# ---------------------------------------------------------------------------
# Shapes seen across the five models
# ---------------------------------------------------------------------------

def test_payload_alone():
    assert _is_the_payload(_extract_payload(PAYLOAD))


def test_fenced_payload():
    assert _is_the_payload(_extract_payload(TRACE + "\n```json\n" + PAYLOAD + "\n```"))


def test_prose_with_unbalanced_braces_before_the_payload():
    """granite wrote explanations around its answer. A `{` that opens nothing
    used to strand a brace-depth scan; raw_decode just fails at that offset and
    the scan moves on."""
    prose = "Set `halted_at` to that item's ID, i.e. {item-214, unclosed\n"
    assert _is_the_payload(_extract_payload(prose + "```json\n" + PAYLOAD + "\n```\n\nThe block above."))


def test_payload_first_then_a_bare_list_of_items():
    """One ministral run emitted the payload, then a bare array of item objects.
    Both sit at the outer level; only one is a returned object."""
    items = ',\n'.join(
        '{"id": "item-%03d", "product": "P1", "intent": "BUG", "hours": 2, "action": "ASSIGN"}' % i
        for i in range(3))
    assert _is_the_payload(_extract_payload(PAYLOAD + "\n\n[\n" + items + "\n]\n" + TRACE))


def test_the_last_returned_object_wins():
    """Two payloads: a model that restates its answer means the second one."""
    first = PAYLOAD.replace('"item-137"', '"item-000"')
    assert _is_the_payload(_extract_payload(first + "\n\nCorrection:\n" + PAYLOAD))


# ---------------------------------------------------------------------------
# Absence
# ---------------------------------------------------------------------------

def test_trace_with_no_payload_is_none():
    assert _extract_payload(TRACE) is None


def test_empty_is_none():
    assert _extract_payload("") is None


def test_a_bare_array_alone_is_not_a_payload():
    assert _extract_payload('[{"id": "item-241", "action": "ASSIGN"}]') is None


def test_braces_inside_strings_do_not_split_the_object():
    doc = '{"status": "OK", "note": "use {{item.id}} in the template", "items": []}'
    got = _extract_payload(TRACE + "\n" + doc)
    assert got is not None and got["note"].startswith("use {{item.id}}")
