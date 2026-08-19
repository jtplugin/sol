# SOL Testing Library

Bespoke test processes ("fixtures") for evaluating SOL execution. This is the **materials**
side of the testing effort; the strategy that frames it is in
[`../doc/testing-strategy.md`](../doc/testing-strategy.md) and the execution-testing method is in
[`../doc/testing-sol.md`](../doc/testing-sol.md).

> These fixtures are **not** the `examples/` at the repo root. Examples are demonstrative;
> fixtures are instrumented and adversarial — built so a machine can decide, without ambiguity,
> whether a run executed the way it had to.

## Layout

`toolchain/` holds the deterministic R1 unit tests for the Python tools around SOL
(`sol-lint.py` and the converters). `fixtures/` holds the bespoke test processes, organized by
**workload class** (`W0–W3` from `doc/SOL-and-models.md`), plus a cross-cutting `error-path/`
family:

```
toolchain/        R1 — deterministic unit tests for sol-lint.py / converters
fixtures/
  w0-transform/     self-contained transform; runs on E0 (model only)
  w1-linear/        linear tool process (RUN/REPEAT over a sandbox); E1+
  w2-branching/     control-flow fidelity (which branch / which items); E1+
  w3-multiagent/    isolation, contracts, model tiers; E2/E2+ only
  error-path/       injected failure → assert ONERROR/HALT
```

## What a fixture bundle contains

A fixture is a self-contained directory holding:

- **the fixture document** (`<name>.md`) — Markdown file with YAML frontmatter and the embedded
  SOL script; the single source of truth for the prompt sent to the model;
- **`inputs/`** — one staged input per branch / collection state the fixture exercises;
- **`expectations.json`** — machine-readable map: each input → its expected path/verdict and the
  oracle that checks it;
- **`README.md`** — the human-readable description: intent, why the path is determined, the
  single concern it isolates.

### Fixture document format (`<name>.md`)

The fixture document is a Markdown file with a YAML frontmatter block followed by the prompt
body that the runner sends to the model.

**Frontmatter fields**

| Field | Required | Description |
|---|---|---|
| `name` | yes | Fixture identifier, e.g. `fixture-w1-log-classifier` |
| `version` | yes | Document version string |
| `system_prompt` | yes | System prompt sent to the model — sets domain expertise without mentioning SOL |
| `description` | yes | One-sentence description of what the fixture tests |
| `accepts` | yes | Input contract (mirrors the SOL `accepts` block) |
| `returns` | yes | Output contract (mirrors the SOL `returns` block) |
| `schema` | no | Path to `sol-schema.json`, for linting |

**Body structure**

The body is the full user-facing prompt, using Markdown headings to separate sections:

```markdown
# <Task label>

<One-sentence task description referencing the SOL script.>

## File content

\`\`\`json
{{file_content}}
\`\`\`

## SOL script

\`\`\`json
{ ...SOL ROUTINE JSON... }
\`\`\`
```

The `{{file_content}}` placeholder is replaced at runtime with the JSON content of the
staged input. The last ` ```json ` block in the body is parsed as the SOL script.

**Design rationale**

Splitting the prompt into a system message (persona) and a user message (structured task)
mirrors standard prompt engineering practice. The system prompt gives the model a domain frame
without revealing anything about SOL — the model must infer the execution semantics from the
SOL script alone. This makes the test a genuine measure of how self-explanatory the SOL
notation is, not a measure of how well we can paraphrase it in natural language.

## Properties every fixture must have

1. **Determined path** — exactly one correct execution path per input; the wrong path is
   detectable in the output.
2. **Single concern** — isolates one variable (e.g. branch selection) with minimal tool/quality
   noise.
3. **Self-describing** — ships its own expectation and oracle.

## Adding a fixture

1. Pick the workload class it belongs to and create `fixtures/<class>/<name>/`.
2. Author the fixture document (`<name>.md`) with frontmatter and body as described above.
3. Embed the SOL ROUTINE JSON as the last ` ```json ` block in the body.
4. Add one input per branch/state under `inputs/`, the `expectations.json`, and a `README.md`.
5. Keep it single-concern — split a second concern into its own fixture.
