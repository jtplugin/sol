# Input/Output Contracts — Design Rationale

*Introduced in SOL 0.6.0. This document explains why `accepts`/`returns` gained an optional structured form, and the alternatives that were weighed and rejected along the way. The normative definition lives in `spec/sol-0.6.md`; this is the "why" behind it.*

---

## The problem

Through 0.5.0, `accepts` and `returns` were natural-language strings:

```json
"accepts": "Modified files and their diffs."
```

This works well when a process author is describing intent to a single reading agent. It breaks down when the descriptor is the **interface between two agents** that must agree without a human in the loop. In practice, authors started cramming structure into the prose — listing fields, marking some "(optional)", embedding path conventions, and mixing in processing steps:

```json
"TODO": "Receive from the orchestrator:\n  - env: 'coding' | 'staging' | 'production'\n  - path_spec: {task_dir}/00_spec.md\n  - git_diff: output of git diff ...\n  - todolist_resume: (optional) present only on resume\nThen read {path_test}, filter entries where env == {env} ..."
```

Three different things are tangled here: the **contract** (what I receive), **path conventions** (where files live), and **routine logic** (what I do with them). Nothing tells a downstream agent reliably which fields are mandatory, which values are admissible, or what type a value has. Each hop between agents adds interpretive entropy: one side writes `git_diff`, the other guesses its shape. The interface is "honored" only by luck.

## The principle: structure the boundary, not the conversation

The fix is **not** to turn SOL into a typed schema language. `accepts`/`returns` describe a conversation between two intelligent agents. When two people talk, what matters is the information exchanged, not the punctuation. The semantic payload belongs in prose — a *description* of each field — because that is what an LLM reads best.

But a contract is different from a conversation in one respect: a contract must be **honored, not interpreted**. So 0.6.0 keeps prose as the carrier of meaning and adds just enough structure to pin down the few things whose misreading has a *mechanical* consequence downstream.

This yields the central design test, applied to every candidate piece of structure:

> Keep it only if getting it wrong breaks the machine, not the conversation.

## What the contract became

A contract is now **either a string or a structured object**.

- **String** — an open contract. Unchanged from 0.5.0. Use it when the exchange needs no constraint.
- **Object** — a map of field name to a set of *optional, composable constraints*.

```json
"accepts": {
  "env":         { "anyof": ["coding", "staging", "production"], "required": true },
  "git_diff":    { "required": true, "desc": "diff vs the merge-base with main" },
  "item_max":    { "number": true, "required": true, "desc": "maximum items to evaluate" },
  "todolist_resume": { "json": true, "desc": "updated todolist; present only when resuming an interrupted run" }
}
```

The constraints are adjectives, not types: `required`, `anyof`, `number`, `json`, plus `desc` for the meaning. Stack any combination; omit them all for a free-form field. `desc` always lives in the same place, on every field, so a reading agent never has to hunt for the meaning.

---

## Alternatives considered

### 1. A full type system (`text`, `path`, `bool`, `json`, `ref`, `enum`, `number`, `list`, ...)

The first instinct was a closed vocabulary of types on a `type` field. **Rejected.** Most of those distinctions matter to a deserializer, not to an agent. `text` vs `path` vs `ref` all reduce to "a string the agent reads and understands"; `bool` is just a two-value `enum` or a number. Applying the design test, only three survived:

- **`anyof` (closed set)** — survives because it *forks downstream behavior*. A closed set is a switch; the closure is precisely what stops the receiver from inventing a value.
- **`number`** — survives because a value either is numeric or you cannot compute with it. It absorbs booleans.
- **`json`** — survives because a receiver that intends to *parse* rather than interpret needs the guarantee.

Everything else collapsed into a free-form field with a `desc`. Five-types-down-to-two-plus-a-default is the whole point: a vocabulary an author never has to think hard about.

### 2. Constraints expressed as a `type` value (`{"type": "enum", "of": [...]}`)

Even after narrowing to a few types, the question was whether to model them as values of a `type` key or as keys in their own right. **Rejected the `type`-value form** in favor of constraint-keys (`anyof`, `number`, `json`). Reframing the types as *composable constraints* — the same shape as `required` — collapsed two concepts (obligation and type) into one mental model: a field is a bag of independent flags. `required` stopped being a special case. And it sidesteps the "is `enum` a type or a refinement?" ambiguity entirely.

### 3. A `mode: open | closed` flag and a `fields` wrapper

An earlier draft wrapped the field map in `{ "mode": "...", "fields": {...} }`. **Rejected as redundant.** Openness is already expressed by the *form*: a string is the open contract; an object is the closed one. A `fields` wrapper adds a level of nesting that carries no information. The string-or-object union says the same thing with less.

### 4. Conditional presence (`when: "status == pass"`)

To express "this return field exists only in some cases," a draft added a `when` clause holding a condition. **Rejected.** A condition is *logic*, and logic in the contract is exactly the leak 0.6.0 set out to remove — the contract drifts back to describing *when/how* instead of *what*. The lean replacement is `required: false`: the field may or may not be present, and the rule for *which* lives in the `ROUTINE`, where logic belongs. If a human note helps, `desc` carries it as prose, not as an evaluable expression.

### 5. A first-class `RETURN` construct at exit points

Since returns are physically produced at exit points, one proposal was a `RETURN` statement placed in the routine, allowing multiple structured exits. **Rejected**, for two reasons:

1. **It re-imports imperative control flow** that SOL deliberately avoids. SOL describes *what* an agent produces, not *where* in its execution it does so.
2. **It is unnecessary.** An agent reads the whole document before executing, so the `returns` contract at the boundary already tells it the shape its final output must take — from whichever branch it exits. The declaration *is* the instruction; no positional marker is needed. Divergent outcomes are modeled with a discriminating field (e.g. a `status` in `anyof`), not with N exit points.

> **Update (0.6.1).** A `RETURN` construct *was* added in 0.6.1 — but not as the mechanism rejected here. The rejection above concerns `RETURN` as a way to *declare structured output shape*; that job still belongs to the `returns` contract, and `RETURN` does **not** take it over (when it carries a value, it merely *echoes* the contract's shape, never redefines it). What 0.6.1's `RETURN` adds is orthogonal: a verb for **early exit that yields control back to the invoker** — the self-evident "I'm done, return to caller" that `HALT` (a global stop) could not express. Both reasons above still hold for the thing they rejected; the 0.6.1 construct is a different thing.

### 6. A shared registry of path/artifact names (`VARS`)

To stop authors repeating `{task_dir}/00_spec.md` in every node, a draft proposed a process-level registry mapping logical names to paths, referenced from contracts via a `ref` type. **Deferred / out of scope.** It is a genuine idea, but it is about *path resolution and project layout*, not about the contract between two agents — a separate concern that should not inflate the I/O design. In 0.6.0, the same effect is achievable with existing constructs (a `description`/context note listing the canonical artifacts, resolved by the agent).

---

## Scope: where contracts live, and where they don't

A contract describes what crosses a **context boundary**. It therefore exists on:

- the **root process** — its outer boundary toward whoever invokes it;
- **`AGENT`** — via `accepts`/`returns`;
- **`SPAWN`** and **`DELEGATE`** — on the invocation-side `returns` (and `with`, in prose).

It does **not** exist on **`SUB`**. A subroutine shares the caller's context — there is no membrane to transfer across, and the data it works on is already in scope. Adding `accepts` to a `SUB` would be two people in the same room writing each other a contract. Keeping contracts strictly at boundaries is what stops them from spreading everywhere "for clarity" and re-bloating the very thing this design keeps thin.

## Where the boundary with deterministic code lives

These contracts are for **agent-to-agent** exchange. When one side is deterministic code — a Python caller expecting a file, an exit code, or stdout — the boundary does not run through `accepts`/`returns` at all. It runs through other constructs: a `TODO` that writes the file described in a spec, or a `RUN` that calls a helper with arguments. A code result is "observable by other means," which is exactly the case where `returns` is omitted. This is why no `json`-for-code or file-path type was needed: that boundary is someone else's job.

## Enforcement

As with everything in SOL, the contract is honored by the agent's understanding, not by a runtime type checker. A structured `accepts` tells the receiving agent that `required` fields are mandatory and `anyof` values are closed — so it does not improvise outside the set — and a structured `returns` tells it to shape its output before completing. The structure makes the contract *legible and predictable*; the agent makes it *real*.
