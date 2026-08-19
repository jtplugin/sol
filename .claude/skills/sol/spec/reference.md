# SOL 0.6 — Full Specification Reference

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
  "role": "Optional persona the agent should adopt.",
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
| `description` | yes | Scope and context; agent reads this first |
| `ref` | no | URL of the published spec |
| `env` | no | Working directory for RUN commands; default: root |
| `model` | no | Default model tier; default: `balanced` |
| `role` | no | Persona; inherited by nested scopes |
| `accepts` | no | Entry contract — what the process expects from its invoker (string or structured object; see AGENT) |
| `returns` | no | Exit contract — what the process produces for its invoker |
| `ONERROR` | no | Global error handler |
| `ROUTINE` | yes | Ordered list of instructions |

### The two root forms

A SOL file has one of two root shapes:

**Process form** — the root *is* the process, as shown above; instructions live directly in the root `ROUTINE`. Use for a "simple script" run top to bottom by a human or another process.

**Agent form** — the root is a thin envelope whose single key is `AGENT`. Use when the file's purpose is to define one reusable agent, imported and invoked via `SPAWN`:

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

The leading `AGENT` key is the file's type discriminator: it signals — to human and agent alike — before any field is read that this file is a single agent with an isolated context boundary, not a top-to-bottom process. The agent's `name` is declared once, inside the block, so there is no separate process `name` to keep in sync. File-level metadata (`ref`, `version`) and dependencies (`IMPORT`) live inside the `AGENT` block; the envelope carries nothing but the single `AGENT` key. When imported, this root agent is available to `SPAWN` by its `name`, exactly like an `AGENT` defined inline. A file that defines *several* agents, or an agent plus an orchestrating routine, uses the process form and declares each `AGENT` inside its `ROUTINE`.

**Library form (a variant of the process form).** A file whose only purpose is to *export* reusable `SUB`s (or `AGENT`s) for other files to `IMPORT` uses the process form, but its `ROUTINE` holds **only definitions** — `SUB`/`AGENT` blocks — and no executable top-level steps. It is never run top to bottom; it is a library. Give its `name`/`description` that meaning ("Shared spec SUBs, imported by …"). Two rules keep such a file honest: its `CALL`s and `SPAWN`s must resolve **within itself or via its own `IMPORT`** (see CALL — a SUB merely assumed present in the importer's context is not in scope), and it declares no root `accepts`, because its SUBs run in the importer's shared context — the boundary, if any, belongs to the importer.

---

## Instructions

### TODO

Natural language instruction. The agent interprets and executes it with judgment.

```json
{ "TODO": "Read all files in raw/" }
{ "TODO": "Extract decisions and next steps", "model": "smart" }
```

---

### IF

Binary condition with optional else.

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

Evaluates a list of conditions; executes matching branches.

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

**Use WHEN when conditions are mutually exclusive.** When conditions may overlap, use sequential IF blocks — each is independent and unambiguous.

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

---

### RUN

Executes a command verbatim. Use `{{placeholder}}` for parts the agent must resolve from context. Everything outside `{{...}}` is passed as written. If the agent must determine the full invocation, use TODO instead.

```json
{ "RUN": "main.py vault-scan {{repository}} {{max_files}}" }
{ "RUN": "git commit -m '{{contextual commit message}}'" }
```

On failure: trivial errors (quoting, path, missing argument) are corrected and retried once. Non-trivial errors execute ONERROR if present, otherwise halt with report.

---

### ONERROR

Error handler. Attach to any instruction (local) or declare at root (global fallback). Local takes precedence over global.

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

Defines a named subroutine that executes in the **caller's shared context**. Can appear anywhere in ROUTINE — the agent reads the full document first, so definition order does not matter. Invoked via CALL.

```json
{
  "SUB": {
    "name": "validate-input",
    "model": "fast",
    "role": "Optional persona for this subroutine.",
    "ROUTINE": [ ... ]
  }
}
```

---

### AGENT

Declares a named agent that executes in a **separate, bounded context** — receives only what SPAWN passes via `with`, returns only what `returns` describes. Definition order does not matter.

```json
{
  "AGENT": {
    "name": "security-auditor",
    "description": "Analyzes code for OWASP top 10 vulnerabilities.",
    "model": "smart",
    "role": "Security engineer specializing in OWASP top 10.",
    "accepts": "Modified files and their diffs.",
    "returns": "Findings with severity, file path, line range, and suggested fix.",
    "ROUTINE": [ ... ]
  }
}
```

| Field | Required | Description |
|---|---|---|
| `name` | yes | Agent identifier; used by SPAWN |
| `description` | no | What the agent does and when to use it |
| `model` | no | Model tier |
| `role` | no | Persona the agent adopts |
| `accepts` | no | Input contract — what the caller should pass via `with`. String or structured object |
| `returns` | no | Output contract — what the agent produces; available to the calling agent after SPAWN |
| `ROUTINE` | yes | The agent's instructions |

`accepts` and `returns` are the contract between caller and agent. They take **either** a natural-language string (open contract) **or** a structured object — a map of field name to composable constraints, used when the boundary must be honored, not interpreted:

```json
"accepts": {
  "env":         { "anyof": ["coding", "staging", "production"], "required": true },
  "git_diff":    { "required": true, "desc": "diff vs the merge-base with main" },
  "item_max":    { "number": true, "required": true, "desc": "maximum items to evaluate" },
  "todolist_resume": { "json": true, "desc": "updated todolist; present only on resume" }
}
```

Field constraints (all optional, composable; omit all for a free-form field):

| Constraint | Meaning |
|---|---|
| `desc` | What the field carries, in natural language — the meaning always lives here |
| `required` | Field must be present (absent ⇒ false) |
| `anyof` | Closed set of admissible values — use when a downstream branch depends on it |
| `number` | Value must be numeric (covers booleans) — set to `true` |
| `json` | Value must be parseable JSON — set to `true` |

Contracts exist only at **context boundaries**: root process, `AGENT`, `SPAWN`, `DELEGATE`. A `SUB` shares the caller's context and has no contract. See `doc/io-contracts.md` for the rationale.

**A contract must be honored on both sides — at the right time** (see `guides/contracts.md`):
- The agent with an `accepts` validates its *incoming* input at the top of its `ROUTINE` and defines what happens on violation — a missing `required`, an `anyof` miss, a malformed `number`/`json`. Use `RETURN` (naming the offending field), a local `ONERROR`, or a stated default; never proceed silently, never `HALT` — a failed guard hands control back to the invoker, it does not kill the whole run. This guard is part of the emitted script.
- The caller satisfies the callee's `accepts` **at authoring time**: when writing a `SPAWN`/`DELEGATE`, read the callee's contract and write a `with` that genuinely supplies it — do not emit a runtime guard around your own `with`, and do not hallucinate `with` without the contract in hand. The caller emits only an `ONERROR` for the case where the callee returns nothing, something malformed, or off-contract. A contracted call with no handling of a bad response is incomplete.

---

### CALL

Invokes a SUB defined in the same file or imported via IMPORT. Executes in the shared context.

```json
{ "CALL": "validate-input" }
```

A `CALL` must resolve to a `SUB` **defined in this file or brought in by an `IMPORT` in this file** — those are the only two ways a name is in scope. A `SUB` that merely *happens* to exist in the context of whoever imported this file (an "ambient" dependency on the importer) is **not** in scope here: if this file calls it, this file must `IMPORT` it. A `CALL` whose target is neither defined nor imported locally is a broken reference even when it works by luck because some importer defined it — the lint rejects it (Pass 7).

---

### SPAWN

Invokes an AGENT defined in the same file or imported via IMPORT. Executes in a separate context.

```json
{ "SPAWN": "security-auditor" }
```

```json
{
  "SPAWN": "security-auditor",
  "with": "Files modified in this sprint and their diffs.",
  "returns": "Only high and critical severity findings."
}
```

| Field | Required | Description |
|---|---|---|
| `SPAWN` | yes | Name of the AGENT to invoke |
| `with` | no | Context to extract and pass; if omitted, agent relies on its `accepts` description |
| `returns` | no | Overrides AGENT.returns for this invocation |
| `model` | no | Overrides the agent's model tier |
| `ONERROR` | no | Handler if the agent fails or returns nothing useful |

---

### DELEGATE

Spawns an inline one-off sub-agent. Unlike SPAWN, no named definition needed — task is described directly. Use for one-off delegations; use AGENT+SPAWN when the agent is reusable or needs a structured routine.

```json
{
  "DELEGATE": {
    "task": "Analyze modified files for security vulnerabilities",
    "model": "smart",
    "role": "Security engineer specializing in OWASP top 10",
    "with": "List of files modified in this sprint and their diffs",
    "returns": "Findings with severity, file path, line range, and suggested fix"
  }
}
```

| Field | Required | Description |
|---|---|---|
| `task` | yes | What the sub-agent must accomplish — natural language |
| `model` | no | Model tier |
| `role` | no | Persona |
| `with` | no | Context to pass; if omitted, agent operates from `task` alone |
| `returns` | no | What to produce; if omitted, output is not explicitly captured |
| `ONERROR` | no | Handler if the sub-agent fails |

---

### IMPORT

Imports SUB and AGENT definitions from an external file. After declaration, SUBs are available via CALL and AGENTs via SPAWN. If the imported file uses the agent root form (a root whose single key is `AGENT`), that root agent is available to SPAWN by its `name`.

```json
{ "IMPORT": "shared/common-routines.json" }
{ "IMPORT": "agents/security-auditor.json" }
```

---

### RETURN

Ends the current process and yields control back to its invoker (parent process, `CALL` site, or the human at top level). Execution resumes *above*; the agent is **not** ended. The common "I'm done here" exit. Optional value is the result yielded — satisfies a declared `returns` contract.

```json
{ "RETURN": null }
{ "RETURN": "Draft approved — handing the result back to the caller." }
```

When the process declares a structured `returns`, the RETURN value **mirrors that contract's shape** — same keys, filled (typically via `{{placeholder}}`). A value that does not match the contract's form is the caller's signal that something went off-contract.

---

### HALT

The red button: stops the **entire** run, agent session included. Control is *not* handed back upward — the whole execution ends. Controlled and intentional, but global. Not an error. Use `RETURN` for ordinary completion; reserve `HALT` for stopping everything.

```json
{ "HALT": null }
{ "HALT": "Unrecoverable state — stopping the entire run." }
```

---

### WAITUSERINPUT

Pauses execution and prompts the user. The user's response is available to subsequent instructions as context.

```json
{ "WAITUSERINPUT": "Review the draft above and type APPROVE to continue, or describe changes:" }
```

**Only use in guaranteed interactive contexts.** In non-interactive or batch contexts, split the workflow into two separate SOL processes instead: the first produces its output and halts normally; the second starts fresh with the human's input as initial context.

---

## Placeholders — `{{...}}`

A placeholder is a slot the agent fills from context at runtime. SOL has **one** placeholder syntax — double braces — and it is the same in **every field**, not only in `RUN`: `TODO` text, a `when` condition, a `with` payload, a `returns` override, a `HALT` message. Everything inside `{{...}}` is resolved from something in scope (an `accepts` field, a prior step's result, a loop item, a document value); everything outside is literal.

```json
{ "RUN": "deploy.py --env {{revision.env}}" }
{ "TODO": "Write the spec to {{task_dir}}/00_spec.md" }
{ "SPAWN": "censor", "with": "path_spec={{task_dir}}/00_spec.md, kind={{kind}}" }
```

**Single braces are never a placeholder.** `{task_dir}` is not resolved — it is literal text that happens to contain braces. A single-brace `{...}` where you meant a placeholder is a defect the lint must catch (Pass 7). Write `{{task_dir}}`.

Each `{{...}}` must resolve to something nameable in its scope. A placeholder that points at nothing — `{{the array built earlier}}` with no named prior step or field behind it — is a smell: name the step, the loop item, or the contract field it reads from.

---

## The `model` field

Available on any instruction, SUB, AGENT, DELEGATE, or at root. Inner scope overrides outer.

| Tier | When to use |
|---|---|
| `fast` | Simple, repetitive, low risk — format conversion, file I/O, iteration |
| `balanced` | Default — general execution with moderate judgment |
| `smart` | Complex reasoning, ambiguous decisions, synthesis, code generation |

An exact model ID can also be specified (e.g. `"claude-opus-4-8"`), useful when precise version control is required. `model` is a hint, not an imperative.

---

## The `role` field

Available on root, any SUB, any AGENT, or any DELEGATE. Inner scope overrides outer. Natural language string; the agent adopts the described persona for the duration of the scope.

`role` is a hint, not an imperative. The agent decides whether to fulfill it inline or by spawning a dedicated sub-agent.

---

## Invocation summary

| | CALL | SPAWN | DELEGATE |
|---|---|---|---|
| Definition | SUB | AGENT | inline |
| Context | shared | bounded | bounded |
| Routine | explicit | explicit | implicit |
| External file | IMPORT | IMPORT | — |
| Contract | none — shared context | `accepts` / `returns` | `with` / `returns` |

Use CALL when the subroutine can see everything the caller sees. Use SPAWN when the agent needs a clean context and a structured routine. Use DELEGATE for one-off tasks that don't warrant a named definition.

---

## Authoring rule — control flow lives in constructs, never in prose

The single most important authoring rule: a `TODO` is a **leaf** — one unit of work that
needs judgment, *after* the surrounding constructs have selected the branch and the
iteration. Decisions, case analyses, loops, error paths and waits are structural facts and
each has a construct. If they appear as sentences inside a `TODO`, the process is described,
not encoded, and the agent re-derives the structure at runtime — defeating SOL.

**Anti-pattern (forbidden):** a `TODO` whose text says "if the file exists… ; depending on
kind: - RUN: … - API: … - WEB: … ; then read env; if it already exists, don't overwrite
unless…". That is an `IF` (exists?) wrapping a `WHEN` (kind), inside a `REPEAT foreach`, with
sibling leaves — all of it lifted out of the prose. See `guides/authoring.md` for the full
refinement passes and the worked transformation of exactly this case.

Smell test — if a `TODO`/`RUN` text contains any of these, lift it into a construct:
"if/se/when/in case" → `IF`/`WHEN`; "depending on / a seconda di / a bulleted case list" →
`WHEN`; "for each / per ogni" → `REPEAT foreach`; "while/until/N times" → `REPEAT`; "on
failure / se va in errore" → `ONERROR`; "ask/wait for the human" → `WAITUSERINPUT`;
"then…, then…" → separate sibling instructions.

**Two companion rules** complete the authoring discipline:

- **Data lives in data, never in the control structure.** A family of near-identical units
  that differ only by their values (e.g. `rev_a`/`rev_b`/`rev_c`, one per env) is a *collection
  to iterate*, not N duplicated SUBs/branches/setup steps. Declare the values as a labelled
  collection and walk them with one `REPEAT foreach`; the loop item is the parameterization.
  Static, authoring-time config may live as a named JSON fence or table **in the document
  hosting the script** (the agent reads the whole document first) and be cited by the
  `foreach` — optionally preceded by a `TODO: "Read the <name> table"`, which is redundant for
  the runtime but worth keeping to disambiguate when several tables exist. Values that cross a
  context boundary at runtime are a **contract**, not document data (see below).

- **Apply the context test to every cross-unit call, including cross-file.** A call into a
  bounded context that exchanges a defined input/output is `AGENT`+`SPAWN` (with `IMPORT` if
  the definition is in another file) — not a `TODO`. Modelling such a call as
  `TODO "call the other skill"` is the cross-boundary twin of burying control flow in prose.
  Keeping cross-unit orchestration at one level with contract-less shells is a valid choice
  only if stated deliberately, not defaulted to.

---

## Construct selection guide

| Source pattern | SOL construct |
|---|---|
| "do X" / "execute Y" requiring agent judgment | `TODO` |
| Exact shell/CLI command | `RUN` |
| if / else / unless | `IF` |
| switch / match with exclusive branches | `WHEN` |
| while / until / repeat N / for each | `REPEAT` |
| N near-identical units differing only by values | labelled collection + `REPEAT foreach` |
| static config the script iterates over | named JSON fence / table in the document, cited by name |
| helper called multiple times, shares context | `SUB` + `CALL` |
| isolated agent with input/output contract, reused (same or other file) | `AGENT` + `SPAWN` (+ `IMPORT` if cross-file) |
| one-off isolated subtask | `DELEGATE` |
| load definitions from another file | `IMPORT` |
| "this process is done" / normal early completion | `RETURN` |
| "stop everything" / global hard stop | `HALT` |
| approval gate / human review | `WAITUSERINPUT` |

---

## File split heuristics

| Signal | Action |
|---|---|
| > 15 top-level instructions | Extract logical sections to separate files |
| ≥ 2 named AGENT definitions | Move each to `agents/<name>.json`, use `IMPORT` |
| SUBs reused across processes | Move to `shared/<name>.json`, use `IMPORT` |
| Clean single flow, < 15 steps | Single file |

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
