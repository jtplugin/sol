# SOL Spec — v0.2.0

> Simple Orchestration Language.

SOL is a JSON format for defining processes that AI agents execute. The agent reads the entire document before executing. No external runtime is required — the agent is the runtime.

---

## Root structure

```json
{
  "name": "process-name",
  "version": "1.0",
  "description": "What this process does, why it exists, when to run it.",
  "ref": "https://example.com/spec-url",
  "env": "path/to/working/directory/",
  "model": "balanced",
  "ONERROR": [ ... ],
  "ROUTINE": [ ... ]
}
```

| Field | Required | Description |
|---|---|---|
| `name` | yes | Process identifier |
| `version` | yes | Process version |
| `description` | yes | Scope and context; the agent reads this before executing |
| `ref` | no | URL of the published spec |
| `env` | no | Working directory for `RUN` commands; default: root |
| `model` | no | Default model tier for the process; default: `balanced` |
| `ONERROR` | no | Global error handler |
| `ROUTINE` | yes | Ordered list of instructions |

---

## Instructions

### TODO

A natural language instruction. The agent interprets and executes it in the context of the process.

```json
{ "TODO": "Read all files in raw/ root" }
```

```json
{ "TODO": "Extract decisions and next steps", "model": "smart" }
```

---

### IF

```json
{
  "IF": {
    "when": "condition",
    "then": [ ... ],
    "else": [ ... ]
  }
}
```

`else` is optional.

---

### CASE

Evaluates multiple conditions in sequence. **All branches whose `when` is true are executed**, in the order they appear. This is intentionally different from SQL CASE (which stops at the first match) — it reflects the exhaustive reasoning style of AI agents.

```json
{
  "CASE": [
    { "when": "condition A", "then": [ ... ] },
    { "when": "condition B", "then": [ ... ] },
    { "else": [ ... ] }
  ]
}
```

`else` is optional and executed only if no `when` matched.

Use `IF` for binary decisions. Use `CASE` when three or more branches exist, or when multiple branches may legitimately co-activate.

---

### REPEAT

```json
{
  "REPEAT": {
    "while|until|for|foreach": "condition or target",
    "ROUTINE": [ ... ]
  }
}
```

| Key | Semantics |
|---|---|
| `while` | Execute while condition is true |
| `until` | Execute until condition becomes true |
| `for` | Execute N times |
| `foreach` | Execute for each element of the target |

For `for` and `foreach`, if iterations are independent the agent executes them in parallel. If there are inter-iteration dependencies, it sequences them. The decision is autonomous.

---

### RUN

Executes a shell command or script. Language is inferred from the extension. Parts in `<...>` are placeholders — the agent substitutes them from context before executing. Everything else is verbatim.

```json
{ "RUN": "main.py vault-scan <repository> <max files>" }
```

```json
{ "RUN": "git commit -m '<contextual commit message>'" }
```

On failure: if the error is trivial (quoting, relative path, missing argument) the agent corrects and retries once. If it fails again, `ONERROR` is executed if present; otherwise the process halts with a report.

---

### ONERROR

Error handler. Can be attached to any instruction (local) or declared at root (global fallback). Local takes precedence over global.

```json
{
  "RUN": "main.py process",
  "ONERROR": [
    { "TODO": "Log error and stderr to log.md" },
    { "TODO": "Notify via webhook" }
  ]
}
```

Root-level global fallback:

```json
{
  "name": "my-process",
  "ROUTINE": [ ... ],
  "ONERROR": [
    { "TODO": "Log error and halt" }
  ]
}
```

---

### SUB

Defines a subroutine. Can appear anywhere in `ROUTINE` — the agent reads the entire document before executing, so definition order does not matter.

```json
{
  "SUB": {
    "name": "subroutine-name",
    "model": "smart",
    "ROUTINE": [ ... ]
  }
}
```

---

### CALL

Invokes a `SUB` defined in the same file.

```json
{ "CALL": "subroutine-name" }
```

---

### LIBRARY

Imports subroutines from an external file. After declaration, its `SUB` definitions are available via `CALL`.

```json
{ "LIBRARY": "shared/common-routines.json" }
```

---

## The `model` field

Available on any instruction, `SUB`, or at root. The nearest scope takes precedence (inner overrides outer).

| Tier | When to use |
|---|---|
| `fast` | Simple, repetitive tasks; low risk of error |
| `balanced` | Default — omitting `model` is equivalent to `balanced` |
| `smart` | Complex reasoning, ambiguous decisions, synthesis |

Alternatively, an exact model ID can be specified (e.g. `"claude-opus-4-7"`), useful when precise version control is required.

`model` is a hint, not an imperative. The agent decides how to fulfill it: inline, or by spawning a sub-agent when context makes that opportune. Process authors express *what kind of reasoning is needed* — not how to achieve it.

---

## Agent behavior

**Read before execute.** The agent reads the entire document before executing any instruction.

**Parallelization.** In `REPEAT for/foreach`, the agent evaluates whether iterations are independent. If so, it executes them in parallel. If there are dependencies, it sequences them. No annotation required.

**Multi-agent.** When sections have different `model` values or context makes it opportune, the agent may spawn sub-agents. No explicit declaration is needed — it is the expected behavior.

**Error handling.**
- `RUN`: reads stderr/exit code. Trivial errors (quoting, path, missing argument) are corrected and retried once. Non-trivial errors execute `ONERROR` if present, otherwise halt with report.
- `TODO`: unexpected results execute `ONERROR` if present, otherwise are reported before continuing.

Non-trivial errors are never silently corrected.

---

## Full example

```json
{
  "name": "vault-ingest",
  "version": "1.0",
  "description": "Process files in raw/ and entries in ingest-queue.json, updating the corresponding wiki pages.",
  "ref": "https://github.com/jtplugin/sol",
  "env": "agentic-os/src/",
  "ONERROR": [
    { "TODO": "Log error to log.md and halt" }
  ],
  "ROUTINE": [
    {
      "RUN": "main.py vault-scan <repository>",
      "ONERROR": [
        { "TODO": "Log error line by line in daily-briefing.md and continue" }
      ]
    },
    {
      "IF": {
        "when": "queue is empty",
        "then": [{ "TODO": "Halt" }]
      }
    },
    {
      "REPEAT": {
        "foreach": "entry in queue (max 5, sorted by detected desc)",
        "ROUTINE": [
          { "CALL": "process-entry" }
        ]
      }
    },
    {
      "SUB": {
        "name": "process-entry",
        "ROUTINE": [
          { "TODO": "Fetch content via GitHub API" },
          { "TODO": "Identify target wiki page" },
          { "TODO": "Update wiki page section" },
          { "TODO": "Append to log.md" }
        ]
      }
    }
  ]
}
```
