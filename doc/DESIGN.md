# SOL Design Rationale

> Why SOL exists, and why it works the way it does.

This document explains the reasoning behind each design choice in the spec. It is intended for anyone who wants to understand, extend, or challenge SOL — not just use it.

---

## The core premise

Most workflow formats are designed for machines: they define a sequence of operations that a deterministic runtime engine executes step by step.

SOL starts from a different premise: **the agent is the runtime**.

An AI agent can read a document, understand its intent, and execute it with judgment — correcting minor errors, deciding which steps to parallelize, choosing sub-agents for complex sections. SOL is designed to exploit this capability, not work around it.

This single premise drives most of the design choices below.

---

## `TODO` vs `RUN` — and why `{{}}` only appears on `RUN`

`TODO` is full natural language: the agent interprets the instruction, decides how to fulfill it, and figures out any commands or arguments on its own.

`RUN` is verbatim: what you write is what gets executed. The agent does not interpret the command — it runs it as written. This is the right choice when you know the exact command and want to prevent the agent from improvising.

The consequence: `RUN` alone cannot express "I know the command but not all the arguments." That's what `{{placeholder}}` is for — a surgical escape hatch that says "fill this spot from context, leave everything else exactly as written."

Without `{{}}`, `RUN` would be too rigid (no dynamic parts at all) or too ambiguous (how much can the agent change?). With `{{}}`, the boundary is explicit: outside the braces, verbatim; inside, agent judgment.

If you're not sure of the command, or want the agent to determine the full invocation, use `TODO` instead.

---

## Why JSON, not YAML or a custom DSL

**YAML** is more human-readable but has well-known edge cases (implicit typing, indentation sensitivity, the Norway problem). When a process fails, you want the format to be unambiguous.

**A custom DSL** would require a parser — which reintroduces runtime dependency, exactly what SOL avoids. Any LLM can parse JSON without special instructions.

**JSON** is universally parseable, diffable, embeddable in other systems, and already the native format of most agent tool calls. The verbosity cost is real but acceptable at the scale of process definitions.

---

## Why `TODO` is open-ended natural language

The alternative is a fixed vocabulary of verbs: `READ`, `WRITE`, `SUMMARIZE`, `SEARCH`, etc.

A fixed vocabulary is a leaky abstraction. Too few verbs and you need workarounds. Too many and you have a maintenance burden. The vocabulary can never keep up with what agents can actually do.

`TODO` delegates interpretation to the agent — the right entity to interpret it, since it has context, tools, and judgment. The cost: less mechanical predictability. The benefit: zero vocabulary maintenance, full expressiveness.

---

## `WHEN` — design, limitations, and honest scope

### Why it's not `CASE`

The instruction is called `WHEN` rather than `CASE` to avoid the baggage of SQL and switch/case, where stopping at the first match is the default assumption. `WHEN` carries no such implication — each entry reads as an independent condition: "when A is true, do X; when B is true, do Y."

### The honest limitation

SOL cannot guarantee how an agent interprets `WHEN` when conditions overlap. The spec intends for all matching branches to execute, but since the agent is the runtime, enforcement is impossible. Different agents, different system prompts, different contexts may produce different behavior.

This is not a bug in SOL — it is a consequence of the core premise. A format that delegates execution to an AI agent cannot make the same guarantees as a deterministic runtime.

**The practical rule:**

| Conditions | Behavior | Recommendation |
|---|---|---|
| Mutually exclusive | Predictable — at most one branch fires | Safe to use `WHEN` |
| Potentially overlapping | Non-deterministic — depends on the agent | Use sequential `IF` blocks |

Sequential `IF` blocks are unambiguous by nature: each is an independent instruction in the `ROUTINE`, evaluated and executed on its own. No construct needed, no semantics to document.

### When `WHEN` is genuinely useful

The primary use case is a shared `else` clause — a default action when none of the conditions apply:

```json
{
  "WHEN": [
    { "when": "condition A", "then": [ ... ] },
    { "when": "condition B", "then": [ ... ] },
    { "else": [ ... ] }
  ]
}
```

With sequential `IF` blocks, a "none of the above" branch requires the agent to re-evaluate all previous conditions — which is redundant and potentially inconsistent if conditions change between evaluations. `WHEN` solves this cleanly, provided conditions are mutually exclusive.

### Authoring vs executing

The "readable without the spec" goal applies to **executing** an SOL process. **Authoring** requires reading the spec — especially this section. A process author who uses `WHEN` with overlapping conditions without understanding the implications will produce a process with unpredictable behavior. The spec cannot prevent this; it can only document it clearly.

---

## Why `model` is a semantic tier, not a model ID

`"model": "claude-opus-4-7"` creates version coupling. A process written today becomes stale when models are updated or retired.

`"model": "smart"` expresses intent: *this step needs the most capable reasoning available*. The agent resolves that to a concrete model at execution time.

| Tier | Meaning |
|---|---|
| `fast` | Simple, repetitive, low risk of error |
| `balanced` | Default — general-purpose execution |
| `smart` | Complex reasoning, ambiguous decisions, synthesis |

These tiers are stable across providers and model generations. Exact model IDs remain available when version pinning is genuinely required.

`model` is also a sub-agent hint: when a section is marked `smart` and the context makes it opportune, the agent may spawn a dedicated sub-agent for that section. No explicit declaration needed.

---

## Why SOL doesn't prescribe execution strategy

SOL expresses *what* a process does, not *how* it runs. Parallelization, sequencing, and scheduling are concerns of the execution context — the system prompt, the operator's configuration, or the orchestrator wrapping the agent.

If you want parallel foreach iterations, tell the agent so in the system prompt: "parallelize whenever you can." If you need fine-grained control over execution order, SOL is probably not the right tool — use a proper orchestration framework.

Encoding execution strategy in the process definition would contradict the core premise: the agent is the runtime, and the runtime gets its instructions from context, not from the document it's executing.

---

## Why `ONERROR` has dual scope

`ONERROR` can be attached to any instruction (local) or declared at root (global fallback). This mirrors how errors actually behave: some are recoverable locally (a specific `RUN` fails — retry with corrected arguments), others are not (the queue is malformed — stop and notify). Both scopes avoid the choice between catch-all handlers that hide errors and per-instruction verbosity that clutters every step.

---

## Why the agent reads the whole document before executing

Process definitions are specifications of intent, not programs. An agent that reads the entire document first can resolve forward references (`CALL` before `SUB` definition), understand overall context, and make better decisions about parallelization. This is why `SUB` can appear anywhere in `ROUTINE` — definition order doesn't matter.

---

## `HALT` vs `ONERROR` — two different kinds of stopping

Both `HALT` and `ONERROR` can stop a process, but they express different intents.

`ONERROR` is reactive: something went wrong, and the process needs to respond. The handler exists to clean up, notify, or escalate — and its presence implies the author considered the failure case.

`HALT` is proactive: the process has reached a point where stopping is the correct outcome, not a failure. A queue that is legitimately empty is not an error. A human-approval gate that decides not to proceed is not an error. Encoding these as errors misrepresents intent and makes processes harder to reason about.

The practical distinction: if you'd use `{ "TODO": "halt" }` inside an `ONERROR` handler, that's an error response — `HALT` is not the right tool there. If you'd use `{ "TODO": "halt" }` in the main `ROUTINE` because the work is done or the condition for stopping is met, replace it with `{ "HALT": "reason" }` — it's explicit and unambiguous.

---

## `WAITUSERINPUT` — human-in-the-loop as a first-class instruction

SOL processes are executed by agents, but agents work for humans. Sometimes the right design includes an explicit human checkpoint: review a draft before publishing, confirm a destructive operation, provide a value the process cannot infer from context.

Before `WAITUSERINPUT`, the only way to express this was via `TODO`: `{ "TODO": "Ask the user to confirm before continuing" }`. This works, but it is opaque — the instruction is indistinguishable from any other natural language step, and the semantics depend entirely on the agent's interpretation.

`WAITUSERINPUT` makes the pause explicit and structural. It tells both the agent and the reader: execution stops here until a human responds. The prompt is the value; the response flows forward as context.

### When `WAITUSERINPUT` is appropriate — and when it is not

`WAITUSERINPUT` is not a general-purpose human-in-the-loop mechanism. It is a context-dependent shortcut that works only when three conditions hold simultaneously:

1. **The execution context is interactive** — a live agent session where a human is present and the harness supports mid-process pausing (e.g., a Claude Code skill, a conversational agent with a UI).
2. **The runtime can preserve state across the pause** — context window, tool state, and working memory survive the interruption and are available when execution resumes.
3. **A prompt system is in place** — the agent has a concrete mechanism for surfacing the prompt and receiving the response, beyond just printing text.

In any other context — scheduled runs, API-invoked agents, CI/CD pipelines, batch processing, non-interactive shells — `WAITUSERINPUT` degrades silently to a `HALT` with the prompt text as a stop message. The process ends. There is no pause, no resumption, no human input. This is correct behavior (never block silently), but it is not what the instruction expresses.

### The robust alternative: process decomposition

When the execution context is uncertain, or when the human checkpoint is a meaningful boundary in the workflow, the right design is two separate SOL processes rather than one process with `WAITUSERINPUT`:

- **Process A** does its work, produces output (a file, a report, a draft), and halts naturally at the end of its `ROUTINE`.
- The human reviews the output and invokes **Process B** with their response or decision as the initial context.
- **Process B** reads that context and continues from where Process A left off.

This pattern works everywhere, because it requires nothing from the runtime beyond the ability to execute a process — the minimum viable requirement for using SOL at all. It is more composable (each process is independently testable), more explicit (the handoff is a real boundary, not an in-process pause), and more reliable (no assumptions about runtime capabilities).

**Use `WAITUSERINPUT` when:** you are writing a skill or interactive agent and you have verified that the execution context supports it.

**Use process decomposition when:** the context is automated, uncertain, or when the human checkpoint represents a genuine phase boundary that warrants separate processes anyway.

The non-interactive fallback of `WAITUSERINPUT` (halt with prompt text) follows the same principle as `RUN` failure handling: never block silently. But the presence of a fallback should not obscure the primary design decision: if you are not certain the context is interactive, design for process decomposition from the start.

---

## Input/output contracts

`accepts` and `returns` describe what crosses a context boundary between two agents. They can be a natural-language string (open) or a structured map of fields with a small set of composable constraints (`required`, `anyof`, `number`, `json`). The structure is deliberately minimal — it pins down only what would break downstream execution if misread, leaving meaning in prose. The full rationale, including the alternatives considered and rejected, is documented separately in `io-contracts.md`.

---

## Relationship to other formats

**AWS Strands Agent SOPs** — the closest in spirit. Markdown-based with RFC 2119 keywords (MUST/SHOULD/MAY), open source, cross-platform. SOL differs in having explicit control flow grammar (`IF`/`WHEN`/`REPEAT` are structured, not prose), the model tier concept, and JSON as the base format. SOPs are human-readable guidelines with constraints; SOL is a grammar with natural language leaves.

**Serverless Workflow** — YAML/JSON DSL for serverless orchestration. Requires a runtime engine. Designed for deterministic execution, not agent autonomy.

**LangGraph / CrewAI / AutoGen** — code-first Python frameworks. Powerful but require a development environment and a running process. SOL is a format, not a framework.

**BPMN** — the established standard for business process modeling. XML-based, runtime-dependent, designed for human-machine collaborative workflows. SOL is lighter and designed for LLM-native execution.

---

## What SOL is not

- Not a programming language (no variables, no types, no memory model)
- Not a replacement for code (complex logic belongs in scripts called via `RUN`)
- Not a runtime (SOL files need an agent to execute them)
- Not trying to be universal (optimized for LLM agents, not general automation)
