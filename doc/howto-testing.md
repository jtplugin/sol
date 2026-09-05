# SOL Testing — How-To

> Practical reference for running tests, adding fixtures, and reading results.
> For the evaluation method, see [`testing-sol.md`](testing-sol.md).
> For the runner architecture, see [`testing-runners.md`](testing-runners.md).
> For the overall strategy, see [`testing-strategy.md`](testing-strategy.md).

---

## 1. Quick start

**Prerequisites**

- Python 3.10+
- For the **session runner** (`executor.py`): the `claude` CLI installed and on PATH (Claude Code).
- For the **API runner** (`api_executor.py`): an Anthropic API key in `ANTHROPIC_API_KEY`, or passed via `--api-key`.

**One-liner: session runner**

```bash
python3 tests/runner/executor.py \
  --fixture w2-branching/release-gate \
  --input i1-blocked \
  --context E1 \
  --model claude-opus-4-8 \
  --dry-run
```

**One-liner: API runner**

```bash
python3 tests/runner/api_executor.py \
  --fixture w2-branching/release-gate \
  --input i1-blocked \
  --context E0 \
  --model claude-opus-4-8 \
  --dry-run
```

Results land in `tests/results/` (gitignored). The global ledger is `tests/results/index.jsonl`.

---

## 2. Running tests with the session runner (`executor.py`)

The session runner invokes `claude -p` and collects the model's full output.

**Basic flags**

| Flag | Required | Default | Description |
|---|---|---|---|
| `--fixture` | yes | — | Fixture ID, e.g. `w2-branching/release-gate` |
| `--input` | yes* | — | Input ID, e.g. `i1-blocked` |
| `--all-inputs` | yes* | — | Run every input in `fixtures/<id>/inputs/` |
| `--context` | no | `E1` | `E0` (no tools) or `E1` (Bash restricted to `cat`) |
| `--model` | no | `claude-opus-4-8` | Any Claude model ID |
| `--runs` | no | `1` | Number of runs per input (distributional testing) |
| `--timeout` | no | `120` | Per-run timeout in seconds |
| `--dry-run` | no | off | Execute and score without writing files |

\* `--input` and `--all-inputs` are mutually exclusive; one is required.

**Run all inputs, 5 times each**

```bash
python3 tests/runner/executor.py \
  --fixture w2-branching/release-gate \
  --all-inputs \
  --context E1 \
  --model claude-opus-4-8 \
  --runs 5
```

**Dry-run (probe mode)**

Always use `--dry-run` before committing results on a new fixture or new expectations
case. It executes the full flow and prints the score without writing anything:

```bash
python3 tests/runner/executor.py \
  --fixture w2-branching/release-gate \
  --input i1-blocked \
  --context E0 \
  --model claude-opus-4-8 \
  --dry-run
```

**Output table columns**

```
  #     Input                               Q      F      Degrade
  -----------------------------------------------------------------------
  1     i1-blocked #1                       ✓      ✓      none
```

- `Q` — quality check: `✓` pass, `✗` fail, `–` not checkable
- `F` — fidelity check (trace-based): same symbols
- `Degrade` — degradation mode (see §6)

**Context choices**

- `E0`: the runner pre-injects the file content into the prompt. The model never calls any tool. Simulates a bare API call with no agent loop.
- `E1`: the staged file is mentioned by path; the model must `cat` it via the Bash tool. Simulates a minimal tool-loop environment.

---

## 3. Running tests with the API runner (`api_executor.py`)

The API runner calls the Anthropic Messages API directly — no `claude` CLI, no
Claude Code session. This makes it suitable for CI pipelines, alternative endpoints,
and benchmarks that need to be independent of the local Claude Code installation.

**Additional flags (beyond the session runner)**

| Flag | Default | Description |
|---|---|---|
| `--mode` | — | Load `runner_type`, `url`, `model`, `backend`, `reasoning`, `temperature` from `tests/modes.json`, and `key` from `tests/env.json` (e.g. `claude-api`) |
| `--api-key` | `$ANTHROPIC_API_KEY` | Anthropic API key (overrides `--mode`) |
| `--api-url` | `https://api.anthropic.com` | API base URL (overrides `--mode`) |
| `--backend` | `anthropic` | `anthropic` \| `ollama` \| `openai` (LM Studio's native `/v1/chat/completions`) |
| `--temperature` | provider default | Sampling temperature (overrides `--mode`'s `temperature` field) |

**LM Studio (`backend: "openai"`)** — E0 only, same restriction as `ollama`. Start the LM
Studio local server (Developer tab -> Start Server), check the exact model identifier under
`GET /v1/models`, and set `url`/`model` in `tests/modes.json` accordingly — a local backend
needs no key, so nothing goes in `tests/env.json`.

All other flags (`--fixture`, `--input`, `--all-inputs`, `--context`, `--model`,
`--runs`, `--timeout`, `--dry-run`) work identically to the session runner.

**Default context is E0** (not E1 as in the session runner), because single-shot
API calls are the natural mode of the API runner.

**Using `--mode` (recommended)**

The simplest way to run the API executor is with `--mode`, which reads the mode
configuration from `tests/modes.json` and the credential, if the mode needs one,
from `tests/env.json`:

```bash
python3 tests/runner/api_executor.py \
  --fixture w2-branching/release-gate \
  --all-inputs \
  --mode claude-api \
  --dry-run
```

**Two files, two jobs.** `tests/modes.json` is the mode configuration and is
**tracked in git**: a fresh clone has every mode ready to run. `tests/env.json`
holds nothing but the Anthropic keys and is **gitignored**; `tests/env.example.json`
is its template. Local modes (`backend` `openai`/`ollama`) and `claude-code-local`
need no entry there at all.

`tests/modes.json` structure (`runner_type`, `backend`, `url`, `model`, `reasoning`,
plus `temperature`/`thinking`/`ctx_size`/`kv_cache_type`/`n_parallel` where the mode
uses them — omit a field to leave it unset, `"thinking": false` is not the same as
absent):

```json
{
  "modes": [
    {
      "mode": "claude-api",
      "runner_type": "api",
      "backend": "anthropic",
      "url":  "https://api.anthropic.com",
      "model": "claude-sonnet-4-6",
      "reasoning": 0
    }
  ]
}
```

`tests/env.json` structure — credentials only, one entry per mode that needs a key:

```json
{
  "modes": [
    { "mode": "claude-api",          "key": "sk-ant-api03-..." },
    { "mode": "claude-api-thinking", "key": "sk-ant-api03-..." }
  ]
}
```

Individual flags (`--api-key`, `--api-url`, `--model`) override the values from `--mode`.

**Override the endpoint manually**

```bash
python3 tests/runner/api_executor.py \
  --fixture w2-branching/release-gate \
  --all-inputs \
  --context E0 \
  --model <provider-model-id> \
  --api-url https://your.provider.endpoint \
  --api-key sk-... \
  --dry-run
```

Any endpoint that implements the Anthropic Messages API (`POST /v1/messages`) is
supported.

**Token usage and cost**

The API response includes `input_tokens` and `output_tokens`. Cost is not available
from the API response and is recorded as `null` in the results. Use the token counts
and your provider's pricing to compute cost externally if needed.

**SDK dependency**

The API runner uses the `anthropic` Python SDK when available (`pip install anthropic`).
If the SDK is not installed it falls back to a pure `urllib` implementation — no
additional dependencies required.

**When to prefer the API runner**

- You want to test a non-default endpoint or provider.
- You are running in CI without a Claude Code installation.
- You want results that explicitly carry `runner_type: "api"` and `api_base_url`
  so they are distinguishable in `index.jsonl`.
- You want E0 single-shot measurement without the session overhead.

---

## 4. Configuring a new test fixture

### Directory layout

```
tests/fixtures/<workload-class>/<fixture-name>/
    <fixture-name>.md        ← fixture document (frontmatter + prompt body with embedded SOL)
    expectations.json        ← expected verdicts, one case per input
    inputs/
        <input-id>.json      ← one input file per test case
    README.md                ← fixture intent, oracle rationale
```

Choose the workload class that matches the constructs exercised:

| Class | Constructs | Min context |
|---|---|---|
| `w0-transform` | model-only (no tools, no control flow) | E0 |
| `w1-linear` | `RUN`, `REPEAT` | E1 |
| `w2-branching` | `WHEN`, `UNLESS`, `accepts` guard | E1 |
| `w3-multi-call` | `CALL`, `SPAWN` | E1+ |
| `error-path` | `ONERROR`, `HALT` | E1 |

### The fixture document (`<name>.md`)

The fixture document is a Markdown file that is the **single source of truth** for the
prompt the runner sends to the model. It has two parts: a YAML frontmatter block and a
Markdown body.

**Frontmatter** — machine-readable metadata:

```yaml
---
name: fixture-w2-release-gate
version: "1.0"
schema: "../../../../sol-schema.json"
system_prompt: "You are a senior software release manager who evaluates release
  readiness criteria and makes go/no-go decisions."
description: "W2 branching fixture. ..."
accepts:
  record_path:
    required: true
    desc: "..."
returns:
  verdict:
    anyof: ["BLOCKED", "READY"]
    required: true
    desc: "..."
---
```

The `system_prompt` field sets the model's domain persona. It gives the model relevant
expertise without mentioning SOL or explaining how to interpret the script — the model must
infer the execution semantics from the SOL script alone. This is intentional: the test
measures how self-explanatory the SOL notation is.

**Body** — the user prompt, structured as Markdown sections:

```markdown
# Gate evaluation task

Evaluate the release record by executing strictly the SOL script below.

## File content

\`\`\`json
{{file_content}}
\`\`\`

## SOL script

\`\`\`json
{ ...your SOL ROUTINE JSON here... }
\`\`\`
```

The runner replaces `{{file_content}}` with the JSON-serialized content of the staged
input before sending the prompt. The last ` ```json ` block in the body is parsed as
the SOL script for internal use (schema validation, E1 staged-path prompts).

**TODO phrasing tip:** Reference the file content explicitly so the model knows where to
read from in E0 (no-tools) context:

```json
{"TODO": "Read the 'line' field from the file content above. ..."}
```

### `expectations.json`

Structure:

```json
{
  "cases": [
    {
      "input": "inputs/i1-blocked.json",
      "expected_verdict": "BLOCKED",
      "expected_branch": "branch-0"
    },
    {
      "input": "inputs/i2-approved.json",
      "expected_verdict": "APPROVED",
      "expected_branch": "branch-1"
    }
  ]
}
```

- `expected_verdict`: the value the model should return in the JSON payload.
- `expected_branch`: the `BRANCH` trace label the model should emit. Omit if the fixture does not emit a `BRANCH` trace line.

**Add the expectation case BEFORE running.** Without a matching case, the checker
scores quality as `fail` (wrong-value) no matter what the model returns, because it
compares the verdict against `null`.

### Probe workflow

1. Write the SOL document and lint it clean.
2. Write one input file and its expectations case.
3. `--dry-run` on that input to verify the score is trustworthy.
4. Only then commit and run with `--runs N`.

### Input file format

An input is a plain JSON object. The schema is whatever your `accepts` contract
specifies. Example:

```json
{
  "pr_id": "PR-42",
  "title": "Add dark mode",
  "checks": ["ci", "review"],
  "all_checks_passed": false
}
```

---

## 5. Reading results

### File layout

```
tests/results/
  <fixture-id>/<context>/<model>/<spec-version>/
    <run-id>.json            ← RunRecord
    <run-id>.score.json      ← ScoreRecord
  index.jsonl                ← append-only ledger, one row per run
```

Example path:
```
tests/results/w2-branching/release-gate/E1/claude-opus-4-8/0.6/
  w2-branching-release-gate-i1-blocked-20260604T125406-r01.json
```

### RunRecord fields (`.json`)

| Field | What it contains |
|---|---|
| `run_id` | Unique identifier for this run |
| `timestamp` | ISO-8601 UTC timestamp |
| `config.fixture_id` | The fixture that was run |
| `config.context` | E0 \| E1 |
| `config.model_id` | Model used |
| `config.runner_type` | `"claude-code"` (session runner) or `"api"` (API runner) |
| `config.api_base_url` | API endpoint if `runner_type="api"`, otherwise `null` |
| `config.env_realization` | `"native"` (session runner) or `"emulated"` (API runner) |
| `execution.status` | `done` \| `error` \| `na` |
| `execution.wall_clock_ms` | Total run time |
| `trace.steps` | Structured trace lines emitted by the model |
| `output.raw` | Full raw model output |
| `output.returned_payload` | Parsed JSON payload from the RETURN |
| `usage.tokens_in` | Input tokens (API runner: from response; session runner: aggregated) |
| `usage.tokens_out` | Output tokens |
| `usage.cost` | Cost in USD (session runner only; `null` for API runner) |

### ScoreRecord fields (`.score.json`)

| Field | Meaning |
|---|---|
| `fidelity.result` | `pass` \| `fail` \| `not_checkable` |
| `fidelity.expected_branch` | Branch label from expectations |
| `fidelity.observed_branch` | Branch label from trace |
| `quality.result` | `pass` \| `fail` \| `not_checkable` |
| `quality.expected` | Expected verdict |
| `quality.got` | Returned verdict |
| `efficiency.wall_clock_ms` | Wall clock (copy from RunRecord) |
| `efficiency.tokens_in/out` | Token usage |
| `degradation_mode` | How the model failed (or `none`) |

### `index.jsonl`

Each line is a JSON row — a flattened summary of one run. Use it to filter and
aggregate without loading individual run files.

**Filter by runner type:**

```python
import json
rows = [json.loads(l) for l in open("tests/results/index.jsonl")]
api_rows     = [r for r in rows if r.get("runner_type") == "api"]
session_rows = [r for r in rows if r.get("runner_type") == "claude-code"]
```

**Compare session vs API on the same fixture:**

```python
fixture = "w2-branching/release-gate"
for rt in ("claude-code", "api"):
    subset = [r for r in rows
              if r["fixture_id"] == fixture and r.get("runner_type") == rt]
    passed = sum(1 for r in subset if r["quality"] == "pass")
    print(f"{rt}: {passed}/{len(subset)} quality pass")
```

---

## 6. Degradation modes

The `degradation_mode` field describes how the model behaved when it did not produce
the expected result:

| Mode | Meaning |
|---|---|
| `none` | Correct result, no degradation |
| `none` | Correct output, exact format |
| `extra-fields` | Correct output, payload has extra fields beyond expected (**pass**) |
| `wrong-format` | Correct value, wrong format (case mismatch, number as string) |
| `wrong-structure` | Correct value, buried inside a nested object instead of at root |
| `wrong-value` | Wrong value returned |
| `no-output` | No JSON payload returned |
| `refused` | Model refused to execute the process |
| `garbled-output` | Output is not parseable JSON |
| `execution-error` | Runner error (timeout, crash, etc.) |
| `na` | Not applicable (e.g., `not_checkable` fixture) |

`not_checkable` in `quality.result` or `fidelity.result` is not a failure — it
means the fixture does not have a deterministic oracle for that dimension. Count
only `pass` and `fail` rows when computing pass rates.

---

## 7. Common workflows

### "I want to check if a model handles a new edge case"

1. Create a new input file in `tests/fixtures/<class>/<name>/inputs/`.
2. Add the corresponding case to `expectations.json`.
3. Run with `--dry-run` first to confirm the score is correct.
4. Run with `--runs 5` to get a distributional sample.

### "I want to compare the session runner vs API runner on the same fixture"

```bash
# Session runner
python3 tests/runner/executor.py \
  --fixture w2-branching/release-gate --all-inputs \
  --context E1 --model claude-opus-4-8 --runs 5

# API runner (same fixture, same model, E0 — closest comparable context)
python3 tests/runner/api_executor.py \
  --fixture w2-branching/release-gate --all-inputs \
  --context E0 --model claude-opus-4-8 --runs 5
```

Then filter `index.jsonl` by `runner_type` to compare results side-by-side.

### "I want to add a new model to the matrix"

Just change `--model`. No fixture changes needed. Results are stored under a
separate `<model>` directory so they do not collide with existing runs.

### "I want to run the full cross-product for a fixture"

```bash
for context in E0 E1; do
  python3 tests/runner/executor.py \
    --fixture w2-branching/release-gate \
    --all-inputs --context $context \
    --model claude-opus-4-8 --runs 3
done
```

### "A run shows wrong-value at 100% — is the model broken?"

Check first: does every input have a matching case in `expectations.json`? If an
input has no case, the checker always scores it as `fail` regardless of the model's
output. Run `--dry-run` on one input and inspect the raw output before concluding
the model is at fault.

### "I want to run the R1 toolchain tests"

```bash
python3 -m pytest tests/toolchain -q
```

These are deterministic unit tests for `sol-lint.py` and `checker.py`. They do not
invoke any model and should pass on every commit.

### "I need to backfill runner_type into existing results"

If you have run records produced before `runner_type` was added to the schema:

```bash
# Preview changes
python3 tests/runner/migrate_runner_type.py --dry-run

# Apply
python3 tests/runner/migrate_runner_type.py
```

The script is idempotent.
