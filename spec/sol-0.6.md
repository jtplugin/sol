# SOL Spec — v0.6.1

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
  "accepts": { ... },
  "returns": { ... },
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
| `accepts` | no | Entry contract — what this process expects from whoever invokes it. See [Input/output contracts](#inputoutput-contracts) |
| `returns` | no | Exit contract — what this process produces for its invoker |
| `ONERROR` | no | Global error handler |
| `ROUTINE` | yes | Ordered list of instructions |

A process invoked by another process or a human is itself an agent from the caller's point of view. `accepts` and `returns` at the root describe that outer boundary, using the same contract form as `AGENT`.

### The two root forms

A SOL file has one of two root shapes:

**Process form** — the root *is* the process, as shown above. The file's instructions live directly in the root `ROUTINE`. Use this for a "simple script": something a human or another process runs top to bottom.

**Agent form** — the root is a thin envelope whose single payload key is `AGENT`. Use this when the file's purpose is to define one reusable agent, meant to be imported and invoked via `SPAWN`:

```json
{
  "AGENT": {
    "name": "feanor",
    "version": "1.0",
    "ref": "https://github.com/jtplugin/sol",
    "description": "What this agent does and when to use it.",
    "IMPORT": ["src/skills/ranger/SKILL.md"],
    "accepts": { ... },
    "returns": { ... },
    "ROUTINE": [ ... ]
  }
}
```

The leading `AGENT` key is the file's type discriminator: it tells the reader — human or agent — before any field is read that this file is a single agent with an isolated context boundary, not a top-to-bottom process. The agent's `name` is declared once, inside the block; there is no separate process `name` to keep in sync.

When such a file is brought in with `IMPORT`, its root agent is available to `SPAWN` by its `name`, exactly like an `AGENT` defined inline within a `ROUTINE`. File-level metadata (`ref`, `version`) and dependencies (`IMPORT`) live inside the `AGENT` block — the envelope itself carries nothing but the single `AGENT` key.

Both forms share the same field semantics; the agent form simply nests them under `AGENT` instead of placing them at the root. A file that needs to define *several* agents, or an agent plus an orchestrating routine, uses the process form and declares each `AGENT` inside its `ROUTINE`.

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

Defines a subroutine. Can appear anywhere in `ROUTINE` — the agent reads the entire document before executing, so definition order does not matter. Invoked via `CALL`.

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

A `SUB` shares the calling agent's context, so it has no `accepts`/`returns`: there is no boundary to contract across. The data a `SUB` works on is already in scope. (See [Input/output contracts](#inputoutput-contracts).)

---

### AGENT

Declares a named agent. Like `SUB`, it can appear anywhere in `ROUTINE` — definition order does not matter. Invoked via `SPAWN`.

Unlike `SUB`, `AGENT` executes in a separate context: it receives only what `SPAWN` passes via `with`, and returns only what `returns` describes. It does not share the calling agent's context.

```json
{
  "AGENT": {
    "name": "security-auditor",
    "description": "Analyzes code for OWASP top 10 vulnerabilities.",
    "model": "smart",
    "role": "Security engineer specializing in OWASP top 10.",
    "accepts": {
      "files":     { "required": true, "desc": "modified files and their diffs" },
      "severity":  { "anyof": ["all", "high+"], "desc": "minimum severity to report" }
    },
    "returns": {
      "findings":  { "json": true, "required": true, "desc": "list of {severity, file, line_range, fix}" }
    },
    "ROUTINE": [ ... ]
  }
}
```

| Field | Required | Description |
|---|---|---|
| `name` | yes | Agent identifier. Used by `SPAWN` |
| `description` | no | What the agent does and when to use it |
| `model` | no | Model tier for the agent — same semantics as the global field |
| `role` | no | Persona the agent adopts |
| `accepts` | no | Input contract — what the caller should pass via `with`. See [Input/output contracts](#inputoutput-contracts) |
| `returns` | no | Output contract — what the agent produces; available to the calling agent as context after `SPAWN` completes |
| `ROUTINE` | yes | The agent's instructions |

`accepts` and `returns` are the contract between the calling agent and this agent — what goes in, what comes out.

---

### CALL

Invokes a `SUB` defined in the same file or imported via `IMPORT`. Executes in the shared context.

```json
{ "CALL": "subroutine-name" }
```

---

### SPAWN

Invokes an `AGENT` defined in the same file or imported via `IMPORT`. Executes in a separate context.

```json
{ "SPAWN": "security-auditor" }
```

```json
{
  "SPAWN": "security-auditor",
  "with": "Files modified in this sprint and their diffs.",
  "returns": { "findings": { "json": true, "desc": "only high and critical severity" } }
}
```

| Field | Required | Description |
|---|---|---|
| `SPAWN` | yes | Name of the `AGENT` to invoke |
| `with` | no | Information to extract from the current context and pass to the agent. If omitted, the agent relies on what `AGENT.accepts` describes |
| `returns` | no | Overrides `AGENT.returns` for this invocation; string or structured contract |
| `model` | no | Overrides the agent's model tier for this invocation |
| `ONERROR` | no | Handler executed if the agent fails or returns nothing useful |

If `with` is omitted, the agent starts with no transferred context and operates from its own `ROUTINE` and `description` alone. If `returns` is omitted at both `SPAWN` and `AGENT` level, the agent's output is not explicitly captured.

---

### DELEGATE

Spawns an inline sub-agent for a self-contained task. Unlike `SPAWN`, `DELEGATE` has no named definition — the task is described directly. Use `DELEGATE` for one-off delegations; use `AGENT` + `SPAWN` when the agent is reusable or has a structured routine.

```json
{
  "DELEGATE": {
    "task": "Analyze modified files for security vulnerabilities",
    "model": "smart",
    "role": "Security engineer specializing in OWASP top 10",
    "with": "List of files modified in this sprint and their diffs",
    "returns": { "findings": { "json": true, "desc": "{severity, file, line_range, fix}" } }
  }
}
```

| Field | Required | Description |
|---|---|---|
| `task` | yes | What the sub-agent must accomplish — natural language |
| `model` | no | Model tier for the sub-agent |
| `role` | no | Persona the sub-agent adopts |
| `with` | no | Information to extract from the current context and pass to the sub-agent |
| `returns` | no | Output contract — string or structured; available to subsequent instructions as context |
| `ONERROR` | no | Handler executed if the sub-agent fails or returns nothing useful |

If `with` is omitted, the sub-agent operates from `task` alone. If `returns` is omitted, the sub-agent's output is not explicitly captured — use this when the result is observable by other means (a written file, a sent message).

---

### IMPORT

Imports definitions from an external file. After declaration, its `SUB` definitions are available via `CALL` and its `AGENT` definitions are available via `SPAWN`. If the imported file uses the [agent root form](#the-two-root-forms) — a root whose single key is `AGENT` — that root agent is itself available to `SPAWN` by its `name`.

```json
{ "IMPORT": "shared/common-routines.json" }
```

```json
{ "IMPORT": "agents/security-auditor.json" }
```

---

### RETURN

Ends the current process cleanly and hands control back to whoever invoked it — a parent process, a `CALL` site, or the human at the top level. Execution resumes *above* this point; nothing further in the current routine runs. This is the normal way a process finishes early.

```json
{ "RETURN": null }
```

```json
{ "RETURN": "Draft approved — handing the result back to the caller." }
```

The optional value is the result the process yields to its invoker. When the process declares a `returns` contract, `RETURN` carries the payload that satisfies it. If `null`, the process returns without a surfaced value.

`RETURN` does **not** end the executing agent — it ends *this process* and yields upward. Use it whenever "I'm done here, the work goes back up" is the intended outcome. This is the common case; reach for `HALT` only when you mean to stop everything.

---

### HALT

The red button: immediately stops **everything**, not just the current process. No further instructions are executed at any level, the whole run terminates, and control is *not* handed back to an invoker — the entire execution, agent session included, comes to a full stop. This is a controlled, intentional, global termination — not an error response.

```json
{ "HALT": null }
```

```json
{ "HALT": "Unrecoverable state — stopping the entire run." }
```

The optional value is a message the agent surfaces before stopping. If `null`, the agent stops silently.

`HALT` is distinct from both `RETURN` and `ONERROR`. Unlike `RETURN`, it does not yield control upward — there is no "above" to return to, the run is over. Unlike `ONERROR`, it expresses intent to stop cleanly, not a failure condition. Reserve `HALT` for when stopping the whole execution is the correct outcome; use `RETURN` for ordinary "this process is done" exits.

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

**Context requirement:** `WAITUSERINPUT` is appropriate only when the execution context is guaranteed to be interactive — the harness supports mid-process pausing, state is preserved across the pause, and a mechanism exists to surface the prompt and receive the response. When these conditions are not met, the correct design is **process decomposition**: split the workflow into two separate SOL processes. The first produces its output and halts normally; the second starts fresh with the human's input as initial context. Process decomposition works in every execution context; `WAITUSERINPUT` works only in interactive ones. See `DESIGN.md` for a full discussion.

---

## Input/output contracts

`accepts` and `returns` describe what crosses a **context boundary** — the membrane between two agents that do not share context. They exist on the root process (its outer boundary), on `AGENT`, and on the invocation-side overrides of `SPAWN` and `DELEGATE`. They do **not** exist on `SUB`: a subroutine shares the caller's context, so there is nothing to transfer and nothing to contract.

These contracts are read by an AI and honored by an AI. The exchange is a structured conversation between intelligent agents, not a serialization format. What matters is therefore the *information* — which fields must be present, and what each carries — not the punctuation. The form stays deliberately thin.

### Two forms

A contract is either a **string** or a **structured object**.

**String — open contract.** A natural-language description of what crosses the boundary. Use it when the exchange need not be constrained.

```json
"returns": "Findings with severity, file path, line range, and suggested fix."
```

**Object — structured contract.** A map of field name to its constraints. Use it when the receiving side must not improvise — when getting a value wrong would break the machine downstream, not just the conversation.

```json
"accepts": {
  "env":         { "anyof": ["coding", "staging", "production"], "required": true },
  "git_diff":    { "required": true, "desc": "diff vs the merge-base with main" },
  "item_max":    { "number": true, "required": true, "desc": "maximum number of items to evaluate" },
  "todolist_resume": { "json": true, "desc": "updated todolist; present only when resuming an interrupted run" }
}
```

### Field constraints

A field is a name mapped to a set of **optional, composable constraints** — like adjectives, not mutually exclusive types. Stack as many as apply; omit them all for a free-form field.

| Constraint | Meaning |
|---|---|
| `desc` | What the field carries, in natural language. The semantic payload — it always lives here, on every field, whatever the other constraints |
| `required` | The field must be present. Absent ⇒ `false` |
| `anyof` | A closed set of admissible values. Use when a downstream branch depends on the value — this is the one case where structure changes behavior |
| `number` | The value must be numeric (covers booleans as well) — set to `true` |
| `json` | The value must be valid, parseable JSON, so the receiver can parse it instead of interpreting it — set to `true` |

A field with no constraint key is free content: the meaning is carried entirely by its `desc`.

### Why so few constraints

The guiding test for whether a constraint earns its place: **keep it only if getting it wrong breaks the machine, not the conversation.**

- `anyof` survives because it forks downstream behavior — a closed set is a switch, and the closure is exactly what stops the receiver from inventing a value.
- `number` survives because a value either is numeric or you cannot compute with it.
- `json` survives because a receiver that intends to parse rather than interpret needs the guarantee.

Everything else — types like `text`, `path`, `bool`, references — collapses into a plain `desc`. Two AIs exchanging information do not need them; the description carries the meaning. Resist adding a sixth constraint unless it passes the same test.

### Where the boundary with deterministic code lives

These contracts are for agent-to-agent exchange. When one side is deterministic code — a Python caller expecting a file, an exit code, or stdout — the boundary does **not** run through `accepts`/`returns`. It runs through other constructs: a `TODO` that writes the file described in a spec, or a `RUN` that calls a helper with arguments. A code result is "observable by other means," and that is the case `returns` is explicitly omitted for.

---

## The `model` field

Available on any instruction, `SUB`, `AGENT`, `DELEGATE`, or at root. The nearest scope takes precedence (inner overrides outer).

| Tier | When to use |
|---|---|
| `fast` | Simple, repetitive tasks; low risk of error |
| `balanced` | Default — omitting `model` is equivalent to `balanced` |
| `smart` | Complex reasoning, ambiguous decisions, synthesis |

Alternatively, an exact model ID can be specified (e.g. `"claude-opus-4-7"`), useful when precise version control is required.

`model` is a hint, not an imperative. The agent decides how to fulfill it: inline, or by spawning a sub-agent when context makes that opportune. Process authors express *what kind of reasoning is needed* — not how to achieve it.

---

## The `role` field

Available on the root process, any `SUB`, any `AGENT`, or any `DELEGATE`. The nearest scope takes precedence (inner overrides outer).

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

## Invocation summary

Three mechanisms exist for invoking reusable work, differing in context scope and definition style:

| | `CALL` | `SPAWN` | `DELEGATE` |
|---|---|---|---|
| Definition | `SUB` | `AGENT` | inline |
| Context | shared | bounded | bounded |
| Routine | explicit | explicit | implicit |
| External file | `IMPORT` | `IMPORT` | — |
| Contract | none — shared context | `accepts` / `returns` | `with` / `returns` |

Use `CALL` when the subroutine can see everything the caller sees. Use `SPAWN` when the agent needs a clean context and a structured routine. Use `DELEGATE` for one-off tasks that don't warrant a named definition.

The contract row reflects the rule from [Input/output contracts](#inputoutput-contracts): a contract exists only where there is a context boundary to cross. `CALL` shares context, so it needs none.

---

## Agent behavior

**Read before execute.** The agent reads the entire document before executing any instruction.

**Multi-agent.** When sections have different `model` values, distinct `role` definitions, or context makes it opportune, the agent may spawn sub-agents. No explicit declaration is needed — it is the expected behavior. For explicit delegation with defined context boundaries, use `DELEGATE` (inline) or `AGENT` + `SPAWN` (named).

**Contracts.** When an `AGENT` or process declares a structured `accepts`, the receiving agent treats `required` fields as mandatory and `anyof` values as closed — it does not invent values outside the set. When it declares a structured `returns`, the agent shapes its output to match before completing. These are honored by the agent's understanding, not by a runtime type checker.

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

The same file in **agent root form** — a single reusable agent meant to be imported and invoked via `SPAWN`. The leading `AGENT` key is the file's type discriminator; `name` is declared once; file-level metadata and dependencies live inside the block:

```json
{
  "AGENT": {
    "name": "feanor",
    "version": "1.0",
    "ref": "https://github.com/jtplugin/sol",
    "description": "Implement the code for the current card. Reads spec + plan, implements, runs a gap check via Ranger, handles stale tests, writes 02_summary.md.",
    "model": "smart",
    "role": "Senior implementation engineer who ships exactly what the spec and plan require — no more, no less.",
    "IMPORT": ["src/skills/ranger/SKILL.md"],
    "accepts": {
      "path_spec": { "required": true,  "desc": "path to 00_spec.md" },
      "path_plan": { "required": true,  "desc": "path to 01_plan.md" },
      "path_test": { "required": true,  "desc": "path to 00_test.json" },
      "repo_root": { "required": true,  "desc": "absolute path to the project root" }
    },
    "returns": {
      "status":  { "anyof": ["done", "blocked"], "required": true, "desc": "implementation outcome" },
      "summary": { "required": true, "desc": "path to the written 02_summary.md" }
    },
    "ROUTINE": [
      { "TODO": "Validate that path_spec, path_plan, path_test and repo_root were provided; if any is missing, HALT with the missing field name." },
      { "TODO": "Read the spec, the plan and the test definition to understand what to build and how it will be verified." },
      { "TODO": "Implement the code described by the plan, staying within the spec's scope." },
      {
        "SPAWN": "ranger",
        "with": "the implemented diff and path_spec",
        "returns": { "gaps": { "json": true, "required": true, "desc": "list of unmet spec requirements" } },
        "ONERROR": [{ "TODO": "If Ranger returns no usable gap report, note it in the summary and continue with status 'blocked'." }]
      },
      {
        "IF": {
          "when": "Ranger reported gaps",
          "then": [{ "TODO": "Address each gap, then re-implement until the gap list is empty." }]
        }
      },
      { "RUN": "cd {{repo_root}} && pytest", "ONERROR": [{ "TODO": "If failures are caused by tests made obsolete by this change, update them to match the new behavior; otherwise fix the implementation." }] },
      { "TODO": "Write 02_summary.md describing what was implemented and any remaining caveats; return its path and the final status." }
    ]
  }
}
```

