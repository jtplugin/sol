#!/usr/bin/env python3
"""
SOL test runner — manual executor.

Stages the input, shows the SOL document and the staged path, prompts the user
to execute the process (manually or via a separate agent session), captures the
full raw output (trace lines + returned payload), writes the run-record, runs
the checker, and prints the score.

Usage:
    python3 tests/runner/runner.py \\
        --fixture w2-branching/release-gate \\
        --input i1-blocked \\
        --context E1 \\
        --model <model-id>

Expected output format from the executing agent:
    [fixture-w2-release-gate][main] BRANCH: branch-0
    {"verdict": "BLOCKED"}

Results are written to tests/results/ (gitignored).
"""
from __future__ import annotations
import argparse
import json
import re
import shutil
import sys
import tempfile
import yaml
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class InputBundle:
    mode: str                              # "single" | "multi"
    payload: dict | None = None            # single: parsed JSON
    files: dict[str, str] = field(default_factory=dict)  # multi: {stem: raw text}

# Matches structured trace lines: [<fixture>][<scope>] <TYPE>: <detail>
_TRACE_LINE_RE = re.compile(r"\[[^\]]+\]\[[^\]]+\]\s+(EVAL|BRANCH|RETURN|START|HALT):.+")

REPO_ROOT    = Path(__file__).resolve().parents[2]
FIXTURES_DIR = REPO_ROOT / "tests" / "fixtures"
RESULTS_DIR  = REPO_ROOT / "tests" / "results"
INDEX_PATH   = RESULTS_DIR / "index.jsonl"

sys.path.insert(0, str(REPO_ROOT / "tests"))
from runner.schema import (
    Config, Execution, Output, RunRecord, Trace, Usage,
)
from runner.checker import check


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

# The minimal instruction of the L1 level (doc/experiment-minimum-context.md
# SS5.1), verbatim. Deliberately NOT part of the fixture body: the body is L0
# (input data + the SOL script, no prose explaining how SOL is read), and every
# level above appends its own collateral on top. Kept next to the fixture loader
# so both executors build the same L1.
L1_INSTRUCTION = "follow the algorithm described in the JSON literally"


def _load_fixture(fixture_id: str):
    """Load a fixture from its .md file.

    Returns (fixture_dir, sol_doc, expectations, fixture_meta) where
    fixture_meta is {"meta": <frontmatter dict>, "body": <markdown body str>}.
    """
    fixture_dir = FIXTURES_DIR / fixture_id
    if not fixture_dir.is_dir():
        sys.exit(f"Fixture not found: {fixture_dir}")
    name = fixture_dir.name
    md_path = fixture_dir / f"{name}.md"
    exp_path = fixture_dir / "expectations.json"
    if not md_path.exists():
        sys.exit(f"Fixture document not found: {md_path}")
    if not exp_path.exists():
        sys.exit(f"expectations.json not found: {exp_path}")

    text = md_path.read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---\n(.*)", text, re.DOTALL)
    if not m:
        sys.exit(f"Invalid fixture MD (missing YAML frontmatter): {md_path}")
    meta = yaml.safe_load(m.group(1))
    body = m.group(2).strip()

    # Find the SOL script: first ```json block containing "ROUTINE".
    json_blocks = re.findall(r"```json\n(.*?)```", body, re.DOTALL)
    if not json_blocks:
        sys.exit(f"No ```json block found in fixture body: {md_path}")
    sol_blocks = [b for b in json_blocks if '"ROUTINE"' in b]
    if not sol_blocks:
        sys.exit(f"No SOL script (ROUTINE) found in fixture body: {md_path}")
    sol_doc = json.loads(sol_blocks[0])
    for key in ("name", "version", "description", "accepts", "returns"):
        if key in meta:
            sol_doc[key] = meta[key]
    if "schema" in meta:
        sol_doc["$schema"] = meta["schema"]

    expectations = json.loads(exp_path.read_text(encoding="utf-8"))

    # SS5.4 of doc/experiment-minimum-context.md: the same process rendered in
    # prose, one file per rendering, named <fixture>-<rendering>.md next to the
    # SOL document. They carry no SOL script, so they are read here rather than
    # through the ROUTINE-bearing path above. Absent files are not an error: a
    # fixture with no prose rendering simply has no prose cells.
    prose = {}
    for prose_path in sorted(fixture_dir.glob(f"{name}-prose-*.md")):
        rendering = prose_path.name[len(name) + 1:-3]
        prose_text = prose_path.read_text(encoding="utf-8")
        pm = re.match(r"^---\n(.*?)\n---\n(.*)",
                      prose_text, re.DOTALL)
        prose[rendering] = pm.group(2).strip() if pm else prose_text.strip()

    fixture_meta = {"meta": meta, "body": body, "prose": prose}
    return fixture_dir, sol_doc, expectations, fixture_meta


def _load_input(fixture_dir: Path, input_id: str) -> InputBundle:
    json_p = fixture_dir / "inputs" / f"{input_id}.json"
    dir_p  = fixture_dir / "inputs" / input_id
    if json_p.exists():
        return InputBundle(mode="single",
                           payload=json.loads(json_p.read_text(encoding="utf-8")))
    if dir_p.is_dir():
        files = {f.stem: f.read_text(encoding="utf-8")
                 for f in sorted(dir_p.iterdir()) if f.is_file()}
        return InputBundle(mode="multi", files=files)
    sys.exit(f"Input not found: {json_p} or {dir_p}/")


def assert_queue_alignment(fixture_dir: Path) -> None:
    """Cross-check the staged queue-NN.json inputs against queues-manifest.json
    and expectations.json for w2-branching/support-intake. The three are meant
    to be regenerated together (build_queues.py then hydrate.py --mode queues,
    FR-21) -- this is the net if someone forgets one half. Raises RuntimeError
    naming the queue id and the index of the first disagreement.

    (a) staged item id order == queues-manifest.json's item_ids for that queue.
    (b) staged item id order == the id sequence derivable from expectations.json's
        expected_sequence for that queue, which only covers the prefix actually
        processed (stops before any items past an ESCALATE halt)."""
    manifest = json.loads((fixture_dir / "queues-manifest.json").read_text(encoding="utf-8"))
    expectations = json.loads((fixture_dir / "expectations.json").read_text(encoding="utf-8"))
    cases_by_input = {c["input"]: c for c in expectations.get("cases", [])}

    for entry in manifest["queues"]:
        queue_id = entry["queue_id"]
        manifest_ids = entry["item_ids"]

        queue_path = fixture_dir / "inputs" / f"{queue_id}.json"
        queue_data = json.loads(queue_path.read_text(encoding="utf-8"))
        staged_ids = [item["id"] for item in queue_data["queue"]]

        if staged_ids != manifest_ids:
            for i, pair in enumerate(zip(staged_ids, manifest_ids)):
                a, b = pair
                if a != b:
                    raise RuntimeError(
                        f"{queue_id}: staged input diverges from queues-manifest.json "
                        f"at index {i} ({a!r} != {b!r})"
                    )
            raise RuntimeError(
                f"{queue_id}: staged input length {len(staged_ids)} != "
                f"queues-manifest.json length {len(manifest_ids)}"
            )

        case = cases_by_input.get(f"inputs/{queue_id}.json")
        if case is None or "expected_sequence" not in case:
            continue
        case_ids = [label.split(" ", 1)[0].removeprefix("item=")
                    for label in case["expected_sequence"]]

        for i, (a, b) in enumerate(zip(staged_ids, case_ids)):
            if a != b:
                raise RuntimeError(
                    f"{queue_id}: staged input diverges from expectations.json "
                    f"expected_sequence at index {i} ({a!r} != {b!r})"
                )


def assert_request_alignment(fixture_dir: Path) -> None:
    """The same net as assert_queue_alignment, for w2-branching/support-routing.

    Three files are meant to be regenerated together -- build_requests.py writes
    items-manifest.json and expectations.json, hydrate.py --mode requests stages
    the inputs from the first of them. Checked here before a server starts,
    because a staged request carrying a world state its expectation was not
    computed against does not fail: it scores, wrongly, and the run looks like a
    result.

    (a) the staged item id is the one the manifest names;
    (b) the staged world state -- remaining hours and the three team states --
        is the one the expectation for that request was computed against;
    (c) the staged item carries no product and no intent, which the model is
        there to supply.
    """
    manifest = json.loads((fixture_dir / "items-manifest.json").read_text(encoding="utf-8"))
    expectations = json.loads((fixture_dir / "expectations.json").read_text(encoding="utf-8"))
    cases_by_input = {c["input"]: c for c in expectations.get("cases", [])}

    for req in manifest["requests"]:
        rid = req["request_id"]
        staged_path = fixture_dir / "inputs" / f"{rid}.json"
        if not staged_path.exists():
            raise RuntimeError(
                f"{rid}: {staged_path} not staged -- run "
                f"'python tests/scripts/hydrate.py --mode requests'")
        staged = json.loads(staged_path.read_text(encoding="utf-8"))

        if staged.get("item", {}).get("id") != req["item_id"]:
            raise RuntimeError(
                f"{rid}: staged item id {staged.get('item', {}).get('id')!r} != "
                f"items-manifest.json {req['item_id']!r}")
        for field in ("product", "intent"):
            if field in staged.get("item", {}):
                raise RuntimeError(
                    f"{rid}: staged item carries {field!r} -- the model classifies it")

        case = cases_by_input.get(f"inputs/{rid}.json")
        if case is None:
            raise RuntimeError(f"{rid}: no case in expectations.json for inputs/{rid}.json")
        for source, label in ((req["world"], "items-manifest.json"),
                              (case.get("world", {}), "expectations.json")):
            if staged.get("remaining_hours") != source.get("remaining_hours"):
                raise RuntimeError(
                    f"{rid}: staged remaining_hours {staged.get('remaining_hours')!r} != "
                    f"{label} {source.get('remaining_hours')!r}")
            if staged.get("teams") != source.get("teams"):
                raise RuntimeError(
                    f"{rid}: staged team states {staged.get('teams')!r} != "
                    f"{label} {source.get('teams')!r}")


def _stage(bundle: InputBundle) -> tuple[Path, Path]:
    sandbox = Path(tempfile.mkdtemp(prefix="sol-run-"))
    if bundle.mode == "single":
        staged = sandbox / "record.json"
        staged.write_text(
            json.dumps(bundle.payload, indent=2, ensure_ascii=False), encoding="utf-8")
        return sandbox, staged
    # multi: copy each file into sandbox; staged = sandbox dir
    for stem, content in bundle.files.items():
        (sandbox / stem).write_text(content, encoding="utf-8")
    return sandbox, sandbox


# ---------------------------------------------------------------------------
# Result paths
# ---------------------------------------------------------------------------

def _record_path(config: Config, run_id: str) -> Path:
    safe_ctx   = config.context.replace("+", "plus")
    safe_model = config.model_id.replace("/", "_").replace(":", "_")
    return (
        RESULTS_DIR / config.fixture_id / safe_ctx / safe_model
        / config.spec_version / f"{run_id}.json"
    )


def _score_path(record_path: Path) -> Path:
    return record_path.with_name(record_path.stem + ".score.json")


def _append_index(record: RunRecord, score) -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    row = {
        "run_id":           record.run_id,
        "fixture_id":       record.config.fixture_id,
        "staged_input_id":  record.staged_input_id,
        "context":          record.config.context,
        "model_id":         record.config.model_id,
        "spec_version":     record.config.spec_version,
        "env_realization":  record.config.env_realization,
        "runner_type":      record.config.runner_type,
        "api_base_url":     record.config.api_base_url,
        "backend":          record.config.backend,
        "reasoning_budget": record.config.reasoning_budget,
        "thinking":         record.config.thinking,
        "ctx_size":         record.config.ctx_size,
        "kv_cache_type":    record.config.kv_cache_type,
        "n_parallel":       record.config.n_parallel,
        "process_rendering": record.config.process_rendering,
        "mode":             record.config.mode,
        "status":           record.execution.status,
        "quality":          score.quality.result,
        # The graded companion of the binary verdict (§12, 2026-08-25): the
        # fraction of expected_output's leaf fields the payload reproduced. It
        # reached the index only through backfill_index_scores.py, never from
        # here, so every run since it was introduced wrote a row without it and
        # the column stayed blank until somebody remembered to backfill --
        # noticed 2026-08-31 on the frontier arm's 280 fresh rows. The measure is
        # exactly what tells "wrong answer" from "right answer, one field off",
        # which is the whole reason it exists.
        "quality_rate":     score.quality.rate,
        "fidelity":         score.fidelity.result,
        "degradation_mode": score.degradation_mode,
        # The continuous metrics. quality and fidelity are binary and, on a
        # fixture that scores semantic comprehension alongside control flow,
        # can only read `fail` -- these are what tells two failing runs apart.
        # None on fixtures without the sequence oracle, and on runs that
        # emitted no trace to score.
        "conditional_rate":   score.fidelity.conditional_rate,
        "comprehension_rate": (score.comprehension.rate
                               if score.comprehension is not None else None),
        "sequence_rate":      score.fidelity.sequence_rate,
        # A run with no trace line is unmeasurable, not failed: every rate
        # above is None for it, and averaging over it would silently drop it.
        "traced":             bool(score.fidelity.observed_sequence),
        "wall_clock_ms":    record.execution.wall_clock_ms,
        "tokens_in":        record.usage.tokens_in,
        "tokens_out":       record.usage.tokens_out,
        "timestamp":        record.timestamp,
    }
    with open(INDEX_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


# ---------------------------------------------------------------------------
# Output parsing helpers
# ---------------------------------------------------------------------------

# Markdown a model wraps a trace line in. Two classes, because they sit
# differently: a blockquote or list marker PRECEDES the line, while emphasis and
# code spans HUG it on both sides. Neither can be part of the content -- the
# line's own grammar opens with '[' and closes on a field value (an id, an
# uppercase action, a team, a number) -- so removing them cannot eat a character
# the oracle needs.
_LINE_MARKER_RE = re.compile(r"^(?:>+\s*)?(?:[-*+]\s+|\d+[.)]\s+)?")
_EMPHASIS_CHARS = "`*_ \t"


def _undecorate(line: str) -> str:
    """A trace line with its markdown wrapper removed, if it had one."""
    return _LINE_MARKER_RE.sub("", line.strip()).strip(_EMPHASIS_CHARS)


def _parse_trace(raw: str) -> list[str]:
    r"""Extract structured trace lines from the raw agent output.

    Tolerant of markdown decoration since 2026-08-24, and deliberately MORE
    tolerant than _extract_payload rather than less. The payload is what the
    process is for; the trace lines are scaffolding the fixture asks for on top
    of it, extra control instructions rather than the deliverable. Holding the
    scaffolding to a stricter formatting standard than the product is backwards,
    and the code was doing exactly that: _extract_payload already accepted a
    fenced ```json object, while this function rejected

        `[fixture-w2-support-intake][main] EVAL: item=item-241 product=P5 intent=BUG`
        - `[fixture-w2-support-intake][main] EVAL: item=item-213 product=P4 intent=FEATURE`

    because _TRACE_LINE_RE.match anchors at position 0 and a backtick is not
    '['. The line never reached trace.steps, so observed_sequence came back
    empty and the run scored traced=False, sequence_rate=0.0, comprehension and
    conditional not_checkable -- the whole of a run's fidelity discarded over a
    decoration character, with the content correct underneath.

    Measured across MAIN's 1,236 records: 61 runs recover a trace carrying real
    values, 60 of them ministral-8b -- 29% of that model's campaign, silently
    zeroed. Two more recover only unsubstituted templates ('item={{item.id}}'),
    which are not executions and score as wrong once visible, which is what they
    are. The split is 61 to 2, so tolerating the wrapper is not a judgement call
    about ambiguous cases.

    Normalising here rather than loosening each oracle's regex keeps the blast
    radius at one function: trace.steps holds clean lines, and every pattern
    downstream in checker.py goes on matching what it always matched. raw stays
    the observation, untouched; steps are a derivation of it, and this changes
    how the derivation is taken.
    """
    out = []
    for line in raw.splitlines():
        candidate = _undecorate(line)
        if _TRACE_LINE_RE.match(candidate):
            out.append(candidate)
    return out


def _extract_payload(raw: str) -> object | None:
    r"""
    Extract the returned JSON payload from the raw agent output: the last
    top-level JSON object in the text.

    A model that follows the process emits its trace lines and then the object,
    so "the payload" is the last object at the outermost level -- never one of
    the items nested inside it, and never a stray object quoted in prose above.

    Matching braces with a regex cannot express that. The first version of this
    function used `\{.*?\}`, which on a payload like

        {"status": "OK", "items": [{"id": "item-241", ...}, ...], ...}

    stopped at the closing brace of the FIRST item, failed to parse, resumed
    after it, and returned the second item as the payload -- a well-formed dict,
    just not the one the model returned. Silent, and it hit 204 of MAIN's runs:
    every model that wrote its trace in plain text ahead of an unfenced object.

    `raw_decode` parses from an offset and reports where the value ended, which
    is what tells a top-level object from a nested one. Offsets that do not
    start a value (a `{` inside prose, an unbalanced one) simply raise and the
    scan moves on, so text around the payload cannot derail it.

    One model emitted its payload first and a bare list of item objects after
    it, which leaves two candidates at the outer level. An object introduced by
    `[` or `,` is an element of an array and cannot be what a RETURN produced,
    so those are skipped -- a syntactic rule, not a guess about the contract.
    """
    text = raw.strip()
    try:
        obj = json.loads(text)
        if isinstance(obj, dict):
            return obj
    except json.JSONDecodeError:
        pass

    decoder = json.JSONDecoder()
    found: object | None = None
    consumed_to = -1
    for m in re.finditer(r"\{", text):
        start = m.start()
        if start < consumed_to:
            continue            # nested inside an object already decoded
        try:
            obj, end = decoder.raw_decode(text, start)
        except json.JSONDecodeError:
            continue
        consumed_to = end
        if not isinstance(obj, dict):
            continue
        before = text[:start].rstrip()
        if before and before[-1] in "[,":
            continue            # an element of an array, not a returned object
        found = obj
    return found


# ---------------------------------------------------------------------------
# Interactive prompt
# ---------------------------------------------------------------------------

def _prompt_output() -> tuple[str, str, list[str], object | None]:
    """
    Ask for the full agent output (trace lines + returned payload).
    Returns (status, raw, trace_steps, payload).
    """
    print()
    print("─" * 60)
    print("Paste the full agent output (trace lines + returned payload).")
    print("  Special values on first line: 'error' | 'na'")
    print("  Blank line to submit.")
    print("─" * 60)
    lines = []
    try:
        while True:
            line = input("> " if not lines else "  ")
            if not line.strip():
                if lines:
                    break
                continue
            if not lines and line.strip().lower() in ("error", "na"):
                return line.strip().lower(), "", [], None
            lines.append(line)
    except EOFError:
        pass

    raw = "\n".join(lines)
    steps   = _parse_trace(raw)
    payload = _extract_payload(raw)
    if payload is None and raw.strip():
        print("[warn] No JSON payload found in output — recording as no-output.",
              file=sys.stderr)
    return "done", raw, steps, payload


# ---------------------------------------------------------------------------
# Main flow
# ---------------------------------------------------------------------------

def run_manual(fixture_id: str, input_id: str, context: str, model_id: str) -> None:
    fixture_dir, sol_doc, expectations, _fixture_meta = _load_fixture(fixture_id)
    bundle  = _load_input(fixture_dir, input_id)
    sandbox, staged = _stage(bundle)

    print()
    print("=" * 60)
    print("  SOL Test Runner — manual executor")
    print("=" * 60)
    print(f"  Fixture : {fixture_id}")
    print(f"  Input   : {input_id}  [{bundle.mode}]")
    print(f"  Context : {context}  (emulated)")
    print(f"  Model   : {model_id or '(unspecified)'}")
    print()
    print(f"  Staged input → {staged}")
    print()
    if bundle.mode == "single":
        print(json.dumps(bundle.payload, indent=2, ensure_ascii=False))
    else:
        for stem, text in bundle.files.items():
            print(f"  -- {stem} --")
            print(text)
    print()
    print("  Execute the SOL document below with:")
    print(f"    record_path = {staged}")
    print()
    print("─" * 60)
    print(json.dumps(sol_doc, indent=2, ensure_ascii=False))
    print("─" * 60)

    t0 = datetime.now(timezone.utc)
    status, raw_output, steps, payload = _prompt_output()
    elapsed_ms = int((datetime.now(timezone.utc) - t0).total_seconds() * 1000)

    shutil.rmtree(sandbox, ignore_errors=True)

    ts  = datetime.now(timezone.utc)
    run_id = (
        f"{fixture_id.replace('/', '-')}-{input_id}-"
        f"{ts.strftime('%Y%m%dT%H%M%S')}"
    )

    config = Config(
        fixture_id=fixture_id,
        context=context,
        model_id=model_id or "unspecified",
        env_realization="emulated",
    )
    record = RunRecord(
        run_id=run_id,
        timestamp=ts.isoformat(),
        config=config,
        staged_input_id=input_id,
        execution=Execution(
            status=status,
            wall_clock_ms=elapsed_ms if status == "done" else None,
        ),
        trace=Trace(steps=steps),
        output=Output(
            raw=raw_output,
            returned_payload=payload if status == "done" else None,
        ),
        usage=Usage(),
    )

    score = check(record, expectations)

    rec_path = _record_path(config, run_id)
    record.save(rec_path)
    score.save(_score_path(rec_path))
    _append_index(record, score)

    # Summary
    q = score.quality
    print()
    print("=" * 60)
    print("  Score")
    print("=" * 60)
    verdict = "✓ PASS" if q.result == "pass" else ("– N/A" if q.result == "not_checkable" else "✗ FAIL")
    f = score.fidelity
    fid_mark = {"pass": "✓ PASS", "fail": "✗ FAIL"}.get(f.result, "– N/A")
    fid_detail = (f"  (expected={f.expected_branch!r}, observed={f.observed_branch!r})"
                  if f.result in ("pass", "fail") else
                  (f"  (observed={f.observed_branch!r})" if f.observed_branch else ""))
    print(f"  Quality  : {verdict}  (expected={q.expected!r}, got={q.got!r})")
    print(f"  Fidelity : {fid_mark}{fid_detail}")
    print(f"  Degradation mode : {score.degradation_mode}")
    if record.execution.wall_clock_ms:
        print(f"  Wall clock : {record.execution.wall_clock_ms} ms")
    print()
    print(f"  Run record → {rec_path.relative_to(REPO_ROOT)}")
    print(f"  Score      → {_score_path(rec_path).relative_to(REPO_ROOT)}")
    print(f"  Index      → {INDEX_PATH.relative_to(REPO_ROOT)}")
    print()


def main():
    p = argparse.ArgumentParser(
        description="SOL test runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--fixture", required=True,
                   help="Fixture ID, e.g. w2-branching/release-gate")
    p.add_argument("--input",   required=True,
                   help="Input ID, e.g. i1-blocked")
    p.add_argument("--context", default="E1",
                   help="Execution context: E0, E1, E2, E2+  (default: E1)")
    p.add_argument("--model",   default="",
                   help="Model ID (optional, e.g. claude-opus-4-8)")
    args = p.parse_args()
    run_manual(args.fixture, args.input, args.context, args.model)


if __name__ == "__main__":
    main()
