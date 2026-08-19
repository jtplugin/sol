# Delegation in SOL: CALL, SPAWN, DELEGATE — from script to system

The previous article assembled the full vocabulary of a *single* routine: the leaves that do the work (`TODO`, `RUN`), the control flow that arranges them (`IF`, `WHEN`, `REPEAT`), and the deliberate ways to stop (`RETURN`, `HALT`, `ONERROR`, `WAITUSERINPUT`). All of it lives in *one context* and runs in *one place*.

One thing stayed out of reach: work that needs to run **somewhere else**. A clean context, separated from the one that invokes it. A reusable specialist to hand a phase to. A one-off side task with its own boundary. That's delegation, and it's where SOL stops being a linear script and becomes a system of collaborating agents.

SOL has three constructs for delegating. Choosing between them isn't about how "big" the task is, nor how important. It comes down to **a single question**.

---

## The question that decides everything: context

When you delegate a piece of work, the only thing that really matters is this:

**Does the delegated work need to see the caller's context, or does it need a clean context?**

The answer picks the construct:

- If the work needs **everything the caller sees** — the same files, the same variables, the state already built up in the conversation — then it shares context. It's a `SUB`, invoked with `CALL`.
- If the work needs **a clean context** — it sees only what you explicitly pass it and returns only what it declares — then it crosses a boundary. It's an `AGENT`, invoked with `SPAWN`; or, if it's needed once and doesn't warrant a named definition, an inline `DELEGATE`.

Everything else — the contracts, the model tiers, the roles — follows from this one choice. Let's take the three constructs one at a time.

---

## CALL — the subroutine that shares context

A `SUB` defines a subroutine: a named block of steps you can invoke more than once without rewriting it. You invoke it with `CALL`.

```json
{
  "SUB": {
    "name": "normalize-entry",
    "ROUTINE": [
      { "TODO": "Trim whitespace and lowercase the entry key" },
      { "TODO": "Drop the entry if its key is empty" }
    ]
  }
}
```

```json
{ "CALL": "normalize-entry" }
```

The defining property of a `SUB` is that it **shares the caller's context**. It receives no data: the data it works on is already in scope. That's why a `SUB` has **no contract** — no `accepts`, no `returns`. There's no boundary to cross, so there's nothing to contract over: it's the simplest case, and the absence of a contract isn't an oversight, it's the direct consequence of sharing context.

One detail that holds for `SUB`, `AGENT`, and everything else: a definition can appear **anywhere** in the `ROUTINE`. The agent reads the whole document before executing, so definition order doesn't matter — you can define a `SUB` at the bottom and call it at the top.

Use `CALL` when the logic repeats and everything it needs is already in front of the caller.

---

## SPAWN — the specialist in an isolated context

An `AGENT` declares a named agent that runs in a **separate context**. Unlike a `SUB`, it doesn't see the caller's conversation: it receives **only** what you pass via `with`, and returns **only** what its `returns` describes. You invoke it with `SPAWN`.

```json
{
  "AGENT": {
    "name": "security-auditor",
    "description": "Audit a code diff for security issues.",
    "accepts": {
      "git_diff": { "required": true, "desc": "diff vs the merge-base with main" }
    },
    "returns": {
      "findings": { "json": true, "desc": "{severity, file, line_range, fix}" }
    },
    "model": "smart",
    "role": "Senior application security engineer",
    "ROUTINE": [
      { "TODO": "Review the diff for injection, authz, and secret-handling flaws" },
      { "RETURN": { "findings": "..." } }
    ]
  }
}
```

```json
{
  "SPAWN": "security-auditor",
  "with": "The files modified in this sprint and their diffs.",
  "ONERROR": [{ "TODO": "Log that the audit produced no usable result and continue" }]
}
```

Several things are happening here, and this is where SOL becomes genuinely multi-agent:

- **Isolation is the point.** The specialist starts clean. It doesn't inherit the parent conversation's history, assumptions, or noise: it sees exactly the diff you pass it and nothing more. This is what makes an `AGENT` *composable* — you can reuse it across different processes without it dragging foreign context along.
- **The contract is explicit.** `accepts` says what must come in, `returns` what comes back. Once the `SPAWN` completes, the parent has the declared output available as context. More on that in a moment.
- **`with` is the bridge.** It's the information you extract from the current context to hand to the agent. Omit `with` and the agent starts with no transferred context, working from its `description` and `ROUTINE` alone.
- **`model` and `role` live where they make sense.** The specialist can run on a different tier (`smart`) and with a declared persona, without the caller needing to know anything about it.

Use `SPAWN` when the work is a reusable specialist, with a structured routine, that needs a clean context.

---

## DELEGATE — the inline, one-off delegation

Sometimes you need to isolate a task but it's not worth giving it a name and a definition: you use it once, here and now. That's `DELEGATE`.

```json
{
  "DELEGATE": {
    "task": "Scan the modified files for hardcoded credentials and report each occurrence",
    "with": "List of files modified in this sprint and their diffs",
    "returns": { "findings": { "json": true, "desc": "{severity, file, line_range, fix}" } }
  }
}
```

A `DELEGATE` is a `SPAWN` without a named definition: the task is described directly in the `task` field. It inherits the same crucial property — **isolated context** — and the same boundary tools: `with` for what goes in, `returns` for what comes out. The only difference is the absence of a reusable definition.

The rule of thumb: `DELEGATE` for one-off delegations; `AGENT` + `SPAWN` when the agent is reusable or has a structured routine that deserves to stand on its own.

---

## The three constructs at a glance

|  | `CALL` | `SPAWN` | `DELEGATE` |
|---|---|---|---|
| Definition | `SUB` | `AGENT` | inline (`task`) |
| Context | **shared** | **isolated** | **isolated** |
| Reusable | yes (named) | yes (named) | no (one-off) |
| Contract | none | `accepts` / `returns` | `with` / `returns` |

The whole table reads from the left: first you decide the context (shared or isolated), then whether the thing is reusable. The contract appears only where there's a boundary to cross — which is exactly the next topic.

---

## Contracts: the membrane between two agents

`accepts` and `returns` describe **what crosses a context boundary** — the membrane between two agents that do not share state. They exist on the process root (its outer boundary toward whoever invokes it), on every `AGENT`, and on the invocation-side overrides of `SPAWN` and `DELEGATE`. They do **not** exist on `SUB`, for the reason we already saw: sharing context, there's nothing to transfer.

A contract takes one of two forms:

- **Open (string)** — a natural-language description. Fine when the boundary carries information the agent interprets, and getting a detail wrong breaks nothing mechanical.

  ```json
  "returns": "Findings with severity, file path, line range, and suggested fix."
  ```

- **Structured (a map of fields)** — when a field has to be exactly right, because something downstream relies on its shape. The constraints compose: `required`, `anyof`, `number`, `json`, plus a free-form `desc`.

  ```json
  "accepts": {
    "env":      { "anyof": ["coding", "staging", "production"], "required": true },
    "git_diff": { "required": true, "desc": "diff vs the merge-base with main" }
  }
  ```

The test for choosing is sharp: **add structure only where getting a field wrong would break the machine, not the conversation.** Everything else stays a string. A contract is not decoration: either it serves and you draw it well, or it doesn't and you leave it out.

And contracts are honored on **both sides**: whoever defines an `AGENT` with an `accepts` validates the input at the top of its routine; whoever invokes it with `SPAWN` writes a `with` that satisfies that contract. It's an agreement, not a decorative suggestion — but *how* it gets enforced is exactly the delicate point we turn to now.

---

## Non-prescriptiveness: SOL cannot force anything

Here we reach the heart of SOL, and an honesty worth making explicit.

The first line of the spec isn't a slogan, it's a constraint: *no external runtime is required — the agent is the runtime.* There is no parser that compels a branch to be taken, no scheduler that guarantees a `SPAWN` becomes a genuinely isolated session, no type checker that enforces a contract. The spec says so plainly: contracts are *"honored by the agent's understanding, not by a runtime type checker"*, and `model` is *"a hint, not an imperative."*

**This is a deliberate stance, not a gap.** It's what lets a `TODO` say *"identify the most likely root cause"* — something no deterministic engine could evaluate. The same holds for delegation: it's what lets an `AGENT` *interpret* its task instead of executing a fixed transition table. The price is that **nothing in the language can force an agent to behave the way you want.**

So the right question is never "how do I make SOL prescriptive?" It's: *"if I need a particular behavior to be predictable, at what layer do I inject that predictability, and what does it cost me?"*

### An asymmetry worth understanding

Not all SOL intents are equally forceable, and delegation offers the cleanest example of this asymmetry.

- **Context isolation is entailed by the contract.** SOL says an `AGENT` *"receives only what `SPAWN` passes via `with`, and returns only what `returns` describes. It does not share the calling agent's context."* That is a statement about *information flow*. Any layer that faithfully enforces *"the callee sees only `with`"* is **compelled** to create a clean context — there's no other way to guarantee the callee can't see the caller's state. So isolation can be **pressured into existence** simply by taking the contract seriously.
- **Model choice is entailed by nothing.** There's no information-flow property that requires a different model. That's precisely why `model` is *only* a hint: it's orthogonal to the contract. Forcing a specific model always requires a layer *outside* the agent's own judgment.

The practical consequence: **you can pressure isolation from inside SOL's own discipline; you cannot pressure model selection without an external resolver.** Keep this in mind when you delegate: a `SPAWN`'s isolation is far more "within reach" than the model tier you assigned it.

### The strategies exist — and deserve an article of their own

The good news is that predictability isn't bought by distorting the language, but by **injecting it at a chosen layer** around it: a prose directive that tells the agent how to treat each `SPAWN`; the execution environment's own native features (in Claude Code, for instance, registering each `AGENT` as a native sub-agent with its own model); a small deterministic runtime alongside SOL; up to, at the extreme, embedding it inside a foreign orchestrator. Each layer buys more determinism at the price of more portability and more engineering — and the recurring rule is to pick **the shallowest layer that meets your real determinism need**.

That's a map in itself, with its trade-offs weighed one by one, and it'll be the subject of **a dedicated future article**. Here the principle suffices: SOL stays the layer of *intent*; predictability is a deployment decision made *around* it, not a property bolted into the language. And precisely because all of this rests on the agent's interpretation, thorough tests are underway to verify that the various dedicated instructions — `SPAWN`, `DELEGATE`, contracts, model tiers — actually produce the agentic configuration they describe; concrete use in Claude Code, meanwhile, is more than satisfying.

---

## From script to system

With delegation, the vocabulary is complete. Inside a routine you know how to arrange leaves, branches, loops, and errors; between one routine and another you know how to pick the right boundary:

- **`CALL` / `SUB`** — same context, shared and reusable logic, no contract.
- **`SPAWN` / `AGENT`** — isolated context, reusable specialist, `accepts` / `returns` contract.
- **`DELEGATE`** — isolated context, inline one-off delegation, `with` / `returns` boundary.

And the rule that runs through all of them is always the same: **decide the context first.** The rest — reuse, contracts, model, role — follows from there.

Other things is left to tell: SOL doesn't live as bare JSON, but as JSON *inside* a markdown document — code and documentation in the same file, configuration tables cited by loops, readable diffs, self-explanatory skills. What that pattern enables is the subject of the next article.

Repository: https://github.com/jtplugin/sol

---
*Author: Gianni Tommasi*
