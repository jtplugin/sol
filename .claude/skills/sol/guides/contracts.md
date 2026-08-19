# Contract Guide — `accepts` / `returns` at process and agent boundaries

SOL 0.6.0 makes `accepts` and `returns` first-class at the **start of a process or an
agent**. They describe what crosses a **context boundary** — the membrane between two agents
that do not share context. This guide defines *when* a contract is worth drawing, *which
form* to use, and the *common cases*.

**Contracts are not mandatory.** A process or agent can run perfectly well without one. The
rule is simpler and stricter than "always add them": *if a contract serves a purpose, it must
be present; and if it is present, it must be done well.* A half-drawn contract — a field
with no `desc`, an `anyof` no branch reads, a `required` that nothing enforces downstream —
is worse than none, because it implies a rigor the script does not actually carry. So this
skill never adds a contract for decoration, and never leaves a needed one implicit or sloppy.

---

## Where contracts exist — and where they do not

| Location | Has `accepts` / `returns`? | Why |
|---|---|---|
| **Root process** | optional | Describes the outer boundary — what the invoker (a human or a parent process) passes in and gets out, *when there is one* |
| **`AGENT`** | optional, usually worth it | An agent runs in a bounded context; when the caller passes inputs or consumes outputs, the contract *is* that boundary |
| **`SPAWN` / `DELEGATE`** | `with` / `returns` (invocation-side) | Per-call override of what is passed and expected back |
| **`SUB`** | **never** | A subroutine shares the caller's context — there is no boundary to contract across |
| **`RUN` / `TODO` → code** | **never** | A boundary with deterministic code runs through a written file, an exit code, or arguments — not through `accepts`/`returns` |

The single deciding question: **is there a context boundary here?** If two agents that do
not share context exchange information, draw a contract. If not, do not invent one.

---

## When the root process needs a contract

Give the **root** an `accepts` when any of these hold:

1. **It is invoked by another process** (via `IMPORT` + `SPAWN`, or as a pipeline stage).
   The parent must know what to pass.
2. **It is parameterized by a human at launch** — "run the audit on `env=staging` with
   `item_max=50`". Those parameters are the entry contract.
3. **It is the second half of a decomposed workflow.** When a process is split around a
   human gate (because `WAITUSERINPUT` is not available in the target context — see the spec
   section on process decomposition), the *second* process starts fresh and takes the human's
   decision plus the first process's output as its `accepts`. This is the canonical reason a
   "starts-fresh" process carries a structured entry contract.

Give the root a `returns` when a caller (human or process) consumes its output as a defined
artifact rather than merely observing a side effect.

A self-contained process that takes no parameters and writes its result to a known file
needs **neither** — its result is "observable by other means."

---

## When an AGENT needs a contract

The decisive case is mandatory, not optional:

> **If an AGENT operates on a specific input and must return predictable information, the
> contract MUST be present.** A specific input means the agent cannot do its job from its
> `description` alone — it needs what the caller hands it: declare `accepts`. Predictable
> information means a later step relies on the shape of the result: declare `returns`. In
> this case omitting the contract is a defect — the boundary carries information and you left
> it unnamed.

- `accepts` — what `SPAWN` must pass via `with`. Required whenever the agent needs a
  specific input; without it the agent starts blind.
- `returns` — what the agent produces back into the caller's context. Required whenever the
  caller relies on the result being a particular thing.

The only case where the contract is genuinely optional — and should then be omitted, not
decorated — is the **pure side-effecting worker**: it takes no specific input from the caller
(it works from its own `description`) and yields no value the caller consumes (it sends a
message, writes a file observed by other means). There the boundary carries no information,
so there is nothing to contract.

So the test is sharp: *specific input or predictable output ⇒ contract required; neither ⇒
no contract.* It is never "an AGENT may skip the contract because it's tedious."

`SUB` is the opposite: it shares context, so it has **no** contract. If you find yourself
wanting an `accepts` on a `SUB`, that is the signal it should be an `AGENT`.

---

## Which form — string or structured

A contract is **either** a natural-language string **or** a structured object. Choose by one
test:

> **Use structured only when getting a field wrong breaks the machine, not the conversation.**

### String — open contract (the default)

Use when the exchange is between two reasoning agents and prose conveys it faithfully.

```json
"accepts": "The modified files in this sprint and their diffs.",
"returns": "Findings with severity, file path, line range, and suggested fix."
```

Reach for a string first. Most agent-to-agent exchanges are conversations, not serialization.

### Structured — object contract

Use when a downstream step must **parse rather than interpret**, branch on a closed set, or
compute on a number. A field is a name mapped to composable constraints:

```json
"accepts": {
  "env":         { "anyof": ["coding", "staging", "production"], "required": true },
  "git_diff":    { "required": true, "desc": "diff vs the merge-base with main" },
  "item_max":    { "number": true, "required": true, "desc": "maximum items to evaluate" },
  "todolist_resume": { "json": true, "desc": "updated todolist; present only when resuming an interrupted run" }
}
```

### The five constraints — and the test each one passes

| Constraint | Meaning | Why it earns its place |
|---|---|---|
| `desc` | what the field carries, in natural language | the meaning always lives here, on every field |
| `required` | field must be present (absent ⇒ false) | a missing mandatory input breaks the receiver |
| `anyof` | closed set of admissible values | a closed set is a switch — it stops the receiver inventing a value a branch depends on |
| `number` | value must be numeric (covers booleans) | you cannot compute with a non-number |
| `json` | value must be parseable JSON | a receiver that parses needs the guarantee |

A field with no constraint is free content — its `desc` carries everything. **Do not add a
sixth constraint** (`text`, `path`, `bool`, `enum`, references…): they collapse into `desc`.
Two AIs do not need them.

### Mixing forms

A single contract is one form or the other. But a structured `accepts` may have some fields
constrained and others free (just a `desc`) — stack constraints only where each passes the
test, leave the rest as prose.

---

## Invocation-side: `with` and `returns` on SPAWN / DELEGATE

The `AGENT.accepts` / `AGENT.returns` declare the *standing* contract. At the call site:

- `with` — the information to extract from the **current** context and hand across the
  boundary. If omitted, the agent relies on its own `accepts` description and starts with no
  transferred context.
- `returns` (on `SPAWN`/`DELEGATE`) — **narrows or overrides** the agent's standing
  `returns` for this one call (e.g. "only high and critical findings").

`DELEGATE` has no standing definition, so its `with` / `returns` *are* the whole contract for
that one-off call.

At every `SPAWN`/`DELEGATE`, apply the two-sided rule above: while writing it, read the
callee's `accepts` and make the `with` genuinely satisfy it (an authoring check, not an
emitted one — and never hallucinate `with` without the contract in hand); and attach an
`ONERROR` that handles a missing, malformed, or off-contract result. A `SPAWN` against a
contracted agent with no handling of a bad response is incomplete.

---

## Honoring the input contract — always handle a violation

A declared `accepts` is a promise the agent **must check**, not assume. When an agent
operates with an input contract, it must always handle the case where the input it actually
receives does **not** satisfy that contract — a `required` field missing, a value outside an
`anyof` set, a non-numeric `number`, unparseable `json`, or `with` simply absent. A contract
that is declared but never verified is a false guarantee: it reads as rigor the script does
not enforce.

So the rule pairs with the mandatory-contract rule above:

> **If an AGENT has an `accepts` contract, its `ROUTINE` must begin by validating the input
> against that contract and must define what happens when the input is invalid.**

This is not redundant with the runtime's understanding — it makes the failure *path* explicit
and deliberate, so the agent does not improvise (guess a default, proceed on half an input,
or fail silently mid-routine). Make the violation the **first** thing the agent decides on,
before any real work.

### A contract has two sides — but they are honored at different times

A contract sits between caller and callee, and each end has a duty. The crucial point is
*when* each duty is discharged — get this wrong and you bloat the generated script with
runtime checks that should never have been written.

> **Satisfying the callee's `accepts` is an authoring-time duty — yours, while writing the
> SOL — not a runtime check to emit.** When you write a `SPAWN`/`DELEGATE`, look at the
> called agent's `accepts` (its definition is in the same file, imported, or its spec is in
> context) and write a `with` that genuinely supplies every `required` field, valid `anyof`
> values, well-formed `number`/`json`. You verify this **now**, by reading the contract — not
> by generating an instruction that re-checks the outgoing `with` at runtime. **Do not emit
> caller-side validation of your own `with`; just write it correctly.** If you do not have
> the callee's contract in context, do not hallucinate the `with` — fetch or ask for the
> contract first.

> **Handling a bad *response* is a runtime duty — and it IS emitted, via `ONERROR`.** The
> caller cannot know at authoring time whether the callee will actually honor its `returns`,
> so the script must handle the case where it comes back empty, malformed, or off-contract.

```json
{
  "SPAWN": "security-auditor",
  "with": "The modified files in this sprint and their diffs.",
  "returns": { "findings": { "json": true, "desc": "list of {severity, file, line_range, fix}" } },
  "ONERROR": [
    { "TODO": "The auditor returned nothing or malformed findings. Log the raw output and re-run once with an explicit reminder of the returns shape." },
    { "TODO": "If it still does not conform, record the gap and continue without blocking the pipeline" }
  ]
}
```

Here the `with` is simply correct because the author checked `security-auditor`'s `accepts`
before writing it — there is no runtime guard around it. The only emitted handling is the
`ONERROR` for a bad response.

So the boundary is honored asymmetrically by design: **input correctness is settled at
authoring time** (the caller writes a valid `with`; the callee additionally validates on the
way in, the guard below, because *it* cannot trust who calls it), while **response soundness
is handled at runtime** by the caller's `ONERROR`. Keep the generated script lean — no check
exists in it that the author could have settled by reading the contract.

### A `WHEN`/`IF` on the result is not the `ONERROR`

A common shape is a `SPAWN` whose result immediately drives a `WHEN` — `result == 'ok'` /
`'ambiguous'` / `'ko'` / `else → …`. It is tempting to treat the `else` as the failure
handler and skip the `ONERROR`. Resist it: the two guard **different membranes**.

- The `WHEN` (including its `else`) dispatches on *values the callee actually returned*. It
  presumes the call **succeeded** and produced a result to switch on; `else` catches an
  *unexpected value*.
- The `ONERROR` fires when the callee **failed, returned nothing, or returned something
  off-contract** — i.e. when there is no honest result to branch on at all.

```json
{ "SPAWN": "censor", "with": "path_spec={{task_dir}}/00_spec.md, kind={{kind}}",
  "ONERROR": [
    { "TODO": "censor failed or returned nothing parseable. Record it as blocked and stop — do not fall through to the value branches." }
  ]
},
{ "WHEN": [
  { "when": "censor_result.result == 'ok'",  "then": [ /* … */ ] },
  { "when": "censor_result.result == 'ko'",  "then": [ /* … */ ] },
  { "else": [ /* unexpected value */ ] }
]}
```

Folding the dead-call case into the `WHEN`'s `else` conflates "censor said something
unexpected" with "censor never answered," and the two demand different recovery. A `SPAWN`
whose result feeds a `WHEN` still needs its own `ONERROR`.

### How the callee guards its input

The guard goes at the top of the agent's `ROUTINE`. Two shapes, by what the violation means:

**Cannot proceed — the agent has no valid input to work on** → `RETURN` with a message that
names the offending field, or a local `ONERROR` if there is a recovery/notification action.
Hand control back to the invoker; do **not** `HALT` — a contract violation in one callee must
not abort the entire run, only end *this* process and report upward.

```json
{
  "AGENT": {
    "name": "deploy-runner",
    "accepts": {
      "env":    { "anyof": ["staging", "production"], "required": true },
      "build":  { "required": true, "desc": "build artifact id to deploy" }
    },
    "returns": "Deployment result: status and target url.",
    "ROUTINE": [
      {
        "IF": {
          "when": "env is missing or not one of [staging, production], or build is missing",
          "then": [
            { "RETURN": "Input contract violated: 'env' must be one of [staging, production] and 'build' is required. Received: {{the actual inputs}}." }
          ]
        }
      },
      { "TODO": "Deploy {{build}} to {{env}}" }
    ]
  }
}
```

**Recoverable — a valid input can be obtained or defaulted deliberately** → handle it
explicitly (request it, derive it, fall back to a stated default), never silently.

```json
{
  "IF": {
    "when": "item_max is absent or not a number",
    "then": [
      { "TODO": "Default item_max to 50 and note in the run log that the caller omitted it" }
    ]
  }
}
```

The same applies at the **root** when it declares `accepts`: a parameterized or
process-decomposed entry point validates its initial input before the first real step, and
halts (or asks, in interactive contexts) on violation.

A contract verified on the way **in** is what makes the contract on the way **out**
trustworthy: an agent that guarantees a `returns` shape must refuse the inputs that would make
that guarantee impossible.

---

## Static document data is not a contract

A contract crosses a **context boundary at runtime**. Do not confuse it with **static data
declared in the document** that hosts the script — a JSON fence, a markdown table, or a CSV
block that the agent reads (the whole document is in context before execution) and that the
ROUTINE iterates over with `REPEAT foreach`. That data is *configuration known at authoring
time*; it carries no boundary, so it gets **no** `accepts`/`returns` and no field constraints.
The `json` constraint here is for a *contract field* an agent must parse on the way in — not
for a config table you wrote yourself and walk with a loop. See the data rule and worked
example in `authoring.md`.

The line is sharp and runs both ways:

- **Static, authoring-time, named ⇒ document data.** Lives in the markdown, cited by name by
  the `foreach`. No contract.
- **Produced at runtime by another context ⇒ contract.** A `SPAWN` result, an `accepts`
  input — this travels through `with`/`accepts`/`returns`, never parked as document prose.

Misfiling either way is a defect: a runtime value dressed as a config table loses its guard;
a static config dressed as a contract invents a boundary that does not exist.

---

## The deterministic-code boundary (do not use a contract)

When one side is plain code — a Python caller expecting a file, an exit code, or stdout — the
boundary does **not** run through `accepts`/`returns`. It runs through:

- a `TODO` that **writes the file** described by a spec, or
- a `RUN` that **calls a helper** with arguments.

A code result is "observable by other means," and that is exactly the case where `returns` is
deliberately omitted. Reserve contracts for agent-to-agent exchange.

---

## Checklist

- [ ] Every AGENT that takes a specific input or returns predictable information HAS its
      contract — that case is mandatory; only the pure side-effecting worker omits it.
- [ ] No needed contract is left implicit, and no contract is added for decoration.
- [ ] The root has `accepts` iff it is invoked/parameterized/the-second-half-of-a-split.
- [ ] No `SUB` has a contract.
- [ ] No code boundary is modeled as a contract.
- [ ] Structured form used only where a field would break the machine if wrong; string
      otherwise.
- [ ] Every structured field has a `desc`; no constraint beyond the five exists.
- [ ] `SPAWN`/`DELEGATE` `with` was written by reading the callee's `accepts` and genuinely
      satisfies it (authoring-time check — no runtime guard around the outgoing `with`); it
      exists in the caller's scope; `returns` narrows rather than contradicts the contract.
      If the callee's contract was not in context, it was fetched — `with` was not guessed.
- [ ] Every AGENT/root with an `accepts` validates its *incoming* input at the top of its
      `ROUTINE` and defines what happens on violation (`RETURN` with the offending field,
      `ONERROR`, or a stated default — never silent, never `HALT`). This guard IS emitted —
      the callee cannot trust who calls it.
- [ ] Every `SPAWN`/`DELEGATE` against a contracted agent has an `ONERROR` handling a missing,
      malformed, or off-contract *response*.
- [ ] A `SPAWN` whose result drives a following `WHEN`/`IF` still has its own `ONERROR`: the
      `WHEN`/`else` dispatches on returned values, the `ONERROR` handles the failed/empty call.
