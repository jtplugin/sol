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
    fixture_meta = {"meta": meta, "body": body}
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
        "predictability_layers": record.config.predictability_layers,
        "status":           record.execution.status,
        "quality":          score.quality.result,
        "fidelity":         score.fidelity.result,
        "degradation_mode": score.degradation_mode,
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

def _parse_trace(raw: str) -> list[str]:
    """Extract structured trace lines from the raw agent output."""
    return [line.strip() for line in raw.splitlines()
            if _TRACE_LINE_RE.match(line.strip())]


def _extract_payload(raw: str) -> object | None:
    """
    Extract the returned JSON payload from the raw agent output.
    Tries the whole text first, then strips markdown fences, then finds
    the last JSON object (multiline-aware).
    """
    text = raw.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Strip ```json ... ``` or ``` ... ``` fences
    fence_m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fence_m:
        try:
            obj = json.loads(fence_m.group(1))
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            pass
    for m in re.finditer(r"\{.*?\}", text, re.DOTALL):
        try:
            obj = json.loads(m.group())
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            pass
    return None


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
