# SOL Spec — v0.3.5

> Simple Orchestration Language.

SOL is a JSON format for defining processes that AI agents execute. The agent reads the entire document before executing. No external runtime is required — the agent is the runtime.

---

## Root structure

```json
{
  "name": "process-name",
  "version": "1.0",
  "description": "What this process does, why it exists, when to run it.",
  "ref": "https://github.com/jtplugin/sol",
  "env": "path/to/working/directory/",
  "model": "balanced",
  "role": "Optional persona or identity the agent should adopt for this process.",
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
| `role` | no | Persona the agent adopts for this process; inherited by nested scopes |
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

### WHEN

Evaluates a list of conditions and executes the matching branches.

```json
{
  "WHEN": [
    { "when": "condition A", "then": [ ... ] },
    { "when": "condition B", "then": [ ... ] },
    { "else": [ ... ] }
  ]
}
```

`else` is optional and executed only if no `when` matched.

**When conditions are mutually exclusive** — at most one branch can be true at a time — behavior is fully predictable regardless of how the agent interprets the construct.

**When conditions can overlap** — more than one `when` may be true simultaneously — behavior is not guaranteed. Some agents will execute all matching branches; others may stop at the first match. SOL cannot enforce a specific interpretation, because the agent is the runtime.

> If you need predictable behavior with potentially overlapping conditions, use sequential `IF` blocks instead — each is an independent instruction and there is no ambiguity about execution.

Use `IF` for binary decisions. Use `WHEN` when conditions are mutually exclusive and you want a shared `else`, or when co-activation of multiple branches is explicitly the desired behavior and the process author accepts that it depends on the agent.

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

Execution strategy (sequential vs parallel) is not prescribed by SOL — it depends on the execution context and the agent's instructions.

---

### RUN

Executes a command verbatim. Language is inferred from the extension. What you write is what gets executed — the agent does not interpret the command.

Use `{{placeholder}}` for parts the agent must resolve from context. Everything outside `{{...}}` is passed as written.

```json
{ "RUN": "main.py vault-scan {{repository}} {{max_files}}" }
```

```json
{ "RUN": "git commit -m '{{contextual commit message}}'" }
```

If you need the agent to figure out the full invocation — command, arguments, order — use `TODO` instead.

On failure: if the error is trivial (quoting, path, missing argument) the agent corrects and retries once. If it fails again, `ONERROR` is executed if present; otherwise the process halts with a report.

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
    "role": "Optional persona for this subroutine.",
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

### HALT

Immediately stops the process. No further instructions are executed. This is a controlled, intentional termination — not an error response.

```json
{ "HALT": null }
```

```json
{ "HALT": "Queue is empty — nothing left to process." }
```

The optional value is a message the agent surfaces before stopping. If `null`, the agent stops silently.

`HALT` is distinct from `ONERROR`: it expresses intent to stop cleanly, not a failure condition. Use it when stopping is the correct outcome, not when something went wrong.

---

### WAITUSERINPUT

Pauses execution and prompts the user for input. The agent presents the prompt, waits for a response, and then continues. The user's response is available to subsequent instructions as context.

```json
{ "WAITUSERINPUT": "Enter the target repository URL:" }
```

```json
{ "WAITUSERINPUT": "Review the draft above and type APPROVE to continue, or describe changes:" }
```

The value is the prompt displayed to the user. It is required — a blank prompt is not meaningful.

In non-interactive contexts (automated pipelines, batch processing), the agent has no user to wait for. In those cases, the agent should halt with the prompt text as the stop message rather than blocking indefinitely.

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

## The `role` field

Available on the root process or any `SUB`. The nearest scope takes precedence (inner overrides outer).

```json
{
  "name": "security-audit",
  "role": "Act as a security engineer specializing in OWASP top 10.",
  "ROUTINE": [
    { "TODO": "Scan all controllers for injection risks" },
    {
      "SUB": {
        "name": "report",
        "role": "Act as a technical writer producing audit reports.",
        "ROUTINE": [
          { "TODO": "Write findings to security-report.md" }
        ]
      }
    }
  ]
}
```

`role` is a natural language string. The agent adopts the described persona for the duration of the scope.

`role` is a hint, not an imperative. Like `model`, it expresses intent — the agent decides whether to fulfill it inline or by spawning a dedicated sub-agent. When a `SUB` carries both a distinct `role` and a `model` tier, both hints apply to that scope.

---

## Agent behavior

**Read before execute.** The agent reads the entire document before executing any instruction.

**Multi-agent.** When sections have different `model` values, distinct `role` definitions, or context makes it opportune, the agent may spawn sub-agents. No explicit declaration is needed — it is the expected behavior.

**Error handling.**
- `RUN`: reads stderr/exit code. Trivial errors (quoting, path, missing argument) are corrected and retried once. Non-trivial errors execute `ONERROR` if present, otherwise halt with report.
- `TODO`: unexpected results execute `ONERROR` if present, otherwise are reported before continuing.

Non-trivial errors are never silently corrected.

---

## Full example

```json
{
  "name": "daily-briefing",
  "version": "1.0",
  "description": "Generate a daily briefing from project status files. Run each morning before starting work.",
  "ref": "https://github.com/jtplugin/sol",
  "ROUTINE": [
    { "TODO": "Read all status files in projects/" },
    {
      "WHEN": [
        {
          "when": "any project has overdue tasks",
          "then": [{ "TODO": "List overdue items at the top with owner and original due date" }]
        },
        {
          "when": "any project has a deadline within 3 days",
          "then": [{ "TODO": "Add an upcoming deadlines section" }]
        },
        {
          "when": "any project has been inactive for more than 7 days",
          "then": [{ "TODO": "Flag stale projects for review" }]
        }
      ]
    },
    { "TODO": "Summarize progress since yesterday for each active project", "model": "fast" },
    { "TODO": "Write the final briefing to output/daily-briefing.md", "model": "smart" }
  ]
}
```
