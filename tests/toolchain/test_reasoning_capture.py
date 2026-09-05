"""R1 tests: a thinking model that returns no answer is not a model that returned
nothing (2026-08-23, during MAIN's first cell).

MAIN's first five rows came back like this:

    L0  in 14916  out 13024  raw 0 char   271s
    L0  in 14916  out 13024  raw 0 char   271s
    L0  in 14916  out 13024  raw 0 char   271s
    L1  in 14925  out 13024  raw 0 char   271s
    L1  in 14925  out  4065  raw 749 char  83s   <- quality pass

13024 is exactly `max(DEFAULT_MAX_TOKENS, reasoning_budget + 1024)` for
llama-qwen3.5-9b-think: four runs were truncated at the ceiling. But
_post_messages_openai read only `message.content`, and llama-server puts the
thinking block in `reasoning_content` when the chat template separates it -- so
the record could not say whether the model had deliberated for 13,000 tokens or
produced nothing at all. Both looked like `raw: ""`, degradation `no-output`.

That is a defect in the reader, not a measurement: on 210 qwen-think rows it would
have spent about fourteen hours recording an ambiguity. Two fields close it --
`Output.reasoning` and `Execution.stop_reason` -- and neither changes what is
scored. The answer is still `content`: the SOL contract asks for the payload, and
deliberating is not delivering.

No server and no model here: the HTTP layer is stubbed.
"""
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "tests"))

import runner.api_executor as api_mod
from runner.schema import Execution, Output, RunRecord


class _Resp:
    def __init__(self, payload):
        self._body = json.dumps(payload).encode()

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


@pytest.fixture
def stub_endpoint(monkeypatch):
    """Answer /v1/chat/completions with whatever the test hands back."""
    sent = {}

    def install(message: dict, finish_reason: str = "stop", usage: dict | None = None):
        import urllib.request

        def fake_urlopen(req, timeout=None):
            sent["payload"] = json.loads(req.data.decode())
            return _Resp({
                "choices": [{"message": message, "finish_reason": finish_reason}],
                "usage": usage or {"prompt_tokens": 10, "completion_tokens": 20},
            })

        monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
        return sent

    return install


def _call(**over):
    kwargs = dict(api_url="http://localhost:8090", model="m",
                  messages=[{"role": "user", "content": "hi"}], max_tokens=13024)
    kwargs.update(over)
    return api_mod._post_messages_openai(**kwargs)


# ---------------------------------------------------------------------------
# the reading
# ---------------------------------------------------------------------------

def test_the_thinking_block_is_no_longer_thrown_away(stub_endpoint):
    stub_endpoint({"content": "", "reasoning_content": "thirteen thousand tokens of it"},
                  finish_reason="length")

    resp = _call()

    assert resp["reasoning"] == "thirteen thousand tokens of it"
    assert resp["stop_reason"] == "length"


def test_the_thinking_block_is_not_the_answer(stub_endpoint):
    """Merging it into content would let a run that never produced a payload score
    on the strength of having thought about one -- and would feed the trace parser
    lines the model only rehearsed."""
    stub_endpoint({"content": '{"status": "OK"}', "reasoning_content": "BRANCH: parse"})

    resp = _call()

    assert api_mod._text_from_content(resp["content"]) == '{"status": "OK"}'
    assert "BRANCH" not in api_mod._text_from_content(resp["content"])


def test_a_provider_that_calls_it_reasoning_is_read_too(stub_endpoint):
    stub_endpoint({"content": "answer", "reasoning": "shorter name, same field"})
    assert _call()["reasoning"] == "shorter name, same field"


def test_a_provider_that_sends_no_thinking_reads_empty_not_missing(stub_endpoint):
    """Every backend but this one returns no such field; `.get` on a missing key
    must not become None and travel into a str field of the record."""
    stub_endpoint({"content": "answer"})
    resp = _call()
    assert resp["reasoning"] == ""
    assert Output(raw="answer", reasoning=resp["reasoning"]).reasoning == ""


# ---------------------------------------------------------------------------
# the record
# ---------------------------------------------------------------------------

def test_the_record_can_tell_a_ceiling_from_a_full_stop():
    """tokens_out == max_tokens was the only clue, and it is circumstantial."""
    hit_ceiling = Execution(status="done", stop_reason="length")
    finished    = Execution(status="done", stop_reason="stop")
    assert hit_ceiling.stop_reason != finished.stop_reason


def test_the_two_fields_survive_a_round_trip_to_disk(tmp_path):
    rec = RunRecord(
        run_id="r1", timestamp="2026-08-23T00:00:00+00:00",
        config=api_mod.Config(fixture_id="f", context="E0", model_id="m"),
        staged_input_id="queue-01",
        execution=Execution(status="done", stop_reason="length"),
        trace=api_mod.Trace(), output=Output(raw="", reasoning="deliberation"),
        usage=api_mod.Usage(tokens_out=13024),
    )
    path = tmp_path / "r1.json"
    rec.save(path)
    back = RunRecord.load(path)

    assert back.execution.stop_reason == "length"
    assert back.output.reasoning == "deliberation"


def test_a_record_written_before_the_fields_existed_still_loads(tmp_path):
    """The nine rows of the aborted first launch, and every historical record."""
    old = {
        "run_id": "old", "timestamp": "2026-06-08T00:00:00+00:00",
        "config": {"fixture_id": "f", "context": "E0", "model_id": "m"},
        "staged_input_id": "i1",
        "execution": {"status": "done"},
        "trace": {}, "output": {"raw": "x"}, "usage": {},
    }
    path = tmp_path / "old.json"
    path.write_text(json.dumps(old), encoding="utf-8")

    back = RunRecord.load(path)

    assert back.execution.stop_reason is None
    assert back.output.reasoning == ""
